import type { ApiError } from "../api/client";
import type { DeviceEntry } from "../api/types";
import type { FieldErrors, FormState } from "../lib/form";
import { hardwareDescription } from "../lib/form";
import { AdvancedPanel } from "./AdvancedPanel";
import { ErrorPanel } from "./ErrorPanel";
import { HardwarePanel } from "./HardwarePanel";
import { ArrowRight, LinkIcon, Lock } from "./Icons";

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
    <section className="panel" id="check" aria-labelledby="check-title">
      <div className="p-5 md:p-8">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="micro micro-accent">01 / Model</p>
            <h2 id="check-title" className="mt-1 text-[17px] font-semibold">
              What are you trying to run?
            </h2>
          </div>
          <span className="badge">estimate, not a benchmark</span>
        </div>

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
          <label htmlFor="model" className="micro">
            Hugging Face model URL or repo id
          </label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <div className="relative min-w-0 flex-1">
              <LinkIcon
                size={17}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--faint)]"
              />
              <input
                id="model"
                name="model"
                className="field field-lg pl-11"
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
            </div>
            <button type="submit" className="btn btn-primary h-[52px] px-5 sm:h-[62px] sm:px-6">
              Run preflight
              <ArrowRight size={16} />
            </button>
          </div>
          <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
            <p id="model-help" className="text-[11.5px] leading-relaxed text-[var(--muted)]">
              A repo id like <span className="font-mono text-[10.5px]">org/model</span> or a
              huggingface.co model page URL. Datasets and Spaces are not supported.
            </p>
            <span className="flex items-center gap-1.5 font-mono text-[9.5px] uppercase tracking-[0.07em] text-[var(--faint)]">
              <Lock size={11} /> no weight downloads
            </span>
          </div>
          {errors.model ? (
            <p id="model-error" className="mt-1 text-[11.5px] text-[var(--no)]">
              {errors.model}
            </p>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="micro">Try</span>
            {EXAMPLES.map((example) => (
              <button
                key={example.model}
                type="button"
                className="group flex items-center gap-2 rounded border border-[var(--line)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-left transition-colors hover:border-[var(--line-strong)]"
                onClick={() => onExample(example.model)}
                title={example.model}
              >
                <span className="text-[11.5px] font-medium text-[var(--text-2)] group-hover:text-[var(--text)]">
                  {example.label}
                </span>
                <span className="font-mono text-[9px] uppercase tracking-[0.06em] text-[var(--faint)]">
                  {example.note}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-8 border-t border-[var(--line)] pt-6">
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

          <div className="mt-6 flex flex-col gap-3 border-t border-[var(--line)] pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="micro">Current setup</p>
              <p className="mt-1 text-[12.5px] text-[var(--text-2)]">{summary}</p>
              <p className="mt-0.5 font-mono text-[10px] text-[var(--faint)]">
                context {form.context || "—"} · batch {form.batch || "—"} · hardware{" "}
                {form.mode === "cpu" && form.cpuMode === "unsure" ? "unknown" : form.mode}
              </p>
            </div>
            <button type="submit" className="btn btn-primary sm:min-w-[160px]">
              Run preflight
              <ArrowRight size={15} />
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
