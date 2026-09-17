"""Eachlabs client for image upload, prediction submission and status polling.

Accepts the documented prediction IDs and terminal status variants.
Limits local prediction concurrency to two."""

from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from .errors import EachlabsError, ErrorKind, provider_error

log = logging.getLogger(__name__)

BASE_URL = "https://api.eachlabs.ai/v1"

_TERMINAL_OK = {"success", "completed", "succeeded"}
_TERMINAL_BAD = {"error", "failed", "cancelled", "canceled"}

# Stay under the 2-concurrent metered ceiling for low-balance accounts.
_SEMAPHORE = asyncio.Semaphore(2)


def _object_response(response: httpx.Response) -> dict:
    try:
        data = response.json()
    except ValueError as exc:
        raise EachlabsError("invalid API JSON", kind=ErrorKind.INVALID_RESPONSE) from exc
    if not isinstance(data, dict):
        raise EachlabsError("expected API object", kind=ErrorKind.INVALID_RESPONSE)
    return data


async def _request(
    client: httpx.AsyncClient, method: str, url: str, *, operation: str,
    retry_poll: bool = False, **kwargs,
) -> httpx.Response:
    # Retry status reads once. A failed POST may have started a paid prediction.
    attempts = 2 if retry_poll else 1
    for attempt in range(attempts):
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            if attempt + 1 < attempts:
                await asyncio.sleep(0.5)
                continue
            kind = ErrorKind.TIMEOUT if isinstance(exc, httpx.TimeoutException) else ErrorKind.NETWORK
            raise EachlabsError(f"{operation}: {type(exc).__name__}", kind=kind) from exc
        if response.status_code < 400:
            return response
        if attempt + 1 < attempts and response.status_code in {500, 502, 503, 504}:
            await asyncio.sleep(0.5)
            continue
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise provider_error(payload, operation=operation, status_code=response.status_code)
    raise AssertionError("request attempt loop exhausted")


def _extract_json(raw: str) -> dict:
    """Parse JSON directly, from a code fence, or from the outermost braces."""
    raw = (raw or "").strip()
    if not raw:
        raise EachlabsError("model returned empty output", kind=ErrorKind.INVALID_RESPONSE)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise EachlabsError("could not parse JSON from output", kind=ErrorKind.INVALID_RESPONSE)


class EachlabsClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL) -> None:
        if not api_key:
            raise EachlabsError("EACHLABS_API_KEY is not set")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._base = base_url.rstrip("/")

    async def upload_image(
        self,
        client: httpx.AsyncClient,
        data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """Presign, PUT the bytes, return the public URL."""
        r = await _request(
            client, "POST",
            f"{self._base}/upload/presign",
            operation="presign",
            headers=self._headers,
            json={"content_type": content_type, "file_type": "image"},
        )
        presign = _object_response(r)

        put_url = presign.get("presigned_url")
        public_url = presign.get("public_url")
        if not isinstance(put_url, str) or not put_url or not isinstance(public_url, str) or not public_url:
            raise EachlabsError("presign response missing URLs", kind=ErrorKind.INVALID_RESPONSE)

        # required_headers must be sent verbatim or the PUT is rejected.
        put_headers = presign.get("required_headers") or {}
        if not isinstance(put_headers, dict):
            raise EachlabsError("invalid upload headers", kind=ErrorKind.INVALID_RESPONSE)
        put_headers = dict(put_headers)
        put_headers.setdefault("Content-Type", content_type)

        await _request(
            client, "PUT", put_url, operation="upload", content=data, headers=put_headers,
        )

        log.info("uploaded %d bytes -> %s", len(data), public_url)
        return public_url

    async def predict(
        self,
        client: httpx.AsyncClient,
        model: str,
        model_input: dict,
        version: str = "0.0.1",
        poll_interval: float = 0.8,  # measured predict_time is ~1-3s
        timeout_s: float = 50.0,
    ) -> dict:
        """Bound queueing, submission and polling by the caller's remaining budget."""
        try:
            async with asyncio.timeout(timeout_s):
                return await self._predict(client, model, model_input, version, poll_interval)
        except TimeoutError as exc:
            raise EachlabsError("prediction deadline exceeded", kind=ErrorKind.TIMEOUT) from exc

    async def _predict(
        self, client: httpx.AsyncClient, model: str, model_input: dict,
        version: str, poll_interval: float,
    ) -> dict:
        async with _SEMAPHORE:
            payload = {"model": model, "version": version, "input": model_input}
            r = await _request(
                client, "POST", f"{self._base}/prediction",
                operation="create prediction", headers=self._headers, json=payload,
            )

            created = _object_response(r)
            # Docs say `predictionID`; their SDK example says `id`.
            pid = created.get("predictionID") or created.get("id") or created.get("prediction_id")
            if not pid:
                raise EachlabsError("no prediction id in response", kind=ErrorKind.INVALID_RESPONSE)

            # Submission success only confirms creation. Poll for the final output.
            while True:
                await asyncio.sleep(poll_interval)

                pr = await _request(
                    client, "GET", f"{self._base}/prediction/{pid}",
                    operation="poll", retry_poll=True, headers=self._headers,
                )
                body = _object_response(pr)
                record = body.get("data") if isinstance(body.get("data"), dict) else body

                status = str(record.get("status", "")).lower()
                if status in _TERMINAL_OK:
                    return record
                if status in _TERMINAL_BAD:
                    # Only structured error fields establish availability or
                    # quota failures. Free-form logs are not a routing signal.
                    detail = record.get("output")
                    if not isinstance(detail, dict):
                        detail = record
                    if status in {"cancelled", "canceled"}:
                        raise EachlabsError("prediction was cancelled")
                    error = provider_error(detail, operation="prediction")
                    error.record = record
                    raise error

    async def predict_json(self, client: httpx.AsyncClient, model: str, model_input: dict, **kw) -> tuple[dict, dict]:
        """predict() plus JSON parsing. Returns (parsed_output, raw_record)."""
        record = await self.predict(client, model, model_input, **kw)
        output = record.get("output")
        if isinstance(output, dict):
            return output, record
        if isinstance(output, list) and output and isinstance(output[0], dict):
            return output[0], record
        if isinstance(output, list):
            output = "".join(str(x) for x in output)
        try:
            parsed = _extract_json(str(output))
            if not isinstance(parsed, dict):
                raise EachlabsError("model output is not an object", kind=ErrorKind.INVALID_RESPONSE)
        except EachlabsError as exc:
            exc.record = record
            raise
        return parsed, record
