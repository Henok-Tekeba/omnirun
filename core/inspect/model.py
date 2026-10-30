"""Top-level model inspection orchestrator.

The contract is intentionally narrow: return what we can prove from metadata,
and record what we could not. Estimation lives in ``core.estimate``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from core.artifacts import has_multiple_gguf_artifacts, primary_gguf_artifact
from core.errors import HFError
from core.hf_client import HFClient, HFRepo
from core.inspect.config import ModelConfig, parse_config
from core.inspect.safetensors import (
    SafetensorsInspection,
    estimate_param_count_from_config,
    inspect_safetensors,
)
from core.inspect.types import Confidence, Issue

_PICKLE_INDEX = "pytorch_model.bin.index.json"
_KNOWN_PICKLE_RE = re.compile(
    r"(?:^|/)pytorch_model(?:-\d{5}-of-\d{5})?\.bin$"
    r"|(?:^|/)model\.bin$"
    r"|(?:^|/)consolidated\.\d+\.pth$"
)
_NON_MODEL_BIN_RE = re.compile(
    r"(training_args|optimizer|scheduler|rng_state|trainer_state|adapter|"
    r"training_state|random_states)",
    re.IGNORECASE,
)


class ModelFormat(StrEnum):
    SAFETENSORS = "safetensors"
    PYTORCH_PICKLE = "pytorch_pickle"
    GGUF = "gguf"
    ADAPTER = "adapter"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PickleInspection:
    files: tuple[str, ...]
    weight_bytes: int | None
    complete: bool
    issues: tuple[Issue, ...]
    confidence: Confidence = Confidence.LOW


@dataclass(frozen=True, slots=True)
class GGUFPlaceholder:
    """File-size-only GGUF view used until the GGUF header parser runs.

    Step 5 replaces this with metadata-aware inspection. It must not be treated
    as an exact weight measurement: GGUF file bytes include metadata.
    """

    files: tuple[str, ...]
    file_bytes: int | None
    complete: bool
    issues: tuple[Issue, ...]
    confidence: Confidence = Confidence.LOW


@dataclass(frozen=True, slots=True)
class ModelInspection:
    repo: HFRepo
    config: ModelConfig | None
    config_raw: Mapping[str, Any] | None
    format: ModelFormat
    safetensors: SafetensorsInspection | None
    pickle: PickleInspection | None
    gguf: GGUFPlaceholder | None
    weight_bytes: int | None
    weight_bytes_exact: bool
    params: int | None
    param_source: str | None
    active_weight_bytes: int | None
    active_weight_source: str | None
    confidence: Confidence
    issues: tuple[Issue, ...]

    @property
    def architecture(self) -> str | None:
        return self.config.primary_architecture if self.config else None

    @property
    def is_llm(self) -> bool:
        if self.repo.pipeline_tag == "text-generation":
            return True
        return bool(
            self.config
            and self.config.primary_architecture
            and "CausalLM" in self.config.primary_architecture
        )

    @property
    def is_asr(self) -> bool:
        return self.repo.pipeline_tag == "automatic-speech-recognition" or (
            self.config is not None and self.config.model_type == "whisper"
        )

    @property
    def is_tts(self) -> bool:
        return self.repo.pipeline_tag == "text-to-speech"

    @property
    def weight_files(self) -> tuple[str, ...]:
        if self.safetensors:
            return self.safetensors.shards
        if self.pickle:
            return self.pickle.files
        if self.gguf:
            return self.gguf.files
        return ()


def _config_issue(code: str, message: str, severity: str = "warning") -> Issue:
    return Issue(code=code, message=message, severity=severity)


async def _load_config(
    client: HFClient, repo: HFRepo, *, token: str | None
) -> tuple[ModelConfig | None, Mapping[str, Any] | None, list[Issue]]:
    issues: list[Issue] = []
    if repo.file("config.json") is None:
        issues.append(
            _config_issue(
                "config_missing",
                "This repo has no config.json. Weight sizes may be inspectable, but "
                "architecture and KV-cache math cannot be trusted.",
                "warning",
            )
        )
        return None, None, issues

    try:
        config_file = await client.get_json_file(repo, "config.json", token=token)
    except HFError as exc:
        if exc.code in {"file_not_found", "file_too_large", "invalid_json"}:
            issues.append(
                _config_issue(
                    "config_unreadable",
                    f"config.json could not be read safely: {exc.message}",
                    "warning",
                )
            )
            return None, None, issues
        raise

    data = config_file.data
    if not isinstance(data, dict):
        issues.append(
            _config_issue(
                "config_not_object",
                "config.json is not a JSON object.",
                "warning",
            )
        )
        return None, None, issues

    config = parse_config(data)
    return config, data, issues


def _pickle_candidates(repo: HFRepo) -> tuple[str, ...]:
    if repo.file(_PICKLE_INDEX) is not None:
        # The index is fetched by the caller; this function only handles the
        # no-index case. Listed for completeness.
        return ()
    known = [path for path in repo.filenames() if _KNOWN_PICKLE_RE.search(path)]
    if known:
        return tuple(sorted(known))
    # Be conservative with unknown names: only accept a single non-training
    # .bin/.pt/.pth file; otherwise report ambiguity.
    loose = [
        path
        for path in repo.filenames()
        if path.lower().endswith((".bin", ".pt", ".pth"))
        and not _NON_MODEL_BIN_RE.search(path)
    ]
    if len(loose) == 1:
        return (loose[0],)
    return ()


async def _inspect_pickle(
    client: HFClient, repo: HFRepo, *, token: str | None
) -> PickleInspection | None:
    if repo.file(_PICKLE_INDEX) is not None:
        try:
            index = await client.get_json_file(repo, _PICKLE_INDEX, token=token)
        except HFError as exc:
            if exc.code in {"file_not_found", "file_too_large", "invalid_json"}:
                return PickleInspection(
                    files=(),
                    weight_bytes=None,
                    complete=False,
                    issues=(
                        _config_issue(
                            "pickle_index_unreadable",
                            f"{_PICKLE_INDEX} could not be read: {exc.message}",
                            "warning",
                        ),
                    ),
                )
            raise
        data = index.data
        weight_map = data.get("weight_map") if isinstance(data, dict) else None
        if isinstance(weight_map, dict):
            files = tuple(
                sorted(
                    {
                        str(path)
                        for path in weight_map.values()
                        if isinstance(path, str)
                        and path.lower().endswith((".bin", ".pt", ".pth"))
                    }
                )
            )
            if files:
                sizes = [repo.file(path).size if repo.file(path) else None for path in files]
                complete = all(size is not None for size in sizes)
                total = sum(size for size in sizes if size is not None) if complete else None
                issues = [
                    _config_issue(
                        "pickle_never_read",
                        "PyTorch pickle shards are never downloaded or unpickled. "
                        "Their API file sizes are an upper bound on model weights.",
                        "info",
                    )
                ]
                if not complete:
                    issues.append(
                        _config_issue(
                            "pickle_size_missing",
                            "At least one pickle shard has no size in the HF file list; "
                            "weight memory is unknown.",
                            "warning",
                        )
                    )
                return PickleInspection(
                    files=files,
                    weight_bytes=total,
                    complete=complete,
                    issues=tuple(issues),
                )

    files = _pickle_candidates(repo)
    if not files:
        return None
    sizes = [repo.file(path).size if repo.file(path) else None for path in files]
    complete = all(size is not None for size in sizes)
    total = sum(size for size in sizes if size is not None) if complete else None
    issues = [
        _config_issue(
            "pickle_never_read",
            "PyTorch pickle weights are never downloaded or unpickled. "
            "Their API file sizes are an upper bound on model weights.",
            "info",
        )
    ]
    if not complete:
        issues.append(
            _config_issue(
                "pickle_size_missing",
                "A pickle shard has no size in the HF file list; weight memory is unknown.",
                "warning",
            )
        )
    return PickleInspection(
        files=files,
        weight_bytes=total,
        complete=complete,
        issues=tuple(issues),
    )


def _inspect_gguf_placeholder(repo: HFRepo) -> GGUFPlaceholder | None:
    artifact = primary_gguf_artifact(repo)
    if artifact is None:
        return None
    issues = [
        _config_issue(
            "gguf_file_size_only",
            "GGUF file bytes include metadata; they are shown as an upper bound.",
            "warning",
        )
    ]
    if has_multiple_gguf_artifacts(repo):
        issues.append(
            _config_issue(
                "multiple_gguf_artifacts",
                "This repo has multiple GGUF variants. The main result uses the smallest "
                "file; see the artifact shelf for each variant.",
                "warning",
            )
        )
    return GGUFPlaceholder(
        files=artifact.files,
        file_bytes=artifact.size_bytes,
        complete=artifact.size_bytes is not None,
        issues=tuple(issues),
    )


async def inspect_model(
    client: HFClient,
    model: str,
    *,
    token: str | None = None,
) -> ModelInspection:
    repo = await client.resolve_repo(model, token=token)
    config, config_raw, issues = await _load_config(client, repo, token=token)

    if repo.file("adapter_config.json") is not None and (
        repo.file("model.safetensors") is None
        and repo.file("model.safetensors.index.json") is None
    ):
        issues.append(
            _config_issue(
                "adapter_repo",
                "This looks like a PEFT/LoRA adapter repo, not a standalone model. "
                "v1 does not estimate adapters or their base model.",
                "risk",
            )
        )
        return ModelInspection(
            repo=repo,
            config=config,
            config_raw=config_raw,
            format=ModelFormat.ADAPTER,
            safetensors=None,
            pickle=None,
            gguf=None,
            weight_bytes=None,
            weight_bytes_exact=False,
            params=None,
            param_source=None,
            active_weight_bytes=None,
            active_weight_source=None,
            confidence=Confidence.LOW,
            issues=tuple(issues),
        )

    safetensors = await inspect_safetensors(
        client,
        repo,
        token=token,
        quantization=config.quantization if config else None,
        moe=config.moe if config else None,
    )
    if safetensors is not None:
        issues.extend(safetensors.issues)
        issues.extend(config.issues if config else [])
        params = safetensors.params
        param_source = "safetensors_headers" if params is not None else None
        if params is None and config is not None:
            params = estimate_param_count_from_config(config)
            param_source = "config_estimate" if params is not None else None
        if safetensors.expert_stats:
            active_weight_bytes = safetensors.expert_stats.active_weight_bytes
            active_weight_source = "expert_tensor_names"
        elif config and config.moe:
            active_weight_bytes = None
            active_weight_source = None
        else:
            active_weight_bytes = safetensors.weight_bytes
            active_weight_source = "exact_weights"
        return ModelInspection(
            repo=repo,
            config=config,
            config_raw=config_raw,
            format=ModelFormat.SAFETENSORS,
            safetensors=safetensors,
            pickle=None,
            gguf=None,
            weight_bytes=safetensors.weight_bytes,
            weight_bytes_exact=safetensors.weight_bytes_exact,
            params=params,
            param_source=param_source,
            active_weight_bytes=active_weight_bytes,
            active_weight_source=active_weight_source,
            confidence=safetensors.confidence,
            issues=tuple(issues),
        )

    pickle = await _inspect_pickle(client, repo, token=token)
    if pickle is not None:
        issues.extend(pickle.issues)
        issues.extend(config.issues if config else [])
        params = estimate_param_count_from_config(config) if config else None
        if config and config.moe and params is not None:
            issues.append(
                _config_issue(
                    "pickle_moe_active_unknown",
                    "MoE active weights cannot be derived from pickle file sizes; "
                    "speed will be UNKNOWN.",
                    "warning",
                )
            )
        return ModelInspection(
            repo=repo,
            config=config,
            config_raw=config_raw,
            format=ModelFormat.PYTORCH_PICKLE,
            safetensors=None,
            pickle=pickle,
            gguf=None,
            weight_bytes=pickle.weight_bytes,
            weight_bytes_exact=False,
            params=params,
            param_source="config_estimate" if params is not None else None,
            active_weight_bytes=None if (config and config.moe) else pickle.weight_bytes,
            active_weight_source=(
                None if (config and config.moe) else "pickle_file_size_upper_bound"
            ),
            confidence=Confidence.LOW,
            issues=tuple(issues),
        )

    gguf = _inspect_gguf_placeholder(repo)
    if gguf is not None:
        issues.extend(gguf.issues)
        issues.extend(config.issues if config else [])
        params = estimate_param_count_from_config(config) if config else None
        return ModelInspection(
            repo=repo,
            config=config,
            config_raw=config_raw,
            format=ModelFormat.GGUF,
            safetensors=None,
            pickle=None,
            gguf=gguf,
            weight_bytes=gguf.file_bytes,
            weight_bytes_exact=False,
            params=params,
            param_source="config_estimate" if params is not None else None,
            active_weight_bytes=None if (config and config.moe) else gguf.file_bytes,
            active_weight_source=(
                None if (config and config.moe) else "gguf_file_size_upper_bound"
            ),
            confidence=Confidence.LOW,
            issues=tuple(issues),
        )

    issues.extend(config.issues if config else [])
    issues.append(
        _config_issue(
            "no_supported_weights",
            "No safetensors, recognized pickle weights, or GGUF files were found.",
            "risk",
        )
    )
    return ModelInspection(
        repo=repo,
        config=config,
        config_raw=config_raw,
        format=ModelFormat.UNKNOWN,
        safetensors=None,
        pickle=None,
        gguf=None,
        weight_bytes=None,
        weight_bytes_exact=False,
        params=None,
        param_source=None,
        active_weight_bytes=None,
        active_weight_source=None,
        confidence=Confidence.LOW,
        issues=tuple(issues),
    )
