"""Download Commons photos for five difficulty groups.

Groups: easy plants, trees, similar-looking species, grasses and toxic lookalikes.
Save species labels, authors, licences and sources in labels.csv."""

from __future__ import annotations

import csv
import pathlib
import sys
import time

import httpx

API = "https://commons.wikimedia.org/w/api.php"
UA = "PlantIdentifierCaseStudy/1.0 (educational evaluation; httpx)"
OUT = pathlib.Path(__file__).parent / "images"
LABELS = pathlib.Path(__file__).parent / "labels.csv"

SPECIES: list[tuple[str, str, str]] = [
    # (scientific_name, common_name, tier)
    ("Monstera deliciosa", "Swiss cheese plant", "easy"),
    ("Ficus lyrata", "Fiddle-leaf fig", "easy"),
    ("Dracaena trifasciata", "Snake plant", "easy"),
    ("Zamioculcas zamiifolia", "ZZ plant", "easy"),
    ("Chlorophytum comosum", "Spider plant", "easy"),
    ("Spathiphyllum wallisii", "Peace lily", "easy"),
    ("Aloe vera", "Aloe vera", "easy"),
    ("Crassula ovata", "Jade plant", "easy"),
    ("Helianthus annuus", "Sunflower", "easy"),
    ("Lavandula angustifolia", "English lavender", "easy"),
    ("Bellis perennis", "Common daisy", "easy"),
    ("Taraxacum officinale", "Dandelion", "easy"),
    ("Hydrangea macrophylla", "Bigleaf hydrangea", "easy"),
    ("Papaver rhoeas", "Common poppy", "easy"),
    ("Digitalis purpurea", "Foxglove", "easy"),
    ("Hedera helix", "Common ivy", "easy"),
    ("Quercus robur", "English oak", "tree"),
    ("Acer palmatum", "Japanese maple", "tree"),
    ("Betula pendula", "Silver birch", "tree"),
    ("Olea europaea", "Olive tree", "tree"),
    ("Ginkgo biloba", "Ginkgo", "tree"),
    ("Epipremnum aureum", "Golden pothos", "confusable"),
    ("Philodendron hederaceum", "Heartleaf philodendron", "confusable"),
    ("Monstera adansonii", "Swiss cheese vine", "confusable"),
    ("Echeveria elegans", "Mexican snowball", "confusable"),
    ("Sempervivum tectorum", "Common houseleek", "confusable"),
    ("Mentha spicata", "Spearmint", "confusable"),
    ("Melissa officinalis", "Lemon balm", "confusable"),
    ("Petroselinum crispum", "Parsley", "confusable"),
    ("Coriandrum sativum", "Coriander", "confusable"),
    ("Poa annua", "Annual meadow grass", "grass"),
    ("Festuca rubra", "Red fescue", "grass"),
    ("Cynodon dactylon", "Bermuda grass", "grass"),
    ("Phragmites australis", "Common reed", "grass"),
    ("Nerium oleander", "Oleander", "toxic"),
    ("Conium maculatum", "Poison hemlock", "toxic"),
    ("Convallaria majalis", "Lily of the valley", "toxic"),
    ("Allium ursinum", "Wild garlic", "toxic"),
    ("Ricinus communis", "Castor bean", "toxic"),
    ("Atropa belladonna", "Deadly nightshade", "toxic"),
]


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    """GET with backoff. Commons rate-limits anonymous search aggressively."""
    delay = 2.0
    for attempt in range(6):
        r = client.get(url, **kw)
        if r.status_code == 429:
            wait = float(r.headers.get("retry-after") or delay)
            print(f"        429, backing off {wait:.0f}s (attempt {attempt+1}/6)")
            time.sleep(wait)
            delay = min(delay * 2, 60)
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("giving up after repeated 429s")


def search_image(client: httpx.Client, species: str) -> dict | None:
    """Find one usable Commons photo for a species."""
    r = _get(
        client,
        API,
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f'filetype:bitmap "{species}"',
            "gsrnamespace": 6,
            "gsrlimit": 8,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime",
            "iiurlwidth": 1024,
        },
    )
    pages = (r.json().get("query") or {}).get("pages") or {}
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if (info.get("width") or 0) < 500:
            continue
        meta = info.get("extmetadata") or {}
        return {
            "title": page.get("title", ""),
            "url": info.get("thumburl") or info.get("url"),
            "licence": (meta.get("LicenseShortName") or {}).get("value", "unknown"),
            "author": (meta.get("Artist") or {}).get("value", "unknown")[:120],
            "descurl": info.get("descriptionurl", ""),
        }
    return None


def load_existing() -> dict[str, dict]:
    """Resume support — keep rows for images already on disk."""
    if not LABELS.exists():
        return {}
    with LABELS.open() as f:
        return {
            r["filename"]: r
            for r in csv.DictReader(f)
            if (OUT / r["filename"]).exists()
        }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    existing = load_existing()
    rows, missing = list(existing.values()), []
    if existing:
        print(f"resuming — {len(existing)} image(s) already present\n")

    with httpx.Client(timeout=60, headers={"User-Agent": UA}, follow_redirects=True) as client:
        for i, (sci, common, tier) in enumerate(SPECIES, 1):
            slug = sci.lower().replace(" ", "_")
            dest = OUT / f"{slug}.jpg"
            if dest.name in existing:
                print(f"  [{i:2}/{len(SPECIES)}] skip  {dest.name}")
                continue

            try:
                hit = search_image(client, sci)
            except Exception as exc:
                print(f"  [{i:2}/{len(SPECIES)}] SEARCH-FAIL {sci}: {exc}")
                missing.append(sci)
                continue
            if not hit or not hit["url"]:
                print(f"  [{i:2}/{len(SPECIES)}] MISS  {sci}")
                missing.append(sci)
                continue

            try:
                img = _get(client, hit["url"])
                dest.write_bytes(img.content)
            except Exception as exc:
                print(f"  [{i:2}/{len(SPECIES)}] DL-FAIL {sci}: {exc}")
                missing.append(sci)
                continue

            kb = len(img.content) // 1024
            print(f"  [{i:2}/{len(SPECIES)}] ok    {dest.name:38} {kb:5}KB  {tier:10} {hit['licence']}")
            rows.append(
                {
                    "filename": dest.name,
                    "scientific_name": sci,
                    "common_name": common,
                    "genus": sci.split()[0],
                    "tier": tier,
                    "licence": hit["licence"],
                    "author": hit["author"],
                    "source": hit["descurl"],
                }
            )
            time.sleep(1.5)  # be polite to the Commons API — it 429s readily

    with LABELS.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "filename", "scientific_name", "common_name", "genus",
                "tier", "licence", "author", "source",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} images -> {OUT}")
    print(f"labels -> {LABELS}")
    if missing:
        print(f"missing ({len(missing)}): {', '.join(missing)}")

    by_tier: dict[str, int] = {}
    for r in rows:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
    print("per tier: " + "  ".join(f"{k}={v}" for k, v in sorted(by_tier.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
