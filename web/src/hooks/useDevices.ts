import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getDevices } from "../api/client";
import type { DeviceEntry } from "../api/types";

type DevicesStatus = "loading" | "ready" | "error";

export function useDevices() {
  const [devices, setDevices] = useState<DeviceEntry[]>([]);
  const [status, setStatus] = useState<DevicesStatus>("loading");
  const [error, setError] = useState<ApiError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
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
    void load();
    return () => controllerRef.current?.abort();
  }, [load]);

  return { devices, status, error, reload: load };
}
