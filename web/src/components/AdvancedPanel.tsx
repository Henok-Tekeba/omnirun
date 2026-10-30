import { useState } from "react";
import type { FieldErrors } from "../lib/form";
import { ChevronDown, Eye, EyeOff, Lock } from "./Icons";

interface AdvancedPanelProps {
  context: string;
  batch: string;
  hfToken: string;
  onChange: (patch: {
    context?: string;
    batch?: string;
    hfToken?: string;
  }) => void;
  errors: FieldErrors;
}

export function AdvancedPanel({
  context,
  batch,
  hfToken,
  onChange,
  errors,
}: AdvancedPanelProps) {
  const [showToken, setShowToken] = useState(false);

  return (
    <details id="advanced" className="group mt-6 border-t border-[var(--line)]">
      <summary className="flex min-h-[42px] cursor-pointer list-none items-center justify-between gap-3 py-2 [&::-webkit-details-marker]:hidden">
        <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="font-mono text-xs uppercase tracking-[0.1em] text-[var(--muted)]">
            Advanced settings
          </span>

        </span>
        <span className="flex items-center gap-2">
          <ChevronDown
            size={14}
            className="text-[var(--faint)] transition-transform duration-150 group-open:rotate-180"
          />
        </span>
      </summary>

      <div className="grid gap-5 border-t border-[var(--line)] pb-2 pt-4 md:grid-cols-2">
        <div>
          <label htmlFor="context" className="micro">
            Context window
          </label>
          <div className="relative mt-2">
            <input
              id="context"
              name="context"
              className="field field-mono pr-16"
              inputMode="numeric"
              autoComplete="off"
              value={context}
              onChange={(event) => onChange({ context: event.target.value })}
              aria-invalid={Boolean(errors.context)}
              aria-describedby="context-help"
            />
            <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-xs text-[var(--faint)]">
              tokens
            </span>
          </div>
          <p id="context-help" className="mt-1.5 text-xs leading-relaxed text-[var(--muted)]">
            The context window used for the memory estimate. If it is above the model
            maximum, it is clamped.
          </p>
          {errors.context ? (
            <p className="mt-1 text-xs text-[var(--no)]">{errors.context}</p>
          ) : null}
        </div>

        <div>
          <label htmlFor="batch" className="micro">
            Batch size
          </label>
          <div className="relative mt-2">
            <input
              id="batch"
              className="field field-mono pr-20"
              inputMode="numeric"
              autoComplete="off"
              value={batch}
              onChange={(event) => onChange({ batch: event.target.value })}
              aria-invalid={Boolean(errors.batch)}
              aria-describedby="batch-help"
            />
            <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-xs text-[var(--faint)]">
              sequences
            </span>
          </div>
          <p id="batch-help" className="mt-1.5 text-xs leading-relaxed text-[var(--muted)]">
            Number of sequences processed together. Speed assumes ideal batching.
          </p>
          {errors.batch ? (
            <p className="mt-1 text-xs text-[var(--no)]">{errors.batch}</p>
          ) : null}
        </div>

        <div className="md:col-span-2">
          <label htmlFor="hf-token" className="micro">
            Hugging Face token (optional)
          </label>
          <div className="relative mt-2">
            <Lock
              size={13}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--faint)]"
            />
            <input
              id="hf-token"
              name="hf-token"
              className="field field-mono px-8 pr-11"
              type={showToken ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              placeholder="hf_… only if the repo is gated or private"
              value={hfToken}
              onChange={(event) => onChange({ hfToken: event.target.value })}
            />
            <button
              type="button"
              className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center text-[var(--muted)] hover:bg-[var(--panel-2)] hover:text-[var(--text)]"
              onClick={() => setShowToken((value) => !value)}
              aria-label={showToken ? "Hide token" : "Show token"}
              title={showToken ? "Hide token" : "Show token"}
            >
              {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <p className="mt-1.5 flex items-start gap-2 text-xs leading-relaxed text-[var(--muted)]">
            <Lock size={11} className="mt-0.5 flex-none text-[var(--accent)]" />
            <span>
              Sent only with this request. Never stored in the URL, browser storage, or the
              result. Not needed for public repos.
            </span>
          </p>
        </div>
      </div>
    </details>
  );
}
