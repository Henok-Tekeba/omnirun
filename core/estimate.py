"""Memory and (later) speed math.

Every constant that is an assumption is named here and repeated in the API
response. Exact quantities keep min == likely == max.

KV cache formula for standard MHA/GQA/MQA:
    2 * layers * kv_heads * head_dim * tokens * batch * dtype_bytes
The 2 is K and V. Sliding-window layers cap ``tokens`` at the window. Because
some runtimes still allocate a full-context cache even when they evict old
tokens, the max end of a windowed estimate uses full context; the likely end
uses the window. MLA uses the compressed latent formula instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.inspect.config import ModelConfig
from core.inspect.model import ModelInspection
from core.inspect.types import Confidence, Issue, RangeEstimate

GIB = 1024**3
MIB = 1024**2

# Runtime context + allocator + compute workspace. These are deliberately broad
# and runtime-agnostic: a PyTorch process has a larger baseline than llama.cpp.
# Base is GiB; fractions apply to weight bytes.
OVERHEAD_BASE_GIB = 0.25
OVERHEAD_FRACTION_MIN = 0.05
OVERHEAD_FRACTION_LIKELY = 0.10
OVERHEAD_FRACTION_MAX = 0.20

# Hypothetical quantization, weights only. 4-bit assumes 4.5 bits/param: 4 bits
# plus one FP16 scale and one FP16 zero per 64-parameter group (32 bits / 64 =
# 0.5 bit). Real GGUF Q4_K_M is often ~4.8 bits/param, so this is optimistic
# for some artifacts; the response labels these as hypothetical.
QUANT_ALTERNATIVES = (
    ("fp16", 2.0, "16-bit weights (FP16/BF16), no quantization overhead."),
    ("int8", 1.01, "8-bit weights + 1% for scales/metadata."),
    (
        "4bit",
        0.5625,
        "4-bit weights + FP16 scale/zero per 64-param group = 4.5 bits/param. "
        "Real GGUF Q4 variants may be larger.",
    ),
)

# If config.json does not declare torch_dtype, we assume a 2-byte KV cache but
# allow up to 4 bytes. The runtime could allocate FP32; it is unlikely to use
# less than 2 bytes in v1's supported model classes.
UNKNOWN_KV_DTYPE_RANGE = (2.0, 2.0, 4.0)


@dataclass(frozen=True, slots=True)
class KVEstimate:
    available: bool
    bytes_range: RangeEstimate | None
    bytes_likely: int | None
    per_sequence_likely: int | None
    batch: int
    context_requested: int
    context_effective: int | None
    dtype_bytes: float | None
    attention: str
    layers_full: int
    layers_windowed: int
    confidence: Confidence
    issues: tuple[Issue, ...]
    formula: str


@dataclass(frozen=True, slots=True)
class QuantAlternative:
    name: str
    bits_per_param: float
    weight_bytes: int | None
    confidence: Confidence
    note: str


@dataclass(frozen=True, slots=True)
class WeightEstimate:
    available: bool
    kind: str  # exact | upper_bound | unknown
    range: RangeEstimate | None
    actual_bytes: int | None
    params: int | None
    param_source: str | None
    confidence: Confidence
    alternatives: tuple[QuantAlternative, ...]
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True)
class MemoryEstimate:
    weights: WeightEstimate
    kv: KVEstimate
    overhead: RangeEstimate | None
    peak: RangeEstimate | None
    context_effective: int | None
    batch: int
    confidence: Confidence
    issues: tuple[Issue, ...]


def _clamp_context(config: ModelConfig, context: int) -> tuple[int, list[Issue]]:
    if context < 1:
        raise ValueError("context must be >= 1")
    issues: list[Issue] = []
    effective = context
    if config.max_positions and context > config.max_positions:
        effective = config.max_positions
        issues.append(
            Issue(
                "context_clamped",
                f"Requested context {context} exceeds the model maximum "
                f"{config.max_positions}; using {effective}.",
                "warning",
            )
        )
    elif config.max_positions is None:
        issues.append(
            Issue(
                "max_positions_unknown",
                "The model maximum context is unknown; the requested context is used "
                "as an assumption.",
                "warning",
            )
        )
    return effective, issues


def estimate_kv_cache(
    config: ModelConfig | None,
    *,
    context: int,
    batch: int,
) -> KVEstimate:
    if batch < 1:
        raise ValueError("batch must be >= 1")
    if config is None:
        return KVEstimate(
            available=False,
            bytes_range=None,
            bytes_likely=None,
            per_sequence_likely=None,
            batch=batch,
            context_requested=context,
            context_effective=None,
            dtype_bytes=None,
            attention="unknown",
            layers_full=0,
            layers_windowed=0,
            confidence=Confidence.LOW,
            issues=(
                Issue(
                    "kv_config_missing",
                    "config.json is unavailable, so KV-cache memory is UNKNOWN.",
                    "risk",
                ),
            ),
            formula="unavailable",
        )

    effective_context, issues = _clamp_context(config, context)
    if config.has_unsupported_attention:
        return KVEstimate(
            available=False,
            bytes_range=None,
            bytes_likely=None,
            per_sequence_likely=None,
            batch=batch,
            context_requested=context,
            context_effective=effective_context,
            dtype_bytes=config.dtype_bytes,
            attention="linear/hybrid",
            layers_full=0,
            layers_windowed=0,
            confidence=Confidence.LOW,
            issues=(
                *issues,
                Issue(
                    "kv_unsupported_attention",
                    "Linear/hybrid attention state is not modeled by v1; KV memory is UNKNOWN.",
                    "risk",
                ),
            ),
            formula="unavailable",
        )

    dtype_min, dtype_likely, dtype_max = UNKNOWN_KV_DTYPE_RANGE
    dtype = config.dtype_bytes
    if dtype is not None:
        dtype_min = dtype_likely = dtype_max = float(dtype)
    else:
        issues.append(
            Issue(
                "kv_dtype_assumed",
                "torch_dtype is missing; KV cache is assumed to be 2 bytes/element, "
                "with a 4-byte upper bound.",
                "warning",
            )
        )

    layers = config.layers
    if not layers:
        return KVEstimate(
            available=False,
            bytes_range=None,
            bytes_likely=None,
            per_sequence_likely=None,
            batch=batch,
            context_requested=context,
            context_effective=effective_context,
            dtype_bytes=dtype_likely,
            attention="unknown",
            layers_full=0,
            layers_windowed=0,
            confidence=Confidence.LOW,
            issues=(
                *issues,
                Issue(
                    "kv_layers_missing",
                    "Layer count is missing; KV-cache memory is UNKNOWN.",
                    "risk",
                ),
            ),
            formula="unavailable",
        )

    if config.mla:
        if not config.mla.kv_lora_rank or not config.mla.qk_rope_head_dim:
            return KVEstimate(
                available=False,
                bytes_range=None,
                bytes_likely=None,
                per_sequence_likely=None,
                batch=batch,
                context_requested=context,
                context_effective=effective_context,
                dtype_bytes=dtype_likely,
                attention="mla",
                layers_full=layers,
                layers_windowed=0,
                confidence=Confidence.LOW,
                issues=(
                    *issues,
                    Issue(
                        "mla_fields_missing",
                        "MLA config fields are incomplete; KV-cache memory is UNKNOWN.",
                        "risk",
                    ),
                ),
                formula="unavailable",
            )
        per_layer_bytes = config.mla.bytes_per_token_per_layer(1.0)
        cache_units = layers * effective_context
        per_sequence_likely = round(cache_units * per_layer_bytes * dtype_likely)
        total_min = round(cache_units * per_layer_bytes * dtype_min * batch)
        total_likely = round(cache_units * per_layer_bytes * dtype_likely * batch)
        total_max = round(cache_units * per_layer_bytes * dtype_max * batch)
        issues.append(
            Issue(
                "mla_cache_layout",
                "MLA KV cache assumes the compressed (kv_lora_rank + qk_rope_head_dim) "
                "layout used by DeepSeek-style runtimes. Other runtimes may differ.",
                "warning",
            )
        )
        return KVEstimate(
            available=True,
            bytes_range=RangeEstimate(total_min, total_likely, total_max),
            bytes_likely=total_likely,
            per_sequence_likely=per_sequence_likely,
            batch=batch,
            context_requested=context,
            context_effective=effective_context,
            dtype_bytes=dtype_likely,
            attention="mla",
            layers_full=layers,
            layers_windowed=0,
            confidence=Confidence.LOW,
            issues=tuple(issues),
            formula=(
                f"{layers} layers * (kv_lora_rank {config.mla.kv_lora_rank} + "
                f"qk_rope_head_dim {config.mla.qk_rope_head_dim}) * {effective_context} "
                f"tokens * {dtype_likely:g} bytes * batch {batch}"
            ),
        )

    kv_heads = config.kv_heads_effective
    head_dim = config.head_dim_effective
    if not kv_heads or not head_dim:
        missing = "num_key_value_heads" if not kv_heads else "head_dim"
        return KVEstimate(
            available=False,
            bytes_range=None,
            bytes_likely=None,
            per_sequence_likely=None,
            batch=batch,
            context_requested=context,
            context_effective=effective_context,
            dtype_bytes=dtype_likely,
            attention="unknown",
            layers_full=0,
            layers_windowed=0,
            confidence=Confidence.LOW,
            issues=(
                *issues,
                Issue(
                    "kv_attention_fields_missing",
                    f"{missing} is missing; KV-cache memory is UNKNOWN.",
                    "risk",
                ),
            ),
            formula="unavailable",
        )

    layers_full = 0
    layers_windowed = 0
    bounded_units = 0
    full_units = 0
    for layer_index in range(layers):
        window = config.sliding_window_for_layer(layer_index)
        if window:
            layers_windowed += 1
            bounded_units += min(effective_context, window)
        else:
            layers_full += 1
            bounded_units += effective_context
        full_units += effective_context

    per_token_per_layer = 2 * kv_heads * head_dim
    per_sequence_likely = round(bounded_units * per_token_per_layer * dtype_likely)
    total_min = round(bounded_units * per_token_per_layer * dtype_min * batch)
    total_likely = round(bounded_units * per_token_per_layer * dtype_likely * batch)
    total_max = round(full_units * per_token_per_layer * dtype_max * batch)

    if layers_windowed:
        issues.append(
            Issue(
                "sliding_window_cache_range",
                "Some layers are windowed. The likely estimate caps their cache at the "
                "window; the max estimate reserves full context in case the runtime does "
                "not evict. This is a runtime-dependent allocation detail.",
                "warning",
            )
        )

    attention = "mha"
    if kv_heads == 1:
        attention = "mqa"
    elif config.attention_heads and kv_heads < config.attention_heads:
        attention = "gqa"

    confidence = Confidence.HIGH
    if layers_windowed or dtype is None:
        confidence = Confidence.MEDIUM

    formula = (
        f"2 (K,V) * {kv_heads} kv heads * {head_dim} head_dim * "
        f"sum(bounded tokens per layer)={bounded_units} * batch {batch} * "
        f"{dtype_likely:g} bytes; max uses sum(full tokens per layer)={full_units}"
    )
    return KVEstimate(
        available=True,
        bytes_range=RangeEstimate(total_min, total_likely, total_max),
        bytes_likely=total_likely,
        per_sequence_likely=per_sequence_likely,
        batch=batch,
        context_requested=context,
        context_effective=effective_context,
        dtype_bytes=dtype_likely,
        attention=attention,
        layers_full=layers_full,
        layers_windowed=layers_windowed,
        confidence=confidence,
        issues=tuple(issues),
        formula=formula,
    )


def _alternatives(
    params: int | None,
    confidence: Confidence,
) -> tuple[QuantAlternative, ...]:
    if not params:
        return ()
    result = []
    for name, bytes_per_param, note in QUANT_ALTERNATIVES:
        result.append(
            QuantAlternative(
                name=name,
                bits_per_param=bytes_per_param * 8,
                weight_bytes=round(params * bytes_per_param),
                confidence=confidence,
                note=note,
            )
        )
    return tuple(result)


def estimate_weights(inspection: ModelInspection) -> WeightEstimate:
    issues: list[Issue] = []
    weight_bytes = inspection.weight_bytes
    if weight_bytes is None:
        return WeightEstimate(
            available=False,
            kind="unknown",
            range=None,
            actual_bytes=None,
            params=inspection.params,
            param_source=inspection.param_source,
            confidence=Confidence.LOW,
            alternatives=_alternatives(inspection.params, Confidence.LOW),
            issues=(
                Issue(
                    "weights_unknown",
                    "OmniRun could not determine the stored model weight size.",
                    "risk",
                ),
            ),
        )

    if inspection.weight_bytes_exact and inspection.format == "safetensors":
        weight_range = RangeEstimate(weight_bytes, weight_bytes, weight_bytes)
        kind = "exact"
        confidence = inspection.confidence
    elif inspection.format == "safetensors":
        weight_range = RangeEstimate(weight_bytes, weight_bytes, weight_bytes)
        kind = "exact" if inspection.confidence == Confidence.HIGH else "upper_bound"
        confidence = Confidence.lowest(inspection.confidence, Confidence.MEDIUM)
        if kind == "upper_bound":
            issues.append(
                Issue(
                    "weights_upper_bound",
                    "Safetensors spans are readable but not fully trustworthy; weight "
                    "bytes are treated as an upper bound.",
                    "warning",
                )
            )
    else:
        # Pickle/GGUF-placeholder: file bytes are an upper bound. The true tensor
        # payload could be smaller, so we do not pretend to know a lower bound.
        weight_range = RangeEstimate(0.0, float(weight_bytes), float(weight_bytes))
        kind = "upper_bound"
        confidence = Confidence.LOW
        issues.append(
            Issue(
                "weights_upper_bound",
                "Weight bytes come from file sizes, not tensor shapes; they are an "
                "upper bound. A lower bound is not known.",
                "warning",
            )
        )

    params = inspection.params
    param_confidence = (
        Confidence.HIGH if inspection.param_source == "safetensors_headers" else Confidence.LOW
    )
    if params is None:
        issues.append(
            Issue(
                "params_unknown",
                "Logical parameter count is unknown; hypothetical quantization sizes "
                "are unavailable.",
                "warning",
            )
        )
    else:
        issues.append(
            Issue(
                "quant_alternatives_hypothetical",
                "FP16/INT8/4-bit alternatives are uniform, weights-only calculations. "
                "They do not imply an artifact exists or is supported.",
                "info",
            )
        )

    return WeightEstimate(
        available=True,
        kind=kind,
        range=weight_range,
        actual_bytes=weight_bytes,
        params=params,
        param_source=inspection.param_source,
        confidence=confidence,
        alternatives=_alternatives(params, param_confidence),
        issues=tuple(issues),
    )


def peak_for_weight_bytes(weight_bytes: int, kv: KVEstimate) -> RangeEstimate | None:
    """Peak memory if weights had a different (hypothetical) byte size."""
    if kv.bytes_range is None:
        return None
    base = OVERHEAD_BASE_GIB * GIB
    overhead_min = base + OVERHEAD_FRACTION_MIN * weight_bytes
    overhead_likely = base + OVERHEAD_FRACTION_LIKELY * weight_bytes
    overhead_max = base + OVERHEAD_FRACTION_MAX * weight_bytes
    return RangeEstimate(
        weight_bytes + kv.bytes_range.min + overhead_min,
        weight_bytes + kv.bytes_range.likely + overhead_likely,
        weight_bytes + kv.bytes_range.max + overhead_max,
    )


def estimate_memory(
    inspection: ModelInspection,
    *,
    context: int,
    batch: int,
) -> MemoryEstimate:
    weights = estimate_weights(inspection)
    kv = estimate_kv_cache(inspection.config, context=context, batch=batch)
    issues: list[Issue] = []
    issues.extend(weights.issues)
    issues.extend(kv.issues)
    issues.append(
        Issue(
            "overhead_assumption",
            "Runtime overhead is a range: 0.25 GiB base plus 5% / 10% / 20% of "
            "weights for context, allocator, and compute workspace. Prefill and "
            "long-prompt activation peaks are not modeled.",
            "info",
        )
    )

    if weights.range is None:
        return MemoryEstimate(
            weights=weights,
            kv=kv,
            overhead=None,
            peak=None,
            context_effective=kv.context_effective,
            batch=batch,
            confidence=Confidence.LOW,
            issues=tuple(issues),
        )

    base = OVERHEAD_BASE_GIB * GIB
    overhead = RangeEstimate(
        base + OVERHEAD_FRACTION_MIN * weights.range.min,
        base + OVERHEAD_FRACTION_LIKELY * weights.range.likely,
        base + OVERHEAD_FRACTION_MAX * weights.range.max,
    )

    if kv.bytes_range is None:
        return MemoryEstimate(
            weights=weights,
            kv=kv,
            overhead=overhead,
            peak=None,
            context_effective=kv.context_effective,
            batch=batch,
            confidence=Confidence.LOW,
            issues=tuple(issues),
        )

    peak = RangeEstimate(
        weights.range.min + kv.bytes_range.min + overhead.min,
        weights.range.likely + kv.bytes_range.likely + overhead.likely,
        weights.range.max + kv.bytes_range.max + overhead.max,
    )
    confidence = Confidence.lowest(weights.confidence, kv.confidence, Confidence.MEDIUM)
    return MemoryEstimate(
        weights=weights,
        kv=kv,
        overhead=overhead,
        peak=peak,
        context_effective=kv.context_effective,
        batch=batch,
        confidence=confidence,
        issues=tuple(issues),
    )
