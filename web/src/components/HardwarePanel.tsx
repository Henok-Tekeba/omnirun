import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import type { ApiError } from "../api/client";
import type { DeviceEntry } from "../api/types";
import type { CpuMode, FieldErrors, HardwareMode } from "../lib/form";
import { formatGBValue, formatInteger, hardwareKindLabel } from "../lib/format";
import { CopyButton } from "./CopyButton";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Cpu,
  Gpu,
  HelpCircle,
  RotateCcw,
  Search,
} from "./Icons";

interface HardwarePanelProps {
  mode: HardwareMode;
  onModeChange: (mode: HardwareMode) => void;
  helperCode: string;
  onHelperCodeChange: (value: string) => void;
  devices: DeviceEntry[];
  devicesStatus: "loading" | "ready" | "error";
  devicesError: ApiError | null;
  onReloadDevices: () => void;
  deviceId: string;
  onDeviceChange: (device: DeviceEntry) => void;
  ramGib: string;
  onRamChange: (value: string) => void;
  cpuMode: CpuMode;
  onCpuModeChange: (mode: CpuMode) => void;
  errors: FieldErrors;
}

const TABS: { id: HardwareMode; label: string }[] = [
  { id: "helper", label: "Helper" },
  { id: "manual", label: "Hardware" },
  { id: "cpu", label: "CPU" },
];

const HELPER_COMMAND = "uv run --with numpy python helper/omnirun_helper.py";

function DeviceIcon({ kind }: { kind: DeviceEntry["kind"] }) {
  return kind === "cpu" ? <Cpu size={13} /> : <Gpu size={13} />;
}

