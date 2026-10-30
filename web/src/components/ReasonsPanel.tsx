import type { CheckResponse } from "../api/types";
import { dedupeIssues, sortIssues } from "../lib/issues";
import { bandwidthSourceLabel, confidenceShort, formatGB } from "../lib/format";
import { AlertTriangle, FileCode, Lock, ShieldCheck } from "./Icons";
import { ReasonList } from "./ReasonList";
import { ConfidenceMeter, EmptyLine, SectionHeading } from "./ui";

function friendlyHardwareNote(note: string): string {
  return note
    .replace(
      "Manual profile: curated device-table bandwidth, not a measurement on this machine.",
      "Hardware profile is curated, not measured on this machine.",
    )
    .replace(
      "Usable unified memory is 75% of total RAM; this is a documented assumption.",
      "Usable memory is 75% of total RAM (documented assumption).",
    )
    .replace(
      "Helper values are self-reported and unsigned; confidence means 'measured by the helper on this machine', not cryptographic attestation.",
      "Helper values are self-reported and not signed.",
    );
}

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
  const importantIssues = issues.filter((issue) => issue.severity !== "info");
  const technicalIssues = issues.filter((issue) => issue.severity === "info");
  const counts = {
    risk: issues.filter((issue) => issue.severity === "risk").length,
    warning: issues.filter((issue) => issue.severity === "warning").length,
    info: technicalIssues.length,
  };

  return (
    <section className="console" aria-labelledby="reasons-title">
      <div className="console-label">
        <span>
          <strong>Warnings and reasons</strong>
        </span>
        <span>
          {counts.risk} risks / {counts.warning} warnings
        </span>
      </div>
      <div className="p-4 md:p-6">
      <SectionHeading id="reasons-title" eyebrow="Evidence" title="Why this result" />

      {result.model.trust_remote_code_required ? (
        <div className="mb-4 flex items-start gap-2.5 border border-[color-mix(in_srgb,var(--optimize)_35%,var(--line))] bg-[var(--optimize-soft)] p-3">
          <FileCode size={15} className="mt-0.5 flex-none text-[var(--optimize)]" />
          <div>
            <p className="text-sm font-medium">This model needs custom code</p>
            <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
              The support matrix covers the architecture and runtime, not this model’s own
              code.
            </p>
          </div>
        </div>
      ) : null}

      {result.model.gated || result.model.private ? (
        <div className="mb-4 flex items-start gap-2.5 border border-[var(--line)] bg-[var(--bg-elevated)] p-3">
          <Lock size={14} className="mt-0.5 flex-none text-[var(--muted)]" />
          <p className="text-sm leading-relaxed text-[var(--muted)]">
            Access to this {result.model.private ? "private" : "gated"} model was confirmed.
            The token is not included in the result or share link.
          </p>
        </div>
      ) : null}

      {importantIssues.length ? (
        <ReasonList issues={importantIssues} />
      ) : (
        <EmptyLine>No warnings.</EmptyLine>
      )}

      {technicalIssues.length ? (
        <details className="mt-3 border-t border-[var(--line)] pt-2">
          <summary className="cursor-pointer list-none py-1 font-mono text-xs uppercase tracking-[0.08em] text-[var(--faint)] hover:text-[var(--text-2)] [&::-webkit-details-marker]:hidden">
            Technical details ({technicalIssues.length})
          </summary>
          <div className="mt-2">
            <ReasonList issues={technicalIssues} />
          </div>
        </details>
      ) : null}

      <div className="mt-5 border-t border-[var(--line)] pt-4">
        <div className="flex items-center justify-between gap-2">
          <p className="micro">Confidence</p>
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
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--line)] pt-3 font-mono text-xs text-[var(--faint)]">
          <span>Speed source: {confidenceShort(result.hardware.bandwidth_confidence)}</span>
          <span>Memory: {confidenceShort(result.hardware.memory_confidence)}</span>
          <span className="col-span-2">
            Hardware: {result.hardware.source} / Speed source:{" "}
            {bandwidthSourceLabel(result.hardware.bandwidth_source)}
          </span>
        </div>

        {result.hardware.notes.length ? (
          <ul className="mt-3 space-y-1.5">
            {result.hardware.notes.map((note) => (
              <li
                key={note}
                className="flex items-start gap-2 text-xs leading-relaxed text-[var(--muted)]"
              >
                <AlertTriangle size={11} className="mt-0.5 flex-none text-[var(--faint)]" />
                {friendlyHardwareNote(note)}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--line)] pt-3 font-mono text-xs text-[var(--faint)]">
        <span className="flex items-center gap-1.5">
          <ShieldCheck size={11} /> budget {formatGB(result.hardware.memory_budget_bytes)}
        </span>
        <span>Hardware: {result.hardware.source}</span>
      </div>
      </div>
    </section>
  );
}
