"""Hardware-first candidate discovery.

The Hub search is only a candidate seed. Every candidate is inspected and
ranked by fit, runtime support, artifact availability, and size. Downloads and
likes are not used as a quality score.
"""

from __future__ import annotations

import asyncio
from typing import Any

from api.schemas import (
    SCHEMA_VERSION,
    FindCandidate,
    FindError,
    FindRequest,
    FindResponse,
    RangeBytes,
    RangeFloat,
)
from api.service import model_class
from core.artifacts import ArtifactInfo, discover_artifacts
from core.claims import ClaimStatus
from core.errors import OmniRunError
from core.estimate import estimate_memory, peak_for_weight_bytes
from core.hardware import (
    DeviceTable,
    HardwareProfile,
    profile_from_helper,
    profile_from_manual,
    profile_from_unknown,
)
from core.hf_client import HFClient
from core.inspect.model import inspect_model
from core.speed import estimate_llm_speed
from core.support import SupportMatrix, build_support_claim
from core.sweep import fit_status
from core.verdict import decide_verdict
from core.verified import build_verified_claim, load_verified_runs


def resolve_hardware(request: FindRequest, table: DeviceTable) -> HardwareProfile:
    hardware = request.hardware
    if hardware.source == "helper":
        return profile_from_helper(hardware.code, table)
    if hardware.source == "manual":
        return profile_from_manual(
            hardware.device_id,
            ram_gib=hardware.ram_gib,
            table=table,
        )
    return profile_from_unknown(ram_gib=hardware.ram_gib)


def _range_bytes(value: Any) -> RangeBytes | None:
    if value is None:
        return None
    return RangeBytes(min=round(value.min), likely=round(value.likely), max=round(value.max))


def _range_float(value: Any) -> RangeFloat | None:
    if value is None:
        return None
    return RangeFloat(min=value.min, likely=value.likely, max=value.max)


def _short_reason(value: str) -> str:
    if value == "GO":
        return "Fits and has a direct runtime path."
    if value == "OPTIMIZE":
        return "May work with a smaller setup."
    if value == "NO":
        return "Does not fit as configured."
    return "Not enough evidence for a GO/NO call."


def _best_artifact(
    artifacts: tuple[ArtifactInfo, ...],
    *,
    hardware: HardwareProfile,
    kv: Any,
) -> ArtifactInfo | None:
    sized = [artifact for artifact in artifacts if artifact.size_bytes is not None]
    if not sized:
        return artifacts[0] if artifacts else None

    def peak(artifact: ArtifactInfo):
        if artifact.size_bytes is None:
            return None
        return peak_for_weight_bytes(artifact.size_bytes, kv)

    fitting = [
        artifact
        for artifact in sized
        if fit_status(peak(artifact), hardware.memory_budget_bytes) == ClaimStatus.YES
    ]
    direct_fitting = [artifact for artifact in fitting if artifact.direct]
    pool = direct_fitting or fitting or [artifact for artifact in sized if artifact.direct] or sized
    return min(pool, key=lambda artifact: artifact.size_bytes or 0)


