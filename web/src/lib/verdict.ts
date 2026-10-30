import type { Verdict } from "../api/types";

export type VerdictTone = "go" | "optimize" | "no" | "unknown";

export function verdictTone(value: Verdict): VerdictTone {
  switch (value) {
    case "GO":
      return "go";
    case "OPTIMIZE":
      return "optimize";
    case "NO":
      return "no";
    default:
      return "unknown";
  }
}

export function verdictNote(value: Verdict): string {
  switch (value) {
    case "GO":
      return "Fits with a runtime that can load it directly. This is not a recorded run.";
    case "OPTIMIZE":
      return "The requested setup is not the cleanest fit; a smaller configuration may work.";
    case "NO":
      return "As configured, this does not fit or has no usable runtime path.";
    default:
      return "There is not enough evidence for a GO or NO claim.";
  }
}

export function basisLabel(value: string): string {
  switch (value) {
    case "fits":
      return "FITS";
    case "supported":
      return "SUPPORTED";
    case "verified":
      return "VERIFIED";
    default:
      return value.toUpperCase();
  }
}
