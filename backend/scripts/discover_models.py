"""List image-to-text models, input fields and prices from the Eachlabs catalog."""

import json
import sys

import httpx

BASE = "https://api.eachlabs.ai/v1"
IMAGE_FIELD_HINTS = ("image", "media", "img", "photo")


def fetch_catalog() -> list[dict]:
    models, offset = [], 0
    with httpx.Client(timeout=30) as client:
        while True:
            r = client.get(f"{BASE}/models", params={"limit": 200, "offset": offset})
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict):
                batch = payload.get("models") or payload.get("data") or []
            else:
                batch = payload
            if not batch:
                break
            models.extend(batch)
            if len(batch) < 200:
                break
            offset += len(batch)
    return models


def fetch_detail(client: httpx.Client, slug: str) -> dict | None:
    try:
        r = client.get(f"{BASE}/models/{slug}")
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def image_fields(model: dict) -> list[str]:
    """Find image URL fields in the model request schema."""
    props = (model.get("request_schema") or {}).get("properties", {})
    found = []
    for name, spec in props.items():
        if not any(h in name.lower() for h in IMAGE_FIELD_HINTS):
            continue
        blob = json.dumps(spec)
        if '"uri"' in blob or "url" in name.lower():
            found.append(name)
    return found


def main() -> int:
    print("Fetching catalog (no auth required)...")
    catalog = fetch_catalog()
    print(f"  {len(catalog)} models in catalog\n")

    matched = []
    for m in catalog:
        if m.get("output_type") != "text":
            continue
        fields = image_fields(m)
        if not fields:
            continue
        matched.append((m, fields))

    print(f"  {len(matched)} with text output + an image input field")
    print("  fetching detail for version/cost...\n")

    candidates = []
    with httpx.Client(timeout=30) as client:
        for m, fields in matched:
            slug = m["slug"]
            detail = fetch_detail(client, slug) or {}
            props = (m.get("request_schema") or {}).get("properties", {})
            candidates.append(
                {
                    "slug": slug,
                    "title": m.get("title"),
                    "version": detail.get("version") or m.get("version") or "0.0.1",
                    "image_fields": fields,
                    "structured_output": "response_schema" in props,
                    "required": (m.get("request_schema") or {}).get("required", []),
                    "cost": detail.get("cost") or m.get("cost"),
                }
            )

    print(f"=== {len(candidates)} image->text model(s) found ===\n")
    for c in candidates:
        print(f"  {c['slug']}  (v{c['version']})  — {c['title']}")
        print(f"    image field(s): {', '.join(c['image_fields'])}")
        print(f"    required:       {c['required']}")
        print(f"    response_schema support: {c['structured_output']}")
        print(f"    cost: {json.dumps(c['cost'])}")
        print()

    with open("backend/scripts/catalog_vlms.json", "w") as f:
        json.dump(candidates, f, indent=2)
    print("Wrote backend/scripts/catalog_vlms.json")
    return 0 if candidates else 1


if __name__ == "__main__":
    sys.exit(main())
