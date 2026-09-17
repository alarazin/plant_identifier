# Final evaluation report

Run date: **2026-09-17**. The evaluation tested 40 images with each of three
models and with the normal app pipeline: **160 requests**, costing **$0.45371725**.
Billing metadata was available for every attempt.

## Results

The app completed all 40 requests. Its first candidate was correct on
**32/40 images (80.0%)**. A correct species appeared in the first three candidates
on **37/40 (92.5%)**. Median backend time was **4.93 seconds**, and the app's
40 requests cost **$0.031503**.

| Configuration | Completed | Effective top-1 | Effective top-3 | Median backend time | Recorded cost |
|---|---:|---:|---:|---:|---:|
| Gemini 2.5 Flash (primary) | 40/40 | 77.5% | 90.0% | 4.85s | $0.0297 |
| OpenAI ChatGPT-5 (fallback 1) | 40/40 | 80.0% | 85.0% | 6.13s | $0.2101 |
| OpenAI router → GPT-5.1 (fallback 2) | 39/40 | 77.5% | 82.5% | 7.52s | $0.1824 |
| App production chain | 40/40 | 80.0% | 92.5% | 4.93s | $0.0315 |

Top-1 and top-3 accuracy include failed requests. All normal app requests used
Gemini because the primary remained available. Fallback models were tested
separately. The difference between the Gemini and app runs reflects variation
between calls, not an improvement from fallback.

GPT-5.1 returned one malformed response; the other configurations completed
every request. There were no taxonomy-scoring errors.

## Findings

- Gemini remains a reasonable primary: it got 31/40 first guesses correct,
  compared with ChatGPT-5's 32/40, at about one-seventh the cost and lower median
  latency. A one-image difference is too small to establish an accuracy advantage.
- Ranked alternatives helped: the app's first three candidates covered five
  images missed by its first guess.
- Difficult plants remain a weakness. The app got 5/9 confusable plants and
  2/4 grasses correct on its first guess.
- The app got 5/6 toxic plants correct. That is not enough to guide decisions
  about eating or handling a plant.

### Malformed response

On `allium_ursinum.jpg`, GPT-5.1 returned a trailing comma after a candidate's
`diagnostic_features` array. The parser rejected the JSON with HTTP 502.
The failed request and its **$0.00529725** charge remain in the results.
It was not retried or replaced with another model's answer.

Including this failure gives GPT-5.1 **31/40 (77.5%)** top-1 accuracy. Excluding
it would report **31/39 (79.5%)**.

## Results by difficulty

| Tier | Images | Primary top-1 | Fallback 1 top-1 | Fallback 2 top-1 | App chain top-1 |
|---|---:|---:|---:|---:|---:|
| confusable | 9 | 55.6% | 66.7% | 55.6% | 55.6% |
| easy | 16 | 93.8% | 100.0% | 87.5% | 93.8% |
| grass | 4 | 50.0% | 50.0% | 75.0% | 50.0% |
| toxic | 6 | 66.7% | 83.3% | 83.3% | 83.3% |
| tree | 5 | 100.0% | 60.0% | 80.0% | 100.0% |

Each group includes all its attempted images. These groups are small, so the
percentages describe this dataset rather than general model accuracy.

## Method

The runner calls `identify_image`, the same function used by `POST /identify`.
It uses the app's image resizing, upload, prompts, validation, polling retries
and 50-second request budget. Individual-model runs disable fallback. The app
run uses the normal fallback rules.

The configured order was `gemini-2-5-flash`, `openai-chatgpt-5`, then
`openai-chat-completion` routing to `gpt-5.1`. All wrapper versions were `0.0.1`.
The runner reads the configured `CHAIN` and model settings from `backend/.env`.

Fallback requires an explicit model-unavailable or model-limit error. Uncertain
answers, non-plants, malformed responses, network failures and account limits
do not trigger another model. Offline tests check these error paths; the live
run did not force outages.

Latency includes backend preprocessing, upload and prediction, including failed
requests. It excludes phone processing, phone-to-backend transport and taxonomy
lookups. Old results measured prediction time only, so their latency is not
directly comparable.

## Dataset and scoring

The dataset contains 40 Wikimedia Commons photos with contributor-supplied
species labels. [labels.csv](labels.csv) records labels, authors, licences and
sources. Smaller runs cycle through the difficulty groups.

[GBIF](https://techdocs.gbif.org/en/openapi/v1/species) resolves predicted and
labelled names to species keys, allowing synonyms to match. A genus-only match
does not count as a correct species. An unmatched name is flagged for review;
it is not proof that the model invented a species.

Lookup failures are recorded separately. Accuracy is left undefined until
pending lookups are scored. Resuming can retry scoring without repeating saved
model calls. Taxonomy matches are saved with each result.

### Limits

This is a small sample of public photos with unverified labels. Some images may
have appeared in model training data. The dataset does not test ordinary phone
photos, non-plant detection, difficult lighting, care advice or confidence
calibration. No specialist plant identifier was tested on the same images.

## Saved results

- [Manifest, source hashes and model inputs](results/2026-09-17-final/manifest.json)
- [Per-image responses, costs and scores](results/2026-09-17-final/trials.json)
- [Summary](results/2026-09-17-final/summary.json)

Historical files in `eval/results/` describe the old models and pipeline. Their
`fabricated` fields mean unmatched taxonomy names, not confirmed fabrication.
Source hashes record the files used for each run; later comment edits also
change those hashes. Keep the saved manifest as the original run record.

## Run again

Install the backend dependencies and set the key in `backend/.env` first.

```bash
# Paid: all models and the app pipeline, 40 images each.
backend/.venv/bin/python eval/run_eval.py

# Paid: five images per configuration.
backend/.venv/bin/python eval/run_eval.py --limit 5

# Paid: normal app requests only.
backend/.venv/bin/python eval/run_eval.py --models production-chain

# Resume with the original --limit and --models options.
backend/.venv/bin/python eval/run_eval.py --output-dir eval/results/<run-directory>
```

Each request is saved before taxonomy scoring. Resume skips saved model calls.
Changed source, model settings or images require a new output directory.

The default $3 spending guard counts reported charges, reserves $0.10 for each
attempt without billing data, and reserves room for the next request. It is a
local estimate, not a provider billing cap. Use `--budget-usd`, `--reserve-usd`
or `--max-new-trials` to limit a run. See [SETUP.md](../SETUP.md) for offline tests.
