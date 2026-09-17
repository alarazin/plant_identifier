"""Offline regression checks: real client + ASGI routes, mocked provider HTTP.

Run: backend/.venv/bin/python -m unittest discover -s backend/tests -v
"""

import asyncio
import io
import json
import logging
import os
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from backend.app import eachlabs
from backend.app.errors import provider_error

# Import the app without requiring or exposing a developer's API key.
with patch.dict(os.environ, {"EACHLABS_API_KEY": "test-key"}):
    from backend.app import main


NON_PLANT = {"is_plant": False, "image_quality": "good", "candidates": []}
UNCERTAIN = {
    "is_plant": True, "image_quality": "good",
    "candidates": [{"common_name": "Plant", "scientific_name": "uncertain",
                    "genus": "Unknown", "confidence": "low"}],
}
CARE = {"light": "Indirect light", "water": "Let soil dry", "toxicity": "Unknown"}
UNAVAILABLE = {"error_code": "MODEL_UNAVAILABLE", "error_message": "Temporarily unavailable"}


class ErrorClassificationTests(unittest.TestCase):
    def test_only_explicit_model_errors_allow_fallback(self):
        cases = [
            (503, UNAVAILABLE, "create prediction", True),
            (503, {"error": "Model is unavailable"}, "create prediction", True),
            (None, UNAVAILABLE, "prediction", True),
            (429, {"error_code": "MODEL_RATE_LIMITED"}, "create prediction", True),
            (None, {"error_code": "MODEL_QUOTA_EXCEEDED"}, "prediction", True),
            (429, {"error": "too many requests"}, "create prediction", False),
            (429, {"error_code": "MODEL_RATE_LIMITED", "scope": "account"}, "create prediction", False),
            (503, {"error": "Service unavailable"}, "create prediction", False),
            (500, {"error": "Internal server error"}, "create prediction", False),
            (404, {"error": "Model not found"}, "create prediction", False),
            (None, {"error_code": "PROVIDER_FAILED", "retryable": True}, "prediction", False),
            (None, {"logs": "Model is unavailable"}, "prediction", False),
            (None, {"error_code": "PROVIDER_AUTH_ERROR", "error_message": "Model is unavailable"}, "prediction", False),
            (429, {"scope": "model", "error": "Rate limit exceeded"}, "create prediction", True),
            (503, UNAVAILABLE, "poll", False),
            (503, UNAVAILABLE, "presign", False),
            (400, UNAVAILABLE, "create prediction", False),
            (401, UNAVAILABLE, "create prediction", False),
            (402, UNAVAILABLE, "create prediction", False),
            (403, UNAVAILABLE, "create prediction", False),
        ]
        for status, payload, operation, expected in cases:
            with self.subTest(status=status, payload=payload, operation=operation):
                error = provider_error(payload, operation=operation, status_code=status)
                self.assertEqual(error.allows_fallback, expected)


class RequestPolicyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        previous_logging = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, previous_logging)
        self.semaphore_patch = patch.object(eachlabs, "_SEMAPHORE", asyncio.Semaphore(2))
        self.semaphore_patch.start()
        self.addCleanup(self.semaphore_patch.stop)
        from backend.app.providers import REGISTRY
        self.chain_patch = patch.object(main, "CHAIN", list(REGISTRY.values()))
        self.chain_patch.start()
        self.addCleanup(self.chain_patch.stop)

    async def call_app(self, override=None, *, task="identify", output=None, image=b"default"):
        """Run all real upload/prediction/error handling without any network."""
        calls = []
        models = []
        async def upstream(request):
            calls.append(request)
            if request.url.path == "/v1/prediction" and request.method == "POST":
                models.append(json.loads(request.content)["model"])
            if override:
                response = await override(request)
                if response is not None:
                    return response
            if request.url.path == "/v1/upload/presign":
                return httpx.Response(200, json={
                    "presigned_url": "https://uploads.test/photo",
                    "public_url": "https://uploads.test/public-photo",
                })
            if request.method == "PUT":
                return httpx.Response(200)
            if request.method == "POST":
                return httpx.Response(200, json={"predictionID": models[-1]})
            return httpx.Response(200, json={
                "status": "success", "output": output if output is not None else (CARE if task == "care" else NON_PLANT),
            })

        real_client = httpx.AsyncClient
        provider_client = real_client(transport=httpx.MockTransport(upstream))
        original_predict = eachlabs.EachlabsClient.predict
        async def fast_poll(instance, *args, **kwargs):
            return await original_predict(instance, *args, **kwargs, poll_interval=0)

        async with real_client(transport=httpx.ASGITransport(app=main.app), base_url="http://app.test") as app_client:
            with patch.object(main.httpx, "AsyncClient", return_value=provider_client), \
                 patch.object(main, "_client", eachlabs.EachlabsClient("test-key")), \
                 patch.object(eachlabs.EachlabsClient, "predict", fast_poll):
                if task == "care":
                    response = await app_client.post("/care", json={"scientific_name": "Test plant"})
                else:
                    if image == b"default":
                        buf = io.BytesIO()
                        Image.new("RGB", (16, 16), "green").save(buf, "JPEG")
                        image = buf.getvalue()
                    response = await app_client.post("/identify", files={"image": ("photo.jpg", image, "image/jpeg")})
        return response, models, calls

    async def test_non_plant_and_uncertain_answers_are_final(self):
        for output in (NON_PLANT, UNCERTAIN):
            with self.subTest(output=output):
                response, models, _ = await self.call_app(output=output)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(models), 1)
                self.assertEqual(response.json()["is_plant"], output["is_plant"])
                self.assertFalse(response.json()["meta"]["fallback"])

    async def test_explicit_unavailability_and_model_limit_use_fallback(self):
        for status, payload in ((503, UNAVAILABLE), (429, {"error_code": "MODEL_RATE_LIMITED"})):
            async def unavailable(request):
                if request.method == "POST" and request.url.path == "/v1/prediction":
                    if json.loads(request.content)["model"] == main.CHAIN[0].slug:
                        return httpx.Response(status, json=payload)
            response, models, calls = await self.call_app(unavailable)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(models, [main.CHAIN[0].slug, main.CHAIN[1].slug])
            self.assertTrue(response.json()["meta"]["fallback"])
            self.assertEqual(sum(r.method == "PUT" for r in calls), 1)

    async def test_terminal_model_quota_uses_fallback(self):
        async def limited(request):
            if request.method == "GET" and request.url.path.endswith(main.CHAIN[0].slug):
                return httpx.Response(200, json={"status": "error", "output": {"error_code": "MODEL_QUOTA_EXCEEDED"}})
        response, models, _ = await self.call_app(limited)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(models), 2)

    async def test_all_unavailable_models_return_controlled_error(self):
        async def unavailable(request):
            if request.method == "POST" and request.url.path == "/v1/prediction":
                return httpx.Response(503, json=UNAVAILABLE)
        response, models, _ = await self.call_app(unavailable)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(models, [p.slug for p in main.CHAIN])

    async def test_malformed_fallback_does_not_try_third_model(self):
        async def unavailable(request):
            if request.method == "POST" and request.url.path == "/v1/prediction":
                if json.loads(request.content)["model"] == main.CHAIN[0].slug:
                    return httpx.Response(503, json=UNAVAILABLE)
        response, models, _ = await self.call_app(unavailable, output="invalid JSON")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(models), 2)

    async def test_account_and_ambiguous_submission_errors_never_fallback_or_retry(self):
        for status in (400, 401, 402, 403, 404, 429, 500, 503, 504):
            with self.subTest(status=status):
                async def failed(request):
                    if request.method == "POST" and request.url.path == "/v1/prediction":
                        return httpx.Response(status, json={"error": "provider detail should not leak"})
                response, models, _ = await self.call_app(failed)
                self.assertEqual(len(models), 1)
                self.assertIn(response.status_code, (502, 503, 504))
                self.assertNotIn("provider detail", response.text)

    async def test_network_failures_are_controlled_without_new_predictions(self):
        for exception, status in ((httpx.ReadTimeout, 504), (httpx.ConnectError, 503)):
            async def failed(request):
                if request.method == "POST" and request.url.path == "/v1/prediction":
                    raise exception("simulated", request=request)
            response, models, _ = await self.call_app(failed)
            self.assertEqual(response.status_code, status)
            self.assertEqual(len(models), 1)

    async def test_upload_network_failure_never_starts_a_prediction(self):
        async def failed(request):
            if request.method == "PUT":
                raise httpx.ConnectError("simulated", request=request)
        response, models, _ = await self.call_app(failed)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(models, [])

    async def test_invalid_api_json_returns_processing_error(self):
        for path in ("/v1/upload/presign", "/v1/prediction"):
            async def invalid(request):
                if request.url.path == path:
                    return httpx.Response(200, text="not JSON")
            response, models, _ = await self.call_app(invalid)
            self.assertEqual(response.status_code, 502)
            self.assertLessEqual(len(models), 1)

    async def test_poll_retries_the_same_prediction_once(self):
        for error in ("timeout", "http"):
            polls = 0
            async def flaky(request):
                nonlocal polls
                if request.method == "GET":
                    polls += 1
                    if polls == 1:
                        if error == "timeout":
                            raise httpx.ReadTimeout("simulated", request=request)
                        return httpx.Response(503, json={"error": "Service unavailable"})
            response, models, calls = await self.call_app(flaky)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(polls, 2)
            self.assertEqual(len(models), 1)
            self.assertEqual(len({str(r.url) for r in calls if r.method == "GET"}), 1)

    async def test_poll_retry_exhaustion_never_switches_models(self):
        async def failed(request):
            if request.method == "GET":
                raise httpx.ReadTimeout("simulated", request=request)
        response, models, calls = await self.call_app(failed)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(len(models), 1)
        self.assertEqual(sum(r.method == "GET" for r in calls), 2)

    async def test_malformed_answers_fail_without_fallback(self):
        for output in ("bad JSON", "[]", {"is_plant": "false"}, {"is_plant": True, "image_quality": "good", "candidates": "bad"}):
            with self.subTest(output=output):
                response, models, _ = await self.call_app(output=output)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(len(models), 1)

    async def test_generic_terminal_failure_does_not_fallback(self):
        async def failed(request):
            if request.method == "GET":
                return httpx.Response(200, json={"status": "error", "output": {"error_code": "PROVIDER_FAILED", "retryable": True}})
        response, models, _ = await self.call_app(failed)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(models), 1)

    async def test_care_has_the_same_policy_and_validates_output(self):
        response, models, _ = await self.call_app(task="care")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(models), 1)
        response, models, _ = await self.call_app(task="care", output={**CARE, "common_problems": "not a list"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(len(models), 1)

    async def test_invalid_images_never_reach_provider(self):
        for image in (b"", b"not an image"):
            response, models, calls = await self.call_app(image=image)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(calls, [])

    async def test_one_deadline_covers_primary_and_fallback(self):
        async def slow(request):
            if request.method == "POST" and request.url.path == "/v1/prediction":
                await asyncio.sleep(0.08)
                if json.loads(request.content)["model"] == main.CHAIN[0].slug:
                    return httpx.Response(503, json=UNAVAILABLE)
        with patch.object(main, "REQUEST_BUDGET_S", 0.13), patch.object(main, "MIN_PREDICTION_BUDGET_S", 0.001):
            response, models, _ = await self.call_app(slow)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(len(models), 2)

    async def test_upload_is_inside_deadline(self):
        async def slow(request):
            await asyncio.sleep(0.1)
        with patch.object(main, "REQUEST_BUDGET_S", 0.02):
            response, models, _ = await self.call_app(slow)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(models, [])

    async def test_care_polling_is_inside_deadline(self):
        async def pending(request):
            if request.method == "GET":
                await asyncio.sleep(0.02)
                return httpx.Response(200, json={"status": "processing"})
        with patch.object(main, "REQUEST_BUDGET_S", 0.04), patch.object(main, "MIN_PREDICTION_BUDGET_S", 0.001):
            response, models, _ = await self.call_app(pending, task="care")
        self.assertEqual(response.status_code, 504)
        self.assertEqual(len(models), 1)

    async def test_queue_wait_is_inside_deadline(self):
        with patch.object(eachlabs, "_SEMAPHORE", asyncio.Semaphore(0)), \
             patch.object(main, "REQUEST_BUDGET_S", 0.03), \
             patch.object(main, "MIN_PREDICTION_BUDGET_S", 0.001):
            response, models, _ = await self.call_app()
        self.assertEqual(response.status_code, 504)
        self.assertEqual(models, [])

    async def test_not_enough_time_does_not_start_fallback(self):
        async def unavailable(request):
            if request.method == "POST" and request.url.path == "/v1/prediction":
                await asyncio.sleep(0.06)
                return httpx.Response(503, json=UNAVAILABLE)
        with patch.object(main, "REQUEST_BUDGET_S", 0.1), patch.object(main, "MIN_PREDICTION_BUDGET_S", 0.05):
            response, models, _ = await self.call_app(unavailable)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(len(models), 1)


if __name__ == "__main__":
    unittest.main()
