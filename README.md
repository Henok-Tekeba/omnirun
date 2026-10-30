# OmniRun

**Preflight local AI models before you download them.**

OmniRun is the preflight layer for local inference. Given a Hugging Face model and a hardware profile, it returns a versioned report with memory fit, runtime support, decode-speed range, real artifacts, and capacity scenarios — without downloading tensor weights.

[Live preview](https://omnirun.enoch.et/) · [Sample report](https://omnirun.enoch.et/?sample=1) · [Methodology](docs/methodology.md) · [Security](SECURITY.md)

> The GitHub Pages deployment is a static product preview. Live preflights and model discovery require the API; see [Deployment](#deployment).

## What it answers

| Question | Output |
| --- | --- |
| Will this model fit? | `FITS` with a worst-case memory range and a confidence level |
| Can I run it? | `SUPPORTED` with the artifact format, runtime, and minimum version |
| Has anyone verified it? | `VERIFIED`, kept separate from fit and support |
| How fast will it decode? | A documented decode-speed range, not a benchmark |
| What will I actually download? | Real GGUF, safetensors, ONNX, and CTranslate2 artifacts from the repository |
| What changes if I reduce context, batch, or memory pressure? | A what-if frontier and fitting configuration |

OmniRun does not treat "fits" as "supported", and does not treat "supported" as "verified".

## Product surface

- **Preflight** — inspect a model against a manual device profile, a measured helper code, or a CPU-only/unknown profile.
- **Artifact shelf** — list the real files in the repository, their size, quantization, runtime path, and fit status.
- **Capacity planning** — calculate the maximum fitting context and batch, the memory frontier, the best fitting quantization, and free-memory or smaller-context scenarios.
- **Hardware-first model finder** — inspect a bounded candidate pool and rank by fit, runtime support, artifact availability, and size. Model quality is not scored.
- **API-first contract** — every result is a versioned JSON report with explicit claims, assumptions, and request metadata.

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node.js 20+.

```bash
npm run dev
```

The development runner starts both services:

```text
Web   http://localhost:5173
API   http://127.0.0.1:8000
Docs  http://127.0.0.1:8000/docs
```

`Ctrl+C` stops both. The first run installs `web/node_modules`.

Production build:

```bash
npm run build
```

## Architecture

```text
web/          React + Vite + TypeScript frontend
api/          FastAPI service, request validation, response assembly
app.py        Vercel FastAPI entrypoint
vercel.json   Vercel function and bundle configuration
Dockerfile    Production API image
render.yaml   Render blueprint for the API
core/       model inspection, memory/speed estimation, support and artifact logic
helper/     local hardware measurement helper
data/       curated device profiles and support matrix
tests/      offline fixtures and API/core test suite
docs/       methodology and operating notes
```

The frontend calls the API through the local `/api` proxy. The API resolves a model revision, reads only metadata and header ranges from Hugging Face, and returns a report. It never fetches tensor payloads and never unpickles model files.

## API

The contract is served at `GET /schema` and in OpenAPI at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/check` | Full preflight report |
| `POST` | `/find` | Hardware-first candidate discovery |
| `GET` | `/devices` | Curated manual hardware profiles |
| `GET` | `/schema` | Versioned request/response schemas |
| `GET` | `/health` | Service health |

Example:

```bash
CODE=$(uv run --with numpy python helper/omnirun_helper.py --code-only)

curl -s http://127.0.0.1:8000/check \
  -H 'content-type: application/json' \
  -d "{
    \"model\": \"HuggingFaceTB/SmolLM2-135M-Instruct\",
    \"hardware\": {\"source\": \"helper\", \"code\": \"$CODE\"},
    \"context\": 4096,
    \"batch\": 1
  }" | python -m json.tool
```

`POST /check` reports `FITS`, `SUPPORTED`, and `VERIFIED` independently. A `GO` requires fit plus a directly usable runtime path; it never implies verification. `artifacts` contains real repository files, and `sweep` contains the capacity-planning analysis.

## Modeling principles

- **No tensor payload downloads.** Only repository metadata, configuration, safetensors headers, and GGUF metadata are read over HTTP range requests.
- **Numbers are traceable.** Every estimate maps to an input, a named constant, or an assumption repeated in the response.
- **Exact math stays exact.** Ranges are reserved for genuine uncertainty, not added for presentation.
- **Unknown is a first-class result.** Missing configuration, unsupported architectures, and insufficient hardware data produce `UNKNOWN`, not a guess.
- **Claims stay separate.** `FITS`, `SUPPORTED`, and `VERIFIED` are never collapsed into a single "works" claim.
- **Units are explicit.** API memory values are bytes; bandwidth is decimal GB/s; UI memory labels use 1 GB = 2³⁰ bytes (GiB).

The full set of assumptions and limitations is in [docs/methodology.md](docs/methodology.md).

## Deployment

The frontend is deployed to GitHub Pages by [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml). GitHub Pages hosts the static Vite build, not the FastAPI process.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Henok-Tekeba/omnirun)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Henok-Tekeba/omnirun)

The repository includes a serverless Vercel entrypoint, a production `Dockerfile`, a `render.yaml` blueprint, CORS configuration, and a full [deployment guide](docs/deployment.md).

- Static preview: [omnirun.enoch.et](https://omnirun.enoch.et/)
- Recorded sample report: [omnirun.enoch.et/?sample=1](https://omnirun.enoch.et/?sample=1)
- Live preflights: run `npm run dev` locally, or deploy the API with [docs/deployment.md](docs/deployment.md) and set the repository variable `VITE_API_BASE_URL` to the API root.

Environment overrides are documented in [`web/.env.example`](web/.env.example).

The custom domain is served from the root path, so the production build uses
`VITE_BASE_PATH=/`.

## Accessibility

The interface uses a 16px base with a rem-based scale. Supporting labels are
never smaller than 12px, UI copy is 14px, and legal body copy is 16px. Text and
background colors are chosen for WCAG AA contrast, focus states use
`:focus-visible`, headings are hierarchical, and the layout is tested down to
320px with no horizontal overflow.

## Testing

Backend:

```bash
uv run pytest
uv run ruff check .
```

Frontend build:

```bash
cd web
npx tsc --noEmit
npm run build
```

End-to-end:

```bash
npm run setup
npm run test:e2e
```

The Playwright suite covers the preflight happy path, ASR handling, the model finder, invalid input, cookie consent, mobile navigation, and legal pages.

## Security

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/Henok-Tekeba/omnirun/security/advisories/new). See [SECURITY.md](SECURITY.md) for scope and reporting guidance.

## Limitations

- Single-device estimates only. Multi-GPU, offload, and distributed serving are out of scope.
- No prefill or time-to-first-token estimate.
- No measured runtime benchmarks; speed is a documented range.
- No server-side result persistence or accounts.
- The public Pages build is a static preview without a live API.
- Model search is fit-ranked, not a quality ranking.
