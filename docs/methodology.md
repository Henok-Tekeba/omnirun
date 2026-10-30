# Methodology & limitations

**Version 1.0 · Last updated October 30, 2026**

OmniRun estimates memory fit and decode speed from model metadata. This document records the assumptions behind those estimates and the boundaries of v1. Every API response repeats the assumptions that affect its numbers.

## 1. Scope and claims

1. **Single-device scope.** v1 evaluates one accelerator or CPU. Multi-GPU, tensor/pipeline parallelism, CPU+GPU offload, and distributed serving are out of scope. A model that only fits across two devices is reported as not fitting one device.
2. **No tensor payloads.** OmniRun reads repository metadata, `config.json`, safetensors headers, and GGUF metadata over HTTP range requests. It never downloads a full weights file and never reads `.bin`/pickle payloads.
3. **Exact math is not padded.** When safetensors headers provide exact weight bytes and the KV formula has no unresolved inputs, the memory range has `min == likely == max`. Uncertainty is represented in confidence, assumptions, and components that genuinely vary.
4. **Quantization alternatives are estimates.** They describe hypothetical memory configurations, not claims that an artifact exists, is supported, or has a particular quality. They are weights-only estimates with a named bits-per-weight overhead; KV cache remains at checkpoint dtype.
5. **`GO` does not mean verified.** v1 ships with no recorded runs, so no result can be `VERIFIED`. A `GO` must name `FITS` and `SUPPORTED`; the verified claim remains "no recorded run".
6. **Runtime support is artifact-specific.** llama.cpp consumes GGUF, whisper.cpp consumes its own GGML format, and CTranslate2 requires conversion. The support matrix records the required artifact path and minimum version. A Hugging Face checkpoint is only directly supported where a runtime can consume that checkpoint format.
7. **Supported model classes are causal LLM, ASR, and TTS.** Other pipeline tags return `UNKNOWN` with an explicit unsupported reason rather than a guessed verdict.
8. **Context is KV-cache allocation context.** Decode speed is reported at that context. Prefill and time-to-first-token are not estimated in v1.
9. **Batch means concurrent sequences.** For decode, weights are read once per forward step and shared across the batch; KV is read per sequence. Aggregate and per-sequence tokens/s are reported. This assumes continuous batching; real runtimes will be lower at small batch.
10. **Requested context above the model maximum is clamped.** The clamped value is echoed and a warning is returned. It is not silently accepted as an impossible configuration.

## 2. Verdict mapping

The top-level verdict is derived from the three claims:

- **FITS** is strict: `yes` only when the worst-case peak is within budget; `no` only when the best-case peak exceeds it; anything straddling is `unknown`.
- **GO**: FITS yes, SUPPORTED yes with a directly usable runtime, and at least 5% worst-case headroom.
- **OPTIMIZE**: FITS yes but tight headroom or conversion-only runtime, or the requested setup does not fit while a documented smaller configuration (quantization, batch 1, or context 4096) fits and is supported.
- **NO**: best-case memory cannot fit, or the support matrix says the architecture/runtime path is unsupported.
- **UNKNOWN**: inspection incomplete, architecture absent from the matrix, runtime support unconfirmed, memory range straddles the budget, or input data is insufficient.

The claims are always separate. `VERIFIED=unknown` prevents the word "verified" but does not block `GO`.

## 3. Hardware budgets

11. **The helper measures CPU/unified-memory bandwidth.** It does not measure discrete-GPU bandwidth without torch/CUDA. For NVIDIA GPUs it reads name and VRAM from `nvidia-smi` but takes bandwidth from the curated device table. Results state which values were measured and which were looked up.
12. **Helper codes are self-reported and unsigned.** They include a version, compression, CRC, strict size limits, and server-side range clamping. Their confidence means "measured on the user's machine by the helper", not cryptographic attestation.
13. **Apple Silicon usable memory is a named constant.** v1 uses 75% of total unified memory. The real wired limit varies by macOS version, RAM size, and running applications. The response labels this as an assumption.
14. **Discrete GPU fit is VRAM fit.** A small runtime reserve is applied. System RAM is reported but does not make a model fit when v1 has no offload.
15. **CPU-only/unknown uses conservative defaults.** The budget is 80% of RAM and bandwidth defaults to 25 GB/s unless a helper or manual profile provides a better value. Confidence is LOW. Without RAM, the result is `UNKNOWN`.
16. **Manual profiles are medium confidence.** The device table is curated, not measured. RAM is user-supplied. For Apple devices the server applies the 75% fraction; for discrete GPUs, VRAM comes from the table rather than system RAM.
17. **Units.** All JSON memory values are bytes. Bandwidth is decimal GB/s (10⁹ bytes/s). Display code may render GiB, but must label the unit.

