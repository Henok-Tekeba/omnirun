"""Parse ``config.json`` into a conservative, architecture-aware view.

Hugging Face configs are not a schema. We read the handful of fields the
estimator actually needs, derive what is safely derivable, and record every
missing/ambiguous field as an issue. Nothing here guesses silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from core.inspect.types import Issue

# Bytes per element for the dtypes that matter to memory/cache math. Unknown
# dtypes are represented by None and lower the result's confidence.
DTYPE_BYTES: dict[str, float] = {
    "bool": 1,
    "u8": 1,
    "uint8": 1,
    "i8": 1,
    "int8": 1,
    "f8_e4m3": 1,
    "f8_e5m2": 1,
    "float8_e4m3fn": 1,
    "float8_e5m2": 1,
    "i16": 2,
    "int16": 2,
    "u16": 2,
    "uint16": 2,
    "f16": 2,
    "float16": 2,
    "fp16": 2,
    "half": 2,
    "bf16": 2,
    "bfloat16": 2,
    "i32": 4,
    "int32": 4,
    "u32": 4,
    "uint32": 4,
    "f32": 4,
    "float32": 4,
    "fp32": 4,
    "f64": 8,
    "float64": 8,
    "fp64": 8,
    "i64": 8,
    "int64": 8,
    "u64": 8,
    "uint64": 8,
}

_DTYPE_ALIASES = {
    "torch.float16": "float16",
    "torch.bfloat16": "bfloat16",
    "torch.float32": "float32",
    "torch.float64": "float64",
    "torch.int8": "int8",
    "torch.uint8": "uint8",
    "torch.int32": "int32",
    "torch.int64": "int64",
}

_AUTO_MAP_BUILTIN_PREFIXES = ("transformers.",)


@dataclass(frozen=True, slots=True)
class QuantizationConfig:
    method: str | None
    bits: int | None
    group_size: int | None
    checkpoint_format: str | None
    desc_act: bool | None
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_quantized(self) -> bool:
        return bool(self.method) or self.bits is not None


@dataclass(frozen=True, slots=True)
class MoEConfig:
    num_experts: int
    experts_per_token: int
    moe_intermediate_size: int | None
    shared_experts: int | None
    shared_expert_intermediate_size: int | None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MLAConfig:
    """DeepSeek-style multi-head latent attention metadata.

    The cache stores a compressed KV latent plus a decoupled RoPE key:
    ``(kv_lora_rank + qk_rope_head_dim) * kv_dtype_bytes`` per token per layer.
    This is materially smaller than ``2 * kv_heads * head_dim``. Because the
    runtime layout is implementation-specific, MLA estimates are LOW confidence.
    """

    kv_lora_rank: int
    qk_rope_head_dim: int
    qk_nope_head_dim: int | None = None
    v_head_dim: int | None = None
    q_lora_rank: int | None = None

    def bytes_per_token_per_layer(self, dtype_bytes: float) -> int:
        return round((self.kv_lora_rank + self.qk_rope_head_dim) * dtype_bytes)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    architectures: tuple[str, ...]
    model_type: str | None
    layers: int | None
    hidden_size: int | None
    attention_heads: int | None
    kv_heads: int | None
    head_dim: int | None
    max_positions: int | None
    vocab_size: int | None
    intermediate_size: int | None
    torch_dtype: str | None
    transformers_version: str | None
    quantization: QuantizationConfig | None
    auto_map: Mapping[str, str]
    tie_word_embeddings: bool | None
    is_encoder_decoder: bool
    sliding_window: int | None
    sliding_window_pattern: int | None
    layer_types: tuple[str, ...]
    moe: MoEConfig | None
    mla: MLAConfig | None
    issues: tuple[Issue, ...] = ()

    @property
    def primary_architecture(self) -> str | None:
        return self.architectures[0] if self.architectures else None

    @property
    def trust_remote_code_required(self) -> bool:
        for value in self.auto_map.values():
            if not any(value.startswith(prefix) for prefix in _AUTO_MAP_BUILTIN_PREFIXES):
                return True
        return False

    @property
    def kv_heads_effective(self) -> int | None:
        return self.kv_heads or self.attention_heads

    @property
    def head_dim_effective(self) -> int | None:
        if self.head_dim:
            return self.head_dim
        if (
            self.hidden_size
            and self.attention_heads
            and self.hidden_size % self.attention_heads == 0
        ):
            return self.hidden_size // self.attention_heads
        return None

    @property
    def dtype_bytes(self) -> float | None:
        if not self.torch_dtype:
            return None
        normalized = _DTYPE_ALIASES.get(self.torch_dtype.lower(), self.torch_dtype.lower())
        return DTYPE_BYTES.get(normalized)

    @property
    def is_moe(self) -> bool:
        return self.moe is not None

    @property
    def is_mla(self) -> bool:
        return self.mla is not None

    @property
    def is_sliding_window(self) -> bool:
        return bool(self.sliding_window) or any(
            kind in {"sliding_attention", "sliding"} for kind in self.layer_types
        )

    @property
    def has_unsupported_attention(self) -> bool:
        return any(kind in {"linear_attention", "linear"} for kind in self.layer_types)

    def sliding_window_for_layer(self, layer_index: int) -> int | None:
        """Return the layer's KV window, or None for full attention.

        ``layer_types`` is authoritative when present. Otherwise Gemma-style
        ``sliding_window_pattern`` means N layers per pattern, with the last
        layer in each group using full attention (e.g. pattern=6 -> 5 sliding,
        1 full). If only ``sliding_window`` is set, all layers are treated as
        sliding.
        """
        if self.layer_types:
            if layer_index < len(self.layer_types):
                kind = self.layer_types[layer_index]
            else:
                kind = self.layer_types[-1]
            if kind in {"sliding_attention", "sliding"}:
                return self.sliding_window
            return None
        if not self.sliding_window:
            return None
        pattern = self.sliding_window_pattern
        if pattern and pattern > 0:
            return self.sliding_window if (layer_index + 1) % pattern != 0 else None
        return self.sliding_window

    @property
    def kv_estimation_issues(self) -> tuple[Issue, ...]:
        missing = [
            name
            for name, value in (
                ("num_hidden_layers", self.layers),
                ("num_attention_heads", self.attention_heads),
                ("head_dim", self.head_dim_effective),
                ("max_position_embeddings", self.max_positions),
            )
            if not value
        ]
        issues = list(self.issues)
        for name in missing:
            issues.append(
                Issue(
                    "missing_kv_field",
                    f"config.json does not provide {name}; KV-cache math cannot be exact.",
                    "warning",
                )
            )
        if self.has_unsupported_attention:
            issues.append(
                Issue(
                    "unsupported_attention",
                    "The config contains linear/hybrid attention layers; v1's KV formula "
                    "does not model their state cache.",
                    "risk",
                )
            )
        return tuple(issues)


def _int(config: Mapping[str, Any], *keys: str, minimum: int = 1) -> int | None:
    for key in keys:
        value = config.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value >= minimum:
            return value
        if isinstance(value, float) and value.is_integer() and int(value) >= minimum:
            return int(value)
    return None


def _str(config: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _bool(config: Mapping[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = config.get(key)
        if isinstance(value, bool):
            return value
    return None


def _quantization(config: Mapping[str, Any]) -> QuantizationConfig | None:
    raw = config.get("quantization_config")
    if not isinstance(raw, dict) or not raw:
        return None
    bits = _int(raw, "bits", "w_bit", "weight_bits", minimum=1)
    if bits is None and isinstance(raw.get("quant_method"), str):
        method = raw["quant_method"].lower()
        if "4" in method:
            bits = 4
        elif "8" in method:
            bits = 8
    method = raw.get("quant_method")
    group_size = _int(raw, "group_size", "q_group_size", minimum=1)
    checkpoint_format = raw.get("checkpoint_format")
    desc_act = raw.get("desc_act")
    return QuantizationConfig(
        method=method if isinstance(method, str) else None,
        bits=bits,
        group_size=group_size,
        checkpoint_format=checkpoint_format if isinstance(checkpoint_format, str) else None,
        desc_act=desc_act if isinstance(desc_act, bool) else None,
        raw=raw,
    )


def _moe(config: Mapping[str, Any]) -> MoEConfig | None:
    num_experts = _int(
        config,
        "num_local_experts",
        "num_experts",
        "n_routed_experts",
        "moe_num_experts",
        minimum=2,
    )
    if num_experts is None:
        return None
    experts_per_token = _int(
        config,
        "num_experts_per_tok",
        "num_experts_per_token",
        "moe_top_k",
        "num_selected_experts",
        "top_k",
        minimum=1,
    )
    if experts_per_token is None:
        experts_per_token = 1
    if experts_per_token > num_experts:
        experts_per_token = num_experts
    return MoEConfig(
        num_experts=num_experts,
        experts_per_token=experts_per_token,
        moe_intermediate_size=_int(config, "moe_intermediate_size", "expert_intermediate_size"),
        shared_experts=_int(config, "n_shared_experts", "num_shared_experts", minimum=0),
        shared_expert_intermediate_size=_int(config, "shared_expert_intermediate_size"),
        raw={
            key: config[key]
            for key in (
                "num_experts_per_tok",
                "n_routed_experts",
                "n_shared_experts",
                "moe_intermediate_size",
            )
            if key in config
        },
    )


def _mla(config: Mapping[str, Any]) -> MLAConfig | None:
    kv_lora_rank = _int(config, "kv_lora_rank", minimum=1)
    qk_rope_head_dim = _int(config, "qk_rope_head_dim", minimum=1)
    if kv_lora_rank is None or qk_rope_head_dim is None:
        return None
    return MLAConfig(
        kv_lora_rank=kv_lora_rank,
        qk_rope_head_dim=qk_rope_head_dim,
        qk_nope_head_dim=_int(config, "qk_nope_head_dim"),
        v_head_dim=_int(config, "v_head_dim"),
        q_lora_rank=_int(config, "q_lora_rank", minimum=0),
    )


def _layer_types(config: Mapping[str, Any]) -> tuple[str, ...]:
    raw = config.get("layer_types")
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if isinstance(item, str))
    raw_attention = config.get("attention_type")
    if isinstance(raw_attention, str):
        return (raw_attention,)
    return ()


def parse_config(config: Mapping[str, Any]) -> ModelConfig:
    """Parse a config dict. Unknown keys are ignored on purpose."""
    architectures_raw = config.get("architectures")
    architectures = (
        tuple(str(a) for a in architectures_raw if isinstance(a, str) and a)
        if isinstance(architectures_raw, list)
        else ()
    )

    model_type = _str(config, "model_type")
    is_encoder_decoder = bool(config.get("is_encoder_decoder", False)) or model_type in {
        "t5",
        "whisper",
        "bart",
        "mbart",
        "pegasus",
        "encoder_decoder",
    }

    layers = _int(
        config,
        "decoder_layers" if is_encoder_decoder else "num_hidden_layers",
        "num_hidden_layers",
        "n_layer",
        "num_layers",
        "n_layers",
        "decoder_layers",
        "encoder_layers",
    )
    hidden_size = _int(config, "hidden_size", "n_embd", "d_model", "dim")
    attention_heads = _int(
        config,
        "decoder_attention_heads" if is_encoder_decoder else "num_attention_heads",
        "num_attention_heads",
        "n_head",
        "num_heads",
        "decoder_attention_heads",
        "encoder_attention_heads",
    )
    kv_heads = _int(
        config,
        "num_key_value_heads",
        "num_kv_heads",
        "n_kv_heads",
        "multi_query_group_num",
        "num_query_groups",
    )
    explicit_head_dim = _int(config, "head_dim", "attention_head_dim", "kv_channels")
    if explicit_head_dim is None and isinstance(config.get("attention_head_dim"), list):
        dims = [
            int(d)
            for d in config["attention_head_dim"]
            if isinstance(d, int) and not isinstance(d, bool) and d > 0
        ]
        if dims and len(set(dims)) == 1:
            explicit_head_dim = dims[0]
    head_dim = explicit_head_dim
    if head_dim is None and hidden_size and attention_heads and hidden_size % attention_heads == 0:
        head_dim = hidden_size // attention_heads

    max_positions = _int(
        config,
        "max_position_embeddings",
        "n_positions",
        "max_seq_len",
        "max_sequence_length",
        "seq_length",
        "n_ctx",
        "max_target_positions",
    )
    vocab_size = _int(config, "vocab_size", "padded_vocab_size", "n_vocab")
    intermediate_size = _int(
        config,
        "intermediate_size",
        "ffn_hidden_size",
        "ffn_dim",
        "d_ff",
        "n_inner",
        "decoder_ffn_dim",
        "inner_hidden_size",
    )

    auto_map_raw = config.get("auto_map")
    auto_map = (
        {str(k): str(v) for k, v in auto_map_raw.items() if isinstance(v, str)}
        if isinstance(auto_map_raw, dict)
        else {}
    )

    issues: list[Issue] = []
    if not architectures:
        issues.append(
            Issue(
                "missing_architectures",
                "config.json does not declare an architecture.",
                "warning",
            )
        )
    if auto_map:
        custom = any(
            not value.startswith("transformers.") for value in auto_map.values()
        )
        if custom:
            issues.append(
                Issue(
                    "trust_remote_code_required",
                    "This repo maps model classes to its own Python modules (auto_map). "
                    "Loading it requires trust_remote_code=True; OmniRun never executes "
                    "repo code, so confidence is reduced.",
                    "risk",
                )
            )
    if explicit_head_dim is None and head_dim is not None:
        issues.append(
            Issue(
                "derived_head_dim",
                f"head_dim was derived as hidden_size / attention_heads = {head_dim}.",
                "info",
            )
        )
    if kv_heads is None and attention_heads is not None:
        issues.append(
            Issue(
                "kv_heads_defaulted_to_heads",
                "num_key_value_heads is absent; assuming full multi-head attention (MHA).",
                "info",
            )
        )
    if torch_dtype := _str(config, "torch_dtype", "dtype"):
        normalized = _DTYPE_ALIASES.get(torch_dtype.lower(), torch_dtype.lower())
        if normalized not in DTYPE_BYTES:
            issues.append(
                Issue(
                    "unknown_torch_dtype",
                    f"Unrecognized torch_dtype {torch_dtype!r}; KV dtype is unclear.",
                    "warning",
                )
            )
    else:
        issues.append(
            Issue(
                "missing_torch_dtype",
                "config.json does not declare torch_dtype; v1 assumes 2-byte KV cache.",
                "warning",
            )
        )

    if quantization := _quantization(config):
        issues.append(
            Issue(
                "quantized_checkpoint",
                f"Checkpoint declares quantization ({quantization.method or 'unknown'}"
                f"{', ' + str(quantization.bits) + '-bit' if quantization.bits else ''}). "
                "Weight bytes come from actual files; hypothetical alternatives are separate.",
                "info",
            )
        )

    if model_type in {"mamba", "mamba2", "rwkv", "rwkv7"}:
        issues.append(
            Issue(
                "state_space_model",
                "This is a state-space/linear-attention model, not a standard "
                "transformer KV-cache architecture. v1 fit/speed estimates are UNKNOWN.",
                "risk",
            )
        )

    if is_encoder_decoder:
        issues.append(
            Issue(
                "encoder_decoder",
                "Encoder-decoder model: v1 estimates decoder self-attention KV only. "
                "Cross-attention and ASR/TTS behavior are handled separately.",
                "info",
            )
        )

    sliding_window = _int(config, "sliding_window", "sliding_window_size")
    layer_types = _layer_types(config)
    if sliding_window or layer_types:
        issues.append(
            Issue(
                "windowed_attention",
                "Some layers use windowed attention; KV cache is bounded per layer "
                "where the config makes the pattern unambiguous.",
                "info",
            )
        )

    moe = _moe(config)
    if moe:
        issues.append(
            Issue(
                "moe_model",
                f"Mixture-of-experts: {moe.num_experts} experts, top-{moe.experts_per_token} "
                "active per token. Speed uses active weights only.",
                "info",
            )
        )
    mla = _mla(config)
    if mla:
        issues.append(
            Issue(
                "mla_attention",
                "Multi-head latent attention detected. KV cache uses the compressed "
                "latent formula; layout differs by runtime, so confidence is LOW.",
                "warning",
            )
        )

    return ModelConfig(
        architectures=architectures,
        model_type=model_type,
        layers=layers,
        hidden_size=hidden_size,
        attention_heads=attention_heads,
        kv_heads=kv_heads,
        head_dim=head_dim,
        max_positions=max_positions,
        vocab_size=vocab_size,
        intermediate_size=intermediate_size,
        torch_dtype=_str(config, "torch_dtype", "dtype"),
        transformers_version=_str(config, "transformers_version"),
        quantization=quantization,
        auto_map=auto_map,
        tie_word_embeddings=_bool(config, "tie_word_embeddings"),
        is_encoder_decoder=is_encoder_decoder,
        sliding_window=sliding_window,
        sliding_window_pattern=_int(config, "sliding_window_pattern"),
        layer_types=layer_types,
        moe=moe,
        mla=mla,
        issues=tuple(issues),
    )
