"""Plant identification and care API. Keeps provider credentials on the server."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

from .eachlabs import EachlabsClient, EachlabsError
from .errors import ErrorKind, public_error
from .providers import Provider, build_chain, coerce_identify
from .schema import CARE_SCHEMA, IDENTIFY_SCHEMA, SAFETY_NOTE, validate_response

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("plantid")

MODEL = os.getenv("EACHLABS_MODEL", "gemini-2-5-flash")
MODEL_VERSION = os.getenv("EACHLABS_MODEL_VERSION", "0.0.1")
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_EDGE_PX = 1024  # Limit image size and upload cost
# The phone waits 60s. Keep handling under 50s, leaving room for network transit.
REQUEST_BUDGET_S = 50.0
MIN_PREDICTION_BUDGET_S = 5.0
HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

app = FastAPI(title="Plant Identifier API", version="1.0.0")

# The app is served from Expo on the LAN, so origins are not predictable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = EachlabsClient(os.getenv("EACHLABS_API_KEY", ""))


def _normalize_image(raw: bytes) -> bytes:
    """Apply EXIF rotation, resize to MAX_EDGE_PX and encode as JPEG without EXIF."""
    img = Image.open(io.BytesIO(raw))
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return buf.getvalue()


CHAIN = build_chain(MODEL, MODEL_VERSION)
log.info("model chain: %s", " -> ".join(p.slug for p in CHAIN))


@asynccontextmanager
async def _service_request():
    """One deadline across upload, queueing, primary, polling and any fallback."""
    deadline = asyncio.get_running_loop().time() + REQUEST_BUDGET_S
    try:
        async with asyncio.timeout_at(deadline):
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                yield client, deadline
    except EachlabsError as exc:
        log.warning("service failed (%s): %s", exc.kind.value, exc)
        status, message = public_error(exc)
        raise HTTPException(status, message) from exc
    except (TimeoutError, httpx.TimeoutException) as exc:
        status, message = public_error(EachlabsError("deadline exceeded", kind=ErrorKind.TIMEOUT))
        raise HTTPException(status, message) from exc
    except httpx.RequestError as exc:
        status, message = public_error(EachlabsError("connection failed", kind=ErrorKind.NETWORK))
        raise HTTPException(status, message) from exc


async def _run_chain(
    client: httpx.AsyncClient, task: str, build, *, deadline: float,
    providers: list[Provider] | None = None, attempts: list[dict] | None = None,
) -> tuple[dict, dict, Provider]:
    """Try another model only after an explicit availability or model-limit error."""
    last_error = EachlabsError("no models available", kind=ErrorKind.MODEL_UNAVAILABLE)
    chain = CHAIN if providers is None else providers
    for provider in chain:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining < MIN_PREDICTION_BUDGET_S:
            raise EachlabsError("not enough time for a prediction", kind=ErrorKind.TIMEOUT)
        trace = {"model": provider.slug, "version": provider.version}
        if attempts is not None:
            attempts.append(trace)
        record = None
        started = time.perf_counter()
        try:
            result, record = await _client.predict_json(
                client, provider.slug, build(provider), version=provider.version,
                timeout_s=remaining,
            )
            validate_response(result, IDENTIFY_SCHEMA if task == "identify" else CARE_SCHEMA)
            if not provider.schema_native:
                result = coerce_identify(result) if task == "identify" else result
            if provider is not chain[0]:
                log.info("%s: used fallback %s", task, provider.slug)
            return result, record, provider
        except EachlabsError as exc:
            trace["error_kind"] = exc.kind.value
            record = record or exc.record
            if not exc.allows_fallback:
                raise
            last_error = exc
            log.warning("%s: %s unavailable (%s)", task, provider.slug, exc.kind.value)
        except (ValueError, TypeError) as exc:
            trace["error_kind"] = ErrorKind.INVALID_RESPONSE.value
            raise EachlabsError("model returned invalid data", kind=ErrorKind.INVALID_RESPONSE) from exc
        finally:
            trace["elapsed_s"] = round(time.perf_counter() - started, 3)
            if record is not None:
                trace["metrics"] = record.get("metrics") or {}
                trace["raw_output"] = record.get("output")
                trace["prediction_id"] = record.get("id") or record.get("predictionID")

    raise last_error


def _usage(record: dict) -> dict:
    """Pull whatever cost/token metadata the prediction record carries."""
    out = {}
    for key in ("usage", "metrics", "cost", "predict_time"):
        if key in record:
            out[key] = record[key]
    return out


@app.get("/healthz")
async def healthz() -> dict:
    return {
        "ok": True,
        "model": MODEL,
        "key_loaded": bool(os.getenv("EACHLABS_API_KEY")),
    }


@app.post("/identify")
async def identify(image: UploadFile = File(...)) -> dict:
    return await identify_image(image)


async def identify_image(
    image: UploadFile, *, providers: list[Provider] | None = None,
    attempts: list[dict] | None = None,
) -> dict:
    """Shared app/evaluation pipeline; explicit providers isolate model comparisons."""
    started = time.perf_counter()
    async with _service_request() as (client, deadline):
        raw = await image.read(MAX_UPLOAD_BYTES + 1)
        if not raw:
            raise HTTPException(400, "empty upload")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "image too large")
        try:
            jpeg = await asyncio.to_thread(_normalize_image, raw)
        except Exception as exc:
            raise HTTPException(400, "Unreadable image. Please choose another photo.") from exc

        # Uploaded once and reused across eligible model fallbacks.
        url = await _client.upload_image(client, jpeg)
        result, record, used = await _run_chain(
            client, "identify", lambda p: p.identify_input(url), deadline=deadline,
            providers=providers, attempts=attempts,
        )

    candidates = result.get("candidates") or []
    # Guard the schema's own edge case: is_plant true but nothing returned.
    if result.get("is_plant") and not candidates:
        result["is_plant"] = False

    return {
        "is_plant": bool(result.get("is_plant")),
        "image_quality": result.get("image_quality", "good"),
        "quality_hint": result.get("quality_hint") or None,
        "candidates": candidates[:3],
        "safety_note": SAFETY_NOTE,
        "meta": {
            "model": used.slug,
            "fallback": used is not (CHAIN if providers is None else providers)[0],
            "elapsed_s": round(time.perf_counter() - started, 2),
            "bytes_sent": len(jpeg),
            **_usage(record),
        },
    }


class CareRequest(BaseModel):
    scientific_name: str
    common_name: str = ""


@app.post("/care")
async def care(req: CareRequest) -> dict:
    """Care info for an already-settled name. Text-only — no image involved."""
    if not req.scientific_name.strip():
        raise HTTPException(400, "scientific_name required")

    started = time.perf_counter()
    async with _service_request() as (client, deadline):
        result, record, used = await _run_chain(
            client,
            "care",
            lambda p: p.care_input(
                req.scientific_name, req.common_name or req.scientific_name
            ),
            deadline=deadline,
        )

    return {
        "care": result,
        "safety_note": SAFETY_NOTE,
        "meta": {
            "model": used.slug,
            "fallback": used is not CHAIN[0],
            "elapsed_s": round(time.perf_counter() - started, 2),
            **_usage(record),
        },
    }
