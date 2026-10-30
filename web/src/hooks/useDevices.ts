import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getDevices } from "../api/client";
import type { DeviceEntry } from "../api/types";
import { IS_STATIC_PREVIEW } from "../lib/env";
import { STATIC_DEVICES } from "../demo/devices";

type DevicesStatus = "loading" | "ready" | "error";

export function useDevices() {
  const [devices, setDevices] = useState<DeviceEntry[]>(
    IS_STATIC_PREVIEW ? STATIC_DEVICES : [],
  );
  const [status, setStatus] = useState<DevicesStatus>(
    IS_STATIC_PREVIEW ? "ready" : "loading",
  );
  const [error, setError] = useState<ApiError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (IS_STATIC_PREVIEW) {
      setDevices(STATIC_DEVICES);
      setStatus("ready");
      setError(null);
      return;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setStatus("loading");
    setError(null);
    try {
      const response = await getDevices(controller.signal);
      if (controller.signal.aborted) return;
      setDevices(response.devices);
      setStatus("ready");
    } catch (caught) {
      if (controller.signal.aborted) return;
      if (caught instanceof ApiError && caught.code === "cancelled") return;
      setError(
        caught instanceof ApiError
          ? caught
          : new ApiError({
              code: "devices_failed",
              message: "Could not load the hardware list.",
              retryable: true,
            }),
      );
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (IS_STATIC_PREVIEW) return;
    void load();
    return () => controllerRef.current?.abort();
  }, [load]);

  return { devices, status, error, reload: load };
}
