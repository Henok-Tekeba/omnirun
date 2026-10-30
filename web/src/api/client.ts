import type {
  CheckRequest,
  CheckResponse,
  DevicesResponse,
  ErrorResponse,
  FindRequest,
  FindResponse,
} from "./types";

const CHECK_TIMEOUT_MS = 60_000;
const FIND_TIMEOUT_MS = 90_000;
const DEVICES_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  code: string;
  hint: string | null;
  status: number | null;
  retryable: boolean;
  retryAfterSeconds: number | null;
  requestId: string | null;
  details: Record<string, unknown>;

  constructor(options: {
    code: string;
    message: string;
    hint?: string | null;
    status?: number | null;
    retryable?: boolean;
    retryAfterSeconds?: number | null;
    requestId?: string | null;
    details?: Record<string, unknown>;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.code = options.code;
    this.hint = options.hint ?? null;
    this.status = options.status ?? null;
    this.retryable = options.retryable ?? false;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.requestId = options.requestId ?? null;
    this.details = options.details ?? {};
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ErrorResponse>;
  return (
    candidate.schema_version === "1.0" &&
    typeof candidate.error === "object" &&
    candidate.error !== null &&
    typeof candidate.error.code === "string" &&
    typeof candidate.error.message === "string"
  );
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    /* Non-JSON errors still get a useful status-based message. */
  }

  if (isErrorResponse(payload)) {
    return new ApiError({
      code: payload.error.code,
      message: payload.error.message,
      hint: payload.error.hint,
      status: payload.error.status,
      retryable: payload.error.retryable,
      retryAfterSeconds: payload.error.retry_after_seconds,
      requestId: payload.request_id,
      details: payload.error.details ?? {},
    });
  }

  if (response.status === 502 || response.status === 503 || response.status === 504) {
    return new ApiError({
      code: "api_unavailable",
      message: "The OmniRun API is not responding correctly.",
      hint: "Check that the API is running on port 8000. `npm run dev` starts both servers.",
      status: response.status,
      retryable: true,
    });
  }

  return new ApiError({
    code: "http_error",
    message: `The OmniRun API returned HTTP ${response.status}.`,
    hint: "Try again. If it persists, check the API logs.",
    status: response.status,
    retryable: true,
  });
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  const abortExternal = () => controller.abort();
  init.signal?.addEventListener("abort", abortExternal, { once: true });

  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: {
        accept: "application/json",
        ...init.headers,
      },
    });

    if (!response.ok) {
      throw await parseError(response);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      if (init.signal?.aborted) {
        throw new ApiError({
          code: "cancelled",
          message: "The preflight was cancelled.",
          retryable: false,
        });
      }
      throw new ApiError({
        code: "client_timeout",
        message: "The preflight took too long and the browser gave up.",
        hint: "Retry. If the API host has a slow connection to Hugging Face, the server may need a longer OMNIRUN_CHECK_TIMEOUT_SECONDS.",
        retryable: true,
      });
    }
    throw new ApiError({
      code: "api_unreachable",
      message: "Can't reach the OmniRun API.",
      hint: "Make sure the API is running on port 8000. `npm run dev` starts both the API and the web app.",
      retryable: true,
    });
  } finally {
    window.clearTimeout(timeout);
    init.signal?.removeEventListener("abort", abortExternal);
  }
}

export function getDevices(signal?: AbortSignal): Promise<DevicesResponse> {
  return requestJson<DevicesResponse>(
    "/api/devices",
    { method: "GET", signal },
    DEVICES_TIMEOUT_MS,
  );
}

export function checkModel(
  payload: CheckRequest,
  signal?: AbortSignal,
): Promise<CheckResponse> {
  return requestJson<CheckResponse>(
    "/api/check",
    {
      method: "POST",
      signal,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
    CHECK_TIMEOUT_MS,
  );
}

export function findModels(
  payload: FindRequest,
  signal?: AbortSignal,
): Promise<FindResponse> {
  return requestJson<FindResponse>(
    "/api/find",
    {
      method: "POST",
      signal,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    },
    FIND_TIMEOUT_MS,
  );
}
