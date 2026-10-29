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
    <details id="advanced" className="group mt-6 border-t border-[var(--line)] pt-1">
      <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-3 py-2 text-[13px] text-[var(--text-2)] [&::-webkit-details-marker]:hidden">
        <span className="flex items-center gap-2">
          <span className="micro">Advanced</span>
          <span className="text-[var(--faint)]">·</span>
          <span>context, batch, HF token</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="badge hidden sm:inline-flex">token not stored</span>
          <ChevronDown
            size={15}
            className="text-[var(--faint)] transition-transform duration-150 group-open:rotate-180"
          />
        </span>
      </summary>

      <div className="grid gap-5 pb-2 pt-3 md:grid-cols-2">
        <div>
          <label htmlFor="context" className="micro">
            Context length
          </label>
          <div className="relative mt-2">
            <input
              id="context"
              className="field field-mono pr-16"
              inputMode="numeric"
              autoComplete="off"
              value={context}
              onChange={(event) => onChange({ context: event.target.value })}
              aria-invalid={Boolean(errors.context)}
              aria-describedby="context-help"
            />
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[10px] text-[var(--faint)]">
              tokens
            </span>
          </div>
          <p id="context-help" className="mt-1.5 text-[11.5px] leading-relaxed text-[var(--muted)]">
            KV-cache allocation context, not prompt length. Above the model maximum, the
            API clamps it and flags the result.
          </p>
          {errors.context ? (
            <p className="mt-1 text-[11.5px] text-[var(--no)]">{errors.context}</p>
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
            <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[10px] text-[var(--faint)]">
              sequences
            </span>
          </div>
          <p id="batch-help" className="mt-1.5 text-[11.5px] leading-relaxed text-[var(--muted)]">
            Concurrent sequences, not gradient batch. Aggregate speed assumes perfect
            continuous batching.
          </p>
          {errors.batch ? (
            <p className="mt-1 text-[11.5px] text-[var(--no)]">{errors.batch}</p>
          ) : null}
        </div>

        <div className="md:col-span-2">
          <label htmlFor="hf-token" className="micro">
            Hugging Face token (optional)
          </label>
          <div className="relative mt-2">
            <Lock
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--faint)]"
            />
            <input
              id="hf-token"
              className="field field-mono px-9 pr-12"
              type={showToken ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              placeholder="hf_… (only if the repo is gated or private)"
              value={hfToken}
              onChange={(event) => onChange({ hfToken: event.target.value })}
            />
            <button
              type="button"
              className="absolute right-1.5 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded text-[var(--muted)] hover:bg-[var(--panel-2)] hover:text-[var(--text)]"
              onClick={() => setShowToken((value) => !value)}
              aria-label={showToken ? "Hide token" : "Show token"}
              title={showToken ? "Hide token" : "Show token"}
            >
              {showToken ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>
          <p className="mt-1.5 flex items-start gap-2 text-[11.5px] leading-relaxed text-[var(--muted)]">
            <Lock size={12} className="mt-0.5 flex-none text-[var(--accent)]" />
            <span>
              Sent only with this request. Never stored in the URL, localStorage, or the
              result. The API does not log request bodies. Not needed for public repos.
            </span>
          </p>
        </div>
      </div>
    </details>
  );
}
