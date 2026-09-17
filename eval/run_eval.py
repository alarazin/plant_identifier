"""Evaluate configured models and the app identification pipeline.

Calls run sequentially and save results after each request. See eval/EVAL.md."""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import logging
import math
from pathlib import Path
import statistics
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile

# Load settings before provider adapters read their environment variables.
load_dotenv(ROOT / "backend" / ".env")
from backend.app.main import CHAIN, REQUEST_BUDGET_S, identify_image

IMAGES = ROOT / "eval" / "images"
RESULTS = ROOT / "eval" / "results"
GBIF_CACHE = RESULTS / "gbif_cache.json"
CONFIGS = {p.slug: [p] for p in CHAIN} | {"production-chain": None}


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def sample_rows(rows, limit):
    """Deterministic tier round-robin, including when limited for cost."""
    tiers = {}
    for row in rows:
        tiers.setdefault(row["tier"], []).append(row)
    ordered = []
    while any(tiers.values()):
        for group in tiers.values():
            if group:
                ordered.append(group.pop(0))
    return ordered[:limit] if limit else ordered


class Gbif:
    URL = "https://api.gbif.org/v1/species/match"

    def __init__(self):
        self.cache = json.loads(GBIF_CACHE.read_text()) if GBIF_CACHE.exists() else {}
        # Old harness cached HTTP failures as NONE; do not trust those entries.
        self.cache = {k: v for k, v in self.cache.items() if v.get("matchType") not in (None, "NONE")}

    async def match(self, client, name):
        key = name.strip().lower()
        if key in self.cache:
            return self.cache[key]
        response = await client.get(self.URL, params={"name": name, "kingdom": "Plantae"})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or "matchType" not in data:
            raise ValueError("Invalid GBIF response")
        self.cache[key] = {k: data.get(k) for k in (
            "matchType", "confidence", "rank", "canonicalName", "species",
            "speciesKey", "genus", "genusKey", "family", "usageKey",
        )}
        write_json(GBIF_CACHE, self.cache)
        return self.cache[key]


async def score_row(client, gbif, truth_sci, candidates):
    truth = await gbif.match(client, truth_sci)
    if not truth.get("speciesKey"):
        raise ValueError(f"Ground truth has no species match: {truth_sci}")
    ranked = []
    for candidate in candidates[:3]:
        name = (candidate.get("scientific_name") or "").strip()
        abstained = name.lower() in ("", "unknown", "uncertain")
        match = {} if abstained else await gbif.match(client, name)
        genus = match.get("genus") or candidate.get("genus") or ""
        family = match.get("family") or candidate.get("family") or ""
        ranked.append({
            "abstained": abstained,
            "unmatched_name": not abstained and match.get("matchType") == "NONE",
            "species_hit": bool(match.get("speciesKey")) and match["speciesKey"] == truth["speciesKey"],
            "genus_hit": bool(genus) and genus.lower() == (truth.get("genus") or "").lower(),
            "family_hit": bool(family) and family.lower() == (truth.get("family") or "").lower(),
            "resolved": match,
        })
    return {
        "top1_species": bool(ranked) and ranked[0]["species_hit"],
        "top3_species": any(r["species_hit"] for r in ranked),
        "top1_genus": bool(ranked) and ranked[0]["genus_hit"],
        "top3_genus": any(r["genus_hit"] for r in ranked),
        "any_unmatched_name": any(r["unmatched_name"] for r in ranked),
        "abstained": not ranked or ranked[0]["abstained"],
        "truth_resolved": truth,
        "ranked": ranked,
    }


def spending(records, reserve):
    known, unknown = 0.0, 0
    for record in records:
        for attempt in record.get("attempts", []):
            cost = (attempt.get("metrics") or {}).get("cost")
            try:
                cost = float(cost)
                if not math.isfinite(cost) or cost < 0:
                    raise ValueError()
            except (TypeError, ValueError):
                unknown += 1
            else:
                known += cost
    return {"recorded_usd": round(known, 8), "unknown_cost_attempts": unknown,
            "recorded_plus_reserve_usd": round(known + unknown * reserve, 8)}


def summarize(records, reserve):
    ok = [r for r in records if r.get("ok")]
    scored = [r for r in ok if "score" in r]
    result = {"attempted": len(records), "completed": len(ok), "failed": len(records) - len(ok),
              "scoring_errors": len(ok) - len(scored), **spending(records, reserve)}
    # Leave accuracy unset while taxonomy lookups are pending.
    for metric in ("top1_species", "top3_species", "top1_genus", "top3_genus"):
        hits = sum(r["score"][metric] for r in scored)
        result[metric + "_hits"] = hits
        result["effective_" + metric] = hits / len(records) if records and len(ok) == len(scored) else None
        result["completed_" + metric] = hits / len(scored) if scored else None
    result["p50_elapsed_s"] = statistics.median(r["elapsed_s"] for r in records) if records else None
    result["fallback_used"] = sum(bool(r.get("response", {}).get("meta", {}).get("fallback")) for r in ok)
    result["errors"] = {}
    for r in records:
        if not r.get("ok"):
            kind = r.get("error_kind", "unknown")
            result["errors"][kind] = result["errors"].get(kind, 0) + 1
    result["by_tier"] = {}
    for tier in sorted({r["tier"] for r in records}):
        group = [r for r in records if r["tier"] == tier]
        result["by_tier"][tier] = {"n": len(group), "top1_hits": sum(r.get("score", {}).get("top1_species", False) for r in group)}
    return result


