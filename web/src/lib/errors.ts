import type { ApiError } from "../api/client";
import { formatRetryAfter } from "./format";

export type ErrorKind =
  | "auth"
  | "not_found"
  | "rate_limit"
  | "timeout"
  | "invalid_input"
  | "api_down"
  | "upstream"
  | "internal"
  | "generic";

export interface ErrorCopy {
  kind: ErrorKind;
  title: string;
  body: string;
  hint: string | null;
  showTokenAction: boolean;
  retryAfter: string | null;
}

const AUTH_CODES = new Set(["repo_auth_required", "repo_access_denied"]);
const NOT_FOUND_CODES = new Set(["repo_not_found"]);
const RATE_CODES = new Set(["hf_rate_limited", "rate_limited"]);
const TIMEOUT_CODES = new Set(["check_timeout", "hf_timeout", "client_timeout"]);
const INPUT_CODES = new Set([
  "invalid_model_input",
  "validation_error",
  "unsupported_hf_resource",
  "invalid_hardware_code",
  "unsupported_hardware_code_version",
  "invalid_ram",
  "ram_required",
  "unknown_device",
]);
const DOWN_CODES = new Set([
  "api_unreachable",
  "api_unavailable",
  "service_not_ready",
  "client_timeout_unreachable",
]);

export function errorCopy(error: ApiError): ErrorCopy {
  const hint = error.hint;
  const retryAfter = formatRetryAfter(error.retryAfterSeconds);

  if (AUTH_CODES.has(error.code)) {
    return {
      kind: "auth",
      title:
        error.code === "repo_access_denied"
          ? "Hugging Face rejected that token."
          : "This model is gated, private, or doesn’t exist.",
      body:
        error.code === "repo_access_denied"
          ? "The token was sent, but Hugging Face did not grant access. Check that it is valid and that the account has accepted the model license."
          : "Hugging Face returns an authentication error for gated, private, and some missing models. OmniRun does not bypass gated access.",
      hint,
      showTokenAction: true,
      retryAfter: null,
    };
  }

  if (NOT_FOUND_CODES.has(error.code)) {
    return {
      kind: "not_found",
      title: "No model found.",
      body:
        "Hugging Face did not find that model. Check the spelling, or paste the model page URL instead.",
      hint,
      showTokenAction: false,
      retryAfter: null,
    };
  }

  if (RATE_CODES.has(error.code)) {
    return {
      kind: "rate_limit",
      title: "Rate limited.",
      body:
        "Too many requests reached Hugging Face or this OmniRun API. Wait a moment and try again. A token can raise Hub rate limits.",
      hint,
      showTokenAction: error.code === "hf_rate_limited",
      retryAfter,
    };
  }

  if (TIMEOUT_CODES.has(error.code)) {
    return {
      kind: "timeout",
      title: "The preflight timed out.",
      body:
        "The API did not finish within its time budget. This can happen on a slow network or when Hugging Face is slow to answer.",
      hint,
      showTokenAction: false,
      retryAfter: null,
    };
  }

  if (INPUT_CODES.has(error.code)) {
    const helperCodeError =
      error.code === "invalid_hardware_code" ||
      error.code === "unsupported_hardware_code_version";
    const unsupportedResource = error.code === "unsupported_hf_resource";
    return {
      kind: "invalid_input",
      title: helperCodeError
        ? "That helper code isn’t valid."
        : unsupportedResource
          ? "That isn’t a model repo."
          : "Check your input.",
      body: error.message,
      hint,
      showTokenAction: false,
      retryAfter: null,
    };
  }

  if (DOWN_CODES.has(error.code)) {
    return {
      kind: "api_down",
      title: "The OmniRun API isn’t reachable.",
      body:
        "The web page loaded, but the API on port 8000 did not answer. If you started both with `npm run dev`, check the API terminal for an error.",
      hint,
      showTokenAction: false,
      retryAfter: null,
    };
  }

  if (error.code === "hf_unreachable" || error.code === "hf_upstream_error") {
    return {
      kind: "upstream",
      title:
        error.code === "hf_unreachable"
          ? "The API can’t reach Hugging Face."
          : "Hugging Face returned an error.",
      body: error.message,
      hint,
      showTokenAction: false,
      retryAfter: null,
    };
  }

  if (error.code === "internal_error") {
    return {
      kind: "internal",
      title: "The API hit an internal error.",
      body:
        "This one is on OmniRun. The request ID below helps trace it in the API logs.",
      hint,
      showTokenAction: false,
      retryAfter: null,
    };
  }

  return {
    kind: "generic",
    title: "The preflight failed.",
    body: error.message,
    hint,
    showTokenAction: false,
    retryAfter: null,
  };
}

export function errorRepoId(error: ApiError): string | null {
  const value = error.details.repo_id;
  return typeof value === "string" && value.length > 0 && value.length <= 200 ? value : null;
}
