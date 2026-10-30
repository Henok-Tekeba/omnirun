import type { CheckResponse } from "../api/types";
import { formatDate, formatDateTime, shortRevision } from "../lib/format";
import { ArtifactShelf } from "./ArtifactShelf";
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
import { WhatIfPanel } from "./WhatIfPanel";
import { WhatYouNeed } from "./WhatYouNeed";

interface ResultViewProps {
  result: CheckResponse;
  shareUrl: string;
  sample?: boolean;
  onEdit: () => void;
}

function RepoTitle({ value }: { value: string }) {
  const [org, ...rest] = value.split("/");
  return (
    <>
      {org}
      {rest.length ? (
        <>
          <wbr />/{rest.join("/")}
        </>
      ) : null}
    </>
  );
}

export function ResultView({ result, shareUrl, sample = false, onEdit }: ResultViewProps) {
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
                {sample ? <span className="badge badge-optimize">recorded sample</span> : null}
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
              <h2 className="repo-title mt-2">
                <RepoTitle value={result.model.repo_id} />
              </h2>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs text-[var(--faint)]">
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
              {sample ? null : (
                <CopyButton
                  value={shareUrl}
                  label="Copy share link"
                  copiedLabel="Link copied"
                  className="!min-h-9 !px-3 !py-2"
                />
              )}
              <button type="button" className="btn btn-secondary btn-sm" onClick={onEdit}>
                <ArrowLeft size={12} /> Edit inputs
              </button>
            </div>
          </div>

          <p className="mt-3 flex items-start gap-2 border-t border-[var(--line)] pt-2 text-xs leading-relaxed text-[var(--faint)]">
            <Clock size={11} className="mt-0.5 flex-none" />
            <span>
              {sample
                ? "This is a recorded sample from the local API, not a live check. The numbers are real for this model and hardware profile."
                : "The share link includes the model, hardware, context, and batch. It never includes your Hugging Face token. Helper codes contain machine details."}
            </span>
          </p>
        </div>
      </div>

      <VerdictHero result={result} />

      <ClaimsGrid result={result} />

      <ArtifactShelf result={result} />

      <div className="grid gap-5 xl:grid-cols-[1.25fr_1fr]">
        <MemoryPanel result={result} />
        <SpeedPanel result={result} />
      </div>

      <WhatIfPanel result={result} />

      <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
        <ReasonsPanel result={result} />
        <WhatYouNeed result={result} />
      </div>

      <AssumptionsPanel result={result} sample={sample} />
    </div>
  );
}