function DevicePicker({
  devices,
  deviceId,
  onDeviceChange,
}: {
  devices: DeviceEntry[];
  deviceId: string;
  onDeviceChange: (device: DeviceEntry) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selected = devices.find((device) => device.id === deviceId);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return devices;
    return devices.filter((device) => {
      const haystack = [
        device.name,
        device.vendor,
        device.kind,
        device.vram_gib ? `${device.vram_gib} gb` : "",
        device.ram_options_gib.map((value) => `${value} gb`).join(" "),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [devices, query]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      cancelAnimationFrame(frame);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  if (devices.length === 0) {
    return (
      <div className="border border-[var(--line)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--muted)]">
        Hardware list requires the live API. Use CPU or run locally.
      </div>
    );
  }

  return (
    <div ref={rootRef} className="relative">
      <label id="hardware-picker-label" className="micro">
        GPU or chip
      </label>
      <button
        ref={triggerRef}
        type="button"
        className="field mt-2 flex items-center justify-between gap-3 text-left"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={selected ? `Hardware: ${selected.name}` : "Select hardware"}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="flex min-w-0 items-center gap-2">
          {selected ? (
            <>
              <DeviceIcon kind={selected.kind} />
              <span className="truncate text-sm">{selected.name}</span>
            </>
          ) : (
            <span className="text-sm text-[var(--muted)]">Select hardware</span>
          )}
        </span>
        <ChevronDown
          size={14}
          className={`flex-none text-[var(--faint)] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="device-popover">
          <div className="relative border-b border-[var(--line)] p-2">
            <Search
              size={14}
              className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--faint)]"
            />
            <input
              ref={inputRef}
              type="search"
              name="device-search"
              className="field h-10 pl-8"
              placeholder="Search hardware…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
              aria-label="Search hardware"
            />
          </div>
          <div className="device-list" role="listbox" aria-label="Hardware options">
            {filtered.length === 0 ? (
              <p className="px-3 py-5 text-center text-sm text-[var(--muted)]">
                No hardware found.
              </p>
            ) : (
              <ul>
                {filtered.map((device) => {
                  const isSelected = device.id === deviceId;
                  return (
                    <li key={device.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        className="device-option"
                        onClick={() => {
                          onDeviceChange(device);
                          setOpen(false);
                          requestAnimationFrame(() => triggerRef.current?.focus());
                        }}
                      >
                        <span className="flex min-w-0 items-center gap-2.5">
                          <span
                            className={`flex h-6 w-6 flex-none items-center justify-center border ${
                              isSelected
                                ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                                : "border-[var(--line)] text-[var(--faint)]"
                            }`}
                          >
                            <DeviceIcon kind={device.kind} />
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-medium">
                              {device.name}
                            </span>
                            <span className="block text-xs text-[var(--faint)]">
                              {device.vendor} / {hardwareKindLabel(device.kind)}
                            </span>
                          </span>
                        </span>
                        <span className="flex flex-none items-center gap-2 font-mono text-xs text-[var(--muted)]">
                          {device.kind === "discrete" && device.vram_gib
                            ? `${formatInteger(device.vram_gib)} GB VRAM`
                            : `${formatInteger(device.bandwidth_gbps)} GB/s`}
                          {isSelected ? <Check size={12} className="text-[var(--accent)]" /> : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RamField({
  id,
  device,
  value,
  onChange,
  error,
  optional = false,
}: {
  id: string;
  device?: DeviceEntry;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  optional?: boolean;
}) {
  const options = device?.ram_options_gib ?? [];
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="micro">
          Total RAM {optional ? "(optional)" : ""}
        </label>
        <span className="font-mono text-xs uppercase tracking-[0.08em] text-[var(--faint)]">
          {optional ? "blank = unknown" : "required"}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[130px] flex-1">
          <input
            id={id}
            name={id}
            className="field field-mono pr-10"
            inputMode="decimal"
            autoComplete="off"
            placeholder="32"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={`${id}-help${error ? ` ${id}-error` : ""}`}
          />
          <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-xs text-[var(--faint)]">
            GB
          </span>
        </div>
        {options.length ? (
          <div className="flex flex-wrap gap-1" aria-label="Common RAM sizes">
            {options.map((option) => (
              <button
                key={option}
                type="button"
                className="badge hover:border-[var(--line-strong)] hover:text-[var(--text)]"
                aria-pressed={Number(value) === option}
                onClick={() => onChange(String(option))}
              >
                {formatInteger(option)}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <p id={`${id}-help`} className="mt-1.5 text-xs leading-relaxed text-[var(--muted)]">
        {optional
          ? "Blank = unknown."
          : device?.kind === "unified"
            ? "75% of RAM is usable."
            : "80% of RAM usable; 25 GB/s assumed."}
      </p>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs text-[var(--no)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function HardwarePanel({
  mode,
  onModeChange,
  helperCode,
  onHelperCodeChange,
  devices,
  devicesStatus,
  devicesError,
  onReloadDevices,
  deviceId,
  onDeviceChange,
  ramGib,
  onRamChange,
  cpuMode,
  onCpuModeChange,
  errors,
}: HardwarePanelProps) {
  const selectedDevice = devices.find((device) => device.id === deviceId);
  const tabOrder = TABS.map((tab) => tab.id);

  function onTabKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    const index = tabOrder.indexOf(mode);
    let next: HardwareMode | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      next = tabOrder[(index + 1) % tabOrder.length];
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      next = tabOrder[(index - 1 + tabOrder.length) % tabOrder.length];
    } else if (event.key === "Home") {
      next = tabOrder[0];
    } else if (event.key === "End") {
      next = tabOrder[tabOrder.length - 1];
    }
    if (!next) return;
    event.preventDefault();
    onModeChange(next);
    requestAnimationFrame(() => document.getElementById(`tab-${next}`)?.focus());
  }

  return (
    <div>
      <div className="section-heading">
        <h2 className="module-title">Hardware</h2>
      </div>

      <div className="tab-list mt-4" role="tablist" aria-label="Hardware input mode">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={mode === tab.id}
            aria-controls={`panel-${tab.id}`}
            tabIndex={mode === tab.id ? 0 : -1}
            className="tab"
            onClick={() => onModeChange(tab.id)}
            onKeyDown={onTabKeyDown}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        id="panel-helper"
        role="tabpanel"
        aria-labelledby="tab-helper"
        hidden={mode !== "helper"}
        className="pt-5"
      >
        <div className="grid gap-5 md:grid-cols-[1.05fr_1fr]">
          <div>
            <h3 className="text-sm font-semibold">Run the helper</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
              Detects CPU, memory, and GPU. No model weights.
            </p>
            <div className="code-block mt-3">
              <code>$ {HELPER_COMMAND}</code>
              <CopyButton value={HELPER_COMMAND} label="Copy" />
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[var(--faint)]">
              Self-reported. Use on trusted machines.
            </p>
          </div>

          <div>
            <label htmlFor="helper-code" className="micro">
              Helper code
            </label>
            <textarea
              id="helper-code"
              className="field field-mono mt-2 min-h-[118px] resize-y text-sm leading-relaxed"
              placeholder="OR1.eyJ2IjoxLCJ0cyI6..."
              value={helperCode}
              onChange={(event) => onHelperCodeChange(event.target.value)}
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              aria-invalid={Boolean(errors.helperCode)}
              aria-describedby={errors.helperCode ? "helper-code-error" : "helper-code-help"}
            />
            <p id="helper-code-help" className="mt-1.5 text-xs leading-relaxed text-[var(--muted)]">
              Saved locally. Share links include machine details.
            </p>
            {errors.helperCode ? (
              <p id="helper-code-error" className="mt-1 text-xs text-[var(--no)]">
                {errors.helperCode}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div
        id="panel-manual"
        role="tabpanel"
        aria-labelledby="tab-manual"
        hidden={mode !== "manual"}
        className="pt-5"
      >
        {devicesStatus === "loading" ? (
          <div className="flex items-center gap-2 border border-[var(--line)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--muted)]">
            <span className="skeleton h-4 w-4 border border-[var(--line)] bg-[var(--panel-2)]" />
            Loading hardware…
          </div>
        ) : devicesStatus === "error" ? (
          <div className="border border-[color-mix(in_srgb,var(--optimize)_45%,var(--line))] bg-[var(--optimize-soft)] p-3">
            <div className="flex items-start gap-2.5">
              <AlertTriangle size={15} className="mt-0.5 flex-none text-[var(--optimize)]" />
              <div>
                <p className="text-sm font-semibold">Hardware list unavailable</p>
                <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
                  {devicesError?.message ?? "Use CPU or retry."}
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm mt-2"
                  onClick={onReloadDevices}
                >
                  <RotateCcw size={11} /> Retry
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <DevicePicker
              devices={devices}
              deviceId={deviceId}
              onDeviceChange={onDeviceChange}
            />
            {selectedDevice ? (
              <div className="mt-3 border border-[var(--line)] bg-[var(--bg-elevated)] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <DeviceIcon kind={selectedDevice.kind} />
                    <span className="truncate text-sm font-medium">{selectedDevice.name}</span>
                  </div>
                  <span className="font-mono text-xs text-[var(--muted)]">
                    {formatInteger(selectedDevice.bandwidth_gbps)} GB/s
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--muted)]">
                  <span>
                    {selectedDevice.kind === "discrete" && selectedDevice.vram_gib
                      ? `${formatGBValue(selectedDevice.vram_gib * 1024 ** 3, 0)} GB VRAM`
                      : selectedDevice.kind === "unified"
                        ? ramGib
                          ? `${ramGib} GB RAM`
                          : "RAM not set"
                        : "CPU profile"}
                  </span>
                  <span>{hardwareKindLabel(selectedDevice.kind)}</span>
                </div>
                {selectedDevice.kind !== "discrete" ? (
                  <div className="mt-3 border-t border-[var(--line)] pt-3">
                    <RamField
                      id="ram-manual"
                      device={selectedDevice}
                      value={ramGib}
                      onChange={onRamChange}
                      error={errors.ramGib}
                    />
                  </div>
                ) : null}
              </div>
            ) : null}
            {errors.hardware ? (
              <p className="mt-2 text-xs text-[var(--no)]">{errors.hardware}</p>
            ) : null}
          </>
        )}
      </div>

      <div
        id="panel-cpu"
        role="tabpanel"
        aria-labelledby="tab-cpu"
        hidden={mode !== "cpu"}
        className="pt-5"
      >
        <div className="grid gap-5 md:grid-cols-[1fr_1fr]">
          <div>
            <div role="radiogroup" aria-label="CPU or unknown hardware" className="grid gap-2">
              <label className="choice-card cursor-pointer">
                <input
                  type="radio"
                  name="cpu-mode"
                  value="cpu"
                  checked={cpuMode === "cpu"}
                  onChange={() => onCpuModeChange("cpu")}
                  className="sr-only"
                />
                <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center border border-[var(--line)] text-[var(--muted)]">
                  <Cpu size={13} />
                </span>
                <span>
                  <span className="block text-sm font-semibold">CPU only</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-[var(--muted)]">
                    Generic CPU profile.
                  </span>
                </span>
              </label>

              <label className="choice-card cursor-pointer">
                <input
                  type="radio"
                  name="cpu-mode"
                  value="unsure"
                  checked={cpuMode === "unsure"}
                  onChange={() => onCpuModeChange("unsure")}
                  className="sr-only"
                />
                <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center border border-[var(--line)] text-[var(--muted)]">
                  <HelpCircle size={13} />
                </span>
                <span>
                  <span className="block text-sm font-semibold">I’m not sure</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-[var(--muted)]">
                    Conservative defaults.
                  </span>
                </span>
              </label>
            </div>
          </div>

          <div className="border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
            <RamField
              id="ram-cpu"
              value={ramGib}
              onChange={onRamChange}
              error={errors.ramGib}
              optional={cpuMode === "unsure"}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
