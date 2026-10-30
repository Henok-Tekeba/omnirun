import type { CheckResponse, Recommendation } from "../api/types";
import { formatBytesRange, formatDate, formatGB } from "../lib/format";
import { CopyButton } from "./CopyButton";
import { Box, ExternalLink, Layers, Terminal } from "./Icons";
import { ConfidenceMeter, EmptyLine, SectionHeading, StatusPill } from "./ui";

function alternativeLabel(name: string): string {
  const normalized = name.toLowerCase();
  if (normalized === "fp16" || normalized === "bf16") return "16-bit";
  if (normalized === "int8") return "8-bit";
  if (normalized === "4bit") return "4-bit";
  return name;
}

function recommendationKind(kind: Recommendation["kind"]): string {
  switch (kind) {
    case "quantization":
      return "quantization";
    case "runtime":
      return "runtime";
    case "smaller_model":
      return "smaller model";
    case "context":
      return "context";
    case "batch":
      return "batch";
    case "environment":
      return "environment";
    default:
      return "note";
  }
}

function RecommendationCard({ item }: { item: Recommendation }) {
  return (
    <article className="border-t border-[var(--line)] py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="badge">{recommendationKind(item.kind)}</span>
          <h3 className="text-[12.5px] font-semibold">{item.title}</h3>
        </div>
        <ConfidenceMeter value={item.confidence} compact />
      </div>
      <p className="mt-1.5 text-[11.5px] leading-relaxed text-[var(--muted)]">{item.detail}</p>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[9.5px] text-[var(--faint)]">
        {item.runtime ? <span>runtime: {item.runtime}</span> : null}
        {item.min_version ? <span>min: {item.min_version}</span> : null}
        {item.requires_conversion ? <span>requires conversion</span> : null}
        {item.estimated_peak_bytes ? (
          <span>peak: {formatBytesRange(item.estimated_peak_bytes)}</span>
        ) : null}
      </div>
      {item.url ? (
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1.5 text-[10.5px] text-[var(--accent)] underline underline-offset-2"
        >
          Open reference <ExternalLink size={11} />
        </a>
      ) : null}
    </article>
  );
}

export function WhatYouNeed({ result }: { result: CheckResponse }) {
  const alternatives = result.memory.weights.alternatives;
  const recommendations = result.recommendations;
  const hint = result.environment_hint;
  const hasAnything =
    alternatives.length > 0 ||
    recommendations.length > 0 ||
    Boolean(hint?.available && (hint.command || hint.notes.length));

  return (
    <section className="console" aria-labelledby="need-title">
      <div className="console-label">
        <span>
          <strong>What you’d need</strong>
        </span>
        <span>From the API</span>
      </div>
      <div className="p-4 md:p-6">
      <SectionHeading
        id="need-title"
        eyebrow="Suggestions"
        title="What you’d need"
        aside={<span className="badge">From the API</span>}
      />

      {!hasAnything ? (
        <div className="border border-dashed border-[var(--line-strong)] bg-[var(--bg-elevated)] p-4">
          <div className="flex items-start gap-2.5">
            <Box size={16} className="mt-0.5 flex-none text-[var(--faint)]" />
            <div>
              <p className="text-[12px] font-medium text-[var(--text-2)]">
                No extra options
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
                The API returned no smaller-weight estimates or suggestions for this model.
                The result above is complete. Try a different context, batch, or machine.
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {alternatives.length ? (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Layers size={14} className="text-[var(--accent)]" />
              <h3 className="text-[13px] font-semibold">Smaller weights</h3>
            </div>
            <span className="badge badge-accent">Estimate only</span>
          </div>
          <p className="mt-1 text-[10.5px] leading-relaxed text-[var(--faint)]">
            These are estimates only. They do not mean a ready-to-use model exists. Context
            memory is unchanged.
          </p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {alternatives.map((alternative) => (
              <article
                key={alternative.name}
                className="border border-[var(--line)] bg-[var(--bg-elevated)] p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-mono text-[12px] text-[var(--text-2)]">
                      {alternativeLabel(alternative.name)}
                    </p>
                    <p className="mt-0.5 text-[9.5px] text-[var(--faint)]">
                      Weights-only estimate
                    </p>
                  </div>
                  <StatusPill status={alternative.fits} />
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[var(--line)] pt-2">
                  <div>
                    <dt className="micro">Weights</dt>
                    <dd className="mt-0.5 font-mono text-[10.5px] text-[var(--text-2)]">
                      {formatGB(alternative.weight_bytes)}
                    </dd>
                  </div>
                  <div>
                    <dt className="micro">Peak</dt>
                    <dd className="mt-0.5 font-mono text-[10.5px] text-[var(--text-2)]">
                      {formatBytesRange(alternative.peak)}
                    </dd>
                  </div>
                </dl>
                <div className="mt-1.5">
                  <ConfidenceMeter value={alternative.confidence} compact />
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {recommendations.length ? (
        <div className={alternatives.length ? "mt-5 border-t border-[var(--line)] pt-4" : ""}>
          <h3 className="text-[13px] font-semibold">Recommendations</h3>
          <div className="mt-2">
            {recommendations.map((item, index) => (
              <RecommendationCard key={`${item.kind}-${item.title}-${index}`} item={item} />
            ))}
          </div>
        </div>
      ) : null}

      {hint?.available && (hint.command || hint.notes.length) ? (
        <div className={alternatives.length || recommendations.length ? "mt-5 border-t border-[var(--line)] pt-4" : ""}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Terminal size={14} className="text-[var(--accent)]" />
              <h3 className="text-[13px] font-semibold">Environment hint</h3>
            </div>
            {hint.reference_date ? (
              <span className="font-mono text-[9.5px] text-[var(--faint)]">
                reference {formatDate(hint.reference_date)}
              </span>
            ) : null}
          </div>
          {hint.command ? (
            <div className="code-block mt-2">
              <code>$ {hint.command}</code>
              <CopyButton value={hint.command} label="Copy" />
            </div>
          ) : null}
          {hint.notes.length ? (
            <ul className="mt-2 space-y-1">
              {hint.notes.map((note) => (
                <li key={note} className="text-[10.5px] leading-relaxed text-[var(--muted)]">
                  {note}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {!alternatives.length && !recommendations.length && hasAnything ? (
        <div className="mt-3">
          <EmptyLine>No smaller-weight estimates were returned.</EmptyLine>
        </div>
      ) : null}
      </div>
    </section>
  );
}
