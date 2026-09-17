# Setup

These steps run the backend on a Mac and the app on an iPhone through Expo Go.
Xcode is needed only for a native iOS build.

## Requirements

- Node 22.13 or later, as required by [Expo SDK 57](https://docs.expo.dev/versions/v57.0.0/).
- Python 3.11 or later.
- Expo Go installed on the iPhone.
- The Mac and phone connected to the same Wi-Fi network.
- An Eachlabs API key.

If Node is missing, install it with Homebrew:

```bash
brew install node
```

Copy or clone the project. Environment files are ignored by Git; create them
from the examples below.

## 1. Backend

Run from the project root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
open -e backend/.env
```

Set your key in `backend/.env`:

```env
EACHLABS_API_KEY=your_key_here
EACHLABS_MODEL=gemini-2-5-flash
EACHLABS_MODEL_VERSION=0.0.1
```

To check the key and model with a real, paid request:

```bash
backend/.venv/bin/python backend/scripts/spike.py eval/images/monstera_deliciosa.jpg
```

The script should print a JSON identification. To inspect available models:

```bash
backend/.venv/bin/python backend/scripts/discover_models.py
```

## 2. App

From the project root:

```bash
cd mobile
npm install
cp -n .env.example .env
cd ..
```

The copy preserves an existing `mobile/.env`. Check that it contains:

```env
EXPO_PUBLIC_USE_RN_FETCH=1
```

This enables the networking implementation used by native photo uploads. Without
it, uploads can fail with `Unsupported FormDataPart implementation`. Keep the
Eachlabs key in `backend/.env`, not the mobile environment. Restart Expo after
changing environment settings.

## 3. Start both servers

In one terminal, from the project root:

```bash
backend/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

In another terminal:

```bash
cd mobile
npx expo start
```

The backend must listen on `0.0.0.0` so the phone can reach it. Scan the QR code
with the iPhone Camera app to open Expo Go. The app uses the Metro host address
to find the backend. For a different backend, set `EXPO_PUBLIC_API_BASE` in
`mobile/.env`.

In the Expo terminal, `r` reloads the app and `Ctrl+C` stops the server.

## 4. Check connectivity

Run this on the Mac:

```bash
curl -s "http://$(ipconfig getifaddr en0):8000/healthz"
```

Expect `{"ok":true,"model":"gemini-2-5-flash","key_loaded":true}` with the default
model. This checks the LAN address used by the phone.

If the Mac firewall blocks Node or Python, allow incoming connections in
System Settings → Network → Firewall → Options, or run:

```bash
bash scripts/allow-firewall.sh
```

The script requests administrator access and allows the Node and Python
executables. It leaves the firewall enabled.

In the app, take a photo or choose one from `eval/images/`. Check a familiar
plant, a difficult grass image, a non-plant object and a blurry photo. Results
can vary; compare evaluation images against `eval/labels.csv`.

## Browser and native builds

For browser development:

```bash
cd mobile
npx expo start --web
```

The browser uses the webcam or photo library. Use a narrow window to check the
phone layout.

For a native iOS build, install Xcode and run:

```bash
cd mobile
npx expo run:ios
```

A physical iPhone build requires code signing. The iOS Simulator has no camera;
use its photo library to test image input.

## Troubleshooting

| Problem | Check |
|---|---|
| Expo Go reports a lost connection | Both devices are on the same network; Node is allowed through the firewall. |
| App opens but identification fails to connect | Backend is running on port 8000 with `--host 0.0.0.0`; Python is allowed through the firewall. |
| Service configuration or credit error (503) | The backend key is valid and the Eachlabs account has credit. |
| Processing or unreadable-response error (502) | Retry the photo and check backend logs. Malformed responses do not trigger fallback. |
| Request timeout (504) | Retry later. The backend budget is 50 seconds; the phone waits 60 seconds. |
| Service busy (503) | Wait for existing predictions to finish. Account-wide limits do not trigger fallback. |
| Environment changes have no effect | Restart the affected backend or Expo process. |
| Port 8081 is in use | Stop the other Metro process or use `npx expo start --port 8082`. |

The client allows two concurrent predictions. Other processes or predictions
still running after a timeout can also consume provider capacity.

## Evaluation

The evaluation imports the backend directly; a running backend server is not
required. It uses the model settings in `backend/.env`.

```bash
# Paid: 40 images with each configured model and the normal app pipeline.
backend/.venv/bin/python eval/run_eval.py

# Paid: five images per configuration, spread across difficulty groups.
backend/.venv/bin/python eval/run_eval.py --limit 5

# Resume saved work with the original --limit and --models options.
backend/.venv/bin/python eval/run_eval.py --output-dir eval/results/<run-directory>

# Offline checks, without API calls.
backend/.venv/bin/python -m unittest discover -s backend/tests -v
backend/.venv/bin/python -m unittest discover -s eval/tests -v
```

Use `--models production-chain` to test normal app requests only. Results are
saved after each request. A changed dataset, configuration or source requires
a new output directory; do not run two processes against the same directory.

The default $3 spending guard uses reported charges and a $0.10 reserve for each
attempt without billing metadata. It also reserves room for the next request.
This is a local estimate, not a provider billing cap. Adjust `--budget-usd`,
`--reserve-usd` or `--max-new-trials` to limit a run.

See [eval/EVAL.md](eval/EVAL.md) for the final results and scoring method.
