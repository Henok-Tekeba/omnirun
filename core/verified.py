"""VERIFIED claim: a recorded real run on similar hardware.

v1 ships an empty dataset. The schema is in ``data/verified_runs.schema.json``;
this module validates the same fields so a malformed hand-edited entry cannot
silently become a claim.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.claims import ClaimStatus
from core.errors import InputError
from core.hardware import HardwareProfile
from core.inspect.model import ModelInspection
from core.inspect.types import Confidence, Issue

_RUNTIMES = {"transformers", "llama.cpp", "whisper.cpp", "ctranslate2"}


@dataclass(frozen=True, slots=True)
class VerifiedRun:
    run_id: str
    repo_id: str
    revision: str
    architecture: str
    hardware_device_id: str | None
    hardware_device_name: str
    runtime: str
    runtime_version: str
    artifact_format: str
    quantization: str | None
    context_tokens: int
    batch: int
    peak_memory_bytes: int
    decode_tokens_per_second: float
    recorded_at: datetime
    source_url: str
    notes: str | None


@dataclass(frozen=True, slots=True)
class VerifiedClaim:
    status: ClaimStatus
    confidence: Confidence
    summary: str
    reasons: tuple[Issue, ...]
    runs: tuple[VerifiedRun, ...]


def default_verified_path() -> Path:
    override = os.environ.get("OMNIRUN_DATA_DIR")
    if override:
        return Path(override).expanduser() / "verified_runs.json"
    return Path(__file__).resolve().parents[1] / "data" / "verified_runs.json"


def load_verified_runs(path: str | Path | None = None) -> tuple[VerifiedRun, ...]:
    source_path = Path(path) if path is not None else default_verified_path()
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(
            "The verified-runs dataset is missing.",
            code="verified_runs_missing",
            hint=f"Expected {source_path}.",
        ) from exc
    except ValueError as exc:
        raise InputError(
            "The verified-runs dataset is not valid JSON.",
            code="verified_runs_invalid",
            hint=str(exc),
        ) from exc
    if (
        not isinstance(raw, dict)
        or raw.get("version") != 1
        or not isinstance(raw.get("runs"), list)
    ):
        raise InputError(
            "The verified-runs dataset has an unsupported shape or version.",
            code="verified_runs_invalid",
        )
    runs: list[VerifiedRun] = []
    for item in raw["runs"]:
        if not isinstance(item, dict):
            raise InputError("A verified run is not an object.", code="verified_runs_invalid")
        try:
            runtime = str(item["runtime"])
            if runtime not in _RUNTIMES:
                raise ValueError("unknown runtime")
            run = VerifiedRun(
                run_id=str(item["run_id"]),
                repo_id=str(item["repo_id"]),
                revision=str(item["revision"]),
                architecture=str(item["architecture"]),
                hardware_device_id=(
                    str(item["hardware_device_id"]) if item.get("hardware_device_id") else None
                ),
                hardware_device_name=str(item["hardware_device_name"]),
                runtime=runtime,
                runtime_version=str(item["runtime_version"]),
                artifact_format=str(item["artifact_format"]),
                quantization=str(item["quantization"]) if item.get("quantization") else None,
                context_tokens=int(item["context_tokens"]),
                batch=int(item["batch"]),
                peak_memory_bytes=int(item["peak_memory_bytes"]),
                decode_tokens_per_second=float(item["decode_tokens_per_second"]),
                recorded_at=datetime.fromisoformat(str(item["recorded_at"]).replace("Z", "+00:00")),
                source_url=str(item["source_url"]),
                notes=str(item["notes"]) if item.get("notes") else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InputError(
                "A verified run is missing required fields or has invalid values.",
                code="verified_runs_invalid",
                hint=str(exc),
            ) from exc
        if (
            run.context_tokens < 1
            or run.batch < 1
            or run.peak_memory_bytes < 1
            or run.decode_tokens_per_second <= 0
            or len(run.revision) != 40
        ):
            raise InputError(
                "A verified run has out-of-range values.",
                code="verified_runs_invalid",
            )
        runs.append(run)
    return tuple(runs)


def build_verified_claim(
    inspection: ModelInspection,
    hardware: HardwareProfile,
    runs: tuple[VerifiedRun, ...],
) -> VerifiedClaim:
    if not runs:
        return VerifiedClaim(
            status=ClaimStatus.UNKNOWN,
            confidence=Confidence.LOW,
            summary=(
                "VERIFIED is unknown: v1 has no recorded real run for this model. "
                "This does not contradict FITS or SUPPORTED; it is simply unverified."
            ),
            reasons=(
                Issue(
                    "no_verified_run",
                    "data/verified_runs.json is empty in v1.",
                    "info",
                ),
            ),
            runs=(),
        )

    repo_id = inspection.repo.repo_id.lower()
    device_id = hardware.device_id
    device_name = hardware.device_name.lower()
    matches = [
        run
        for run in runs
        if run.repo_id.lower() == repo_id
        and (
            (device_id is not None and run.hardware_device_id == device_id)
            or run.hardware_device_name.lower() == device_name
        )
    ]
    if not matches:
        return VerifiedClaim(
            status=ClaimStatus.UNKNOWN,
            confidence=Confidence.LOW,
            summary=(
                "VERIFIED is unknown for this hardware: recorded runs exist for other "
                "models or machines, but none match this model and hardware."
            ),
            reasons=(
                Issue(
                    "no_matching_verified_run",
                    "No recorded run matches this repo and hardware profile.",
                    "info",
                ),
            ),
            runs=(),
        )

    confidence = Confidence.HIGH
    if hardware.memory_budget_bytes is None or any(
        run.peak_memory_bytes > hardware.memory_budget_bytes for run in matches
    ):
        confidence = Confidence.MEDIUM
    return VerifiedClaim(
        status=ClaimStatus.YES,
        confidence=confidence,
        summary=f"VERIFIED by {len(matches)} recorded run(s) on matching hardware.",
        reasons=(
            Issue(
                "matching_verified_run",
                "A recorded real run matches this repo and hardware profile.",
                "info",
            ),
        ),
        runs=tuple(matches),
    )
