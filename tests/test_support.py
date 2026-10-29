from __future__ import annotations

from pathlib import Path

from core.claims import ClaimStatus
from core.hf_client import HFRepo, RepoFile
from core.inspect.config import parse_config
from core.inspect.model import ModelFormat, ModelInspection, inspect_model
from core.inspect.types import Confidence
from core.support import build_support_claim, load_support_matrix
from tests.hf_fixtures import fixture_client, load_json


def fake_inspection(
    *,
    architecture_config: dict,
    files: dict[str, int],
    fmt: ModelFormat,
    weight_bytes: int | None = 1_000_000,
    pipeline_tag: str = "text-generation",
) -> ModelInspection:
    repo = HFRepo(
        repo_id="org/model",
        requested_repo_id="org/model",
        sha="a" * 40,
        pipeline_tag=pipeline_tag,
        library_name="transformers",
        files={path: RepoFile(path=path, size=size) for path, size in files.items()},
    )
    config = parse_config(architecture_config)
    return ModelInspection(
        repo=repo,
        config=config,
        config_raw=architecture_config,
        format=fmt,
        safetensors=None,
        pickle=None,
        gguf=None,
        weight_bytes=weight_bytes,
        weight_bytes_exact=fmt == ModelFormat.SAFETENSORS,
        params=None,
        param_source=None,
        active_weight_bytes=weight_bytes,
        active_weight_source="exact_weights",
        confidence=Confidence.HIGH,
        issues=(),
    )


def test_support_matrix_loads() -> None:
    matrix = load_support_matrix()
    entry, matched_by = matrix.lookup("LlamaForCausalLM", "llama")
    assert entry is not None
    assert matched_by == "architecture"
    assert {runtime.name for runtime in entry.runtimes} == {"transformers", "llama.cpp"}
    assert matrix.lookup("UnknownForCausalLM", None)[0] is None
    assert matrix.lookup(None, "whisper")[0] is not None


def test_support_matrix_rejects_bad_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("version: 2\narchitectures: {}\n", encoding="utf-8")
    try:
        load_support_matrix(path)
    except Exception as exc:
        assert getattr(exc, "code", None) == "support_matrix_invalid"
    else:  # pragma: no cover
        raise AssertionError("bad matrix accepted")


async def test_smollm_support_has_direct_transformers(tmp_path: Path) -> None:
    async with fixture_client("smollm2_135m", tmp_path) as client:
        inspection = await inspect_model(client, "HuggingFaceTB/SmolLM2-135M-Instruct")
    claim = build_support_claim(inspection, load_support_matrix())
    assert claim.status == ClaimStatus.YES
    assert claim.direct_runtime_available is True
    paths = {path.name: path for path in claim.runtimes}
    assert paths["transformers"].available is True
    assert paths["transformers"].status == "available"
    assert paths["llama.cpp"].status == "requires_conversion"
    assert paths["transformers"].min_version == "4.28.0"


def test_custom_architecture_is_unknown() -> None:
    inspection = fake_inspection(
        architecture_config=load_json("chatglm3", "config.json"),
        files={"config.json": 10, "model.safetensors": 100},
        fmt=ModelFormat.SAFETENSORS,
    )
    claim = build_support_claim(inspection, load_support_matrix())
    assert claim.status == ClaimStatus.UNKNOWN
    assert claim.matrix_entry_found is False
    assert claim.custom_code_risk is True
    assert any(issue.code == "architecture_not_in_support_matrix" for issue in claim.reasons)


def test_whisper_support_paths() -> None:
    inspection = fake_inspection(
        architecture_config=load_json("whisper_tiny", "config.json"),
        files={"config.json": 10, "model.safetensors": 100},
        fmt=ModelFormat.SAFETENSORS,
        pipeline_tag="automatic-speech-recognition",
    )
    claim = build_support_claim(inspection, load_support_matrix())
    assert claim.status == ClaimStatus.YES
    paths = {path.name: path for path in claim.runtimes}
    assert paths["transformers"].status == "available"
    assert paths["whisper.cpp"].status == "requires_conversion"
    assert paths["ctranslate2"].status == "requires_conversion"


def test_gguf_llama_uses_direct_llama_cpp() -> None:
    inspection = fake_inspection(
        architecture_config={
            "architectures": ["LlamaForCausalLM"],
            "model_type": "llama",
            "num_hidden_layers": 2,
            "hidden_size": 32,
            "num_attention_heads": 4,
            "num_key_value_heads": 2,
            "head_dim": 8,
            "max_position_embeddings": 128,
            "torch_dtype": "float16",
        },
        files={"model.gguf": 100},
        fmt=ModelFormat.GGUF,
        weight_bytes=100,
    )
    claim = build_support_claim(inspection, load_support_matrix())
    assert claim.status == ClaimStatus.YES
    assert claim.direct_runtime_available is True
    paths = {path.name: path for path in claim.runtimes}
    assert paths["llama.cpp"].status == "available"
    assert paths["transformers"].status == "artifact_missing"


def test_t5_gguf_is_conversion_only() -> None:
    inspection = fake_inspection(
        architecture_config={
            "architectures": ["T5ForConditionalGeneration"],
            "model_type": "t5",
            "num_layers": 2,
            "d_model": 32,
            "num_heads": 4,
            "max_position_embeddings": 128,
        },
        files={"model.gguf": 100},
        fmt=ModelFormat.GGUF,
        weight_bytes=100,
    )
    claim = build_support_claim(inspection, load_support_matrix())
    assert claim.status == ClaimStatus.YES
    assert claim.direct_runtime_available is False
    paths = {path.name: path for path in claim.runtimes}
    assert paths["ctranslate2"].status == "requires_conversion"


def test_adapter_is_not_supported() -> None:
    inspection = fake_inspection(
        architecture_config={
            "architectures": ["LlamaForCausalLM"],
            "num_hidden_layers": 2,
        },
        files={"adapter_config.json": 10, "adapter_model.safetensors": 100},
        fmt=ModelFormat.ADAPTER,
        weight_bytes=None,
    )
    claim = build_support_claim(inspection, load_support_matrix())
    assert claim.status == ClaimStatus.UNKNOWN
    assert claim.matrix_entry_found is False
