# Recorded Hugging Face fixtures

These are public model metadata snapshots recorded on 2026-10-29 with
`scripts/record_fixtures.py`. They contain:

- the `/api/models/{repo}?blobs=true` record (file list, sizes, tags, SHA),
- `config.json` and safetensors index JSON,
- raw safetensors JSON headers (never tensor payloads),
- the 401 body for the gated Llama fixture.

No tokens, credentials, or weights are stored. Each repo's commit SHA is pinned
in `manifest.json`; tests never use the live network.

Sources:

| fixture | repo | commit |
| --- | --- | --- |
| `smollm2_135m` | `HuggingFaceTB/SmolLM2-135M-Instruct` | `12fd25f77366fa6b3b4b768ec3050bf629380bac` |
| `mistral_7b` | `mistralai/Mistral-7B-v0.1` | `27d67f1b5f57dc0953326b2601d68371d40ea8da` |
| `opt_350m` | `facebook/opt-350m` | `08ab08cc4b72...` (see manifest) |
| `llama_3_2_1b_gated` | `meta-llama/Llama-3.2-1B` | `4e20de362430cd3b72f300e6b0f18e50e7166e08` |
| `chatglm3` | `THUDM/chatglm3-6b` | `e9e0406d062c...` (see manifest) |
| `whisper_tiny` | `openai/whisper-tiny` | `169d4a4341b3...` (see manifest) |

These repos retain their own licenses; the fixtures are metadata snapshots used
solely to test OmniRun's parser. Delete or re-record them if a repo owner asks.
