"""FITS / SUPPORTED / VERIFIED claims and the top-level GO/OPTIMIZE/NO/UNKNOWN.

Decision table (v1):
- GO: FITS yes, SUPPORTED yes with a directly usable runtime, and at least 5%
  worst-case memory headroom.
- OPTIMIZE: FITS yes but tight/conversion-only, or the requested setup does not
  fit while a documented smaller configuration (quantization, batch=1, or a
  smaller context) does.
- NO: best-case memory cannot fit, or the support matrix says no path.
- UNKNOWN: inspection incomplete, architecture not in the matrix, runtime
  support unconfirmed, or the model class is not covered in this step.

FITS is deliberately strict: status=yes requires the *worst-case* peak to fit.
A range that straddles the budget is UNKNOWN, not "probably yes".
"""

from __future__ import annotations

from dataclasses import dataclass

from core.claims import ClaimStatus, Verdict
from core.estimate import (
    MemoryEstimate,
    QuantAlternative,
    estimate_memory,
    peak_for_weight_bytes,
)
from core.hardware import HardwareProfile
from core.inspect.model import ModelInspection
from core.inspect.types import Confidence, Issue, RangeEstimate
from core.support import SupportClaim
from core.verified import VerifiedClaim

TIGHT_HEADROOM_FRACTION = 0.05
SMALLER_CONTEXT_TOKENS = 4096


@dataclass(frozen=True, slots=True)
class FitClaim:
    status: ClaimStatus
    confidence: Confidence
    summary: str
    reasons: tuple[Issue, ...]
    budget_bytes: int | None
    peak: RangeEstimate | None
    headroom_bytes: int | None
    headroom_ratio: float | None


@dataclass(frozen=True, slots=True)
class QuantFit:
    alternative: QuantAlternative
    peak: RangeEstimate | None
    status: ClaimStatus
    note: str


@dataclass(frozen=True, slots=True)
class OptimizationOption:
    kind: str  # quantization | batch | context
    label: str
    detail: str
    peak: RangeEstimate
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class VerdictResult:
    value: Verdict
    summary: str
    basis_claims: tuple[str, ...]
    reasons: tuple[Issue, ...]
    confidence: Confidence
    fit: FitClaim
    quant_fits: tuple[QuantFit, ...]
    options: tuple[OptimizationOption, ...]


def _fit_status(peak: RangeEstimate | None, budget: int | None) -> ClaimStatus:
    if peak is None or budget is None:
        return ClaimStatus.UNKNOWN
    if peak.max <= budget:
        return ClaimStatus.YES
    if peak.min > budget:
        return ClaimStatus.NO
    return ClaimStatus.UNKNOWN


