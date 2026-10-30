import type { CpuMode, FormState, HardwareMode } from "./form";
import { DEFAULT_FORM } from "./form";

export interface QueryState {
  form: FormState;
  autoRun: boolean;
}

function isMode(value: string | null): value is HardwareMode {
  return value === "helper" || value === "manual" || value === "cpu";
}

function isCpuMode(value: string | null): value is CpuMode {
  return value === "cpu" || value === "unsure";
}

function safeNumberString(value: string | null, maxLength: number): string | null {
  if (!value || value.length > maxLength) return null;
  if (!/^\d+(\.\d+)?$/.test(value)) return null;
  return value;
}

export function readQuery(search: string = window.location.search): QueryState {
  const params = new URLSearchParams(search);
  const model = params.get("model")?.slice(0, 512) ?? "";
  const rawMode = params.get("hw");
  let mode: HardwareMode = isMode(rawMode) ? rawMode : DEFAULT_FORM.mode;
  let cpuMode: CpuMode = isCpuMode(params.get("cpu"))
    ? (params.get("cpu") as CpuMode)
    : DEFAULT_FORM.cpuMode;

  // "unknown" is the wire name for the not-sure path; keep the UI on the CPU tab.
  if (rawMode === "unknown") {
    mode = "cpu";
    cpuMode = "unsure";
  }

  const form: FormState = {
    ...DEFAULT_FORM,
    model,
    mode,
    cpuMode,
    helperCode: (params.get("code") ?? "").slice(0, 4096),
    deviceId: (params.get("device") ?? "").slice(0, 100),
    ramGib: safeNumberString(params.get("ram"), 16) ?? "",
    context: safeNumberString(params.get("ctx"), 8) ?? DEFAULT_FORM.context,
    batch: safeNumberString(params.get("batch"), 6) ?? DEFAULT_FORM.batch,
    hfToken: "",
  };

  return { form, autoRun: params.get("run") === "1" && Boolean(model) };
}

export function writeQuery(form: FormState, autoRun: boolean): string {
  const params = new URLSearchParams();
  params.set("model", form.model.trim());
  params.set(
    "hw",
    form.mode === "cpu" && form.cpuMode === "unsure" ? "unknown" : form.mode,
  );
  if (form.mode === "helper" && form.helperCode.trim()) {
    params.set("code", form.helperCode.trim());
  }
  if (form.mode === "manual" && form.deviceId) {
    params.set("device", form.deviceId);
  }
  if (form.mode === "cpu" && form.cpuMode) {
    params.set("cpu", form.cpuMode);
  }
  if (form.ramGib.trim()) params.set("ram", form.ramGib.trim());
  params.set("ctx", form.context.trim());
  params.set("batch", form.batch.trim());
  if (autoRun) params.set("run", "1");

  const next = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, "", next);
  return window.location.href;
}

export function clearRunFlag(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("run");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

export function clearSampleFlag(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("sample");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

export function setSampleFlag(): void {
  const url = new URL(window.location.href);
  url.searchParams.set("sample", "1");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}
