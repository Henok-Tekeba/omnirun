"""Actual model artifacts present in a Hugging Face repo.

This is deliberately metadata-only: paths and file sizes from the HF tree. It
does not download weights and it does not claim a runtime can load an artifact
unless the artifact format is in the v1 support matrix.

The shelf exists because hypothetical quantization alternatives are useful, but
"there is a real Q4_K_M file and here is its size" is much more useful.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.hf_client import HFRepo
from core.inspect.types import Confidence

MAX_ARTIFACTS = 32


class ArtifactFormat(StrEnum):
    GGUF = "gguf"
    SAFETENSORS = "safetensors"
    PYTORCH_PICKLE = "pytorch_pickle"
    CTRANSLATE2 = "ctranslate2"
    ONNX = "onnx"
    ADAPTER = "adapter"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    path: str
    files: tuple[str, ...]
    format: ArtifactFormat
    quantization: str | None
    size_bytes: int | None
    runtime_hint: str | None
    direct: bool
    confidence: Confidence
    note: str

    @property
    def files_count(self) -> int:
        return len(self.files)


_QUANT_RE = re.compile(
    r"(?i)(IQ\d+_[A-Z]+|Q\d+_K_[SML]|Q\d+_K|Q\d+_\d|Q\d+_[A-Z]+|"
    r"F16|BF16|F32|FP16|FP8|INT8|INT4|UINT8|BNB4|AWQ|GPTQ|4BIT|8BIT|MXFP4)"
)
_SHARD_RE = re.compile(
    r"^(?P<base>.+?)-\d{5}-of-\d{5}(?P<ext>\.(?:gguf|safetensors|bin|pth))$",
    re.IGNORECASE,
)
_PICKLE_RE = re.compile(
    r"(?:^|/)pytorch_model(?:-\d{5}-of-\d{5})?\.bin$"
    r"|(?:^|/)consolidated\.\d+\.pth$"
    r"|(?:^|/)model\.pt$",
    re.IGNORECASE,
)
_ADAPTER_WEIGHT_RE = re.compile(r"(?:^|/)adapter_model\.(?:safetensors|bin)$", re.IGNORECASE)
_CT2_AUX_NAMES = {"shared_vocabulary.txt", "vocabulary.txt", "config.json"}

_FORMAT_ORDER = {
    ArtifactFormat.GGUF: 0,
    ArtifactFormat.SAFETENSORS: 1,
    ArtifactFormat.ONNX: 2,
    ArtifactFormat.CTRANSLATE2: 3,
    ArtifactFormat.PYTORCH_PICKLE: 4,
    ArtifactFormat.ADAPTER: 5,
    ArtifactFormat.UNKNOWN: 6,
}


def _group_key(path: str) -> str:
    match = _SHARD_RE.match(path)
    if match:
        return match.group("base") + match.group("ext")
    return path


def _quantization(path: str) -> str | None:
    lowered = path.lower()
    match = _QUANT_RE.search(path)
    if match:
        value = match.group(1).upper()
        if value == "F16" and "q4f16" in lowered:
            return "Q4F16"
        if value == "F16" and "q8f16" in lowered:
            return "Q8F16"
        return value
    for token, label in (
        ("q4f16", "Q4F16"),
        ("q4", "Q4"),
        ("q8", "Q8"),
        ("quantized", "QUANTIZED"),
    ):
        if token in lowered:
            return label
    return None


def _size(repo: HFRepo, files: tuple[str, ...]) -> int | None:
    sizes = [repo.file(path).size if repo.file(path) else None for path in files]
    if any(size is None for size in sizes):
        return None
    return sum(size for size in sizes if size is not None)


def _gguf_artifact(repo: HFRepo, path: str, files: tuple[str, ...]) -> ArtifactInfo:
    return ArtifactInfo(
        path=path,
        files=files,
        format=ArtifactFormat.GGUF,
        quantization=_quantization(path),
        size_bytes=_size(repo, files),
        runtime_hint="llama.cpp",
        direct=True,
        confidence=Confidence.LOW,
        note=(
            "GGUF file. Size includes metadata, so the memory estimate is an upper bound. "
            "Runtime support depends on the llama.cpp version."
        ),
    )


def _safetensors_artifact(repo: HFRepo, path: str, files: tuple[str, ...]) -> ArtifactInfo:
    lowered = path.lower()
    quant = _quantization(path)
    if "mlx" in lowered:
        runtime = "MLX"
        direct = False
        note = "MLX checkpoint. Not covered by the v1 support matrix."
    elif quant in {"AWQ", "GPTQ"}:
        runtime = "vLLM"
        direct = False
        note = (
            f"{quant} checkpoint. Not covered by the v1 support matrix; "
            "check the runtime separately."
        )
    elif quant is not None:
        runtime = "transformers"
        direct = True
        note = "Quantized safetensors checkpoint. File size is an upper bound."
    else:
        runtime = "transformers"
        direct = True
        note = "Safetensors checkpoint. File size is an upper bound on weight bytes."
    return ArtifactInfo(
        path=path,
        files=files,
        format=ArtifactFormat.SAFETENSORS,
        quantization=quant,
        size_bytes=_size(repo, files),
        runtime_hint=runtime,
        direct=direct,
        confidence=Confidence.LOW,
        note=note,
    )


def _pickle_artifact(repo: HFRepo, path: str, files: tuple[str, ...]) -> ArtifactInfo:
    return ArtifactInfo(
        path=path,
        files=files,
        format=ArtifactFormat.PYTORCH_PICKLE,
        quantization=None,
        size_bytes=_size(repo, files),
        runtime_hint="transformers",
        direct=True,
        confidence=Confidence.LOW,
        note="Pickle checkpoint. Never read by OmniRun; file size is an upper bound.",
    )


def _onnx_artifact(repo: HFRepo, path: str) -> ArtifactInfo:
    quant = _quantization(path)
    return ArtifactInfo(
        path=path,
        files=(path,),
        format=ArtifactFormat.ONNX,
        quantization=quant,
        size_bytes=_size(repo, (path,)),
        runtime_hint="ONNX Runtime",
        direct=False,
        confidence=Confidence.LOW,
        note="ONNX artifact. Not covered by the v1 support matrix.",
    )


def _ct2_artifact(repo: HFRepo, path: str, files: tuple[str, ...]) -> ArtifactInfo:
    return ArtifactInfo(
        path=path,
        files=files,
        format=ArtifactFormat.CTRANSLATE2,
        quantization=None,
        size_bytes=_size(repo, files),
        runtime_hint="CTranslate2",
        direct=True,
        confidence=Confidence.LOW,
        note="CTranslate2 model file. The runtime path depends on the architecture.",
    )


def _adapter_artifact(repo: HFRepo, path: str, files: tuple[str, ...]) -> ArtifactInfo:
    return ArtifactInfo(
        path=path,
        files=files,
        format=ArtifactFormat.ADAPTER,
        quantization=None,
        size_bytes=None,
        runtime_hint="PEFT",
        direct=False,
        confidence=Confidence.LOW,
        note="Adapter, not a standalone model. It needs a base model.",
    )


def discover_artifacts(repo: HFRepo) -> tuple[ArtifactInfo, ...]:
    """Return actual weight artifacts in the repo, largest decision value first.

    The scan uses only the HF file tree. Sizes are summed only when every shard
    has a size; otherwise the artifact is kept with ``size_bytes=None`` so the
    UI can say "unknown" instead of inventing a number.
    """
    paths = repo.filenames()
    path_set = set(paths)
    groups: dict[str, list[str]] = {}
    onnx_paths: list[str] = []

    for path in paths:
        lowered = path.lower()
        if lowered.endswith(".gguf"):
            groups.setdefault(_group_key(path), []).append(path)
        elif lowered.endswith(".safetensors"):
            if "adapter_config.json" in path_set and _ADAPTER_WEIGHT_RE.search(path):
                continue
            groups.setdefault(_group_key(path), []).append(path)
        elif lowered.endswith(".onnx"):
            onnx_paths.append(path)
        elif lowered.endswith("/model.bin") or lowered == "model.bin":
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            siblings = {
                item.rsplit("/", 1)[-1] if "/" in item else item
                for item in paths
                if (item.rsplit("/", 1)[0] if "/" in item else "") == parent
            }
            if siblings & _CT2_AUX_NAMES:
                groups.setdefault(f"{parent}/model.bin" if parent else path, []).append(path)
            else:
                groups.setdefault(_group_key(path), []).append(path)
        elif _PICKLE_RE.search(path):
            groups.setdefault(_group_key(path), []).append(path)

    artifacts: list[ArtifactInfo] = []
    for group_path, files in groups.items():
        ordered = tuple(sorted(files))
        lowered = group_path.lower()
        if lowered.endswith(".gguf"):
            artifacts.append(_gguf_artifact(repo, group_path, ordered))
        elif lowered.endswith(".safetensors"):
            artifacts.append(_safetensors_artifact(repo, group_path, ordered))
        elif lowered.endswith("/model.bin") or lowered == "model.bin":
            artifacts.append(_ct2_artifact(repo, group_path, ordered))
        elif lowered.endswith((".bin", ".pth")):
            artifacts.append(_pickle_artifact(repo, group_path, ordered))

    for path in onnx_paths:
        artifacts.append(_onnx_artifact(repo, path))

    if "adapter_config.json" in path_set:
        adapter_files = tuple(
            sorted(path for path in paths if _ADAPTER_WEIGHT_RE.search(path))
        )
        artifacts.append(
            _adapter_artifact(
                repo,
                "adapter_config.json",
                adapter_files or ("adapter_config.json",),
            )
        )

    artifacts.sort(
        key=lambda artifact: (
            _FORMAT_ORDER[artifact.format],
            artifact.size_bytes if artifact.size_bytes is not None else 2**63,
            artifact.path,
        )
    )
    return tuple(artifacts[:MAX_ARTIFACTS])


def primary_gguf_artifact(repo: HFRepo) -> ArtifactInfo | None:
    """The smallest GGUF artifact, used as the default single-file result.

    A repo with several quants should not sum all of them into one impossible
    model. The smallest file is the conservative default; the artifact shelf
    lets the caller inspect the rest.
    """
    gguf = [
        artifact
        for artifact in discover_artifacts(repo)
        if artifact.format == ArtifactFormat.GGUF
    ]
    if not gguf:
        return None
    sized = [artifact for artifact in gguf if artifact.size_bytes is not None]
    if sized:
        return min(sized, key=lambda artifact: artifact.size_bytes or 0)
    return gguf[0]


def has_multiple_gguf_artifacts(repo: HFRepo) -> bool:
    return (
        len(
            [
                artifact
                for artifact in discover_artifacts(repo)
                if artifact.format == ArtifactFormat.GGUF
            ]
        )
        > 1
    )


__all__ = [
    "MAX_ARTIFACTS",
    "ArtifactFormat",
    "ArtifactInfo",
    "discover_artifacts",
    "has_multiple_gguf_artifacts",
    "primary_gguf_artifact",
]