def build_fit_claim(memory: MemoryEstimate, hardware: HardwareProfile) -> FitClaim:
    budget = hardware.memory_budget_bytes
    peak = memory.peak
    status = _fit_status(peak, budget)
    reasons: list[Issue] = []

    if budget is None:
        reasons.append(
            Issue(
                "memory_budget_unknown",
                "The hardware profile does not provide a usable memory budget.",
                "risk",
            )
        )
    if peak is None:
        reasons.append(
            Issue(
                "memory_estimate_incomplete",
                "Weight or KV-cache memory is unknown, so FITS cannot be evaluated.",
                "risk",
            )
        )

    headroom_bytes = None
    headroom_ratio = None
    if peak is not None and budget is not None:
        headroom_bytes = budget - round(peak.max)
        headroom_ratio = headroom_bytes / budget if budget > 0 else 0.0

    confidence = memory.confidence
    if status == ClaimStatus.YES:
        reasons.append(
            Issue(
                "fits_worst_case",
                f"Worst-case peak {peak.max / 1e9:.2f} GB is within the "
                f"{budget / 1e9:.2f} GB budget.",
                "info",
            )
        )
        if headroom_ratio is not None and headroom_ratio < TIGHT_HEADROOM_FRACTION:
            reasons.append(
                Issue(
                    "tight_memory_headroom",
                    f"Worst-case headroom is only {headroom_ratio:.1%}; allocator "
                    "fragmentation or a longer context can erase it.",
                    "warning",
                )
            )
        summary = (
            f"FITS: worst-case peak {peak.max / 1e9:.2f} GB <= "
            f"budget {budget / 1e9:.2f} GB "
            f"(headroom {headroom_bytes / 1e9:.2f} GB, {headroom_ratio:.1%})."
        )
    elif status == ClaimStatus.NO:
        reasons.append(
            Issue(
                "does_not_fit_best_case",
                f"Best-case peak {peak.min / 1e9:.2f} GB exceeds the "
                f"{budget / 1e9:.2f} GB budget.",
                "warning",
            )
        )
        summary = (
            f"NO FIT: best-case peak {peak.min / 1e9:.2f} GB > "
            f"budget {budget / 1e9:.2f} GB even before the likely overhead."
        )
    elif peak is not None and budget is not None:
        reasons.append(
            Issue(
                "memory_range_straddles_budget",
                f"Peak range {peak.min / 1e9:.2f}-{peak.max / 1e9:.2f} GB straddles "
                f"the {budget / 1e9:.2f} GB budget. FITS is UNKNOWN rather than a guess.",
                "warning",
            )
        )
        summary = (
            f"FITS is unknown: peak range {peak.min / 1e9:.2f}-{peak.max / 1e9:.2f} GB "
            f"straddles the {budget / 1e9:.2f} GB budget."
        )
        confidence = Confidence.lowest(confidence, Confidence.MEDIUM)
    else:
        summary = "FITS is unknown: the memory estimate is incomplete."

    # Surface the assumptions that could move the answer.
    for issue in memory.issues:
        if issue.code in {
            "weights_upper_bound",
            "sliding_window_cache_range",
            "mla_cache_layout",
            "kv_dtype_assumed",
            "kv_unsupported_attention",
            "weights_unknown",
            "params_unknown",
        }:
            reasons.append(issue)

    if status == ClaimStatus.UNKNOWN:
        confidence = Confidence.lowest(confidence, Confidence.MEDIUM)
    return FitClaim(
        status=status,
        confidence=confidence,
        summary=summary,
        reasons=tuple(reasons),
        budget_bytes=budget,
        peak=peak,
        headroom_bytes=headroom_bytes,
        headroom_ratio=headroom_ratio,
    )


def quantify_alternatives(
    memory: MemoryEstimate, budget: int | None
) -> tuple[QuantFit, ...]:
    result: list[QuantFit] = []
    for alternative in memory.weights.alternatives:
        if alternative.weight_bytes is None:
            peak = None
            status = ClaimStatus.UNKNOWN
            note = "Parameter count is unknown; this alternative cannot be sized."
        else:
            peak = peak_for_weight_bytes(alternative.weight_bytes, memory.kv)
            status = _fit_status(peak, budget)
            note = alternative.note
        result.append(
            QuantFit(
                alternative=alternative,
                peak=peak,
                status=status,
                note=note,
            )
        )
    return tuple(result)


