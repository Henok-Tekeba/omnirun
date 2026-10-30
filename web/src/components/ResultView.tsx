import type { CheckResponse } from "../api/types";
import { formatDate, formatDateTime, shortRevision } from "../lib/format";
import { AssumptionsPanel } from "./AssumptionsPanel";
import { ClaimsGrid } from "./ClaimsGrid";
import { CopyButton } from "./CopyButton";
import {
  ArrowLeft,
  Clock,
  ExternalLink,
  FileCode,
  Lock,
} from "./Icons";
import { MemoryPanel } from "./MemoryPanel";
import { ReasonsPanel } from "./ReasonsPanel";
import { SpeedPanel } from "./SpeedPanel";
import { VerdictHero } from "./VerdictHero";
import { WhatYouNeed } from "./WhatYouNeed";

interface ResultViewProps {
  result: CheckResponse;
  shareUrl: string;
  onEdit: () => void;
}

export function ResultView({ result, shareUrl, onEdit }: ResultViewProps) {
  return (
    <div className="space-y-5">
      <p className="sr-only" role="status" aria-live="polite">
        Preflight result ready. Verdict {result.verdict.value}.
      </p>

      <div className="console">
        <div className="console-label">
          <span>
            <strong>Preflight report</strong>
          </span>
          <span>{formatDateTime(result.checked_at)}</span>
        </div>
        <div className="p-4 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="badge">{result.model.model_class.toUpperCase()}</span>
                <span className="badge">{result.model.format}</span>
                {result.model.gated ? (
                  <span className="badge">
                    <Lock size={10} /> gated
                  </span>
                ) : null}
                {result.model.private ? (
                  <span className="badge">
                    <Lock size={10} /> private
                  </span>
                ) : null}
                {result.model.trust_remote_code_required ? (
                  <span className="badge badge-optimize">
                    <FileCode size={10} /> custom code
                  </span>
                ) : null}
              </div>
              <h1 className="repo-title mt-2">{result.model.repo_id}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[9px] text-[var(--faint)]">
                <span>Revision {shortRevision(result.model.revision, 10)}</span>
                <span>Checked {formatDateTime(result.checked_at)}</span>
                {result.model.last_modified ? (
                  <span>Updated {formatDate(result.model.last_modified)}</span>
                ) : null}
                <a
                  href={result.links.hf_model}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[var(--muted)] underline underline-offset-2 hover:text-[var(--text)]"
                >
                  huggingface.co <ExternalLink size={10} />
                </a>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <CopyButton
                value={shareUrl}
                label="Copy share link"
                copiedLabel="Link copied"
                className="!min-h-9 !px-3 !py-2"
              />
              <button type="button" className="btn btn-secondary btn-sm" onClick={onEdit}>
                <ArrowLeft size={12} /> Edit inputs
              </button>
            </div>
          </div>

          <p className="mt-3 flex items-start gap-2 border-t border-[var(--line)] pt-2 text-[9.5px] leading-relaxed text-[var(--faint)]">
            <Clock size={11} className="mt-0.5 flex-none" />
            <span>
              The share link includes the model, hardware, context, and batch. It never
              includes your Hugging Face token. Helper codes contain machine details.
            </span>
          </p>
        </div>
      </div>

      <VerdictHero result={result} />

      <ClaimsGrid result={result} />

      <div className="grid gap-5 xl:grid-cols-[1.25fr_1fr]">
        <MemoryPanel result={result} />
        <SpeedPanel result={result} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
        <ReasonsPanel result={result} />
        <WhatYouNeed result={result} />
      </div>

      <AssumptionsPanel result={result} />
    </div>
  );
}
