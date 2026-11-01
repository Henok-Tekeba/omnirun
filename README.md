<div align="center">

# OmniRun

**The preflight layer for local AI models.**

Paste a Hugging Face model. OmniRun estimates memory fit, runtime support, and decode speed before you download the weights.

[![Live site](https://img.shields.io/badge/live-static%20preview-111111?style=flat-square)](https://omnirun.enoch.et/)
[![Recorded sample](https://img.shields.io/badge/demo-recorded%20sample-111111?style=flat-square)](https://omnirun.enoch.et/?sample=1)
[![Source](https://img.shields.io/badge/source-GitHub-181717?style=flat-square)](https://github.com/Henok-Tekeba/omnirun)
[![License](https://img.shields.io/badge/license-MIT-2ea44f?style=flat-square)](LICENSE)

**Live:** [omnirun.enoch.et](https://omnirun.enoch.et/) · **Sample:** [recorded report](https://omnirun.enoch.et/?sample=1) · **Local live checks:** [quick start](#local-setup)

</div>

<p align="center">
  <a href="https://omnirun.enoch.et/">
    <img src="docs/screenshots/landing.png" alt="OmniRun landing page with the tagline The preflight layer for local AI models and a console preview" width="100%" />
  </a>
</p>

<p align="center"><sub>Static preview · no account required</sub></p>

> The public Pages build is a static preview. Live preflights and model discovery require the FastAPI service. Run it locally with `npm run dev`, or connect a hosted API using the [deployment guide](docs/deployment.md).

## Why OmniRun

A model card tells you the parameter count and license. It usually does not tell you whether the weights fit your machine, which runtime can load the artifact, or how much headroom remains at your context and batch size.

Downloading multi-gigabyte weights to find out is slow and unnecessary. OmniRun reads metadata and safetensors/GGUF headers over HTTP range requests, then returns a versioned report with explicit assumptions. It is a preflight, not a benchmark: **FITS**, **SUPPORTED**, and **VERIFIED** stay separate, and `GO` never means verified.

## A day with OmniRun

1. **Choose hardware.** Pick a curated GPU or chip, run the local helper, or use CPU-only mode.
2. **Paste a model.** Use a Hugging Face repo ID or model URL; adjust context and batch if needed.
3. **Run the preflight.** OmniRun resolves the revision and inspects metadata and headers.
4. **Read the claims.** Memory, runtime, and recorded-run evidence are reported separately.
5. **Choose the next action.** Inspect artifacts, use what-if planning, share the report, or open the finder.

## Features

- **Three independent claims.** FITS, SUPPORTED, and VERIFIED are never collapsed into one “works” answer.
- **No weight downloads.** Metadata, config, safetensors headers, and GGUF headers only. No tensor payloads or pickle parsing.
- **Hardware-first finder.** Candidates are ranked by fit, runtime support, artifact availability, and size. Model quality is not scored.
- **Real artifact shelf.** Actual repository files with format, quantization, size, runtime path, and fit status.
- **What-if planning.** Explore context, batch, free memory, and quantization alternatives, including maximum fitting context and batch.
- **Shareable reports.** The URL carries model, hardware, context, and batch. It never carries your Hugging Face token.

## Design principles

- **Claims stay separate.** A model can fit but lack a runtime path; it can be supported but unverified.
- **Unknown is first-class.** Missing configuration, unsupported architectures, and insufficient hardware data produce `UNKNOWN`, not a guess.
- **Exact math is not padded.** When weight bytes and the KV formula are exact, the memory range is exact.
- **Single device, stated plainly.** v1 does not model multi-GPU, offload, or distributed serving.

## Product screens

All screenshots use public demo data and a **1440 × 900** viewport.

| Dashboard / sample report | Preflight |
| --- | --- |
| <img src="docs/screenshots/dashboard.png" alt="OmniRun results dashboard showing a GO verdict, separate FITS, SUPPORTED, and VERIFIED claims, and a recorded sample report for SmolLM2-135M on an Apple M2 Pro" width="100%" /> | <img src="docs/screenshots/preflight.png" alt="OmniRun preflight form with a SmolLM2 model, an Apple M2 Pro hardware profile, 32 GB RAM, and the searchable hardware dropdown" width="100%" /> |
| **Hardware-first finder** | **Privacy and legal surface** |
| <img src="docs/screenshots/finder.png" alt="OmniRun hardware-first model finder showing fit-ranked public SmolLM2 candidates for an Apple M2 Pro" width="100%" /> | <img src="docs/screenshots/privacy.png" alt="OmniRun privacy policy explaining metadata-only processing, local storage, and no accounts" width="100%" /> |

There are no settings, account, or onboarding screens in v1. Hardware preferences live in the Preflight form and are remembered locally.

## Auth model

OmniRun is **anonymous by design**. There is no sign-up, login, session store, password database, or user profile.

```text
Browser (no account)
   │ optional HF token in request body
   ▼
FastAPI (stateless)
   │ request-scoped token
   ▼
Hugging Face (metadata + range requests)
```

- **Accounts and sessions:** none. No auth cookies, account recovery, or password handling.
- **Local browser state:** hardware preference and cookie-notice choice only.
- **Token handling:** optional Hugging Face tokens are request-scoped, never logged, never stored in results, and never included in share URLs.
- **Data isolation:** no user records exist; result cache keys include a one-way token-scope hash.

## Architecture

```text
Browser (React 19 · Vite · TypeScript)
   │ /api in dev · VITE_API_BASE_URL in production
   ▼
FastAPI (api/ + core/ + data/)
   │ validation · memory · KV math · speed · support · artifacts
   ▼
Hugging Face (metadata + HTTP range requests)
```

| Layer | Local | Production |
| --- | --- | --- |
| Frontend | Vite at `localhost:5173` | GitHub Pages at `omnirun.enoch.et` |
| API | Uvicorn at `127.0.0.1:8000` | Vercel, Render, or any Python host |
| Persistence | `~/.cache/omnirun` | Ephemeral cache, e.g. `/tmp/omnirun-cache` |
| Database / auth | None / none | None / none |

API: `POST /check` · `POST /find` · `GET /devices` · `GET /schema` · `GET /health` · `GET /docs`. The contract is `schema_version: "1.0"`; JSON memory is bytes and bandwidth is decimal GB/s.

## Stack

| Layer | Technology | Notes |
| --- | --- | --- |
| Frontend | React 19.3, TypeScript 5.9, Vite 8.3, Tailwind 4.3 | Static SPA |
| API | Python 3.11–3.13, FastAPI 0.115+, Pydantic 2, Uvicorn | OpenAPI at `/docs` |
| Inspection | `huggingface-hub`, `httpx`, safetensors/GGUF readers | Metadata and range requests only |
| Modeling | `core/` Python modules | Memory, KV, speed, support, verdict, artifacts |
| Data / persistence | YAML + JSON, filesystem cache | No database, no user records |
| Testing / deploy | pytest, Ruff, Playwright; GitHub Pages, Vercel, Render, Docker | 152 backend tests, 5 browser tests |

## Local setup

Requirements: **Python 3.11–3.13**, **uv**, **Node.js 20+**, and **npm**.

```bash
git clone https://github.com/Henok-Tekeba/omnirun.git
cd omnirun
uv sync
npm run setup
npm run dev
```

Open `http://localhost:5173`; API is at `http://127.0.0.1:8000` and docs at `/docs`. `Ctrl+C` stops both. Public model checks need no account or API key.

```bash
# Production frontend build
npm run build
```

## Environment variables

Local development works with defaults. These are optional overrides.

```dotenv
# web/.env.local
VITE_API_BASE_URL=
VITE_BASE_PATH=/

# .env (API) — never commit
OMNIRUN_CORS_ORIGINS=
OMNIRUN_CACHE_DIR=
OMNIRUN_TRUST_PROXY_HEADERS=false
```

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | Production | empty | API origin without `/api`; empty means static preview |
| `VITE_BASE_PATH` | No | `/` | `/` for custom domain, `/repo/` for project Pages |
| `OMNIRUN_CORS_ORIGINS` | Production | empty | Exact comma-separated frontend origins |
| `OMNIRUN_CACHE_DIR` | No | `~/.cache/omnirun` | Use `/tmp/omnirun-cache` on serverless |
| `OMNIRUN_TRUST_PROXY_HEADERS` | No | `false` | Trust `X-Forwarded-For` only behind a trusted proxy |
| `OMNIRUN_RATE_LIMIT_PER_MINUTE` | No | `30` | Per-client-IP budget |

Full settings are in [docs/deployment.md](docs/deployment.md). Do not put tokens, API keys, or credentials in `.env`.

## Database setup

There is **no database**. No migrations, seeds, ORM, or `DATABASE_URL`.

Durable data is source-controlled: `data/devices.yaml`, `data/support_matrix.yaml`, and `data/verified_runs.json`. The only runtime state is a disposable cache:

```bash
rm -rf "${OMNIRUN_CACHE_DIR:-$HOME/.cache/omnirun}"
```

**Warning:** do not delete `data/`; it contains the curated device table and support matrix. Clearing the cache is safe and only forces fresh metadata requests.

## OAuth/provider setup

OmniRun does **not use OAuth**. There is no provider, redirect URI, scope, callback route, client ID, or client secret. The optional Hugging Face token is a per-request bearer token, not an OAuth flow. If authentication is added later, keep provider secrets server-side and out of `VITE_*` variables.

## Testing

```bash
uv run pytest          # 152 backend tests, recorded fixtures
uv run ruff check .    # lint
npm run build          # TypeScript + production build
npm run test:e2e       # 5 Playwright tests against local API + web
```

Backend tests cover validation, revision pinning, metadata inspection, safetensors/GGUF parsing, memory/KV math, speed, support, verdicts, artifacts, caching, rate limiting, CORS, and errors. Playwright covers preflight, ASR `UNKNOWN`, the finder, invalid input, cookie consent, mobile navigation, and legal pages.

Last verified: **152 backend tests passed**, **Ruff clean**, **frontend build passed**, **5 browser tests passed**.

## Deployment

The frontend is live as a static preview. The API configuration is included but not hosted.

### GitHub Pages

The workflow builds `web/` with `VITE_BASE_PATH=/` and the optional repository variable `VITE_API_BASE_URL`. If the variable is unset, the build stays in static-preview mode.

### Vercel

```bash
npx vercel login
npx vercel --prod
```

Set `OMNIRUN_CORS_ORIGINS=https://omnirun.enoch.et,https://henok-tekeba.github.io`, `OMNIRUN_CACHE_DIR=/tmp/omnirun-cache`, and `OMNIRUN_TRUST_PROXY_HEADERS=true`. Vercel loads the ASGI app from `app.py`. Hobby is for personal, non-commercial use; check current plan terms.

### Render / Docker

[`render.yaml`](render.yaml) defines a Docker service named `omnirun-api` with a `/health` check. Free services sleep; the keepalive workflow pings `/health` every 10 minutes when configured.

```bash
docker build -t omnirun-api .
```

### Connect the frontend

```bash
gh variable set VITE_API_BASE_URL \
  --repo Henok-Tekeba/omnirun \
  --body "https://<api-origin>"

gh workflow run deploy-pages.yml --repo Henok-Tekeba/omnirun
```

CORS origins must exactly match the frontend. Cloudflare Pages is not configured in this repository; if used, host the FastAPI service separately and build `web/` with `VITE_BASE_PATH=/`. See [docs/deployment.md](docs/deployment.md).

## Security notes

- **No accounts, passwords, sessions, or auth cookies.** There is no password hash or user profile to protect.
- **No service keys in the frontend.** Never expose a Hugging Face token or provider secret through `VITE_*`.
- **Tokens are request-scoped.** They are not logged, not stored in results, and excluded from share URLs; cache keys use a one-way token-scope hash.
- **Metadata only.** No tensor payloads and no unpickling.
- **Rate limiting is per process.** Multi-worker deployments need a shared limiter.
- **CORS is an allowlist.** Use exact origins in production, never a wildcard.
- **No analytics or tracking cookies.** Local storage is used only for hardware preference and cookie choice.

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/Henok-Tekeba/omnirun/security/advisories/new). See [SECURITY.md](SECURITY.md).

## Project structure

```text
.
├── api/        FastAPI app, schemas, rate limiting, service assembly
├── core/       Inspection, memory/speed math, support, artifacts, verdict
├── data/       Devices, support matrix, verified-run registry
├── helper/     Local hardware measurement helper
├── web/        React + Vite + TypeScript frontend
├── tests/      Offline pytest suite and Hugging Face fixtures
├── docs/       Deployment, methodology, screenshots
├── scripts/    Dev runner, type generation, fixture recorder
├── app.py / Dockerfile / render.yaml / vercel.json
├── LICENSE
└── README.md
```

## Roadmap and status

| Area | Status |
| --- | --- |
| Public frontend | Live static preview |
| Hosted API | Configuration ready; not deployed |
| Live preflights | Available locally with `npm run dev` |
| Accounts / database | Not in v1 |
| Verified runs | Registry empty by design |
| Backend / browser tests | 152 / 5 passing |
| Device scope | Single device only |

**Next:** host the API and set `VITE_API_BASE_URL`; add verified-run records; add saved-report comparison; add a CLI and GitHub Action; add runtime recipes; add a Hugging Face browser extension.

**Out of scope for v1:** multi-GPU, offload, distributed serving, prefill/TTFT estimates, quality rankings, weight hosting, and accounts.

## Repository, source, and license

- **Source:** [github.com/Henok-Tekeba/omnirun](https://github.com/Henok-Tekeba/omnirun)
- **Issues:** [github.com/Henok-Tekeba/omnirun/issues](https://github.com/Henok-Tekeba/omnirun/issues)
- **Security:** [SECURITY.md](SECURITY.md)
- **Methodology:** [docs/methodology.md](docs/methodology.md)
- **Deployment:** [docs/deployment.md](docs/deployment.md)

OmniRun is released under the [MIT License](LICENSE). Model metadata and artifacts belong to their repository owners. OmniRun does not redistribute model weights.

Estimates are decision support, not guarantees. Validate on the hardware and runtime you intend to use.
