import type { ApiError } from "../api/client";
import { errorCopy, errorRepoId } from "../lib/errors";
import {
  AlertTriangle,
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
          <span className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center border border-[color-mix(in_srgb,var(--no)_55%,transparent)] bg-[var(--no-soft)] text-[var(--no)]">
            <AlertTriangle size={15} />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--no)]">
                Something went wrong
              </span>
              <span className="font-mono text-[8.5px] text-[var(--faint)]">
                {error.code}
                {error.status ? ` / HTTP ${error.status}` : ""}
              </span>
            </div>
            <p className="mt-1.5 text-[14px] font-semibold">{copy.title}</p>
            <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-[var(--text-2)]">
              {copy.body}
            </p>
            {copy.hint ? (
              <p className="mt-2 max-w-2xl text-[11px] leading-relaxed text-[var(--muted)]">
                {copy.hint}
              </p>
            ) : null}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
                <RotateCcw size={11} /> {retryLabel}
              </button>
              {copy.showTokenAction ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={onOpenToken}>
                  <Lock size={11} /> Add a Hugging Face token
                </button>
              ) : null}
              {repoId ? (
                <a
                  href={`https://huggingface.co/${repoId}`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-ghost btn-sm"
                >
                  Open on Hugging Face <ExternalLink size={11} />
                </a>
              ) : null}
            </div>

            {error.requestId ? (
              <p className="mt-3 font-mono text-[8.5px] text-[var(--faint)]">
                Request ID: {error.requestId}
              </p>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          className="icon-button h-7 w-7 flex-none border-transparent"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X size={13} />
        </button>
      </div>

      <div className="mt-3 border-t border-[color-mix(in_srgb,var(--no)_25%,var(--line))] pt-2 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)]">
        No model files were downloaded.
      </div>
    </div>
  );
}