## 4. Inspection and artifacts

18. **Revision pinning.** OmniRun resolves `main` to a commit SHA once, then uses that SHA for config, index, and header range requests. This keeps one report internally consistent and makes immutable cache entries safe.
19. **Safetensors are authoritative for weight bytes.** Tensor spans are summed across every shard and cross-checked against the index and file sizes. Tied embeddings are counted once. Header size, shard count, tensor count, and declared spans are capped and validated.
20. **KV cache formula.** Standard MHA/GQA uses `2 × layers × kv_heads × head_dim × context × batch × kv_bytes`. Sliding-window layers use `min(context, window)`; mixed patterns are handled per layer when configuration exposes them, otherwise full context is used as an upper bound and flagged. MLA uses the compressed latent formula when fields are present and is flagged LOW confidence.
21. **Runtime overhead is a named range.** Runtime context, allocator, and compute workspace constants live in `core/estimate.py` and are repeated in response assumptions.
22. **Decode speed** is `effective_bandwidth × efficiency / bytes_read_per_token`, where `bytes_read_per_token = active_weight_bytes / batch + kv_bytes_per_seq`. Dense efficiency is 0.55–0.85 (likely 0.70); MoE is 0.25–0.60 (likely 0.40). These are documented engineering ranges, not measured constants.
23. **ASR/TTS speed is a coarse class.** v1 reports `real-time likely`, `uncertain`, or `slow` with LOW confidence. No real-time factor is invented.
24. **Pickle-only repositories.** File sizes from the Hugging Face API are an upper bound. If the upper bound fits, FITS can be yes with LOW confidence; if it does not fit, FITS is `UNKNOWN`, never a confident no. Tensor shapes are not inspected without unpickling, and OmniRun never unpickles.
25. **GGUF.** Metadata and tensor-info headers are read with progressive ranges and validated. Split shards are recognized by filename and summed. Actual artifact bytes are used for weights; tensor info supplies architecture and parameter counts. Unknown GGML quantization types lower confidence.
26. **Gated/private repositories are not bypassed.** A missing token produces a clear auth error and a link to the repository. A supplied token is used only for that request chain, is never echoed, logged, or stored in results, and cache keys use a one-way token scope hash. Anonymous and token responses do not share cache entries.
27. **Per-file commit dates are best-effort.** v1 uses the Hugging Face tree endpoint's `lastCommit` for config/weight files, with repository `lastModified` as a labelled fallback.
28. **Environment hints are text only.** `uv pip compile --exclude-newer <date>` is printed; nothing is executed. Old model commits do not guarantee compatible wheels for Python 3.11+.

## 5. Reliability and security

29. **Hugging Face cache.** Disk JSON cache under `~/.cache/omnirun` (override with `OMNIRUN_CACHE_DIR`). Mutable refs use short TTLs; SHA-pinned metadata uses long TTLs. Stale entries are used only for explicitly marked stale-on-error fallbacks. Corrupt entries are discarded.
30. **Rate limiting.** The API uses an in-process per-IP token bucket and a bounded global concurrency semaphore. v1 is single-process; multi-worker deployments need a shared limiter.
31. **Timeouts and retries.** Hugging Face requests have connect/read timeouts and retry only timeouts, connection failures, 429, and 5xx, honoring `Retry-After`. 401/403/404 are never retried. Whole `/check` requests have a deadline.
32. **No token leakage in logs.** The API does not log request bodies. Access logs are the deployment's responsibility. Cache entries and responses never include the token.
33. **Schema versioning.** Responses use `schema_version: "1.0"`. Additive fields may appear in 1.x; breaking changes require a new major version. Errors use a versioned envelope too. OpenAPI is generated from Pydantic.
34. **Tests run offline.** Recorded Hugging Face fixtures live under `tests/fixtures`. Live network is only used by explicit fixture-recording scripts, never by CI tests.

## 6. Known limitations

- Single device only; no offload or distributed serving.
- No prefill, time-to-first-token, or benchmark-grade throughput measurement.
- No quality ranking for model discovery.
- No accounts, saved results, or server-side persistence.
- The GitHub Pages deployment is a static preview; live checks require the API.
- The curated device table is a lookup, not a measurement.
- Support-matrix coverage is intentionally conservative; unsupported paths return `UNKNOWN`.
