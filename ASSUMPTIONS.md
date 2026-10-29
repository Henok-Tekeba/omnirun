# OmniRun v1 — assumptions and spec notes

Written before implementation. These are product decisions, not hidden behavior:
every API result repeats the ones that affect its numbers.

## Scope and semantics

1. **v1 is single-device.** One accelerator or CPU. No multi-GPU, tensor/pipeline
   parallelism, CPU+GPU offload, or distributed serving. A model that only fits
   across two GPUs is reported as not fitting one device.
2. **"No weight downloads" means no tensor payloads.** OmniRun reads HTTP ranges
   covering only JSON/GGUF metadata and safetensors headers. It never fetches a
   full weights file. `.bin`/pickle files are never read at all, not even a
   header.
3. **Exact math is not padded into fake uncertainty.** If safetensors headers
   give exact weight bytes and the KV formula has no unresolved inputs, the
   memory range has `min == likely == max`. Uncertainty lives in confidence,
   assumptions, and the parts that genuinely have ranges (runtime overhead,
   speed efficiency, pickle upper bounds, unusual attention). "Always output a
   range" is satisfied structurally, but we do not invent spread.
4. **Quantization alternatives are hypothetical memory alternatives**, not
   claims that an artifact exists, is supported, or has a particular quality.
   They are weights-only estimates with a named bits-per-weight overhead. KV
   cache remains at checkpoint dtype. v1 does not quantize or convert anything.
5. **GO does not mean verified.** v1 ships `verified_runs.json` empty, so no
   result can be VERIFIED. A GO must name FITS and SUPPORTED explicitly; the
   verified claim is reported as "no recorded run" every time.
6. **Runtime support is not architecture support alone.** llama.cpp consumes
   GGUF, whisper.cpp consumes its own GGML format, and CTranslate2 requires
   conversion. The support matrix records the required artifact path and the
   minimum version we are willing to claim. An HF checkpoint is only
   "SUPPORTED" directly where a runtime can consume that checkpoint format.
7. **v1 model classes are causal LLM, ASR, and TTS.** Other pipeline tags
   (embeddings, image, fill-mask, etc.) return UNKNOWN with a clear unsupported
   reason rather than a guessed verdict. This may be widened later.
8. **Context is the KV-cache allocation context, not the prompt length.**
   Decode speed is reported at that context. Prefill and time-to-first-token are
   explicitly not estimated in v1.
9. **Batch means concurrent sequences, not gradient batch.** For decode,
   weights are read once per forward step and shared across the batch; KV is
   read per sequence. Aggregate tokens/s is reported, with per-sequence
   tokens/s also shown. This assumes perfect continuous batching; real runtimes
   will be lower at small batch.
10. **Requested context above the model maximum is clamped** to the maximum,
    echoed in the response, and warned about. It is not silently accepted as an
    impossible configuration.
11. **Top-level verdict mapping** (documented until reviewed):
    - `GO`: FITS yes with medium/high confidence and SUPPORTED yes.
    - `OPTIMIZE`: FITS yes but tight/low-confidence, or does not fit as requested
      while a documented smaller memory configuration (quantization, lower
      context, batch 1) would fit **and** is supported.
    - `NO`: best-case memory cannot fit, or the support matrix says the
      architecture/runtime path is unsupported.
    - `UNKNOWN`: inspection failed, architecture/format unsupported, runtime
      support unconfirmed, or input data is insufficient (e.g. no RAM).
    The three claim levels are always separate. VERIFIED=unknown prevents the
    word "verified" but does not block GO.

## Hardware

12. **The helper cannot measure discrete-GPU bandwidth without torch/CUDA.**
    It measures CPU/unified-memory bandwidth with a short NumPy copy benchmark.
    For NVIDIA GPUs it reads name/VRAM from `nvidia-smi` but takes bandwidth
    from `data/devices.yaml`. The result says which value was measured and which
    was looked up.
13. **The helper code is self-reported, unsigned, and not tamper-proof.** It has
    a version, compression, CRC, strict size limits, and server-side range
    clamping. Its confidence means "measured on the user's machine by our
    script", not "cryptographically attested".
14. **Apple Silicon usable memory is a named constant:** 75% of total unified
    memory (`APPLE_SILICON_USABLE_MEMORY_FRACTION = 0.75`). The real wired limit
    varies by macOS version, RAM size, and other running apps. The response
    says this is an assumption, not an OS query.
