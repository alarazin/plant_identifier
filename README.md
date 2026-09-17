# PlantKey

PlantKey identifies plants from photos and provides care advice. The app runs
on iOS and Android with Expo, with a Python backend for model requests.

## Features

- Take a photo or choose one from the library.
- Compare up to three candidates, with species, genus, family and visible features.
- See confidence as Confident, Fairly sure or Uncertain.
- Get care advice for the selected candidate.
- Retake photos when the image is unclear or the subject is not a plant.
- Reopen recent identifications from local history.

## Setup

Follow [SETUP.md](SETUP.md). You need Python, Node, Expo Go and an Eachlabs API
key in `backend/.env`. The phone and backend must be on the same network.

## Architecture

```text
Expo app → FastAPI backend → Eachlabs
   photo     resize/upload    prediction
   result ← validated JSON ← polling
```

The backend keeps the API key off the phone, uploads images and polls predictions.
It resizes images to at most 1024 pixels and validates model responses before
returning them. Identification and care use separate requests, so selecting
another candidate loads care advice for that plant.

The configured model order is:

1. `gemini-2-5-flash` — primary, with a JSON response schema.
2. `openai-chatgpt-5` — first fallback.
3. `openai-chat-completion`, routing to `gpt-5.1` — second fallback.

A fallback runs only when the provider reports model unavailability or a
model-specific limit. Non-plant answers, uncertainty, malformed output, network
errors and account limits do not trigger a different model.

Each backend request has a 50-second budget; the phone waits 60 seconds. Failed
status reads can retry once using the same prediction ID. Prediction submissions
are not retried because the first request may already have started a paid call.
An accepted prediction may finish upstream after the backend stops waiting.

## Evaluation

On 2026-09-17, all 40 labelled images were tested with each model and with the
normal app pipeline. Accuracy includes failed requests.

| Configuration | Completed | Top-1 accuracy | Top-3 accuracy | Median backend time | Total cost |
|---|---:|---:|---:|---:|---:|
| Gemini 2.5 Flash | 40/40 | 77.5% | 90.0% | 4.85s | $0.0297 |
| ChatGPT-5 | 40/40 | 80.0% | 85.0% | 6.13s | $0.2101 |
| GPT-5.1 router | 39/40 | 77.5% | 82.5% | 7.52s | $0.1824 |
| App pipeline | 40/40 | 80.0% | 92.5% | 4.93s | $0.0315 |

The 160 requests cost **$0.4537**. GPT-5.1 returned one malformed response, which
was rejected and counted as a failure. The app pipeline used Gemini throughout;
its difference from the separate Gemini run reflects variation between calls.
This small dataset does not establish that one model is more accurate overall.

[Full report](eval/EVAL.md) ·
[Raw results](eval/results/2026-09-17-final/trials.json) ·
[Summary](eval/results/2026-09-17-final/summary.json)

## Checks

These tests run without API calls:

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests -v
backend/.venv/bin/python -m unittest discover -s eval/tests -v
```

To rerun the paid evaluation:

```bash
backend/.venv/bin/python eval/run_eval.py
```

Use `--limit 5` for a smaller run. See the [report](eval/EVAL.md) for scoring,
budget settings and resume instructions.

## Limitations

- The backend runs locally and must be reachable from the phone.
- Expo Go is used for development; no store build is included.
- The evaluation uses 40 Commons images, not a representative set of phone photos.
- Care accuracy, confidence calibration and non-plant detection need separate evaluation.
- No specialist plant identifier was tested on the same dataset.

## Project layout

```text
mobile/             Expo app, screens and components
backend/app/        API, provider client, prompts and validation
backend/scripts/    Model discovery and comparison tools
backend/tests/      Request and fallback tests
eval/run_eval.py    Evaluation runner
eval/EVAL.md        Final results and methodology
eval/labels.csv     Image labels and attribution
eval/images/        Evaluation photos
eval/results/       Saved predictions and scores
scripts/            Local setup helpers
SETUP.md            Installation and troubleshooting
```

## Attribution and safety

Photo authors, licences and sources are listed in [eval/labels.csv](eval/labels.csv).
Scoring uses the [GBIF](https://www.gbif.org) taxonomy service to match species names.

Identifications can be wrong, including for toxic plants. Do not eat, brew or
apply a plant based on the app's result.
