import type { CheckRequest, DeviceEntry, HardwareInput } from "../api/types";

export type HardwareMode = "helper" | "manual" | "cpu";
export type CpuMode = "cpu" | "unsure";

export interface FormState {
  model: string;
  mode: HardwareMode;
  helperCode: string;
  deviceId: string;
  ramGib: string;
  cpuMode: CpuMode;
  context: string;
  batch: string;
  hfToken: string;
}

export const DEFAULT_FORM: FormState = {
  model: "",
  mode: "manual",
  helperCode: "",
  deviceId: "",
  ramGib: "",
  cpuMode: "cpu",
  context: "4096",
  batch: "1",
  hfToken: "",
};

export type FieldErrors = Partial<Record<keyof FormState | "hardware", string>>;

export interface ValidationResult {
  ok: boolean;
  errors: FieldErrors;
  payload: CheckRequest | null;
  firstError: string | null;
}

function parseInteger(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null;
  const number = Number(value.trim());
  return Number.isSafeInteger(number) ? number : null;
}

function parseRam(value: string): number | null {
  if (!value.trim()) return null;
  const number = Number(value.trim());
  if (!Number.isFinite(number)) return null;
  return number;
}

export function validateForm(
  form: FormState,
  devices: DeviceEntry[],
): ValidationResult {
  const errors: FieldErrors = {};
  const model = form.model.trim();

  if (!model) {
    errors.model = "Paste a Hugging Face model URL or repo id.";
  } else if (model.length > 512) {
    errors.model = "That model reference is too long (max 512 characters).";
  }

  const context = parseInteger(form.context);
  if (context === null || context < 1 || context > 1_048_576) {
    errors.context = "Context must be a whole number from 1 to 1,048,576.";
  }

  const batch = parseInteger(form.batch);
  if (batch === null || batch < 1 || batch > 1024) {
    errors.batch = "Batch must be a whole number from 1 to 1024.";
  }

  const ram = parseRam(form.ramGib);
  if (form.ramGib.trim() && (ram === null || ram < 1 || ram > 4096)) {
    errors.ramGib = "RAM must be a number from 1 to 4096 GB.";
  }

  let hardware: HardwareInput | null = null;

  if (form.mode === "helper") {
    const code = form.helperCode.trim();
    if (!code) {
      errors.helperCode = "Paste the OR1… code printed by the helper.";
    } else if (!code.startsWith("OR1.")) {
      errors.helperCode = "Helper codes start with OR1.";
    } else if (code.length > 4096) {
      errors.helperCode = "That helper code is too long.";
    } else {
      hardware = { source: "helper", code };
    }
  }

  if (form.mode === "manual") {
    const device = devices.find((item) => item.id === form.deviceId);
    if (!device) {
      errors.hardware = "Pick a GPU or chip from the list.";
    } else if (device.kind !== "discrete" && ram === null) {
      errors.ramGib = "RAM is required for this device.";
    } else if (device.kind !== "discrete" && (ram === null || ram < 1 || ram > 4096)) {
      errors.ramGib = "RAM must be a number from 1 to 4096 GB.";
    } else {
      hardware = {
        source: "manual",
        device_id: device.id,
        ...(device.kind !== "discrete" && ram !== null ? { ram_gib: ram } : {}),
      };
    }
  }

  if (form.mode === "cpu") {
    if (form.cpuMode === "cpu") {
      if (ram === null || ram < 1 || ram > 4096) {
        errors.ramGib = "Enter this machine's RAM (1–4096 GB), or choose “I'm not sure”.";
      } else {
        hardware = { source: "manual", device_id: "cpu-generic", ram_gib: ram };
      }
    } else {
      hardware = {
        source: "unknown",
        ...(ram !== null && ram >= 1 && ram <= 4096 ? { ram_gib: ram } : {}),
      };
    }
  }

  const firstError =
    errors.model ??
    errors.hardware ??
    errors.helperCode ??
    errors.ramGib ??
    errors.context ??
    errors.batch ??
    null;

  if (firstError || hardware === null || context === null || batch === null) {
    return { ok: false, errors, payload: null, firstError };
  }

  return {
    ok: true,
    errors: {},
    firstError: null,
    payload: {
      model,
      hardware,
      context,
      batch,
      ...(form.hfToken.trim() ? { hf_token: form.hfToken.trim() } : {}),
    },
  };
}

export function hardwareDescription(
  form: FormState,
  devices: DeviceEntry[],
): string {
  if (form.mode === "helper") {
    return form.helperCode.trim() ? "Helper code · measured profile" : "Helper code";
  }
  if (form.mode === "cpu") {
    const ram = form.ramGib.trim() ? `${form.ramGib.trim()} GB RAM` : "RAM unknown";
    return form.cpuMode === "cpu" ? `CPU only · ${ram}` : `Not sure · ${ram}`;
  }
  const device = devices.find((item) => item.id === form.deviceId);
  if (!device) return "No device selected";
  if (device.kind === "discrete") {
    return `${device.name} · ${device.vram_gib ?? "?"} GB VRAM`;
  }
  return `${device.name}${form.ramGib.trim() ? ` · ${form.ramGib.trim()} GB RAM` : ""}`;
}

export function deviceIsDiscrete(device: DeviceEntry | undefined): boolean {
  return device?.kind === "discrete";
}
