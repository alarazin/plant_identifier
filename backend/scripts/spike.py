"""Check one image identification through Eachlabs.

Usage: backend/.venv/bin/python backend/scripts/spike.py path/to/plant.jpg"""

import asyncio
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import httpx
from dotenv import load_dotenv

from backend.app.eachlabs import EachlabsClient, EachlabsError
from backend.app.main import _identify_input, _normalize_image

load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")

import os

MODEL = os.getenv("EACHLABS_MODEL", "gemini-2-5-flash")


async def main(path: str) -> int:
    key = os.getenv("EACHLABS_API_KEY", "")
    if not key:
        print("FAIL: EACHLABS_API_KEY not set. Put it in backend/.env")
        return 1
    print(f"key loaded: ...{key[-4:]}  model: {MODEL}\n")

    raw = pathlib.Path(path).read_bytes()
    jpeg = _normalize_image(raw)
    print(f"[1/4] normalized {len(raw):,} -> {len(jpeg):,} bytes")

    client = EachlabsClient(key)
    async with httpx.AsyncClient(timeout=120) as http:
        try:
            t0 = time.perf_counter()
            url = await client.upload_image(http, jpeg)
            print(f"[2/4] uploaded in {time.perf_counter()-t0:.1f}s")
            print(f"      {url}")

            t1 = time.perf_counter()
            print("[3/4] predicting (create + poll)...")
            result, record = await client.predict_json(http, MODEL, _identify_input(url))
            print(f"[4/4] done in {time.perf_counter()-t1:.1f}s\n")
        except EachlabsError as exc:
            print(f"\nFAIL: {exc}")
            print("\nIf the model slug is rejected, try in backend/.env:")
            print("  EACHLABS_MODEL=openai-chat-completion   # then adjust input keys")
            return 1

    print("=== PARSED ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n=== RECORD META ===")
    print(json.dumps({k: v for k, v in record.items() if k != "output"}, indent=2)[:1500])
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
