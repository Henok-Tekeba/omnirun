from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from core.estimate import GIB, estimate_kv_cache, estimate_memory
from core.inspect.config import parse_config
from core.inspect.model import inspect_model
from tests.hf_fixtures import fixture_client, load_json


def base_config(**overrides):
    data = {
        "architectures": ["LlamaForCausalLM"],
        "num_hidden_layers": 2,
        "hidden_size": 32,
        "num_attention_heads": 4,
        "num_key_value_heads": 4,
        "max_position_embeddings": 128,
        "vocab_size": 100,
        "intermediate_size": 64,
        "torch_dtype": "float16",
    }
    data.update(overrides)
    return parse_config(data)


def test_kv_mha_vs_gqa_hand_computed() -> None:
    mha = estimate_kv_cache(base_config(), context=16, batch=1)
    assert mha.available
    assert mha.bytes_likely == 4096
    assert mha.attention == "mha"

    gqa = estimate_kv_cache(
        base_config(num_key_value_heads=2), context=16, batch=1
    )
    assert gqa.bytes_likely == 2048
    assert gqa.attention == "gqa"

    mqa = estimate_kv_cache(
        base_config(num_key_value_heads=1), context=16, batch=1
    )
    assert mqa.bytes_likely == 1024
    assert mqa.attention == "mqa"


def test_kv_batch_multiplies_total_but_not_per_sequence() -> None:
    batch1 = estimate_kv_cache(base_config(), context=16, batch=1)
    batch3 = estimate_kv_cache(base_config(), context=16, batch=3)
    assert batch3.bytes_likely == batch1.bytes_likely * 3
    assert batch3.per_sequence_likely == batch1.per_sequence_likely


def test_kv_sliding_window_range() -> None:
    config = base_config(
        num_hidden_layers=4,
        max_position_embeddings=16,
        sliding_window=8,
        sliding_window_pattern=2,
    )
    kv = estimate_kv_cache(config, context=16, batch=1)
    # bounded tokens: 8 + 16 + 8 + 16 = 48; full: 64
    # per-token-per-layer = 2*4*8 = 64 bytes; * 2 bytes dtype
    assert kv.layers_windowed == 2
    assert kv.layers_full == 2
    assert kv.bytes_range is not None
    assert kv.bytes_range.min == 48 * 64 * 2
    assert kv.bytes_range.likely == 48 * 64 * 2
    assert kv.bytes_range.max == 64 * 64 * 2
    assert kv.confidence.value == "medium"


def test_kv_context_is_clamped() -> None:
    config = parse_config(load_json("smollm2_135m", "config.json"))
    kv = estimate_kv_cache(config, context=10_000, batch=1)
    assert kv.context_effective == 8192
    assert any(issue.code == "context_clamped" for issue in kv.issues)


def test_kv_mla_formula() -> None:
    config = parse_config(
        {
            "architectures": ["DeepseekV3ForCausalLM"],
            "model_type": "deepseek_v3",
            "num_hidden_layers": 61,
            "hidden_size": 7168,
            "num_attention_heads": 128,
            "num_key_value_heads": 128,
            "head_dim": 128,
            "max_position_embeddings": 4096,
            "torch_dtype": "bfloat16",
            "kv_lora_rank": 512,
            "qk_rope_head_dim": 64,
        }
    )
    kv = estimate_kv_cache(config, context=4096, batch=1)
    assert kv.attention == "mla"
    assert kv.bytes_likely == 61 * (512 + 64) * 2 * 4096
    assert kv.confidence.value == "low"


def test_kv_missing_dtype_has_range() -> None:
    config = replace(base_config(), torch_dtype=None)
    kv = estimate_kv_cache(config, context=16, batch=1)
    assert kv.bytes_range is not None
    assert kv.bytes_range.min == kv.bytes_range.likely < kv.bytes_range.max
    assert any(issue.code == "kv_dtype_assumed" for issue in kv.issues)


async def test_memory_estimate_exact_weights(tmp_path: Path) -> None:
    async with fixture_client("smollm2_135m", tmp_path) as client:
        inspection = await inspect_model(client, "HuggingFaceTB/SmolLM2-135M-Instruct")
    memory = estimate_memory(inspection, context=4096, batch=1)

    assert memory.weights.kind == "exact"
    assert memory.weights.range is not None
    assert memory.weights.range.min == memory.weights.range.max
    assert memory.kv.bytes_likely == 94_371_840
    assert memory.peak is not None
    assert memory.peak.min < memory.peak.likely < memory.peak.max
    expected_overhead = 0.25 * GIB + 0.10 * memory.weights.range.likely
    assert math.isclose(
        memory.peak.likely,
        memory.weights.range.likely + memory.kv.bytes_likely + expected_overhead,
        rel_tol=0,
        abs_tol=2,
    )
    assert memory.confidence.value in {"medium", "low"}


async def test_quantization_alternatives_are_hypothetical(tmp_path: Path) -> None:
    async with fixture_client("smollm2_135m", tmp_path) as client:
        inspection = await inspect_model(client, "HuggingFaceTB/SmolLM2-135M-Instruct")
    memory = estimate_memory(inspection, context=4096, batch=1)
    alternatives = {item.name: item for item in memory.weights.alternatives}
    params = memory.weights.params
    assert params is not None
    assert alternatives["fp16"].weight_bytes == round(params * 2.0)
    assert alternatives["int8"].weight_bytes == round(params * 1.01)
    assert alternatives["4bit"].weight_bytes == round(params * 0.5625)
    assert all(item.confidence.value == "high" for item in alternatives.values())


async def test_pickle_memory_is_an_upper_bound(tmp_path: Path) -> None:
    async with fixture_client("opt_350m", tmp_path) as client:
        inspection = await inspect_model(client, "facebook/opt-350m")
    memory = estimate_memory(inspection, context=2048, batch=1)
    assert memory.weights.kind == "upper_bound"
    assert memory.weights.range is not None
    assert memory.weights.range.min == 0
    assert memory.weights.range.max == memory.weights.actual_bytes
    assert memory.peak is not None
    assert memory.peak.min < memory.peak.likely
    assert any(issue.code == "weights_upper_bound" for issue in memory.issues)


def test_invalid_context_rejected() -> None:
    with pytest.raises(ValueError):
        estimate_kv_cache(base_config(), context=0, batch=1)
    with pytest.raises(ValueError):
        estimate_kv_cache(base_config(), context=1, batch=0)
