import type { FormState, HardwareMode, CpuMode } from "./form";

const HARDWARE_KEY = "omnirun.hardware.v1";
const THEME_KEY = "omnirun.theme";

export type Theme = "dark" | "light";

interface StoredHardware {
  mode: HardwareMode;
  helperCode: string;
  deviceId: string;
  ramGib: string;
  cpuMode: CpuMode;
}

function isHardwareMode(value: unknown): value is HardwareMode {
  return value === "helper" || value === "manual" || value === "cpu";
}

function isCpuMode(value: unknown): value is CpuMode {
  return value === "cpu" || value === "unsure";
}

export function loadHardware(): Partial<StoredHardware> {
  try {
    const raw = localStorage.getItem(HARDWARE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const item = parsed as Record<string, unknown>;
    const result: Partial<StoredHardware> = {};
    if (isHardwareMode(item.mode)) result.mode = item.mode;
    if (typeof item.helperCode === "string" && item.helperCode.length <= 4096) {
      result.helperCode = item.helperCode;
    }
    if (typeof item.deviceId === "string" && item.deviceId.length <= 100) {
      result.deviceId = item.deviceId;
    }
    if (typeof item.ramGib === "string" && item.ramGib.length <= 16) {
      result.ramGib = item.ramGib;
    }
    if (isCpuMode(item.cpuMode)) result.cpuMode = item.cpuMode;
    return result;
  } catch {
    return {};
  }
}

export function saveHardware(form: FormState): void {
  try {
    const payload: StoredHardware = {
      mode: form.mode,
      helperCode: form.helperCode,
      deviceId: form.deviceId,
      ramGib: form.ramGib,
      cpuMode: form.cpuMode,
    };
    localStorage.setItem(HARDWARE_KEY, JSON.stringify(payload));
  } catch {
    /* Storage can be disabled or full; the app keeps working in memory. */
  }
}

export function loadTheme(): Theme | null {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* Non-fatal. */
  }
}
