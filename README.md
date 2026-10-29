# OmniRun

Preflight a Hugging Face model against your hardware **without downloading weights**.

Paste a model URL or repo id. OmniRun reads only repository metadata, `config.json`,
safetensors headers, and GGUF headers over HTTP range requests. It returns a
versioned JSON report with memory math, decode-speed ranges, and three separate
claims: **FITS**, **SUPPORTED**, and **VERIFIED**.

> Status: under construction. The backend, core library, and hardware helper are
> being built first. The frontend is a later deliverable.

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
```

Run the API:

```bash
uv run uvicorn api.main:app --reload
```

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

The response always reports FITS, SUPPORTED, and VERIFIED as separate claims.
GO means FITS + a directly usable SUPPORTED runtime; it does not mean VERIFIED.
VERIFIED is empty in v1.

## Honesty rules

- No weight downloads, ever. Only metadata/header byte ranges.
- Every number traces to an input or a named assumption in the response.
- Exact math is not padded with fake ranges.
- `VERIFIED` is empty in v1. A GO never implies a recorded real run.
- Unknown is a valid answer.

See [ASSUMPTIONS.md](ASSUMPTIONS.md) for the decisions and open questions.
