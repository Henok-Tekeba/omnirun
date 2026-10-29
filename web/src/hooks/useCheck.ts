import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, checkModel } from "../api/client";
import type { CheckRequest, CheckResponse } from "../api/types";

type CheckStatus = "idle" | "loading" | "success" | "error";

export function useCheck() {
  const [status, setStatus] = useState<CheckStatus>("idle");
  const [result, setResult] = useState<CheckResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

  const cancel = useCallback(() => {
    runIdRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    setStatus("idle");
  }, []);

  const reset = useCallback(() => {
    runIdRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    setStatus("idle");
    setResult(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
    setStatus((current) => (current === "error" ? "idle" : current));
  }, []);

  const run = useCallback(async (payload: CheckRequest): Promise<CheckResponse | null> => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const runId = ++runIdRef.current;

    setStatus("loading");
    setResult(null);
    setError(null);

    try {
      const response = await checkModel(payload, controller.signal);
      if (runId !== runIdRef.current) return null;
      setResult(response);
      setStatus("success");
      return response;
    } catch (caught) {
      if (runId !== runIdRef.current) return null;
      if (caught instanceof ApiError && caught.code === "cancelled") {
        setStatus("idle");
        return null;
      }
      setError(
        caught instanceof ApiError
          ? caught
          : new ApiError({
              code: "unknown_error",
              message: "The preflight failed unexpectedly.",
              retryable: true,
            }),
      );
      setStatus("error");
      return null;
    } finally {
      if (runId === runIdRef.current) controllerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      runIdRef.current += 1;
      controllerRef.current?.abort();
    };
  }, []);

  return { status, result, error, run, cancel, reset, clearError };
}
