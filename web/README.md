# OmniRun web

Vite + React + TypeScript + Tailwind frontend for the OmniRun API.

The root page is a fixed light marketing composition (hero + pastel console
preview). “Run a preflight” opens the app dashboard: a light sidebar shell with
white cards, the same visual language as the preview. Method/claims
explanations are dialogs; the landing page has a site footer, mobile menu, and
links to the legal pages.

The result view includes an **artifact shelf** backed by `GET /check` →
`artifacts`: real GGUF/safetensors/ONNX/CTranslate2 files from the HF tree,
with size, quantization, runtime hint, fit status, and copyable download
commands. Hypothetical quantization alternatives are only shown when the repo
has no real artifacts.

The result also includes a **What-if** panel backed by `sweep`: max fitting
context and batch, a context-vs-memory frontier, the best smaller weights that
fit, and free-memory/smaller-context/batch-1 scenarios.

The dashboard’s **Find models** view calls `POST /find` with the current
hardware. It searches a bounded HF candidate pool, inspects each candidate, and
ranks by fit, support, artifact availability, and size. It does not rank model
quality.

## Static GitHub Pages build

The GitHub Pages workflow builds the frontend only. GitHub Pages cannot run the
Python API, so a production build without `VITE_API_BASE_URL` renders a
**Static preview** banner and a recorded sample result. Live checks require the
local API or a separately hosted API.

- `VITE_BASE_PATH` controls the Pages subpath (for example `/omnirun/`).
- `VITE_API_BASE_URL` points the frontend at a hosted API root. When omitted,
  API calls use the local `/api` Vite proxy in development and the static
  preview mode in a production build.
- Legal pages live at `?page=privacy` and `?page=terms`.
- Cookie choice and hardware preference are stored in `localStorage`; the app
  sets no analytics or advertising cookies.

## Run everything from the repo root

```bash
npm run dev
```

This starts FastAPI on `http://127.0.0.1:8000` and Vite on
`http://localhost:5173`, then prints both URLs. The dev script installs
`web/node_modules` on the first run. `Ctrl+C` stops both processes.

If you only need the web app, `npm --prefix web run dev` works, but the API must
already be running for checks and the device list.

## Setup / tests

```bash
npm run setup
npm run test:e2e
```

The Playwright smoke test uses a real public model
(`HuggingFaceTB/SmolLM2-135M-Instruct`) and the manual Apple M2 Pro profile.
Playwright starts the API and Vite if they are not already running.

## API contract

- The frontend calls `/api/check` and `/api/devices`; Vite proxies `/api/*` to
  FastAPI on port 8000 and strips the prefix.
- TypeScript types are generated from `app.openapi()` with
  `openapi-typescript`:

  ```bash
  npm run gen:types
  ```

  `web/src/api/schema.gen.ts` is generated. Do not hand-edit it.
- `GET /devices` was added to the API for the manual hardware picker. It is a
  read-only view of `data/devices.yaml`, not a measurement.

## Frontend assumptions

1. **Loading stages are approximate.** `POST /check` is one request. The staged
   list maps to backend phases but is not server-reported progress. No fake
   percentage is shown.
2. **`recommendations` and `environment_hint` are empty/null today.** The
   "What you'd need" section shows a graceful empty state and never invents
   options.
3. **ASR/TTS return UNKNOWN.** The result view says OmniRun can inspect the
   model but cannot judge it yet. It is not treated as an error.
4. **VERIFIED is always unknown in v1.** The UI says "No recorded runs yet" and
   never implies GO means verified.
5. **Units:** the brief asked for GB labels, while `ASSUMPTIONS.md` item 18 asks
   for GiB. The UI labels memory as **GB** and defines 1 GB = 2³⁰ bytes (GiB)
   in the units note. The API returns raw bytes; `devices.yaml` capacities are
   binary GiB. Bandwidth remains decimal GB/s.
6. **Last hardware choice** is saved in `localStorage` inside try/catch. The
   helper code is included because it is the hardware choice; the model id and
   HF token are not saved.
7. **HF token:** kept in React state only, sent only with the request. It is
   never placed in the URL, localStorage, or the share link. The UI states that
   the API does not log request bodies.
8. **Share links** contain model, hardware mode/device/RAM or helper code,
   context, batch, and `run=1`. Opening one re-runs the preflight. Helper codes
   contain machine details, and the UI warns about that.
9. **Manual device list** comes from the API; there is no hard-coded duplicate.
   If `/devices` fails, helper and CPU/unknown modes remain usable.
10. **Client validation** mirrors the API limits: context 1–1,048,576, batch
    1–1024, RAM 1–4096 GB, model max 512 chars. The API remains the source of
    truth.

## Error handling

Human-readable panels cover: gated/private/unknown repos (`repo_auth_required`),
rejected tokens (`repo_access_denied`), repo not found, Hugging Face rate limits,
timeouts, invalid model/hardware input, API unreachable, and upstream failures.
The raw error code and request ID stay visible for debugging.

## Known limitations

- No multi-device view, history, saved results, or comparison.
- No server-side result persistence; a share link re-runs the API.
- The device table is curated, not measured. Manual profiles are MEDIUM
  confidence; CPU/unknown paths are LOW.
- The API currently returns no recommendations or environment hints, so that
  part of the result is usually an empty state.
- The UI's loading stages are cosmetic ordering, not progress events.