15. **Discrete GPU fit is VRAM fit**, with a small runtime reserve. System RAM is
    reported but does not make a model fit if v1 has no offload.
16. **CPU-only/unknown** uses conservative defaults: 80% of RAM as the budget
    and 25 GB/s bandwidth unless the helper or manual profile provides a better
    number. Confidence is LOW. Without RAM, the result must be UNKNOWN; we do
    not guess the user's machine.
17. **Manual profiles are medium confidence.** The device table is a curated
    lookup, not a measurement. RAM is user-supplied. For Apple devices, the
    server applies the same 75% fraction. For dGPUs, VRAM comes from the table,
    not the user-entered system RAM.
18. **Units:** all JSON memory numbers are bytes; all bandwidth numbers are
    decimal GB/s (10^9 bytes/s). Display code may render GiB, but must label it.

## Inspection and estimation

19. **Revision pinning:** OmniRun resolves `main` to a commit SHA once, then uses
    that SHA for config, index, and header range requests. This keeps one
    response internally consistent and makes immutable cache entries safe.
20. **Safetensors is authoritative for weight bytes.** We sum tensor spans from
    every shard's header and cross-check with the index/file sizes. Tied
    embeddings are counted once because only one tensor is stored.
    Header size, shard count, tensor count, and declared spans are capped and
    validated to avoid malicious or absurd responses.
21. **KV cache uses `2 * layers * kv_heads * head_dim * context * batch *
    kv_bytes`** for standard MHA/GQA. Sliding-window layers use
    `min(context, window)`; mixed patterns are handled per layer when the config
    exposes them, otherwise full context is used as an upper bound and flagged.
    MLA (DeepSeek-style) uses the compressed latent formula when config fields
    are present, and is flagged LOW confidence. Unknown attention layouts
    produce a range/UNKNOWN rather than a confident number.
22. **Runtime overhead is a named range**, not a single invented number:
    runtime context + allocator + compute workspace. The exact constants live in
    `core/estimate.py` with comments and are repeated in the response
    assumptions.
23. **Decode speed** is
    `effective_bandwidth * efficiency / bytes_read_per_token`, where
    `bytes_read_per_token = active_weight_bytes / batch + kv_bytes_per_seq`.
    Dense efficiency range is 0.55–0.85 (likely 0.70); MoE is 0.25–0.60
    (likely 0.40). These are documented engineering ranges, not measured
    constants, and the speed confidence is never higher than medium in v1.
    For MoE, active weights are derived from tensor names/config; if that cannot
    be done honestly, speed is UNKNOWN instead of using total weights.
24. **ASR/TTS speed is only a coarse class** (`real-time likely`, `uncertain`,
    `slow`) with LOW confidence. No RTF is invented. The class comes from a
    stated size/bandwidth heuristic and is labelled as such.
25. **Pickle-only repos:** file sizes from the HF API are an upper bound because
    a checkpoint may contain optimizer state or unrelated tensors. If the upper
    bound fits, FITS can be yes with LOW confidence; if it does not fit, FITS is
    UNKNOWN (the real model may be smaller), never a confident NO. We do not
    inspect tensor shapes without unpickling, and we never unpickle.
26. **GGUF:** metadata/tensor-info headers are read with progressive ranges and
    validated. Split shards are recognized by filename and summed. Actual
    artifact bytes are used for weights; tensor info supplies architecture and
    parameter counts. Unknown GGML quantization types lower confidence.
27. **Gated/private repos are not bypassed.** A missing token produces a clear
    gated/auth error and a link to the repo page. A supplied token is used only
    for that request chain, is never echoed, logged, or stored in results, and
    cache keys use a one-way token scope hash. Anonymous and token responses do
    not share cache entries.
28. **Per-file last-commit date is not in the model-info response.** v1 uses the
    HF tree endpoint's `lastCommit` for config/weight files, with repo
    `lastModified` as a labelled fallback. This is best-effort and may be
    approximate for some repos.
29. **Environment hints are text only.** `uv pip compile --exclude-newer
    <date>` is printed; nothing is executed. An old model commit date does not
    guarantee that old wheels exist for Python 3.11+, so the hint is explicitly
    best-effort.

## Reliability and security

30. **HF cache:** disk JSON cache under `~/.cache/omnirun` (override with
    `OMNIRUN_CACHE_DIR`). Mutable refs use short TTLs; SHA-pinned metadata uses
    long TTLs. Stale entries may be used only for explicitly marked
    stale-on-error fallbacks. Corrupt entries are discarded.
