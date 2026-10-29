"""Decode-speed estimation for causal LLMs.

tok/s ~ effective_bandwidth * efficiency / bytes_read_per_token

`bytes_read_per_token` includes the active weights read once per forward step
(shared by the batch) and the KV cache read for each sequence. Prefill/TTFT are
out of scope in v1. Efficiency is a documented range, never a measured claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.claims import SpeedClass
from core.estimate import MemoryEstimate
from core.hardware import HardwareProfile
from core.inspect.model import ModelInspection
from core.inspect.types import Confidence, Issue, RangeEstimate

DENSE_EFFICIENCY = (0.55, 0.70, 0.85)
MOE_EFFICIENCY = (0.25, 0.40, 0.60)
INTERACTIVE_TOKENS_PER_SECOND = 20.0
USABLE_TOKENS_PER_SECOND = 5.0

# A single decode step for a batch B reads:
#   active_weight_bytes  (once, shared by all sequences)
#   B * kv_bytes_per_seq (one KV read per sequence)
# so aggregate tok/s = B * effective_bw * efficiency / (weights + B*kv).
# Bytes per *generated token* at B=1 is weights + kv. At B>1 the weight read is
# amortized, which is why aggregate throughput improves with batching.


@dataclass(frozen=True, slots=True)
class SpeedEstimate:
    available: bool
    aggregate: RangeEstimate | None
    per_sequence: RangeEstimate | None
    speed_class: SpeedClass
    confidence: Confidence
    bandwidth_gbps: float | None
    active_weight_bytes: int | None
    active_weight_source: str | None
    kv_bytes_per_sequence: int | None
    efficiency: RangeEstimate
    batch: int
    notes: tuple[str, ...]
    issues: tuple[Issue, ...]


def _unavailable(
    *,
    reason: str,
    confidence: Confidence = Confidence.LOW,
    bandwidth_gbps: float | None = None,
    batch: int,
    active_weight_bytes: int | None = None,
    kv_bytes_per_sequence: int | None = None,
) -> SpeedEstimate:
    return SpeedEstimate(
        available=False,
        aggregate=None,
        per_sequence=None,
        speed_class=SpeedClass.UNKNOWN,
        confidence=confidence,
        bandwidth_gbps=bandwidth_gbps,
        active_weight_bytes=active_weight_bytes,
        active_weight_source=None,
        kv_bytes_per_sequence=kv_bytes_per_sequence,
        efficiency=RangeEstimate(*DENSE_EFFICIENCY),
        batch=batch,
        notes=(reason,),
        issues=(Issue("speed_unavailable", reason, "warning"),),
    )


def estimate_llm_speed(
    inspection: ModelInspection,
    memory: MemoryEstimate,
    hardware: HardwareProfile,
    *,
    batch: int,
) -> SpeedEstimate:
    if not inspection.is_llm:
        return _unavailable(
            reason=(
                "v1's decode-speed formula covers causal LLMs only. ASR/TTS speed "
                "uses a coarse class in a later step."
            ),
            batch=batch,
            active_weight_bytes=inspection.active_weight_bytes,
        )
    if hardware.bandwidth_gbps is None:
        return _unavailable(
            reason=(
                "No bandwidth is available for this GPU. OmniRun will not guess a "
                "speed from a device name it does not recognize."
            ),
            batch=batch,
            active_weight_bytes=inspection.active_weight_bytes,
        )
    if inspection.active_weight_bytes is None:
        return _unavailable(
            reason=(
                "Active weight bytes are unknown (likely an unrecognized MoE tensor "
                "layout). Speed is UNKNOWN rather than using total expert weights."
            ),
            batch=batch,
        )
    if memory.kv.bytes_range is None or memory.kv.per_sequence_likely is None:
        return _unavailable(
            reason="KV-cache memory is unknown, so bytes read per token cannot be computed.",
            batch=batch,
            bandwidth_gbps=hardware.bandwidth_gbps,
            active_weight_bytes=inspection.active_weight_bytes,
        )

    is_moe = bool(inspection.config and inspection.config.is_moe)
    efficiency = RangeEstimate(*(MOE_EFFICIENCY if is_moe else DENSE_EFFICIENCY))
    kv_range = memory.kv.bytes_range
    kv_min_per_seq = kv_range.min / batch
    kv_likely_per_seq = kv_range.likely / batch
    kv_max_per_seq = kv_range.max / batch

    bandwidth_bytes = hardware.bandwidth_gbps * 1e9
    weight_bytes = float(inspection.active_weight_bytes)

    # Aggregate tokens/s for a whole decode step. The min uses the slowest
    # efficiency and the largest KV read; max uses the fastest efficiency and
    # the smallest KV read. Weight bytes are exact or an upper bound.
    step_min = weight_bytes + batch * kv_max_per_seq
    step_likely = weight_bytes + batch * kv_likely_per_seq
    step_max = weight_bytes + batch * kv_min_per_seq
    if step_min <= 0:
        return _unavailable(
            reason="Decode bytes per token are zero; speed cannot be estimated.",
            batch=batch,
            bandwidth_gbps=hardware.bandwidth_gbps,
            active_weight_bytes=inspection.active_weight_bytes,
        )
    aggregate = RangeEstimate(
        round(bandwidth_bytes * efficiency.min / step_min * batch, 1),
        round(bandwidth_bytes * efficiency.likely / step_likely * batch, 1),
        round(bandwidth_bytes * efficiency.max / step_max * batch, 1),
    )
    per_sequence = RangeEstimate(
        round(aggregate.min / batch, 1),
        round(aggregate.likely / batch, 1),
        round(aggregate.max / batch, 1),
    )

    likely = aggregate.likely
    if likely >= INTERACTIVE_TOKENS_PER_SECOND:
        speed_class = SpeedClass.INTERACTIVE
    elif likely >= USABLE_TOKENS_PER_SECOND:
        speed_class = SpeedClass.USABLE
    else:
        speed_class = SpeedClass.SLOW

    confidence = Confidence.lowest(
        hardware.bandwidth_confidence,
        memory.confidence,
        Confidence.MEDIUM,
    )
    if is_moe and inspection.safetensors and inspection.safetensors.expert_stats:
        confidence = Confidence.lowest(
            confidence, inspection.safetensors.expert_stats.confidence
        )

    notes = [
        "Decode-only estimate. Prefill and time-to-first-token are not estimated in v1.",
        (
            f"Formula: {hardware.bandwidth_gbps:g} GB/s * efficiency / "
            f"(active weights {inspection.active_weight_bytes / 1e9:.3f} GB + "
            f"batch {batch} * KV {kv_likely_per_seq / 1e9:.3f} GB), then * batch "
            "for aggregate tokens/s."
        ),
        (
            f"Efficiency range {efficiency.min:.2f}-{efficiency.max:.2f} "
            f"(likely {efficiency.likely:.2f}) is a documented engineering assumption, "
            "not a measured constant."
        ),
        "The KV read uses the effective context and the memory estimate's KV range.",
        "Batch assumes perfect continuous batching; small-batch real-world throughput "
        "may be lower.",
    ]
    if inspection.active_weight_source == "expert_tensor_names":
        notes.append("MoE uses active expert bytes inferred from tensor names, not total weights.")
    if inspection.weight_bytes_exact is False:
        notes.append(
            "Active weight bytes are an upper bound (pickle/GGUF file sizes), so this "
            "speed estimate is conservative."
        )
    if hardware.kind.value == "cpu":
        notes.append(
            "CPU-only throughput is especially sensitive to runtime threading and SIMD; "
            "treat this range as a coarse planning number."
        )

    return SpeedEstimate(
        available=True,
        aggregate=aggregate,
        per_sequence=per_sequence,
        speed_class=speed_class,
        confidence=confidence,
        bandwidth_gbps=hardware.bandwidth_gbps,
        active_weight_bytes=inspection.active_weight_bytes,
        active_weight_source=inspection.active_weight_source,
        kv_bytes_per_sequence=memory.kv.per_sequence_likely,
        efficiency=efficiency,
        batch=batch,
        notes=tuple(notes),
        issues=(),
    )