async def _inspect_candidate(
    client: HFClient,
    repo_id: str,
    *,
    request: FindRequest,
    hardware: HardwareProfile,
    support_matrix: SupportMatrix,
    verified_runs: Any,
    token: str | None,
) -> FindCandidate:
    inspection = await inspect_model(client, repo_id, token=token)
    memory = estimate_memory(
        inspection,
        context=request.context,
        batch=request.batch,
    )
    support = build_support_claim(inspection, support_matrix)
    verified = build_verified_claim(inspection, hardware, verified_runs)
    speed = estimate_llm_speed(inspection, memory, hardware, batch=request.batch)
    verdict = decide_verdict(
        inspection=inspection,
        memory=memory,
        hardware=hardware,
        support=support,
        verified=verified,
        context=request.context,
        batch=request.batch,
        model_class_supported=inspection.is_llm,
    )
    artifacts = discover_artifacts(inspection.repo)
    best = _best_artifact(artifacts, hardware=hardware, kv=memory.kv)

    return FindCandidate(
        repo_id=inspection.repo.repo_id,
        license=inspection.repo.license,
        pipeline_tag=inspection.repo.pipeline_tag,
        library_name=inspection.repo.library_name,
        model_class=model_class(inspection),  # type: ignore[arg-type]
        format=inspection.format.value,  # type: ignore[arg-type]
        gated=inspection.repo.gated,
        private=inspection.repo.private,
        trust_remote_code_required=bool(
            inspection.config and inspection.config.trust_remote_code_required
        ),
        verdict=verdict.value.value,  # type: ignore[arg-type]
        confidence=verdict.confidence.value,  # type: ignore[arg-type]
        fits=verdict.fit.status.value,  # type: ignore[arg-type]
        supported=support.status.value,  # type: ignore[arg-type]
        verified=verified.status.value,  # type: ignore[arg-type]
        direct_runtime_available=support.direct_runtime_available,
        memory_budget_bytes=hardware.memory_budget_bytes,
        peak=_range_bytes(memory.peak),
        speed=_range_float(speed.aggregate),
        artifacts_count=len(artifacts),
        best_artifact=best.path if best else None,
        best_artifact_size_bytes=best.size_bytes if best else None,
        reason=_short_reason(verdict.value.value),
    )


def _rank(candidates: list[FindCandidate]) -> list[FindCandidate]:
    fit_order = {"yes": 0, "unknown": 1, "no": 2}
    support_order = {"yes": 0, "unknown": 1, "no": 2}

    def key(candidate: FindCandidate):
        return (
            fit_order[candidate.fits],
            support_order[candidate.supported],
            0 if candidate.artifacts_count else 1,
            candidate.best_artifact_size_bytes
            if candidate.best_artifact_size_bytes is not None
            else 2**63,
            candidate.repo_id.lower(),
        )

    return sorted(candidates, key=key)


async def run_finder(
    client: HFClient,
    request: FindRequest,
    *,
    request_id: str,
    device_table: DeviceTable,
    support_matrix: SupportMatrix,
    verified_runs: Any = None,
) -> FindResponse:
    token = request.hf_token.get_secret_value() if request.hf_token else None
    hardware = resolve_hardware(request, device_table)
    search_limit = min(12, max(request.limit * 2, 6))
    repo_ids = await client.search_models(
        request.query,
        pipeline_tag=request.task,
        limit=search_limit,
        token=token,
    )
    if not repo_ids:
        return FindResponse(
            schema_version=SCHEMA_VERSION,
            request_id=request_id,
            candidates=[],
            errors=[],
            searched=0,
        )

    verified = verified_runs if verified_runs is not None else load_verified_runs()
    semaphore = asyncio.Semaphore(3)
    errors: list[FindError] = []

    async def inspect_one(repo_id: str) -> FindCandidate | None:
        async with semaphore:
            try:
                return await _inspect_candidate(
                    client,
                    repo_id,
                    request=request,
                    hardware=hardware,
                    support_matrix=support_matrix,
                    verified_runs=verified,
                    token=token,
                )
            except OmniRunError as exc:
                errors.append(FindError(repo_id=repo_id, code=exc.code, message=exc.message))
            except Exception:
                errors.append(
                    FindError(
                        repo_id=repo_id,
                        code="candidate_inspection_failed",
                        message="This candidate could not be inspected.",
                    )
                )
            return None

    results = await asyncio.gather(*(inspect_one(repo_id) for repo_id in repo_ids))
    candidates = _rank([candidate for candidate in results if candidate is not None])
    return FindResponse(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        candidates=candidates[: request.limit],
        errors=errors,
        searched=len(repo_ids),
    )


__all__ = ["resolve_hardware", "run_finder"]