31. **Rate limiting:** the API has an in-process per-IP token bucket and a
    bounded global concurrency semaphore. v1 is single-process; multi-worker
    deployments need a shared limiter (out of scope and documented).
32. **Timeouts/retries:** HF requests have connect/read timeouts and retry
    only timeouts, connection failures, 429, and 5xx, honoring `Retry-After`.
    401/403/404 are never retried. Whole `/check` requests have a deadline.
33. **No token leakage in logs.** The API does not log request bodies. Access
    logs are the deployment's responsibility. Cache entries and responses never
    include the token.
34. **Schema versioning:** the response is `schema_version: "1.0"`. Additive
    fields may appear in 1.x; breaking changes get a new major version. Errors
    use a versioned envelope too. OpenAPI is generated from Pydantic.
35. **Tests run offline.** Recorded HF fixtures live under `tests/fixtures`.
    Live network is only used by explicit fixture-recording scripts, never by
    CI/tests.

## Spec issues found (and choices made)

- **Helper benchmark scope:** CPU bandwidth is measurable cross-platform; dGPU
  VRAM bandwidth is not, without torch/CUDA. The spec's "measured specs
  (highest confidence)" is therefore split into measured memory/CPU bandwidth
  vs looked-up accelerator bandwidth.
- **"GPU/chip + RAM" lacks VRAM** for discrete GPUs. Added `vram_gb` to device
  entries and a separate budget rule.
- **"CPU-only/unknown" conflates a hardware type with missing data.** v1 uses
  `source: manual` + a CPU device for CPU-only, and `source: unknown` for
  missing hardware. Unknown without RAM yields UNKNOWN, not a guess.
- **KV formula is incomplete** for sliding-window, mixed attention, MLA, and
  models that do not cache K and V symmetrically. Handled explicitly; flagged.
- **Decode formula omits KV reads and batch amortization.** Added both to the
  formula and to the assumptions. Prefill/TTFT is explicitly out of scope.
- **Support matrix keyed only by architecture is too coarse.** Added artifact
  format/path and runtime version floors; entries carry notes. llama.cpp
  version floors are build labels (`b####`), not semver, so they are strings.
- **Step 4 needs the support matrix, but step 6 schedules it.** The matrix is
  seeded in step 4 with a few entries and expanded in step 6.
- **VERIFIED is empty in v1**, so the strongest claim can never be awarded. GO
  is allowed on FITS+SUPPORTED, but the response always says VERIFIED=unknown.
- **"Always ranges" vs exact math** is contradictory. Exact components are
  exact; ranges are real, not decorative.
- **ASR/TTS coarse speed classes have no thresholds in the spec.** v1 defines
  them as heuristics from model bytes and bandwidth, with LOW confidence and no
  RTF.
- **Gated vs private vs nonexistent is ambiguous** because HF returns 401 to
  avoid leaking existence. v1 explains all three possibilities and suggests a
  token, without claiming which one it is when anonymous.
- **Cache/revision consistency:** `main` moves. v1 pins the SHA before any
  file reads; otherwise config and header could come from different commits.
- **"Short code" was undefined.** v1 defines `OR1.` + base64url(zlib(JSON)) +
  CRC32, with version/size validation. It is not signed.
- **Rate limiting behind proxies/multiple workers** needs deployment input. v1
  uses `request.client.host` and does not trust `X-Forwarded-For` by default.
- **No unit convention was specified.** All API memory numbers are bytes;
  bandwidth is decimal GB/s.

## Review questions (defaults chosen so work can continue)

1. Is the GO/OPTIMIZE/NO/UNKNOWN mapping in item 11 what you want? In
   particular: GO when FITS+SUPPORTED but unverified, and UNKNOWN (not
   OPTIMIZE) when FITS is yes but runtime support is unconfirmed.
2. Is 75% the right Apple Silicon usable-memory fraction, or should it vary by
   RAM size (e.g. 0.75 up to 64 GB, lower above)?
3. Should v1 support only causal LLM/ASR/TTS, or also embeddings/fill-mask?
4. Should a caller be able to force a smaller KV dtype / context than the model
   checkpoint dtype? Currently KV dtype follows checkpoint dtype.
5. Do you want an optional server-side `HF_TOKEN` fallback for gated repos, or
   strictly per-request tokens (default: strictly per-request, safer)?
