import type { components } from "./schema.gen";

export type CheckRequest = components["schemas"]["CheckRequest"];
export type CheckResponse = components["schemas"]["CheckResponse"];
export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type DevicesResponse = components["schemas"]["DevicesResponse"];
export type DeviceEntry = components["schemas"]["DeviceEntry"];
export type HardwareInput = CheckRequest["hardware"];
export type ManualHardwareInput = components["schemas"]["ManualHardwareInput"];
export type HelperHardwareInput = components["schemas"]["HelperHardwareInput"];
export type UnknownHardwareInput = components["schemas"]["UnknownHardwareInput"];
export type VerdictReport = components["schemas"]["VerdictReport"];
export type ClaimsReport = components["schemas"]["ClaimsReport"];
export type FitClaimReport = components["schemas"]["FitClaimReport"];
export type SupportClaimReport = components["schemas"]["SupportClaimReport"];
export type VerifiedClaimReport = components["schemas"]["VerifiedClaimReport"];
export type MemoryReport = components["schemas"]["MemoryReport"];
export type SpeedReport = components["schemas"]["SpeedReport"];
export type RangeBytes = components["schemas"]["RangeBytes"];
export type RangeFloat = components["schemas"]["RangeFloat"];
export type Recommendation = components["schemas"]["Recommendation"];
export type EnvironmentHint = components["schemas"]["EnvironmentHint"];
export type ArtifactReport = components["schemas"]["ArtifactReport"];
export type SweepReport = components["schemas"]["SweepReport"];
export type SweepPointReport = components["schemas"]["SweepPointReport"];
export type SweepScenarioReport = components["schemas"]["SweepScenarioReport"];
export type FindRequest = components["schemas"]["FindRequest"];
export type FindResponse = components["schemas"]["FindResponse"];
export type FindCandidate = components["schemas"]["FindCandidate"];
export type FindError = components["schemas"]["FindError"];
export type HardwareSummary = components["schemas"]["HardwareSummary"];
export type ModelSummary = components["schemas"]["ModelSummary"];
export type Reason = components["schemas"]["Reason"];
export type WarningItem = components["schemas"]["WarningItem"];
export type AssumptionItem = components["schemas"]["AssumptionItem"];
export type RuntimePath = components["schemas"]["RuntimePathReport"];

// These are OpenAPI inline unions, not named component schemas. Deriving them
// from the generated response fields keeps the source of truth in OpenAPI.
export type Confidence = CheckResponse["verdict"]["confidence"];
export type ClaimStatus = CheckResponse["claims"]["fits"]["status"];
export type Verdict = CheckResponse["verdict"]["value"];
export type HardwareKind = CheckResponse["hardware"]["kind"];
