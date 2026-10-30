# OmniRun

Preflight a Hugging Face model against your hardware **without downloading weights**.

Paste a model URL or repo id. OmniRun reads only repository metadata, `config.json`,
safetensors headers, and GGUF headers over HTTP range requests. It returns a
versioned JSON report with memory math, decode-speed ranges, and three separate
claims: **FITS**, **SUPPORTED**, and **VERIFIED**.

> Status: v1 backend, core library, hardware helper, and web frontend.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/), plus Node.js 20+.

```bash
npm run dev
```

That one command starts both servers and prints:

```text
Web   http://localhost:5173
API   http://127.0.0.1:8000
Docs  http://127.0.0.1:8000/docs
```

The dev runner installs `web/node_modules` on the first run. `Ctrl+C` stops both.

For a production-style web build:

```bash
npm run build
```

## Development

Backend:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn api.main:app --reload
```

Web:

```bash
npm --prefix web install
npm --prefix web run dev
```

The Vite dev server proxies `/api` to FastAPI. The frontend calls `/api/check`
and `/api/devices`; the API remains the source of truth for the contract.

Generate TypeScript types from the live OpenAPI schema:

```bash
npm run gen:types
```

The generated file is `web/src/api/schema.gen.ts`.

Playwright smoke test (real public model + manual hardware picker):

```bash
npm run setup
npm run test:e2e
```

See [web/README.md](web/README.md) for frontend assumptions and known
limitations.

## API contract

The contract is served at `GET /schema` and in the OpenAPI docs at `/docs`.
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

`GET /devices` returns the curated manual profiles from `data/devices.yaml`
for the web picker. It is a lookup table, not a measurement.

The response always reports FITS, SUPPORTED, and VERIFIED as separate claims.
GO means FITS + a directly usable SUPPORTED runtime; it does not mean VERIFIED.
VERIFIED is empty in v1. `artifacts` lists actual files found in the repo
(GGUF/safetensors/ONNX/etc.) with sizes and fit estimates; the UI uses it for
the real artifact shelf instead of inventing quantization alternatives.

## Honesty rules

- No weight downloads, ever. Only metadata/header byte ranges.
- Every number traces to an input or a named assumption in the response.
- Exact math is not padded with fake ranges.
- `VERIFIED` is empty in v1. A GO never implies a recorded real run.
- Unknown is a valid answer.
- The web UI labels memory as GB and defines 1 GB = 2³⁰ bytes (GiB) in its
  units note; the API itself returns bytes.

See [ASSUMPTIONS.md](ASSUMPTIONS.md) for the decisions and open questions.
