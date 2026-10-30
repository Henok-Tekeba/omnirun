import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { ApiError } from "../api/client";
import type { DeviceEntry } from "../api/types";
import type { CpuMode, FieldErrors, HardwareMode } from "../lib/form";
import { formatGBValue, formatInteger, hardwareKindLabel } from "../lib/format";
import { CopyButton } from "./CopyButton";
import {
  AlertTriangle,
  Check,
  Cpu,
  Gpu,
  HelpCircle,
  RotateCcw,
  Search,
  Terminal,
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

const TABS: { id: HardwareMode; label: string; short: string }[] = [
  { id: "helper", label: "Helper code", short: "Helper" },
  { id: "manual", label: "Pick my hardware", short: "Pick" },
  { id: "cpu", label: "CPU only / not sure", short: "CPU" },
];

const HELPER_COMMAND = "uv run --with numpy python helper/omnirun_helper.py";

function DeviceIcon({ kind }: { kind: DeviceEntry["kind"] }) {
  return kind === "cpu" ? <Cpu size={13} /> : <Gpu size={13} />;
}

function DeviceList({
  devices,
  deviceId,
  onDeviceChange,
}: {
  devices: DeviceEntry[];
  deviceId: string;
  onDeviceChange: (device: DeviceEntry) => void;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

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

  return (
    <div>
      <div className="flex items-end justify-between gap-2">
        <label htmlFor="device-search" className="micro">
          Search GPU or chip
        </label>
        <span className="font-mono text-xs text-[var(--faint)]">
          {filtered.length}/{devices.length}
        </span>
      </div>
      <div className="relative mt-2">
        <Search
          size={14}
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--faint)]"
        />
        <input
          ref={inputRef}
          id="device-search"
          name="device-search"
          className="field pl-8"
          type="search"
          placeholder="M2 Pro, RTX 4090, CPU…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
        />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-[var(--faint)]">
          Curated device list
        </p>
        {query ? (
          <button
            type="button"
            className="font-mono text-xs uppercase tracking-[0.08em] text-[var(--muted)] underline underline-offset-2 hover:text-[var(--text)]"
            onClick={() => {
              setQuery("");
              inputRef.current?.focus();
            }}
          >
            clear
          </button>
        ) : null}
      </div>

      <div className="device-list mt-2" aria-label="Device profiles">
        {filtered.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-[var(--muted)]">
            {devices.length === 0
              ? "The device list requires the live API. Use CPU only or run locally."
              : "No matching profiles. Try “M2”, “4090”, or “CPU”."}
          </p>
        ) : (
          <ul>
            {filtered.map((device) => {
              const selected = device.id === deviceId;
              return (
                <li key={device.id}>
                  <button
                    type="button"
                    className="device-option"
                    aria-pressed={selected}
                    onClick={() => onDeviceChange(device)}
                  >
                    <span className="flex min-w-0 items-center gap-2.5">
                      <span
                        className={`flex h-6 w-6 flex-none items-center justify-center border ${
                          selected
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
                        <span className="block font-mono text-xs uppercase tracking-[0.06em] text-[var(--faint)]">
                          {device.vendor} / {hardwareKindLabel(device.kind)}
                        </span>
                      </span>
                    </span>
                    <span className="flex flex-none items-center gap-2">
                      <span className="hidden text-right font-mono text-xs text-[var(--muted)] sm:block">
                        {device.kind === "discrete" && device.vram_gib
                          ? `${formatInteger(device.vram_gib)} GB VRAM`
                          : `${formatInteger(device.bandwidth_gbps)} GB/s`}
                      </span>
                      {selected ? <Check size={12} className="text-[var(--accent)]" /> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
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
          ? "Without RAM, memory fit stays UNKNOWN rather than guessing your machine."
          : device?.kind === "unified"
            ? "Usable unified memory will be 75% of this value (documented assumption)."
            : "The CPU budget will be 80% of this value; bandwidth is assumed at 25 GB/s."}
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

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
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
        <span className="rule-tag">Measured, curated, or conservative</span>
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
            <span className="hidden sm:inline">{tab.label}</span>
            <span className="sm:hidden">{tab.short}</span>
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
            <h3 className="text-sm font-semibold">Run the helper on this machine</h3>
            <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
              It detects your processor, memory, and GPU, then runs a quick memory speed
              test. It does not download model weights. Paste the code it prints below.
            </p>
            <div className="code-block mt-3">
              <code>$ {HELPER_COMMAND}</code>
              <CopyButton value={HELPER_COMMAND} label="Copy" />
            </div>
            <p className="mt-2 font-mono text-xs leading-relaxed text-[var(--faint)]">
              Run this from the repository root.
            </p>
            <div className="note-box mt-4">
              <strong className="text-[var(--text-2)]">Self-reported, not signed.</strong>{" "}
              The code reports what the helper measured. It is not proof of hardware; use it
              on machines you trust.
            </div>
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
              Saved on this device as your last hardware choice. Share links include it
              because it contains machine details.
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
          <div className="grid gap-4 md:grid-cols-[1.05fr_1fr]">
            <div>
              <div className="skeleton h-[44px] border border-[var(--line)] bg-[var(--panel-2)]" />
              <div className="mt-3 space-y-1">
                {[0, 1, 2, 3, 4].map((item) => (
                  <div
                    key={item}
                    className="h-[38px] border border-[var(--line)] bg-[var(--panel-2)] opacity-60"
                  />
                ))}
              </div>
            </div>
            <div className="border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
              <p className="micro">Loading device table</p>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Reading curated profiles from the API…
              </p>
            </div>
          </div>
        ) : devicesStatus === "error" ? (
          <div className="border border-[color-mix(in_srgb,var(--optimize)_45%,var(--line))] bg-[var(--optimize-soft)] p-4">
            <div className="flex items-start gap-2.5">
              <AlertTriangle size={15} className="mt-0.5 flex-none text-[var(--optimize)]" />
              <div>
                <p className="text-sm font-semibold">Couldn’t load the device list</p>
                <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
                  {devicesError?.message ?? "The API did not return the hardware profiles."}{" "}
                  Helper code and CPU-only modes still work.
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm mt-3"
                  onClick={onReloadDevices}
                >
                  <RotateCcw size={11} /> Retry
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid items-start gap-5 md:grid-cols-[1.05fr_1fr]">
            <DeviceList
              devices={devices}
              deviceId={deviceId}
              onDeviceChange={onDeviceChange}
            />

            <div className="border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
              {selectedDevice ? (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold leading-snug">
                        {selectedDevice.name}
                      </p>
                      <p className="mt-1 font-mono text-xs uppercase tracking-[0.08em] text-[var(--faint)]">
                        {selectedDevice.vendor} / {hardwareKindLabel(selectedDevice.kind)}
                      </p>
                    </div>
                    <span className="badge">{selectedDevice.id}</span>
                  </div>

                  <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[var(--line)] pt-3">
                    <div>
                      <dt className="micro">Bandwidth</dt>
                      <dd className="mt-0.5 font-mono text-sm text-[var(--text-2)]">
                        {formatInteger(selectedDevice.bandwidth_gbps)} GB/s
                      </dd>
                      <dd className="mt-0.5 text-xs text-[var(--faint)]">device table</dd>
                    </div>
                    <div>
                      <dt className="micro">
                        {selectedDevice.kind === "discrete" ? "VRAM" : "Memory"}
                      </dt>
                      <dd className="mt-0.5 font-mono text-sm text-[var(--text-2)]">
                        {selectedDevice.kind === "discrete" && selectedDevice.vram_gib
                          ? `${formatGBValue(selectedDevice.vram_gib * 1024 ** 3, 0)} GB`
                          : ramGib
                            ? `${ramGib} GB`
                            : "set below"}
                      </dd>
                      <dd className="mt-0.5 text-xs text-[var(--faint)]">
                        {selectedDevice.kind === "discrete" ? "device table" : "user input"}
                      </dd>
                    </div>
                  </dl>

                  {selectedDevice.kind === "discrete" ? (
                    <div className="note-box mt-4">
                      The budget is VRAM minus a small runtime reserve. System RAM is not
                      added in v1.
                    </div>
                  ) : (
                    <div className="mt-4">
                      <RamField
                        id="ram-manual"
                        device={selectedDevice}
                        value={ramGib}
                        onChange={onRamChange}
                        error={errors.ramGib}
                      />
                    </div>
                  )}

                  {selectedDevice.notes ? (
                    <p className="mt-3 border-t border-[var(--line)] pt-3 text-xs leading-relaxed text-[var(--faint)]">
                      {selectedDevice.notes}
                    </p>
                  ) : null}
                  <p className="mt-3 border-t border-[var(--line)] pt-3 font-mono text-xs leading-relaxed text-[var(--faint)]">
                    Source: {selectedDevice.source}
                  </p>
                </>
              ) : (
                <div className="flex min-h-[120px] flex-col items-start justify-center md:min-h-[190px]">
                  <Gpu size={20} className="text-[var(--faint)]" />
                  <p className="mt-3 text-sm font-medium">No device selected</p>
                  <p className="mt-1 max-w-xs text-sm leading-relaxed text-[var(--muted)]">
                    Choose a device to see its memory budget.
                  </p>
                </div>
              )}
              {errors.hardware ? (
                <p className="mt-2 text-xs text-[var(--no)]">{errors.hardware}</p>
              ) : null}
            </div>
          </div>
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
                    Use the generic CPU profile. Enter this machine’s RAM; the budget is 80%
                    of it and bandwidth is assumed at 25 GB/s.
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
                    Use conservative defaults. RAM is optional; without it, FITS is UNKNOWN
                    rather than a guess.
                  </span>
                </span>
              </label>
            </div>
            <p className="mt-3 font-mono text-xs leading-relaxed text-[var(--faint)]">
              These are conservative estimates. Use the helper for a measured profile.
            </p>
          </div>

          <div className="border border-[var(--line)] bg-[var(--bg-elevated)] p-4">
            <RamField
              id="ram-cpu"
              value={ramGib}
              onChange={onRamChange}
              error={errors.ramGib}
              optional={cpuMode === "unsure"}
            />
            <div className="mt-4 border-t border-[var(--line)] pt-3">
              <p className="micro">What we'll use</p>
              <p className="mt-1.5 text-xs leading-relaxed text-[var(--muted)]">
                {cpuMode === "cpu"
                  ? "The generic CPU profile with your RAM."
                  : "Conservative defaults, with your RAM if provided."}
              </p>
              <div className="mt-3 flex items-center gap-2 text-xs text-[var(--faint)]">
                <Terminal size={12} />
                <span>No helper code needed.</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