def _options(
    inspection: ModelInspection,
    memory: MemoryEstimate,
    hardware: HardwareProfile,
    *,
    batch: int,
    context: int,
) -> tuple[OptimizationOption, ...]:
    options: list[OptimizationOption] = []
    budget = hardware.memory_budget_bytes
    actual_bytes = memory.weights.actual_bytes
    for quant in quantify_alternatives(memory, budget):
        if (
            quant.status == ClaimStatus.YES
            and quant.peak is not None
            and (actual_bytes is None or (quant.alternative.weight_bytes or 0) < actual_bytes)
        ):
            options.append(
                OptimizationOption(
                    kind="quantization",
                    label=f"{quant.alternative.name} weights",
                    detail=(
                        f"Hypothetical {quant.alternative.name} weights fit with a "
                        f"worst-case peak of {quant.peak.max / 1e9:.2f} GB. This does "
                        "not claim an artifact or runtime exists."
                    ),
                    peak=quant.peak,
                    confidence=quant.alternative.confidence,
                )
            )

    if batch > 1:
        lower = estimate_memory(inspection, context=memory.context_effective or context, batch=1)
        if _fit_status(lower.peak, budget) == ClaimStatus.YES and lower.peak is not None:
            options.append(
                OptimizationOption(
                    kind="batch",
                    label="batch = 1",
                    detail=(
                        f"Batch 1 fits with a worst-case peak of {lower.peak.max / 1e9:.2f} GB. "
                        "Use the lower batch if the single sequence fits your "
                        "latency/throughput need."
                    ),
                    peak=lower.peak,
                    confidence=lower.confidence,
                )
            )

    effective = memory.context_effective or context
    if effective > SMALLER_CONTEXT_TOKENS:
        lower = estimate_memory(inspection, context=SMALLER_CONTEXT_TOKENS, batch=batch)
        if _fit_status(lower.peak, budget) == ClaimStatus.YES and lower.peak is not None:
            options.append(
                OptimizationOption(
                    kind="context",
                    label=f"context = {SMALLER_CONTEXT_TOKENS}",
                    detail=(
                        f"Reducing context to {SMALLER_CONTEXT_TOKENS} tokens fits with a "
                        f"worst-case peak of {lower.peak.max / 1e9:.2f} GB. KV-cache size "
                        "scales with context; weights do not."
                    ),
                    peak=lower.peak,
                    confidence=lower.confidence,
                )
            )
    return tuple(options)


