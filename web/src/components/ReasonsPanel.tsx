import type { CheckResponse } from "../api/types";
import { dedupeIssues, sortIssues } from "../lib/issues";
import { bandwidthSourceLabel, confidenceShort, formatGB } from "../lib/format";
import { AlertTriangle, FileCode, Lock, ShieldCheck } from "./Icons";
import { ReasonList } from "./ReasonList";
import { ConfidenceMeter, EmptyLine, SectionHeading } from "./ui";

export function ReasonsPanel({ result }: { result: CheckResponse }) {
  const issues = sortIssues(
    dedupeIssues(
      result.verdict.reasons,
      result.claims.fits.reasons,
      result.claims.supported.reasons,
      result.claims.verified.reasons,
      result.warnings,
    ),
  );
  const counts = {
    risk: issues.filter((issue) => issue.severity === "risk").length,
    warning: issues.filter((issue) => issue.severity === "warning").length,
    info: issues.filter((issue) => issue.severity === "info").length,
  };

  return (
    <section className="panel p-5 md:p-6" aria-labelledby="reasons-title">
      <SectionHeading
        id="reasons-title"
        eyebrow="Evidence"
        title="Reasons, warnings, confidence"
        aside={
          <span className="font-mono text-[9.5px] text-[var(--faint)]">
            {counts.risk} risk · {counts.warning} warning · {counts.info} info
          </span>
        }
      />

      {result.model.trust_remote_code_required ? (
        <div className="mb-4 flex items-start gap-2.5 rounded border border-[color-mix(in_srgb,var(--optimize)_35%,var(--line))] bg-[var(--optimize-soft)] p-3">
          <FileCode size={15} className="mt-0.5 flex-none text-[var(--optimize)]" />
          <div>
            <p className="text-[12px] font-medium">Custom code is required</p>
            <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
              This repo requires <span className="font-mono text-[10px]">trust_remote_code</span>.
              The support matrix covers the architecture/runtime pair, not the repo’s own
              implementation.
            </p>
          </div>
        </div>
      ) : null}

      {result.model.gated || result.model.private ? (
        <div className="mb-4 flex items-start gap-2.5 rounded border border-[var(--line)] bg-[var(--bg-elevated)] p-3">
          <Lock size={14} className="mt-0.5 flex-none text-[var(--muted)]" />
          <p className="text-[11px] leading-relaxed text-[var(--muted)]">
            {result.model.private ? "Private repo" : "Gated repo"} access was confirmed for
            this request. The token is not echoed in the result or share link.
          </p>
        </div>
      ) : null}

      {issues.length ? (
        <ReasonList issues={issues} />
      ) : (
        <EmptyLine>No reasons or warnings were returned.</EmptyLine>
      )}

      <div className="mt-5 border-t border-[var(--line)] pt-4">
        <div className="flex items-center justify-between gap-2">
          <p className="micro">Confidence inputs</p>
          <span className="badge">not certainty</span>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
          <div>
            <dt className="micro">Verdict</dt>
            <dd className="mt-1">
              <ConfidenceMeter value={result.verdict.confidence} />
            </dd>
          </div>
          <div>
            <dt className="micro">Memory</dt>
            <dd className="mt-1">
              <ConfidenceMeter value={result.memory.confidence} />
            </dd>
          </div>
          <div>
            <dt className="micro">Speed</dt>
            <dd className="mt-1">
              <ConfidenceMeter value={result.speed.confidence} />
            </dd>
          </div>
          <div>
            <dt className="micro">Hardware</dt>
            <dd className="mt-1">
              <ConfidenceMeter value={result.hardware.confidence} />
            </dd>
          </div>
        </dl>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--line)] pt-3 font-mono text-[9.5px] text-[var(--faint)]">
          <span>bandwidth: {confidenceShort(result.hardware.bandwidth_confidence)}</span>
          <span>memory: {confidenceShort(result.hardware.memory_confidence)}</span>
          <span className="col-span-2">
            source: {result.hardware.source} · {bandwidthSourceLabel(result.hardware.bandwidth_source)}
          </span>
        </div>

        {result.hardware.notes.length ? (
          <ul className="mt-3 space-y-1.5">
            {result.hardware.notes.map((note) => (
              <li
                key={note}
                className="flex items-start gap-2 text-[10.5px] leading-relaxed text-[var(--muted)]"
              >
                <AlertTriangle size={11} className="mt-0.5 flex-none text-[var(--faint)]" />
                {note}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--line)] pt-3 font-mono text-[9.5px] text-[var(--faint)]">
        <span className="flex items-center gap-1.5">
          <ShieldCheck size={11} /> budget {formatGB(result.hardware.memory_budget_bytes)}
        </span>
        <span>source {result.hardware.source}</span>
        <span>schema {result.schema_version}</span>
      </div>
    </section>
  );
}
