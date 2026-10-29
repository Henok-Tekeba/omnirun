import type { ApiError } from "../api/client";
import { errorCopy, errorRepoId } from "../lib/errors";
import {
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  Lock,
  RotateCcw,
  X,
} from "./Icons";

interface ErrorPanelProps {
  error: ApiError;
  onRetry: () => void;
  onDismiss: () => void;
  onOpenToken: () => void;
}

export function ErrorPanel({
  error,
  onRetry,
  onDismiss,
  onOpenToken,
}: ErrorPanelProps) {
  const copy = errorCopy(error);
  const repoId = errorRepoId(error);
  const retryLabel = copy.retryAfter ? `Retry after ${copy.retryAfter}` : "Try again";

  return (
    <div id="check-error" className="error-panel" role="alert" aria-live="assertive">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-full border border-[color-mix(in_srgb,var(--no)_45%,transparent)] bg-[var(--no-soft)] text-[var(--no)]">
            <AlertTriangle size={16} />
          </span>
          <div>
            <p className="text-[14px] font-semibold">{copy.title}</p>
            <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed text-[var(--text-2)]">
              {copy.body}
            </p>
            {copy.hint ? (
              <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-[var(--muted)]">
                {copy.hint}
              </p>
            ) : null}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
                <RotateCcw size={12} /> {retryLabel}
              </button>
              {copy.showTokenAction ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={onOpenToken}>
                  <Lock size={12} /> Add an HF token
                </button>
              ) : null}
              {repoId ? (
                <a
                  href={`https://huggingface.co/${repoId}`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-ghost btn-sm"
                >
                  Open on Hugging Face <ExternalLink size={12} />
                </a>
              ) : null}
              {copy.kind === "api_down" ? (
                <span className="font-mono text-[10px] text-[var(--faint)]">
                  npm run dev
                </span>
              ) : null}
            </div>

            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[9.5px] text-[var(--faint)]">
              <span>code: {error.code}</span>
              {error.status ? <span>http: {error.status}</span> : null}
              {error.requestId ? <span>request: {error.requestId}</span> : null}
            </div>
          </div>
        </div>
        <button
          type="button"
          className="icon-button h-8 w-8 flex-none border-transparent"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X size={14} />
        </button>
      </div>

      <div className="mt-3 flex items-center gap-1.5 border-t border-[color-mix(in_srgb,var(--no)_22%,var(--line))] pt-3 font-mono text-[9.5px] uppercase tracking-[0.08em] text-[var(--faint)]">
        <ArrowRight size={11} />
        Nothing was downloaded; the request failed before a result was produced.
      </div>
    </div>
  );
}
