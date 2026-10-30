"""What-if sweeps over an inspected model and a hardware profile.

The estimator is cheap after inspection, so these are real evaluations rather
than interpolation. The sweep never invents a fit: a range that straddles the
budget stays UNKNOWN.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.claims import ClaimStatus
from core.estimate import MemoryEstimate, estimate_memory
from core.hardware import GIB, HardwareProfile
from core.inspect.model import ModelInspection
from core.inspect.types import RangeEstimate
from core.verdict import QuantFit, quantify_alternatives

MAX_BATCH = 1024
SMALLER_CONTEXT = 4096
FREE_MEMORY_SCENARIO_BYTES = 4 * GIB
MAX_SWEEP_CONTEXT = 1_048_576


@dataclass(frozen=True, slots=True)
class SweepPoint:
    context: int
    peak: RangeEstimate | None
    fits: ClaimStatus


@dataclass(frozen=True, slots=True)
class SweepScenario:
    id: str
    label: str
    context: int
    batch: int
    budget_bytes: int | None
    peak: RangeEstimate | None
    fits: ClaimStatus


@dataclass(frozen=True, slots=True)
class SweepResult:
    budget_bytes: int | None
    model_max_context: int | None
    context_points: tuple[SweepPoint, ...]
    max_context_that_fits: int | None
    max_batch_that_fits: int | None
    best_quantization: QuantFit | None
    scenarios: tuple[SweepScenario, ...]


def fit_status(peak: RangeEstimate | None, budget: int | None) -> ClaimStatus:
    if peak is None or budget is None:
        return ClaimStatus.UNKNOWN
    if peak.max <= budget:
        return ClaimStatus.YES
    if peak.min > budget:
        return ClaimStatus.NO
    return ClaimStatus.UNKNOWN


def _effective_max_context(inspection: ModelInspection, requested: int) -> int:
    if inspection.config and inspection.config.max_positions:
        return min(MAX_SWEEP_CONTEXT, max(1, inspection.config.max_positions))
    return min(MAX_SWEEP_CONTEXT, max(requested, SMALLER_CONTEXT))


def _max_fitting(
    estimate: Callable[[int], RangeEstimate | None],
    upper: int,
    budget: int | None,
) -> int | None:
    if budget is None or upper < 1:
        return None
    first = estimate(1)
    if first is None or first.max > budget:
        return None
    low, high = 1, upper
    while low < high:
        middle = (low + high + 1) // 2
        peak = estimate(middle)
        if peak is not None and peak.max <= budget:
            low = middle
        else:
            high = middle - 1
    return low


def _context_points(
    inspection: ModelInspection,
    max_context: int,
    requested: int,
    batch: int,
) -> tuple[SweepPoint, ...]:
    candidates = {
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
        32768,
        65536,
        131072,
    }
    candidates = {value for value in candidates if value <= max_context}
    candidates.add(min(requested, max_context))
    candidates.add(max_context)
    points: list[SweepPoint] = []
    for context in sorted(candidates):
        peak = estimate_memory(inspection, context=context, batch=batch).peak
        points.append(SweepPoint(context=context, peak=peak, fits=ClaimStatus.UNKNOWN))
    return tuple(points)


def build_sweep(
    inspection: ModelInspection,
    hardware: HardwareProfile,
    memory: MemoryEstimate,
    *,
    context: int,
    batch: int,
) -> SweepResult:
    budget = hardware.memory_budget_bytes
    max_context = _effective_max_context(inspection, context)

    def context_estimate(value: int) -> RangeEstimate | None:
        return estimate_memory(inspection, context=value, batch=batch).peak

    def batch_estimate(value: int) -> RangeEstimate | None:
        effective = memory.context_effective or context
        return estimate_memory(inspection, context=effective, batch=value).peak

    max_context_fit = _max_fitting(context_estimate, max_context, budget)
    max_batch_fit = _max_fitting(batch_estimate, MAX_BATCH, budget)

    points = tuple(
        SweepPoint(
            context=point.context,
            peak=point.peak,
            fits=fit_status(point.peak, budget),
        )
        for point in _context_points(inspection, max_context, context, batch)
    )

    scenarios: list[SweepScenario] = []
    free_budget = budget + FREE_MEMORY_SCENARIO_BYTES if budget is not None else None
    scenarios.append(
        SweepScenario(
            id="free_4gb",
            label="Free 4 GB",
            context=memory.context_effective or context,
            batch=batch,
            budget_bytes=free_budget,
            peak=memory.peak,
            fits=fit_status(memory.peak, free_budget),
        )
    )

    if context > SMALLER_CONTEXT:
        smaller = estimate_memory(inspection, context=SMALLER_CONTEXT, batch=batch)
        scenarios.append(
            SweepScenario(
                id="smaller_context",
                label=f"Context {SMALLER_CONTEXT:,}",
                context=SMALLER_CONTEXT,
                batch=batch,
                budget_bytes=budget,
                peak=smaller.peak,
                fits=fit_status(smaller.peak, budget),
            )
        )

    if batch > 1:
        single = estimate_memory(
            inspection,
            context=memory.context_effective or context,
            batch=1,
        )
        scenarios.append(
            SweepScenario(
                id="batch_1",
                label="Batch 1",
                context=memory.context_effective or context,
                batch=1,
                budget_bytes=budget,
                peak=single.peak,
                fits=fit_status(single.peak, budget),
            )
        )

    alternatives = quantify_alternatives(memory, budget)
    actual_bytes = memory.weights.actual_bytes
    fitting = [
        item
        for item in alternatives
        if item.status == ClaimStatus.YES
        and (
            actual_bytes is None
            or (item.alternative.weight_bytes or 0) < actual_bytes
        )
    ]
    best = max(
        fitting,
        key=lambda item: (
            item.alternative.bits_per_param,
            -(item.peak.max if item.peak is not None else float("inf")),
        ),
        default=None,
    )

    return SweepResult(
        budget_bytes=budget,
        model_max_context=max_context,
        context_points=points,
        max_context_that_fits=max_context_fit,
        max_batch_that_fits=max_batch_fit,
        best_quantization=best,
        scenarios=tuple(scenarios),
    )


__all__ = [
    "FREE_MEMORY_SCENARIO_BYTES",
    "MAX_BATCH",
    "SMALLER_CONTEXT",
    "SweepPoint",
    "SweepResult",
    "SweepScenario",
    "build_sweep",
    "fit_status",
]
