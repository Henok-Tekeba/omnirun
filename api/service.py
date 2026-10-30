from __future__ import annotations

from datetime import UTC, datetime

from api.schemas import (
    SCHEMA_VERSION,
    ArtifactReport,
    AssumptionItem,
    CacheInfo,
    CheckRequest,
    CheckResponse,
    ClaimsReport,
    EnvironmentHint,
    ErrorDetail,
    ErrorResponse,
    FitClaimReport,
    HardwareSummary,
    InputsSummary,
    KVReport,
    Links,
    MemoryReport,
    ModelSummary,
    QuantAlternativeReport,
    RangeBytes,
    RangeFloat,
    Reason,
    Recommendation,
    RuntimePathReport,
    SpeedReport,
    SupportClaimReport,
    SweepPointReport,
    SweepReport,
    SweepScenarioReport,
    VerdictReport,
    VerifiedClaimReport,
    VerifiedRunReport,
    WarningItem,
    WeightReport,
)
from core.artifacts import ArtifactFormat, ArtifactInfo
from core.claims import ClaimStatus
from core.estimate import MemoryEstimate, peak_for_weight_bytes, weights_peak_for_bytes
from core.hardware import (
    DeviceTable,
    HardwareProfile,
    profile_from_helper,
    profile_from_manual,
    profile_from_unknown,
)
from core.inspect.model import ModelInspection
from core.inspect.types import Issue, RangeEstimate
from core.speed import SpeedEstimate
from core.support import SupportClaim
from core.sweep import SweepResult, build_sweep
from core.verdict import VerdictResult
from core.verified import VerifiedClaim


def resolve_hardware(request: CheckRequest, table: DeviceTable) -> HardwareProfile:
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


def model_class(inspection: ModelInspection) -> str:
    if inspection.is_llm:
        return "llm"
    if inspection.is_asr:
        return "asr"
    if inspection.is_tts:
        return "tts"
    return "unsupported"


def _range_bytes(value: RangeEstimate | None) -> RangeBytes | None:
    if value is None:
        return None
    return RangeBytes(
        min=round(value.min),
        likely=round(value.likely),
        max=round(value.max),
    )


def _range_float(value: RangeEstimate | None) -> RangeFloat | None:
    if value is None:
        return None
    return RangeFloat(min=value.min, likely=value.likely, max=value.max)


def _reason(issue: Issue) -> Reason:
    return Reason(code=issue.code, message=issue.message, severity=issue.severity)


def _warning(issue: Issue) -> WarningItem:
    return WarningItem(code=issue.code, message=issue.message, severity=issue.severity)


