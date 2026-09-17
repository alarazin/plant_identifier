"""Compare model responses for the same uploaded images.

Checks response fields and prints predictions, confidence, latency and cost.
Usage: backend/.venv/bin/python backend/scripts/compare_models.py [image ...]"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from backend.app.eachlabs import EachlabsClient, EachlabsError, _extract_json  # noqa: E402
from backend.app.main import _normalize_image  # noqa: E402
from backend.app.providers import REGISTRY, coerce_identify  # noqa: E402

DEFAULT_IMAGES = [
    "eval/images/monstera_deliciosa.jpg",   # distinctive houseplant
    "eval/images/conium_maculatum.jpg",     # toxic lookalike
    "eval/images/festuca_rubra.jpg",        # difficult grass image
    "eval/images/dracaena_trifasciata.jpg", # easy houseplant
]

ORDER = ["gemini-2-5-flash", "openai-chatgpt-5", "openai-chat-completion"]
REQUIRED_TOP = ("is_plant", "image_quality", "candidates")
REQUIRED_CAND = ("common_name", "scientific_name", "genus", "confidence")


def expected_binomial(path: str) -> str:
    return os.path.basename(path).rsplit(".", 1)[0].replace("_", " ").capitalize()


def check_shape(raw_output, parsed: dict) -> dict:
    """Check required fields before normalizing the response."""
    problems = []

    # Check whether the raw output was valid JSON.
    rescued = False
    if isinstance(raw_output, str):
        try:
            json.loads(raw_output.strip())
        except Exception:
            rescued = True

    for key in REQUIRED_TOP:
        if key not in parsed:
            problems.append(f"missing {key}")

    quality = parsed.get("image_quality")
    if quality not in {"good", "blurry", "too_far", "occluded", "dark"}:
        problems.append(f"image_quality={quality!r} not in enum")

    cands = parsed.get("candidates")
    if not isinstance(cands, list):
        problems.append("candidates not a list")
        cands = []
    for i, c in enumerate(cands):
        if not isinstance(c, dict):
            problems.append(f"candidate[{i}] not an object")
            continue
        for key in REQUIRED_CAND:
            if not c.get(key):
                problems.append(f"candidate[{i}].{key} missing/empty")
        if c.get("confidence") not in ("high", "medium", "low"):
            problems.append(f"candidate[{i}].confidence={c.get('confidence')!r} not in enum")

    return {"rescued_from_prose": rescued, "problems": problems}


async def run_one(client, api, provider, url) -> dict:
    started = time.perf_counter()
    try:
        record = await api.predict(client, provider.slug, provider.identify_input(url),
                                  version=provider.version)
    except EachlabsError as exc:
        return {"error": str(exc), "elapsed": round(time.perf_counter() - started, 2)}

    out = record.get("output")
    if isinstance(out, dict):
        parsed = out
    elif isinstance(out, list) and out and isinstance(out[0], dict):
        parsed = out[0]
    else:
        try:
            parsed = _extract_json(str(out) if not isinstance(out, list) else "".join(map(str, out)))
        except EachlabsError as exc:
            return {"error": f"unparseable: {exc}", "raw": str(out)[:200],
                    "elapsed": round(time.perf_counter() - started, 2)}

    shape = check_shape(out, parsed)
    try:
        coerced = coerce_identify(parsed)
        coerce_error = None
    except Exception as exc:
        coerced, coerce_error = None, str(exc)

    metrics = record.get("metrics") or {}
    return {
        "parsed": parsed,
        "shape": shape,
        "coerced": coerced,
        "coerce_error": coerce_error,
        "elapsed": round(time.perf_counter() - started, 2),
        "cost": metrics.get("cost"),
        "predict_time": metrics.get("predict_time"),
    }


async def main() -> None:
    images = sys.argv[1:] or DEFAULT_IMAGES
    api = EachlabsClient(os.getenv("EACHLABS_API_KEY", ""))
    results: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=180) as client:
        for path in images:
            print(f"\n=== {path}  (expect: {expected_binomial(path)}) ===", flush=True)
            jpeg = _normalize_image(open(path, "rb").read())
            url = await api.upload_image(client, jpeg)
            results[path] = {}

            for slug in ORDER:
                provider = REGISTRY[slug]
                # Sequential: the account ceiling is 2 concurrent predictions.
                r = await run_one(client, api, provider, url)
                results[path][slug] = r

                if "error" in r:
                    print(f"  {slug:<24} ERROR  {r['error'][:90]}", flush=True)
                    continue

                src = r["coerced"] or r["parsed"]
                top = (src.get("candidates") or [{}])[0]
                cost = f"${r['cost']:.5f}" if r.get("cost") else "n/a"
                flags = []
                if r["shape"]["rescued_from_prose"]:
                    flags.append("PROSE")
                if r["shape"]["problems"]:
                    flags.append(f"{len(r['shape']['problems'])} shape issues")
                if r["coerce_error"]:
                    flags.append(f"COERCE FAIL: {r['coerce_error']}")
                print(
                    f"  {slug:<24} {str(top.get('scientific_name'))[:28]:<29}"
                    f"{str(top.get('confidence')):<8}q={str(src.get('image_quality')):<9}"
                    f"{r['elapsed']:>5.1f}s {cost:>10}  {' | '.join(flags)}",
                    flush=True,
                )
                for p in r["shape"]["problems"][:4]:
                    print(f"      - {p}", flush=True)

    out = "/tmp/plant-identifier-compare.json"
    json.dump(results, open(out, "w"), indent=2, default=str)
    print(f"\nfull output -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
