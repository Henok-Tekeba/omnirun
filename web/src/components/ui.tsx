import type { ReactNode } from "react";
import type { ClaimStatus, Confidence } from "../api/types";
import { claimStatusLabel, confidenceLabel } from "../lib/format";
import { Check, HelpCircle, Minus, X } from "./Icons";

export function ConfidenceMeter({
  value,
  compact = false,
}: {
  value: Confidence;
  compact?: boolean;
}) {
  return (
    <span
      className="inline-flex items-center gap-2 text-[var(--muted)]"
      title={confidenceLabel(value)}
    >
      <span className="confidence-bars" data-level={value} aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span className="font-mono text-xs uppercase tracking-[0.08em]">
        {compact ? value : confidenceLabel(value)}
      </span>
    </span>
  );
}

export function StatusPill({ status }: { status: ClaimStatus }) {
  const Icon = status === "yes" ? Check : status === "no" ? X : HelpCircle;
  return (
    <span className={`status-pill status-${status}`}>
      <Icon size={10} />
      {claimStatusLabel(status)}
    </span>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  aside,
  id,
}: {
  eyebrow?: string;
  title: string;
  aside?: ReactNode;
  id?: string;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 id={id} className="module-title">
          {title}
        </h2>
        {eyebrow ? (
          <p className="mt-1 font-mono text-xs uppercase tracking-[0.08em] text-[var(--faint)]">
            {eyebrow}
          </p>
        ) : null}
      </div>
      {aside ? <div className="flex flex-wrap items-center gap-2">{aside}</div> : null}
    </div>
  );
}

export function EmptyLine({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 py-2 text-sm text-[var(--muted)]">
      <Minus size={13} className="mt-0.5 flex-none text-[var(--faint)]" />
      <span>{children}</span>
    </div>
  );
}

export function KeyValue({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="micro">{label}</dt>
      <dd className="mt-1 text-sm text-[var(--text-2)]">{children}</dd>
    </div>
  );
}