def fingerprint(rows, configs):
    sources = [ROOT / "backend" / "app" / name for name in
               ("main.py", "eachlabs.py", "errors.py", "providers.py", "prompts.py", "schema.py")]
    sources.append(Path(__file__))
    return {
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "dataset": [{**r, "sha256": hashlib.sha256((IMAGES / r["filename"]).read_bytes()).hexdigest()} for r in rows],
        "configurations": {name: [{"model": p.slug, "version": p.version,
                                  "input_template": p.identify_input("<uploaded-image-url>")}
                                 for p in (CONFIGS[name] or CHAIN)] for name in configs},
        "backend_deadline_s": REQUEST_BUDGET_S,
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Images per configuration; 0 means all")
    parser.add_argument("--models", nargs="+", choices=CONFIGS, default=list(CONFIGS))
    parser.add_argument("--output-dir", type=Path, help="Existing directory resumes without repeating paid calls")
    parser.add_argument("--budget-usd", type=float, default=3.0)
    parser.add_argument("--reserve-usd", type=float, default=0.10, help="Conservative per-attempt reserve, not a provider billing cap")
    parser.add_argument("--max-new-trials", type=int, default=0, help="Pause after this many new calls; 0 means no limit")
    args = parser.parse_args()
    if args.limit < 0 or args.max_new_trials < 0 or args.budget_usd <= 0 or args.reserve_usd <= 0:
        parser.error("Limits must be nonnegative; budget and reserve must be positive")
    logging.getLogger().setLevel(logging.ERROR)
    with (ROOT / "eval" / "labels.csv").open() as handle:
        rows = sample_rows(list(csv.DictReader(handle)), args.limit)
    output = args.output_dir or RESULTS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = fingerprint(rows, args.models)  # Check files/config before paying.
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous["fingerprint"] != manifest:
            parser.error("Dataset, code or configuration changed; choose a new output directory")
    else:
        write_json(manifest_path, {"started_utc": datetime.now(timezone.utc).isoformat(), "fingerprint": manifest,
                                  "budget_usd": args.budget_usd, "reserve_usd": args.reserve_usd,
                                  "timing": "Backend normalization, upload and prediction; excludes taxonomy scoring and mobile transport"})
    raw_path = output / "trials.json"
    records = json.loads(raw_path.read_text()) if raw_path.exists() else []
    done = {(r["configuration"], r["filename"]) for r in records}
    gbif = Gbif()
    new_count = 0
    stop_reason = "complete"

    def checkpoint():
        write_json(raw_path, records)
        write_json(output / "summary.json", {
            "planned_trials": len(rows) * len(args.models), "stop_reason": stop_reason,
            **spending(records, args.reserve_usd),
            "configurations": {name: summarize([r for r in records if r["configuration"] == name], args.reserve_usd)
                               for name in args.models},
        })

    async with httpx.AsyncClient(timeout=15) as taxonomy_client:
        async def score(record):
            if record.get("ok") and "score" not in record:
                try:
                    record["score"] = await score_row(taxonomy_client, gbif, record["truth"], record["response"]["candidates"])
                    record.pop("scoring_error", None)
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    record["scoring_error"] = str(exc)
                checkpoint()

        for record in records:
            await score(record)
        print(f"Results: {output}\nPlan: {len(rows)} images × {len(args.models)} configurations", flush=True)
        for row in rows:
            for name in args.models:
                if (name, row["filename"]) in done:
                    continue
                reserve_next = args.reserve_usd * len(CONFIGS[name] or CHAIN)
                if spending(records, args.reserve_usd)["recorded_plus_reserve_usd"] + reserve_next > args.budget_usd:
                    stop_reason = "budget guard"
                    break
                if args.max_new_trials and new_count >= args.max_new_trials:
                    stop_reason = "trial limit"
                    break
                record = {"configuration": name, "filename": row["filename"], "truth": row["scientific_name"],
                          "tier": row["tier"], "attempts": [], "started_utc": datetime.now(timezone.utc).isoformat()}
                started = time.perf_counter()
                upload = UploadFile(io.BytesIO((IMAGES / row["filename"]).read_bytes()), filename=row["filename"])
                try:
                    record["response"] = await identify_image(upload, providers=CONFIGS[name], attempts=record["attempts"])
                    record["ok"] = True
                except HTTPException as exc:
                    record.update(ok=False, http_status=exc.status_code, error=exc.detail)
                    last = record["attempts"][-1] if record["attempts"] else {}
                    record["error_kind"] = last.get("error_kind") or ("timeout" if exc.status_code == 504 else f"http_{exc.status_code}")
                finally:
                    await upload.close()
                record["elapsed_s"] = round(time.perf_counter() - started, 3)
                records.append(record)
                new_count += 1
                checkpoint()  # Preserve paid output before free taxonomy lookups.
                await score(record)
                cost = spending(records, args.reserve_usd)
                verdict = ("hit" if record.get("score", {}).get("top1_species") else "miss") if record["ok"] else record["error_kind"]
                print(f"[{len(records)}/{len(rows)*len(args.models)}] {name} {row['filename']}: {verdict}, {record['elapsed_s']:.1f}s; recorded ${cost['recorded_usd']:.4f}, unknown costs {cost['unknown_cost_attempts']}", flush=True)
            if stop_reason != "complete":
                break
    checkpoint()
    print(f"Stopped: {stop_reason}. Summary: {output / 'summary.json'}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
