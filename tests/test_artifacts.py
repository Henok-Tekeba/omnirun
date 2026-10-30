from __future__ import annotations

from core.artifacts import (
    ArtifactFormat,
    discover_artifacts,
    has_multiple_gguf_artifacts,
    primary_gguf_artifact,
)
from core.hf_client import HFRepo, RepoFile

GIB = 1024**3


def make_repo(files: dict[str, int | None]) -> HFRepo:
    return HFRepo(
        repo_id="org/model",
        requested_repo_id="org/model",
        sha="a" * 40,
        files={
            path: RepoFile(path=path, size=size)
            for path, size in files.items()
        },
    )


def test_discover_groups_split_gguf_and_orders_artifacts() -> None:
    repo = make_repo(
        {
            "model-Q4_K_M-00001-of-00002.gguf": 2 * GIB,
            "model-Q4_K_M-00002-of-00002.gguf": 2 * GIB,
            "model-Q8_0.gguf": 8 * GIB,
            "model.safetensors": 16 * GIB,
            "onnx/model_q4.onnx": 2 * GIB,
            "ct2/model.bin": 1 * GIB,
            "ct2/shared_vocabulary.txt": 100,
            "adapter_config.json": 100,
            "adapter_model.safetensors": 50 * 1024**2,
            "README.md": 100,
        }
    )

    artifacts = discover_artifacts(repo)
    by_path = {artifact.path: artifact for artifact in artifacts}

    assert "model-Q4_K_M.gguf" in by_path
    q4 = by_path["model-Q4_K_M.gguf"]
    assert q4.format == ArtifactFormat.GGUF
    assert q4.quantization == "Q4_K_M"
    assert q4.size_bytes == 4 * GIB
    assert q4.files_count == 2
    assert q4.runtime_hint == "llama.cpp"
    assert q4.direct is True

    assert by_path["model-Q8_0.gguf"].quantization == "Q8_0"
    assert by_path["model.safetensors"].format == ArtifactFormat.SAFETENSORS
    assert by_path["onnx/model_q4.onnx"].format == ArtifactFormat.ONNX
    assert by_path["onnx/model_q4.onnx"].direct is False
    assert by_path["ct2/model.bin"].format == ArtifactFormat.CTRANSLATE2
    assert by_path["adapter_config.json"].format == ArtifactFormat.ADAPTER
    assert "adapter_model.safetensors" not in by_path
    assert "README.md" not in by_path

    # GGUF variants come first, then the base checkpoint, then other formats.
    assert [artifact.format for artifact in artifacts[:2]] == [
        ArtifactFormat.GGUF,
        ArtifactFormat.GGUF,
    ]
    assert artifacts[0].path == "model-Q4_K_M.gguf"


def test_primary_gguf_is_smallest_variant() -> None:
    repo = make_repo(
        {
            "model-Q8_0.gguf": 8 * GIB,
            "model-Q4_K_M.gguf": 4 * GIB,
        }
    )
    primary = primary_gguf_artifact(repo)
    assert primary is not None
    assert primary.path == "model-Q4_K_M.gguf"
    assert has_multiple_gguf_artifacts(repo) is True


def test_onnx_quant_labels_are_read_from_filenames() -> None:
    repo = make_repo(
        {
            "onnx/model_q4f16.onnx": 1,
            "onnx/model_q4.onnx": 1,
            "onnx/model_quantized.onnx": 1,
        }
    )
    labels = {artifact.path: artifact.quantization for artifact in discover_artifacts(repo)}
    assert labels["onnx/model_q4f16.onnx"] == "Q4F16"
    assert labels["onnx/model_q4.onnx"] == "Q4"
    assert labels["onnx/model_quantized.onnx"] == "QUANTIZED"


def test_missing_size_is_not_invented() -> None:
    repo = make_repo({"model-Q4_K_M.gguf": None})
    artifact = discover_artifacts(repo)[0]
    assert artifact.size_bytes is None
    assert artifact.quantization == "Q4_K_M"


def test_no_gguf_returns_none() -> None:
    repo = make_repo({"model.safetensors": 1 * GIB})
    assert primary_gguf_artifact(repo) is None
    assert has_multiple_gguf_artifacts(repo) is False
