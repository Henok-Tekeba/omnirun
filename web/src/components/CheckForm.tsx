import type { ApiError } from "../api/client";
import type { DeviceEntry } from "../api/types";
import type { FieldErrors, FormState } from "../lib/form";
import { hardwareDescription } from "../lib/form";
import { AdvancedPanel } from "./AdvancedPanel";
import { ErrorPanel } from "./ErrorPanel";
import { HardwarePanel } from "./HardwarePanel";
import { ArrowRight, Lock } from "./Icons";

const EXAMPLES = [
  {
    label: "SmolLM2 135M",
    model: "HuggingFaceTB/SmolLM2-135M-Instruct",
    note: "small LLM",
  },
  {
    label: "Mistral 7B",
    model: "mistralai/Mistral-7B-v0.1",
    note: "larger LLM",
  },
  {
    label: "Whisper Tiny",
    model: "openai/whisper-tiny",
    note: "ASR · UNKNOWN",
  },
];

interface CheckFormProps {
  form: FormState;
  onChange: (patch: Partial<FormState>) => void;
  devices: DeviceEntry[];
  devicesStatus: "loading" | "ready" | "error";
  devicesError: ApiError | null;
  onReloadDevices: () => void;
  errors: FieldErrors;
  error: ApiError | null;
  onSubmit: () => void;
  onRetry: () => void;
  onDismissError: () => void;
  onExample: (model: string) => void;
}

export function CheckForm({
  form,
  onChange,
  devices,
  devicesStatus,
  devicesError,
  onReloadDevices,
  errors,
  error,
  onSubmit,
  onRetry,
  onDismissError,
  onExample,
}: CheckFormProps) {
  const summary = hardwareDescription(form, devices);

  function openToken() {
    const details = document.getElementById("advanced") as HTMLDetailsElement | null;
    if (details) details.open = true;
    requestAnimationFrame(() => document.getElementById("hf-token")?.focus());
  }

  return (
    <section className="console" id="check" aria-labelledby="check-title">
      <div className="console-label">
        <span>
          <strong>Input bay</strong> / model + hardware
        </span>
        <span>Estimate only</span>
        <span className="hidden sm:inline">POST /check</span>
      </div>

      <div className="p-4 md:p-7">
        {error ? (
          <div className="mb-5">
            <ErrorPanel
              error={error}
              onRetry={onRetry}
              onDismiss={onDismissError}
              onOpenToken={openToken}
            />
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          noValidate
        >
          <div className="section-heading">
            <h2 id="check-title" className="module-title">
              Model
            </h2>
            <span className="rule-tag">repo id / huggingface.co URL</span>
          </div>

          <label htmlFor="model" className="micro mt-4 block">
            HF reference
          </label>
          <div className="input-bay mt-2">
            <span className="prompt" aria-hidden="true">
              ›
            </span>
            <input
              id="model"
              name="model"
              type="text"
              placeholder="HuggingFaceTB/SmolLM2-135M-Instruct"
              value={form.model}
              onChange={(event) => onChange({ model: event.target.value })}
              autoComplete="off"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              aria-invalid={Boolean(errors.model)}
              aria-describedby={errors.model ? "model-error" : "model-help"}
            />
            <button type="submit" className="btn btn-primary">
              Run preflight
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
            <p id="model-help" className="text-[11px] leading-relaxed text-[var(--muted)]">
              Datasets and Spaces are not supported. A repo id like{" "}
              <span className="font-mono text-[10px]">org/model</span> is enough.
            </p>
            <span className="flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)]">
              <Lock size={10} /> no weight downloads
            </span>
          </div>
          {errors.model ? (
            <p id="model-error" className="mt-1 text-[11px] text-[var(--no)]">
              {errors.model}
            </p>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span className="micro">Examples</span>
            {EXAMPLES.map((example) => (
              <button
                key={example.model}
                type="button"
                className="group inline-flex items-baseline gap-1.5 text-left"
                onClick={() => onExample(example.model)}
                title={example.model}
              >
                <span className="font-mono text-[10px] text-[var(--text-2)] underline decoration-[var(--line-strong)] underline-offset-3 group-hover:text-[var(--accent)] group-hover:decoration-[var(--accent)]">
                  {example.label}
                </span>
                <span className="font-mono text-[8px] uppercase tracking-[0.06em] text-[var(--faint)]">
                  {example.note}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-7">
            <HardwarePanel
              mode={form.mode}
              onModeChange={(mode) => onChange({ mode })}
              helperCode={form.helperCode}
              onHelperCodeChange={(helperCode) => onChange({ helperCode })}
              devices={devices}
              devicesStatus={devicesStatus}
              devicesError={devicesError}
              onReloadDevices={onReloadDevices}
              deviceId={form.deviceId}
              onDeviceChange={(device) => {
                const nextRam =
                  device.kind !== "discrete"
                    ? form.ramGib ||
                      (device.default_ram_gib ? String(device.default_ram_gib) : "")
                    : form.ramGib;
                onChange({ deviceId: device.id, ramGib: nextRam });
              }}
              ramGib={form.ramGib}
              onRamChange={(ramGib) => onChange({ ramGib })}
              cpuMode={form.cpuMode}
              onCpuModeChange={(cpuMode) => onChange({ cpuMode })}
              errors={errors}
            />
          </div>

          <AdvancedPanel
            context={form.context}
            batch={form.batch}
            hfToken={form.hfToken}
            onChange={onChange}
            errors={errors}
          />

          <div className="mt-6 flex flex-col gap-3 border-t border-[var(--line)] pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="micro">Selected setup</p>
              <p className="mt-1 text-[12px] text-[var(--text-2)]">{summary}</p>
              <p className="mt-0.5 font-mono text-[9px] text-[var(--faint)]">
                context {form.context || "—"} / batch {form.batch || "—"} / hardware{" "}
                {form.mode === "cpu" && form.cpuMode === "unsure" ? "unknown" : form.mode}
              </p>
            </div>
            <button type="submit" className="btn btn-primary sm:min-w-[170px]">
              Run preflight
              <ArrowRight size={13} />
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