def _dedupe_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, str]] = set()
    result: list[Issue] = []
    for issue in issues:
        key = (issue.code, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _assumptions(
    *,
    request: CheckRequest,
    inspection: ModelInspection,
    memory: MemoryEstimate,
    hardware: HardwareProfile,
) -> list[AssumptionItem]:
    items = [
        AssumptionItem(
            id="single_device",
            text=(
                "v1 is single-device: one GPU/chip or CPU. No multi-GPU, offload, "
                "or distributed serving."
            ),
        ),
        AssumptionItem(
            id="no_weight_download",
            text=(
                "OmniRun reads only metadata and safetensors/GGUF headers. "
                "No tensor payload is downloaded and pickle files are never read."
            ),
        ),
        AssumptionItem(
            id="memory_units",
            text="JSON memory values are bytes; bandwidth values are decimal GB/s (10^9 bytes/s).",
        ),
        AssumptionItem(
            id="peak_definition",
            text=(
                "Peak memory = stored weights + KV cache + runtime overhead. "
                "Prefill activation peaks are not modeled."
            ),
        ),
        AssumptionItem(
            id="overhead",
            text=(
                "Runtime overhead is 0.25 GiB plus 5% / 10% / 20% of weights for "
                "min / likely / max; it covers runtime context, allocator, and decode workspace."
            ),
        ),
        AssumptionItem(
            id="kv_formula",
            text=(
                "KV cache = 2 * layers * kv_heads * head_dim * tokens * batch * dtype bytes; "
                "windowed layers cap tokens at their window. MLA uses its compressed "
                "latent formula."
            ),
        ),
        AssumptionItem(
            id="decode_speed",
            text=(
                "Speed is decode-only: bandwidth * efficiency / (active weights + batch*KV). "
                "Prefill and TTFT are not estimated. Efficiency is a documented range, "
                "not measured."
            ),
        ),
        AssumptionItem(
            id="quant_hypothetical",
            text=(
                "FP16/INT8/4-bit alternatives are hypothetical weights-only sizes; "
                "they do not imply an artifact exists, is supported, or has a particular quality."
            ),
        ),
        AssumptionItem(
            id="support_not_verified",
            text=(
                "SUPPORTED is a documented architecture/runtime path with a version floor. "
                "It is not a real run and does not imply VERIFIED."
            ),
        ),
        AssumptionItem(
            id="verified_empty",
            text=(
                "VERIFIED is empty in v1. No result can claim a recorded real run; "
                "GO never means verified."
            ),
        ),
    ]
    if hardware.apple_fraction is not None:
        items.append(
            AssumptionItem(
                id="apple_fraction",
                text=(
                    f"Usable Apple Silicon memory is {hardware.apple_fraction:.0%} of total RAM. "
                    "The actual macOS wired limit varies with OS version, RAM size, and other apps."
                ),
            )
        )
    if hardware.kind.value == "discrete":
        items.append(
            AssumptionItem(
                id="vram_reserve",
                text=(
                    "Discrete GPU budget is VRAM minus a 512 MiB runtime reserve; "
                    "system RAM does not add capacity in v1."
                ),
            ),
        )
    if hardware.source.value == "unknown":
        items.append(
            AssumptionItem(
                id="unknown_hardware_defaults",
                text=(
                    "Unknown/CPU-only hardware uses 80% of RAM and 25 GB/s unless RAM "
                    "is missing, in which case FITS is UNKNOWN."
                ),
            )
        )
    if memory.weights.kind == "upper_bound":
        items.append(
            AssumptionItem(
                id="weights_upper_bound",
                text=(
                    "Weight bytes come from file sizes, not tensor shapes; they are an "
                    "upper bound and the lower bound is unknown."
                ),
            )
        )
    if memory.kv.layers_windowed:
        items.append(
            AssumptionItem(
                id="sliding_window",
                text=(
                    "Windowed layers use min(context, window) as the likely KV allocation; "
                    "the max reserves full context in case the runtime does not evict."
                ),
            )
        )
    if inspection.config and inspection.config.mla:
        items.append(
            AssumptionItem(
                id="mla_layout",
                text=(
                    "MLA KV cache assumes a compressed (kv_lora_rank + qk_rope_head_dim) "
                    "layout; runtime implementations differ."
                ),
            )
        )
    if request.batch > 1:
        items.append(
            AssumptionItem(
                id="batch_amortization",
                text=(
                    "Batch > 1 assumes perfect continuous batching: active weights are read "
                    "once per forward step, KV once per sequence. Real throughput may be lower."
                ),
            )
        )
    if memory.context_effective is not None and memory.context_effective != request.context:
        items.append(
            AssumptionItem(
                id="context_clamped",
                text=(
                    f"Requested context {request.context} was clamped to the model maximum "
                    f"{memory.context_effective}."
                ),
            )
        )
    return items


def _quant_report(quant) -> QuantAlternativeReport:
    return QuantAlternativeReport(
        name=quant.alternative.name,
        bits_per_param=quant.alternative.bits_per_param,
        weight_bytes=quant.alternative.weight_bytes,
        peak=_range_bytes(quant.peak),
        fits=quant.status.value,
        confidence=quant.alternative.confidence.value,
        note=quant.note,
    )


def _sweep_report(sweep: SweepResult) -> SweepReport:
    return SweepReport(
        budget_bytes=sweep.budget_bytes,
        model_max_context=sweep.model_max_context,
        context_points=[
            SweepPointReport(
                context=point.context,
                peak=_range_bytes(point.peak),
                fits=point.fits.value,
            )
            for point in sweep.context_points
        ],
        max_context_that_fits=sweep.max_context_that_fits,
        max_batch_that_fits=sweep.max_batch_that_fits,
        best_quantization=(
            _quant_report(sweep.best_quantization)
            if sweep.best_quantization is not None
            else None
        ),
        scenarios=[
            SweepScenarioReport(
                id=scenario.id,
                label=scenario.label,
                context=scenario.context,
                batch=scenario.batch,
                budget_bytes=scenario.budget_bytes,
                peak=_range_bytes(scenario.peak),
                fits=scenario.fits.value,
            )
            for scenario in sweep.scenarios
        ],
    )


def _artifact_report(
    artifact: ArtifactInfo,
    memory: MemoryEstimate,
    hardware: HardwareProfile,
) -> ArtifactReport:
    peak = None
    weights_peak = None
    if artifact.size_bytes is not None:
        weights_peak = _range_bytes(weights_peak_for_bytes(artifact.size_bytes))
    if (
        artifact.format not in {ArtifactFormat.ADAPTER, ArtifactFormat.UNKNOWN}
        and artifact.size_bytes is not None
    ):
        peak = _range_bytes(peak_for_weight_bytes(artifact.size_bytes, memory.kv))

    budget = hardware.memory_budget_bytes
    if peak is None or budget is None:
        fits = ClaimStatus.UNKNOWN
    elif peak.max <= budget:
        fits = ClaimStatus.YES
    elif peak.min > budget:
        fits = ClaimStatus.NO
    else:
        fits = ClaimStatus.UNKNOWN

    if weights_peak is None or budget is None:
        weights_fit = ClaimStatus.UNKNOWN
    elif weights_peak.max <= budget:
        weights_fit = ClaimStatus.YES
    elif weights_peak.min > budget:
        weights_fit = ClaimStatus.NO
    else:
        weights_fit = ClaimStatus.UNKNOWN

    # If weights alone exceed the budget, the full model cannot fit even when
    # the context cache is unknown. Keep that definitive answer.
    if weights_fit == ClaimStatus.NO:
        fits = ClaimStatus.NO

    return ArtifactReport(
        path=artifact.path,
        files=list(artifact.files),
        format=artifact.format.value,  # type: ignore[arg-type]
        quantization=artifact.quantization,
        size_bytes=artifact.size_bytes,
        runtime_hint=artifact.runtime_hint,
        direct=artifact.direct,
        fits=fits.value,
        peak=peak,
        weights_fit=weights_fit.value,
        weights_peak=weights_peak,
        confidence=artifact.confidence.value,  # type: ignore[arg-type]
        note=artifact.note,
    )


def build_response(
    *,
    request: CheckRequest,
    request_id: str,
    inspection: ModelInspection,
    hardware: HardwareProfile,
    memory: MemoryEstimate,
    speed: SpeedEstimate,
    support: SupportClaim,
    verified: VerifiedClaim,
    result: VerdictResult,
    artifacts: tuple[ArtifactInfo, ...],
    cache_info: CacheInfo,
) -> CheckResponse:
    cls = model_class(inspection)
    warnings = _dedupe_issues(
        list(inspection.issues) + list(support.reasons) + list(result.reasons)
    )
    if inspection.repo.cache_stale:
        warnings.append(
            Issue(
                "stale_model_info",
                "Hugging Face was unreachable; OmniRun used a stale cached model record.",
                "warning",
            )
        )

    fit = result.fit
    fit_report = FitClaimReport(
        status=fit.status.value,
        confidence=fit.confidence.value,
        summary=fit.summary,
        reasons=[_reason(issue) for issue in fit.reasons],
        budget_bytes=fit.budget_bytes,
        peak=_range_bytes(fit.peak),
        headroom_bytes=fit.headroom_bytes,
        headroom_ratio=fit.headroom_ratio,
    )
    support_report = SupportClaimReport(
        status=support.status.value,
        confidence=support.confidence.value,
        summary=support.summary,
        reasons=[_reason(issue) for issue in support.reasons],
        architecture=support.architecture,
        matched_by=support.matched_by,
        matrix_entry_found=support.matrix_entry_found,
        direct_runtime_available=support.direct_runtime_available,
        custom_code_risk=support.custom_code_risk,
        runtimes=[
            RuntimePathReport(
                name=path.name,
                min_version=path.min_version,
                version_scheme=path.version_scheme,
                artifact=path.artifact,
                available=path.available,
                status=path.status,  # type: ignore[arg-type]
                direct=path.direct,
                notes=path.notes,
                source=path.source,
            )
            for path in support.runtimes
        ],
    )
    verified_report = VerifiedClaimReport(
        status=verified.status.value,
        confidence=verified.confidence.value,
        summary=verified.summary,
        reasons=[_reason(issue) for issue in verified.reasons],
        runs=[
            VerifiedRunReport(
                run_id=run.run_id,
                repo_id=run.repo_id,
                revision=run.revision,
                architecture=run.architecture,
                hardware_device_id=run.hardware_device_id,
                hardware_device_name=run.hardware_device_name,
                runtime=run.runtime,
                runtime_version=run.runtime_version,
                artifact_format=run.artifact_format,
                quantization=run.quantization,
                context_tokens=run.context_tokens,
                batch=run.batch,
                peak_memory_bytes=run.peak_memory_bytes,
                decode_tokens_per_second=run.decode_tokens_per_second,
                recorded_at=run.recorded_at,
                source_url=run.source_url,
                notes=run.notes,
            )
            for run in verified.runs
        ],
    )
    claims = ClaimsReport(
        fits=fit_report,
        supported=support_report,
        verified=verified_report,
    )

    alternatives = [_quant_report(quant) for quant in result.quant_fits]
    weights = WeightReport(
        kind=memory.weights.kind,  # type: ignore[arg-type]
        actual_bytes=memory.weights.actual_bytes,
        range=_range_bytes(memory.weights.range),
        params=memory.weights.params,
        param_source=memory.weights.param_source,
        confidence=memory.weights.confidence.value,
        alternatives=alternatives,
    )
    kv = KVReport(
        available=memory.kv.available,
        bytes_range=_range_bytes(memory.kv.bytes_range),
        bytes_likely=memory.kv.bytes_likely,
        per_sequence_likely=memory.kv.per_sequence_likely,
        attention=memory.kv.attention,
        layers_full=memory.kv.layers_full,
        layers_windowed=memory.kv.layers_windowed,
        dtype_bytes=memory.kv.dtype_bytes,
        context_requested=memory.kv.context_requested,
        context_effective=memory.kv.context_effective,
        batch=memory.kv.batch,
        confidence=memory.kv.confidence.value,
        formula=memory.kv.formula,
    )
    memory_report = MemoryReport(
        budget_bytes=hardware.memory_budget_bytes,
        context_requested=request.context,
        context_effective=memory.context_effective,
        batch=request.batch,
        weights=weights,
        kv_cache=kv,
        overhead=_range_bytes(memory.overhead),
        peak=_range_bytes(memory.peak),
        confidence=memory.confidence.value,
    )

    speed_report = SpeedReport(
        available=speed.available,
        metric="decode_tokens_per_second",
        aggregate=_range_float(speed.aggregate),
        per_sequence=_range_float(speed.per_sequence),
        speed_class=speed.speed_class.value,
        confidence=speed.confidence.value,
        bandwidth_gbps=speed.bandwidth_gbps,
        active_weight_bytes=speed.active_weight_bytes,
        active_weight_source=speed.active_weight_source,
        kv_bytes_per_sequence=speed.kv_bytes_per_sequence,
        efficiency=_range_float(speed.efficiency) or RangeFloat(min=0, likely=0, max=0),
        prefill_estimated=False,
        batch=speed.batch,
        notes=list(speed.notes),
    )

    model = ModelSummary(
        repo_id=inspection.repo.repo_id,
        requested_repo_id=inspection.repo.requested_repo_id,
        revision=inspection.repo.sha,
        source_url=request.model if "://" in request.model else None,
        model_class=cls,  # type: ignore[arg-type]
        architecture=inspection.architecture,
        model_type=inspection.config.model_type if inspection.config else None,
        pipeline_tag=inspection.repo.pipeline_tag,
        library_name=inspection.repo.library_name,
        format=inspection.format.value,  # type: ignore[arg-type]
        gated=inspection.repo.gated,
        private=inspection.repo.private,
        trust_remote_code_required=bool(
            inspection.config and inspection.config.trust_remote_code_required
        ),
        config_available=inspection.config is not None,
        last_modified=inspection.repo.last_modified,
        weight_files_count=len(inspection.weight_files),
    )
    inputs = InputsSummary(
        model_input=request.model,
        context_requested=request.context,
        context_effective=memory.context_effective,
        context_clamped=(
            memory.context_effective is not None
            and memory.context_effective != request.context
        ),
        batch=request.batch,
        hardware_source=hardware.source.value,  # type: ignore[arg-type]
    )
    hardware_report = HardwareSummary(**hardware.to_dict())
    verdict = VerdictReport(
        value=result.value.value,
        summary=result.summary,
        basis_claims=list(result.basis_claims),  # type: ignore[arg-type]
        reasons=[_reason(issue) for issue in result.reasons],
        confidence=result.confidence.value,
    )

    return CheckResponse(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        checked_at=datetime.now(UTC),
        model=model,
        inputs=inputs,
        hardware=hardware_report,
        verdict=verdict,
        claims=claims,
        memory=memory_report,
        speed=speed_report,
        recommendations=[],
        environment_hint=None,
        artifacts=[_artifact_report(artifact, memory, hardware) for artifact in artifacts],
        sweep=_sweep_report(
            build_sweep(
                inspection,
                hardware,
                memory,
                context=request.context,
                batch=request.batch,
            )
        ),
        assumptions=_assumptions(
            request=request,
            inspection=inspection,
            memory=memory,
            hardware=hardware,
        ),
        warnings=[_warning(issue) for issue in warnings],
        links=Links(
            hf_model=f"https://huggingface.co/{inspection.repo.repo_id}",
            hf_tree=f"https://huggingface.co/{inspection.repo.repo_id}/tree/{inspection.repo.sha}",
        ),
        cache=cache_info,
    )


def error_response(
    *,
    request_id: str,
    code: str,
    message: str,
    status: int,
    hint: str | None = None,
    retryable: bool = False,
    retry_after_seconds: float | None = None,
    details: dict | None = None,
) -> ErrorResponse:
    return ErrorResponse(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        error=ErrorDetail(
            code=code,
            message=message,
            hint=hint,
            status=status,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
            details=details or {},
        ),
    )


__all__ = [
    "EnvironmentHint",
    "Recommendation",
    "build_response",
    "error_response",
    "model_class",
    "resolve_hardware",
]
