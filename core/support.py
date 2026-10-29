"""Support matrix: architecture + runtime paths.

SUPPORTED means a documented runtime path exists, with a minimum version floor.
It does not mean VERIFIED: no real run is implied.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from core.claims import ClaimStatus
from core.errors import InputError
from core.inspect.model import ModelFormat, ModelInspection
from core.inspect.types import Confidence, Issue

_ARTIFACTS = {"hf_checkpoint", "gguf", "ggml", "ctranslate2"}
_RUNTIMES = {"transformers", "llama.cpp", "whisper.cpp", "ctranslate2"}


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    name: str
    min_version: str
    version_scheme: str
    artifact: str
    conversion_supported: bool
    source: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class ArchitectureSupport:
    architecture: str
    display_name: str
    model_types: tuple[str, ...]
    runtimes: tuple[RuntimeSpec, ...]


@dataclass(frozen=True, slots=True)
class SupportMatrix:
    architectures: Mapping[str, ArchitectureSupport]
    by_model_type: Mapping[str, ArchitectureSupport]
    version: int
    updated: str | None

    def lookup(
        self, architecture: str | None, model_type: str | None
    ) -> tuple[ArchitectureSupport | None, str | None]:
        if architecture and architecture in self.architectures:
            return self.architectures[architecture], "architecture"
        if model_type and model_type in self.by_model_type:
            return self.by_model_type[model_type], "model_type"
        return None, None


@dataclass(frozen=True, slots=True)
class RuntimePath:
    name: str
    min_version: str
    version_scheme: str
    artifact: str
    available: bool
    status: str  # available | requires_conversion | artifact_missing
    direct: bool
    notes: str | None
    source: str | None


@dataclass(frozen=True, slots=True)
class SupportClaim:
    status: ClaimStatus
    confidence: Confidence
    summary: str
    reasons: tuple[Issue, ...]
    architecture: str | None
    matched_by: str | None
    matrix_entry_found: bool
    direct_runtime_available: bool
    runtimes: tuple[RuntimePath, ...]
    custom_code_risk: bool


def default_support_path() -> Path:
    import os

    override = os.environ.get("OMNIRUN_DATA_DIR")
    if override:
        return Path(override).expanduser() / "support_matrix.yaml"
    return Path(__file__).resolve().parents[1] / "data" / "support_matrix.yaml"


def load_support_matrix(path: str | Path | None = None) -> SupportMatrix:
    source_path = Path(path) if path is not None else default_support_path()
    try:
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(
            "The support matrix is missing.",
            code="support_matrix_missing",
            hint=f"Expected {source_path}.",
        ) from exc
    except yaml.YAMLError as exc:
        raise InputError(
            "The support matrix is not valid YAML.",
            code="support_matrix_invalid",
            hint=str(exc),
        ) from exc
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise InputError(
            "The support matrix has an unsupported version.",
            code="support_matrix_invalid",
        )
    entries = raw.get("architectures")
    if not isinstance(entries, dict) or not entries:
        raise InputError("The support matrix has no architectures.", code="support_matrix_invalid")

    architectures: dict[str, ArchitectureSupport] = {}
    by_model_type: dict[str, ArchitectureSupport] = {}
    for architecture, item in entries.items():
        if not isinstance(architecture, str) or not isinstance(item, dict):
            raise InputError("A support matrix entry is invalid.", code="support_matrix_invalid")
        runtimes_raw = item.get("runtimes")
        if not isinstance(runtimes_raw, list) or not runtimes_raw:
            raise InputError(
                f"Architecture {architecture!r} has no runtimes.",
                code="support_matrix_invalid",
            )
        runtimes: list[RuntimeSpec] = []
        seen_names: set[str] = set()
        for runtime in runtimes_raw:
            if not isinstance(runtime, dict):
                raise InputError(
                    f"Architecture {architecture!r} has an invalid runtime.",
                    code="support_matrix_invalid",
                )
            name = str(runtime.get("name", "")).strip()
            if name not in _RUNTIMES or name in seen_names:
                raise InputError(
                    f"Architecture {architecture!r} has an invalid runtime name {name!r}.",
                    code="support_matrix_invalid",
                )
            artifact = str(runtime.get("artifact", "")).strip()
            if artifact not in _ARTIFACTS:
                raise InputError(
                    f"Architecture {architecture!r} has an invalid artifact {artifact!r}.",
                    code="support_matrix_invalid",
                )
            min_version = runtime.get("min_version")
            if not isinstance(min_version, str) or not min_version.strip():
                raise InputError(
                    f"Architecture {architecture!r} runtime {name!r} has no min_version.",
                    code="support_matrix_invalid",
                )
            runtimes.append(
                RuntimeSpec(
                    name=name,
                    min_version=min_version.strip(),
                    version_scheme=str(runtime.get("version_scheme", "semver")),
                    artifact=artifact,
                    conversion_supported=bool(runtime.get("conversion_supported", False)),
                    source=str(runtime["source"]) if runtime.get("source") else None,
                    notes=str(runtime["notes"]) if runtime.get("notes") else None,
                )
            )
            seen_names.add(name)
        model_types_raw = item.get("model_types") or []
        if not isinstance(model_types_raw, list):
            raise InputError(
                f"Architecture {architecture!r} model_types must be a list.",
                code="support_matrix_invalid",
            )
        support = ArchitectureSupport(
            architecture=architecture,
            display_name=str(item.get("display_name", architecture)),
            model_types=tuple(str(value) for value in model_types_raw if isinstance(value, str)),
            runtimes=tuple(runtimes),
        )
        architectures[architecture] = support
        for model_type in support.model_types:
            existing = by_model_type.get(model_type)
            if existing is not None and existing.architecture != architecture:
                raise InputError(
                    f"model_type {model_type!r} maps to more than one architecture.",
                    code="support_matrix_invalid",
                )
            by_model_type[model_type] = support

    return SupportMatrix(
        architectures=architectures,
        by_model_type=by_model_type,
        version=1,
        updated=str(raw.get("updated")) if raw.get("updated") else None,
    )


def _artifact_available(artifact: str, inspection: ModelInspection) -> bool:
    repo = inspection.repo
    paths = repo.files
    if artifact == "hf_checkpoint":
        return inspection.format in {ModelFormat.SAFETENSORS, ModelFormat.PYTORCH_PICKLE}
    if artifact == "gguf":
        return inspection.format == ModelFormat.GGUF or any(
            path.lower().endswith(".gguf") for path in paths
        )
    if artifact == "ggml":
        return any(
            path.lower().endswith(".bin") and "ggml" in path.lower() for path in paths
        )
    if artifact == "ctranslate2":
        return repo.library_name == "ctranslate2" or (
            "model.bin" in paths and "shared_vocabulary.txt" in paths
        )
    return False


def build_support_claim(inspection: ModelInspection, matrix: SupportMatrix) -> SupportClaim:
    architecture = inspection.architecture
    model_type = inspection.config.model_type if inspection.config else None
    reasons: list[Issue] = []

    if (
        inspection.format in {ModelFormat.ADAPTER, ModelFormat.UNKNOWN}
        or inspection.weight_bytes is None
    ):
        return SupportClaim(
            status=ClaimStatus.UNKNOWN,
            confidence=Confidence.LOW,
            summary="The repo format is not one v1 can match to a runtime path.",
            reasons=(
                Issue(
                    "unsupported_artifact",
                    "Runtime support cannot be claimed without a recognized model artifact.",
                    "risk",
                ),
            ),
            architecture=architecture,
            matched_by=None,
            matrix_entry_found=False,
            direct_runtime_available=False,
            runtimes=(),
            custom_code_risk=bool(
                inspection.config and inspection.config.trust_remote_code_required
            ),
        )

    entry, matched_by = matrix.lookup(architecture, model_type)
    if entry is None:
        reasons.append(
            Issue(
                "architecture_not_in_support_matrix",
                f"{architecture or model_type or 'This architecture'} has no entry in "
                "data/support_matrix.yaml. OmniRun will not invent a runtime path.",
                "risk",
            )
        )
        return SupportClaim(
            status=ClaimStatus.UNKNOWN,
            confidence=Confidence.LOW,
            summary=(
                f"No support-matrix entry for {architecture or model_type or 'this architecture'}; "
                "SUPPORTED is unknown."
            ),
            reasons=tuple(reasons),
            architecture=architecture,
            matched_by=None,
            matrix_entry_found=False,
            direct_runtime_available=False,
            runtimes=(),
            custom_code_risk=bool(
                inspection.config and inspection.config.trust_remote_code_required
            ),
        )

    paths: list[RuntimePath] = []
    for runtime in entry.runtimes:
        available = _artifact_available(runtime.artifact, inspection)
        if available:
            status = "available"
            direct = True
        elif runtime.conversion_supported:
            status = "requires_conversion"
            direct = False
        else:
            status = "artifact_missing"
            direct = False
        paths.append(
            RuntimePath(
                name=runtime.name,
                min_version=runtime.min_version,
                version_scheme=runtime.version_scheme,
                artifact=runtime.artifact,
                available=available,
                status=status,
                direct=direct,
                notes=runtime.notes,
                source=runtime.source,
            )
        )

    # Direct/available paths first, then conversion paths, then missing.
    order = {"available": 0, "requires_conversion": 1, "artifact_missing": 2}
    paths.sort(key=lambda path: (order[path.status], path.name))
    has_any_path = any(path.status in {"available", "requires_conversion"} for path in paths)
    has_direct = any(path.status == "available" for path in paths)
    custom_risk = bool(inspection.config and inspection.config.trust_remote_code_required)

    if not has_any_path:
        reasons.append(
            Issue(
                "no_supported_artifact",
                "The architecture is known, but this repo has no artifact format the "
                "matrix can run or convert.",
                "risk",
            )
        )
        return SupportClaim(
            status=ClaimStatus.NO,
            confidence=Confidence.MEDIUM,
            summary="No supported runtime artifact is present.",
            reasons=tuple(reasons),
            architecture=architecture,
            matched_by=matched_by,
            matrix_entry_found=True,
            direct_runtime_available=False,
            runtimes=tuple(paths),
            custom_code_risk=custom_risk,
        )

    if not has_direct:
        reasons.append(
            Issue(
                "conversion_required",
                "Only runtime paths that require model conversion are available; "
                "OmniRun v1 does not convert models.",
                "warning",
            )
        )
    if custom_risk:
        reasons.append(
            Issue(
                "custom_code_runtime_risk",
                "This repo requires trust_remote_code for its own model implementation. "
                "The support matrix covers the architecture/runtime pair, not this "
                "repo's custom code.",
                "risk",
            )
        )

    available_names = [
        f"{path.name} >= {path.min_version}" for path in paths if path.status == "available"
    ]
    conversion_names = [
        f"{path.name} >= {path.min_version}"
        for path in paths
        if path.status == "requires_conversion"
    ]
    summary_parts = []
    if available_names:
        summary_parts.append("direct " + ", ".join(available_names))
    if conversion_names:
        summary_parts.append("conversion-only " + ", ".join(conversion_names))
    summary = "SUPPORTED: " + "; ".join(summary_parts) + "."
    confidence = Confidence.HIGH if has_direct and not custom_risk else Confidence.MEDIUM
    if custom_risk and not has_direct:
        confidence = Confidence.LOW
    return SupportClaim(
        status=ClaimStatus.YES,
        confidence=confidence,
        summary=summary,
        reasons=tuple(reasons),
        architecture=architecture,
        matched_by=matched_by,
        matrix_entry_found=True,
        direct_runtime_available=has_direct,
        runtimes=tuple(paths),
        custom_code_risk=custom_risk,
    )
