import type { Confidence, RangeBytes, RangeFloat } from "../api/types";

export const GIB = 1024 ** 3;

/**
 * The app's visible unit is "GB", defined as 2^30 bytes (GiB). The API's JSON
 * memory values are raw bytes. This keeps labels short without pretending the
 * numbers are decimal GB; the UI repeats the definition in its units note.
 */
export function formatGB(bytes: number | null | undefined, digits = 2): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return "—";
  const value = bytes / GIB;
  if (value === 0) return "0 GB";
  if (Math.abs(value) >= 100) return `${value.toFixed(0)} GB`;
  if (Math.abs(value) >= 10) return `${value.toFixed(1)} GB`;
  return `${value.toFixed(digits)} GB`;
}

export function formatGBValue(bytes: number | null | undefined, digits = 2): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return "—";
  const value = bytes / GIB;
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1);
  return value.toFixed(digits);
}

export function formatBytesRange(
  range: RangeBytes | null | undefined,
  digits = 2,
): string {
  if (!range) return "—";
  const min = formatGBValue(range.min, digits);
  const max = formatGBValue(range.max, digits);
  if (range.min === range.max) return `${min} GB`;
  return `${min}–${max} GB`;
}

export function formatRangeFloat(
  range: RangeFloat | null | undefined,
  unit = "",
  digits = 1,
): string {
  if (!range) return "—";
  const min = range.min.toFixed(digits);
  const max = range.max.toFixed(digits);
  const suffix = unit ? ` ${unit}` : "";
  if (range.min === range.max) return `${min}${suffix}`;
  return `${min}–${max}${suffix}`;
}

export function formatLikely(range: RangeFloat | null | undefined, unit = "", digits = 1): string {
  if (!range) return "—";
  const suffix = unit ? ` ${unit}` : "";
  return `${range.likely.toFixed(digits)}${suffix}`;
}

export function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function formatFloat(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function formatPercent(ratio: number | null | undefined, digits = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return "—";
  return `${(ratio * 100).toFixed(digits)}%`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(date);
}

export function shortRevision(value: string | null | undefined, length = 8): string {
  if (!value) return "—";
  return value.slice(0, length);
}

export function confidenceLabel(value: Confidence): string {
  switch (value) {
    case "high":
      return "High confidence";
    case "medium":
      return "Medium confidence";
    case "low":
      return "Low confidence";
    default:
      return "Unknown confidence";
  }
}

export function confidenceShort(value: Confidence): string {
  switch (value) {
    case "high":
      return "High";
    case "medium":
      return "Medium";
    case "low":
      return "Low";
    default:
      return "Unknown";
  }
}

export function claimStatusLabel(value: "yes" | "no" | "unknown"): string {
  switch (value) {
    case "yes":
      return "Yes";
    case "no":
      return "No";
    case "unknown":
      return "Unknown";
    default:
      return value;
  }
}

export function bandwidthSourceLabel(value: string): string {
  switch (value) {
    case "helper_measured":
      return "Measured by helper";
    case "device_table":
      return "Device table";
    case "assumed":
      return "Assumed default";
    case "unknown":
      return "Unknown";
    default:
      return value.replaceAll("_", " ");
  }
}

export function bandwidthSourceKind(
  value: string,
): "measured" | "table" | "assumed" | "unknown" {
  if (value === "helper_measured") return "measured";
  if (value === "device_table") return "table";
  if (value === "assumed") return "assumed";
  return "unknown";
}

export function memorySourceLabel(value: string): string {
  switch (value) {
    case "helper_measured":
      return "Measured by helper";
    case "device_table":
      return "Device table";
    case "user":
      return "User input";
    case "assumed":
      return "Assumed";
    case "unknown":
      return "Unknown";
    default:
      return value.replaceAll("_", " ");
  }
}

export function hardwareKindLabel(value: string): string {
  switch (value) {
    case "unified":
      return "Unified memory";
    case "discrete":
      return "Discrete GPU";
    case "cpu":
      return "CPU";
    default:
      return value;
  }
}

export function speedClassLabel(value: string): string {
  switch (value) {
    case "interactive":
      return "Interactive";
    case "usable":
      return "Usable";
    case "slow":
      return "Slow";
    default:
      return "Unknown";
  }
}

export function formatRetryAfter(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return null;
  if (seconds < 60) return `${Math.max(1, Math.ceil(seconds))}s`;
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} min`;
}