def decide_verdict(
    *,
    inspection: ModelInspection,
    memory: MemoryEstimate,
    hardware: HardwareProfile,
    support: SupportClaim,
    verified: VerifiedClaim,
    context: int,
    batch: int,
    model_class_supported: bool,
) -> VerdictResult:
    fit = build_fit_claim(memory, hardware)
    quant_fits = quantify_alternatives(memory, hardware.memory_budget_bytes)
    options = _options(
        inspection,
        memory,
        hardware,
        batch=batch,
        context=context,
    )
    reasons: list[Issue] = []
    reasons.extend(fit.reasons)
    reasons.extend(support.reasons)
    reasons.append(
        Issue(
            (
                "verification_unknown"
                if verified.status == ClaimStatus.UNKNOWN
                else "verification_checked"
            ),
            verified.summary,
            "info" if verified.status == ClaimStatus.UNKNOWN else "warning",
        )
    )

    if not model_class_supported:
        summary = (
            "UNKNOWN: this build's verdict logic covers causal LLMs only. "
            "ASR/TTS fit and coarse speed are a later step."
        )
        reasons.append(
            Issue(
                "model_class_pending",
                "No GO/NO claim for this model class in this step.",
                "warning",
            )
        )
        return VerdictResult(
            value=Verdict.UNKNOWN,
            summary=summary,
            basis_claims=(),
            reasons=tuple(reasons),
            confidence=Confidence.LOW,
            fit=fit,
            quant_fits=quant_fits,
            options=options,
        )

    if support.status == ClaimStatus.NO:
        summary = "NO: the support matrix has no usable runtime path for this repo/artifact."
        return VerdictResult(
            value=Verdict.NO,
            summary=summary,
            basis_claims=("supported",),
            reasons=tuple(reasons),
            confidence=support.confidence,
            fit=fit,
            quant_fits=quant_fits,
            options=options,
        )

    if fit.status == ClaimStatus.NO:
        if options and support.status == ClaimStatus.YES:
            labels = ", ".join(option.label for option in options)
            summary = (
                f"OPTIMIZE: the requested configuration does not fit, but {labels} "
                f"would fit. {support.summary}"
            )
            reasons.append(
                Issue(
                    "smaller_configuration_fits",
                    f"Documented smaller configurations fit: {labels}.",
                    "info",
                )
            )
            return VerdictResult(
                value=Verdict.OPTIMIZE,
                summary=summary,
                basis_claims=("supported",),
                reasons=tuple(reasons),
                confidence=Confidence.lowest(
                    fit.confidence, support.confidence, Confidence.MEDIUM
                ),
                fit=fit,
                quant_fits=quant_fits,
                options=options,
            )
        summary = (
            "NO: even the best-case memory estimate does not fit, and no smaller "
            "configuration is known to fit."
        )
        return VerdictResult(
            value=Verdict.NO,
            summary=summary,
            basis_claims=("fits",),
            reasons=tuple(reasons),
            confidence=fit.confidence,
            fit=fit,
            quant_fits=quant_fits,
            options=options,
        )

    if fit.status == ClaimStatus.UNKNOWN:
        if options and support.status == ClaimStatus.YES:
            labels = ", ".join(option.label for option in options)
            summary = (
                f"OPTIMIZE: the requested memory range is uncertain, but {labels} "
                f"fits under the worst-case assumption. {support.summary}"
            )
            reasons.append(
                Issue(
                    "smaller_configuration_fits",
                    f"Documented smaller configurations fit: {labels}.",
                    "info",
                )
            )
            return VerdictResult(
                value=Verdict.OPTIMIZE,
                summary=summary,
                basis_claims=("supported",),
                reasons=tuple(reasons),
                confidence=Confidence.lowest(
                    fit.confidence, support.confidence, Confidence.MEDIUM
                ),
                fit=fit,
                quant_fits=quant_fits,
                options=options,
            )
        if support.status == ClaimStatus.YES:
            summary = (
                "UNKNOWN: the memory range straddles the budget. OmniRun will not "
                "turn that into a GO."
            )
        else:
            summary = (
                "UNKNOWN: runtime support or the memory estimate is not confirmed."
            )
        return VerdictResult(
            value=Verdict.UNKNOWN,
            summary=summary,
            basis_claims=(),
            reasons=tuple(reasons),
            confidence=Confidence.LOW,
            fit=fit,
            quant_fits=quant_fits,
            options=options,
        )

    # FITS yes.
    if support.status != ClaimStatus.YES:
        summary = (
            "UNKNOWN: FITS is yes, but SUPPORTED is not confirmed. "
            "OmniRun will not say GO on memory alone."
        )
        return VerdictResult(
            value=Verdict.UNKNOWN,
            summary=summary,
            basis_claims=("fits",),
            reasons=tuple(reasons),
            confidence=Confidence.lowest(
                fit.confidence, support.confidence, Confidence.MEDIUM
            ),
            fit=fit,
            quant_fits=quant_fits,
            options=options,
        )

    tight = fit.headroom_ratio is not None and fit.headroom_ratio < TIGHT_HEADROOM_FRACTION
    if not support.direct_runtime_available:
        summary = (
            "OPTIMIZE: FITS and SUPPORTED, but every known runtime path requires "
            f"conversion. {support.summary}"
        )
        value = Verdict.OPTIMIZE
        confidence = Confidence.lowest(fit.confidence, support.confidence, Confidence.MEDIUM)
    elif tight:
        summary = (
            f"OPTIMIZE: FITS and SUPPORTED, but worst-case headroom is only "
            f"{fit.headroom_ratio:.1%}. Reduce context/batch or use smaller weights. "
            f"{support.summary}"
        )
        value = Verdict.OPTIMIZE
        confidence = Confidence.lowest(fit.confidence, support.confidence)
    else:
        summary = (
            f"GO. {fit.summary} {support.summary} "
            "VERIFIED is unknown: no recorded real run."
        )
        value = Verdict.GO
        confidence = Confidence.lowest(fit.confidence, support.confidence)

    return VerdictResult(
        value=value,
        summary=summary,
        basis_claims=("fits", "supported"),
        reasons=tuple(reasons),
        confidence=confidence,
        fit=fit,
        quant_fits=quant_fits,
        options=options,
    )
