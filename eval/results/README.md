# Evaluation results

The final-model run is in [2026-09-17-final/](2026-09-17-final/).
See [EVAL.md](../EVAL.md) for results and methodology.

Each run saves:

- `manifest.json`: image and source hashes, model settings and input templates.
- `trials.json`: responses, model attempts, costs and scores for each image.
- `summary.json`: totals by model and difficulty group.

Costs include failed predictions when billing data is available. Missing cost
metadata is counted separately. API keys and upload URLs are not saved.

The `raw_*.json` and `summary.json` directly in this directory are from the
2026-09-16 experiment with Gemini 2.5 Flash, Gemini 2.0 Flash Lite and GPT-4.1 Mini.
They describe the old pipeline. Their `fabricated` fields flag unmatched GBIF
names, not confirmed fabrication.

`gbif_cache.json` is an ignored local cache. New trial records also include the
taxonomy matches used for scoring.
