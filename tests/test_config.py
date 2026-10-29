from __future__ import annotations

from core.inspect.config import parse_config
from tests.hf_fixtures import load_json


def codes(config) -> set[str]:
    return {issue.code for issue in config.issues}


def test_smollm_config() -> None:
    config = parse_config(load_json("smollm2_135m", "config.json"))
    assert config.primary_architecture == "LlamaForCausalLM"
    assert config.layers == 30
    assert config.hidden_size == 576
    assert config.attention_heads == 9
    assert config.kv_heads == 3
    assert config.head_dim_effective == 64
    assert config.max_positions == 8192
    assert config.dtype_bytes == 2
    assert config.tie_word_embeddings is True
    assert config.sliding_window is None
    assert "derived_head_dim" in codes(config)
    assert config.kv_estimation_issues


def test_mistral_config_gqa_and_sliding_window() -> None:
    config = parse_config(load_json("mistral_7b", "config.json"))
    assert config.primary_architecture == "MistralForCausalLM"
    assert config.layers == 32
    assert config.head_dim_effective == 128
    assert config.kv_heads_effective == 8
    assert config.sliding_window == 4096
    assert config.sliding_window_for_layer(0) == 4096
    assert config.sliding_window_for_layer(31) == 4096
    assert config.is_sliding_window is True
    assert "windowed_attention" in codes(config)


def test_gemma_style_sliding_pattern() -> None:
    config = parse_config(
        {
            "architectures": ["Gemma3ForCausalLM"],
            "num_hidden_layers": 6,
            "hidden_size": 256,
            "num_attention_heads": 4,
            "num_key_value_heads": 2,
            "head_dim": 64,
            "max_position_embeddings": 32768,
            "sliding_window": 512,
            "sliding_window_pattern": 6,
            "torch_dtype": "bfloat16",
        }
    )
    assert [config.sliding_window_for_layer(i) for i in range(6)] == [512] * 5 + [None]


def test_chatglm_custom_architecture_and_fields() -> None:
    config = parse_config(load_json("chatglm3", "config.json"))
    assert config.primary_architecture == "ChatGLMModel"
    assert config.trust_remote_code_required is True
    assert config.layers == 28
    assert config.hidden_size == 4096
    assert config.attention_heads == 32
    assert config.kv_heads_effective == 2
    assert config.head_dim_effective == 128
    assert config.intermediate_size == 13696
    assert config.max_positions == 8192
    assert "trust_remote_code_required" in codes(config)


def test_whisper_encoder_decoder_fields() -> None:
    config = parse_config(load_json("whisper_tiny", "config.json"))
    assert config.primary_architecture == "WhisperForConditionalGeneration"
    assert config.is_encoder_decoder is True
    assert config.layers == 4
    assert config.hidden_size == 384
    assert config.attention_heads == 6
    assert config.head_dim_effective == 64
    assert config.max_positions == 448
    assert "encoder_decoder" in codes(config)


def test_missing_fields_do_not_guess() -> None:
    config = parse_config({"architectures": ["MysteryForCausalLM"], "torch_dtype": "bfloat16"})
    assert config.layers is None
    assert config.kv_estimation_issues
    assert any(issue.code == "missing_kv_field" for issue in config.kv_estimation_issues)


def test_state_space_model_flagged() -> None:
    config = parse_config(
        {
            "architectures": ["MambaForCausalLM"],
            "model_type": "mamba",
            "num_hidden_layers": 24,
            "hidden_size": 768,
            "torch_dtype": "float32",
        }
    )
    assert "state_space_model" in codes(config)
