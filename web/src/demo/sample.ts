import sample from "./sample-result.json";
import type { CheckResponse } from "../api/types";

export const SAMPLE_RESULT = sample as unknown as CheckResponse;
export const SAMPLE_DESCRIPTION =
  "Recorded sample: HuggingFaceTB/SmolLM2-135M-Instruct on Apple M2 Pro, 32 GB RAM.";
