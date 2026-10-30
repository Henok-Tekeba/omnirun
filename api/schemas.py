"""The versioned JSON contract.

This file is the frontend contract. Keep field names stable within 1.x; add
fields rather than renaming them. All memory numbers are bytes; bandwidth is
decimal GB/s (10^9 bytes/s). Human display code chooses GiB/GB labels.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

SCHEMA_VERSION = "1.0"

ConfidenceValue = Literal["high", "medium", "low"]
ClaimStatusValue = Literal["yes", "no", "unknown"]
SeverityValue = Literal["info", "warning", "risk"]
VerdictValue = Literal["GO", "OPTIMIZE", "NO", "UNKNOWN"]
SpeedClassValue = Literal["interactive", "usable", "slow", "unknown"]
ModelFormatValue = Literal["safetensors", "pytorch_pickle", "gguf", "adapter", "unknown"]
HardwareSourceValue = Literal["helper", "manual", "unknown"]
HardwareKindValue = Literal["unified", "discrete", "cpu"]
ModelClassValue = Literal["llm", "asr", "tts", "unsupported"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------- request


class HelperHardwareInput(StrictModel):
    source: Literal["helper"]
    code: str = Field(min_length=1, max_length=4096, description="OR1... code from helper")


class ManualHardwareInput(StrictModel):
    source: Literal["manual"]
    device_id: str = Field(min_length=1, max_length=100, description="id from data/devices.yaml")
    ram_gib: float | None = Field(default=None, ge=1, le=4096)


class UnknownHardwareInput(StrictModel):
    source: Literal["unknown"]
    ram_gib: float | None = Field(default=None, ge=1, le=4096)


HardwareInput = Annotated[
    HelperHardwareInput | ManualHardwareInput | UnknownHardwareInput,
    Field(discriminator="source"),
]


class CheckRequest(StrictModel):
    model: str = Field(
        min_length=1,
        max_length=512,
        description="Hugging Face URL or repo id",
    )
    hardware: HardwareInput
    context: int = Field(default=4096, ge=1, le=1_048_576)
    batch: int = Field(default=1, ge=1, le=1024)
    hf_token: SecretStr | None = Field(
        default=None,
        exclude=True,
        description="Optional HF token for gated/private repos. Never echoed or logged.",
    )

    @field_validator("model")
    @classmethod
    def _model_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("model must not be blank")
        return value


# -------------------------------------------------------------------- envelopes


class RangeBytes(StrictModel):
    min: int = Field(ge=0)
    likely: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> RangeBytes:
        if not (self.min <= self.likely <= self.max):
            raise ValueError("range must satisfy min <= likely <= max")
        return self


class RangeFloat(StrictModel):
    min: float = Field(ge=0)
    likely: float = Field(ge=0)
    max: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> RangeFloat:
        if not (self.min <= self.likely <= self.max):
            raise ValueError("range must satisfy min <= likely <= max")
        return self


class Reason(StrictModel):
    code: str
    message: str
    severity: SeverityValue


class WarningItem(StrictModel):
    code: str
    message: str
    severity: SeverityValue


class AssumptionItem(StrictModel):
    id: str
    text: str


class CacheInfo(StrictModel):
    model_info_cached: bool
    model_info_stale: bool
    result_cache_hit: bool
    result_age_seconds: float | None = None


class Links(StrictModel):
    hf_model: str
    hf_tree: str


# ---------------------------------------------------------------------- model


class ModelSummary(StrictModel):
    repo_id: str
    requested_repo_id: str
    revision: str
    source_url: str | None
    model_class: ModelClassValue
    architecture: str | None
    model_type: str | None
    pipeline_tag: str | None
    library_name: str | None
    format: ModelFormatValue
    gated: bool
    private: bool
    trust_remote_code_required: bool
    config_available: bool
    last_modified: datetime | None
    weight_files_count: int


class InputsSummary(StrictModel):
    model_input: str
    context_requested: int
    context_effective: int | None
    context_clamped: bool
    batch: int
    hardware_source: HardwareSourceValue


class HardwareSummary(StrictModel):
    source: HardwareSourceValue
    kind: HardwareKindValue
    device_id: str | None
    device_name: str
    vendor: str | None
    system_ram_bytes: int | None
    device_memory_bytes: int | None
    memory_budget_bytes: int | None
    bandwidth_gbps: float | None
    bandwidth_source: str
    memory_source: str
    confidence: ConfidenceValue
    memory_confidence: ConfidenceValue
    bandwidth_confidence: ConfidenceValue
    apple_fraction: float | None
    measured_at: datetime | None
    cpu: str | None
    cores: int | None
    helper_tool: str | None
    notes: list[str]


# --------------------------------------------------------------------- claims


class FitClaimReport(StrictModel):
    status: ClaimStatusValue
    confidence: ConfidenceValue
    summary: str
    reasons: list[Reason]
    budget_bytes: int | None
    peak: RangeBytes | None
    headroom_bytes: int | None
    headroom_ratio: float | None


class RuntimePathReport(StrictModel):
    name: str
    min_version: str
    version_scheme: str
    artifact: str
    available: bool
    status: Literal["available", "requires_conversion", "artifact_missing"]
    direct: bool
    notes: str | None
    source: str | None


class SupportClaimReport(StrictModel):
    status: ClaimStatusValue
    confidence: ConfidenceValue
    summary: str
    reasons: list[Reason]
    architecture: str | None
    matched_by: str | None
    matrix_entry_found: bool
    direct_runtime_available: bool
    custom_code_risk: bool
    runtimes: list[RuntimePathReport]


class VerifiedRunReport(StrictModel):
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


class VerifiedClaimReport(StrictModel):
    status: ClaimStatusValue
    confidence: ConfidenceValue
    summary: str
    reasons: list[Reason]
    runs: list[VerifiedRunReport]


class ClaimsReport(StrictModel):
    fits: FitClaimReport
    supported: SupportClaimReport
    verified: VerifiedClaimReport


class VerdictReport(StrictModel):
    value: VerdictValue
    summary: str
    basis_claims: list[Literal["fits", "supported", "verified"]]
    reasons: list[Reason]
    confidence: ConfidenceValue


# --------------------------------------------------------------------- memory


class QuantAlternativeReport(StrictModel):
    name: str
    bits_per_param: float
    weight_bytes: int | None
    peak: RangeBytes | None
    fits: ClaimStatusValue
    confidence: ConfidenceValue
    note: str


class WeightReport(StrictModel):
    kind: Literal["exact", "upper_bound", "unknown"]
    actual_bytes: int | None
    range: RangeBytes | None
    params: int | None
    param_source: str | None
    confidence: ConfidenceValue
    alternatives: list[QuantAlternativeReport]


class KVReport(StrictModel):
    available: bool
    bytes_range: RangeBytes | None
    bytes_likely: int | None
    per_sequence_likely: int | None
    attention: str
    layers_full: int
    layers_windowed: int
    dtype_bytes: float | None
    context_requested: int
    context_effective: int | None
    batch: int
    confidence: ConfidenceValue
    formula: str


class MemoryReport(StrictModel):
    budget_bytes: int | None
    context_requested: int
    context_effective: int | None
    batch: int
    weights: WeightReport
    kv_cache: KVReport
    overhead: RangeBytes | None
    peak: RangeBytes | None
    confidence: ConfidenceValue


# ---------------------------------------------------------------------- speed


class SpeedReport(StrictModel):
    available: bool
    metric: Literal["decode_tokens_per_second"]
    aggregate: RangeFloat | None
    per_sequence: RangeFloat | None
    speed_class: SpeedClassValue
    confidence: ConfidenceValue
    bandwidth_gbps: float | None
    active_weight_bytes: int | None
    active_weight_source: str | None
    kv_bytes_per_sequence: int | None
    efficiency: RangeFloat
    prefill_estimated: bool
    batch: int
    notes: list[str]


# ------------------------------------------------------------- recommendations


class Recommendation(StrictModel):
    kind: Literal[
        "quantization",
        "runtime",
        "smaller_model",
        "context",
        "batch",
        "environment",
        "note",
    ]
    title: str
    detail: str
    confidence: ConfidenceValue
    runtime: str | None = None
    min_version: str | None = None
    requires_conversion: bool | None = None
    estimated_peak_bytes: RangeBytes | None = None
    url: str | None = None


class EnvironmentHint(StrictModel):
    available: bool
    command: str | None
    reference_date: date | None
    notes: list[str]


# --------------------------------------------------------------- artifacts


class ArtifactReport(StrictModel):
    path: str
    files: list[str]
    format: Literal[
        "gguf",
        "safetensors",
        "pytorch_pickle",
        "ctranslate2",
        "onnx",
        "adapter",
        "unknown",
    ]
    quantization: str | None
    size_bytes: int | None
    runtime_hint: str | None
    direct: bool
    fits: ClaimStatusValue
    peak: RangeBytes | None
    weights_fit: ClaimStatusValue
    weights_peak: RangeBytes | None
    confidence: ConfidenceValue
    note: str


# ------------------------------------------------------------------- response


class CheckResponse(StrictModel):
    schema_version: Literal["1.0"]
    request_id: str
    checked_at: datetime
    model: ModelSummary
    inputs: InputsSummary
    hardware: HardwareSummary
    verdict: VerdictReport
    claims: ClaimsReport
    memory: MemoryReport
    speed: SpeedReport
    recommendations: list[Recommendation]
    environment_hint: EnvironmentHint | None
    artifacts: list[ArtifactReport]
    assumptions: list[AssumptionItem]
    warnings: list[WarningItem]
    links: Links
    cache: CacheInfo


class ErrorDetail(StrictModel):
    code: str
    message: str
    hint: str | None
    status: int
    retryable: bool
    retry_after_seconds: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(StrictModel):
    schema_version: Literal["1.0"]
    request_id: str
    error: ErrorDetail


class SchemaResponse(StrictModel):
    schema_version: Literal["1.0"]
    request: dict[str, Any]
    response: dict[str, Any]
    error: dict[str, Any]


# --------------------------------------------------------------------- devices


class DeviceEntry(StrictModel):
    id: str
    name: str
    vendor: str
    kind: HardwareKindValue
    bandwidth_gbps: float
    vram_gib: float | None
    ram_options_gib: list[float]
    default_ram_gib: float | None
    source: str
    notes: str | None


class DevicesResponse(StrictModel):
    schema_version: Literal["1.0"]
    devices: list[DeviceEntry]
