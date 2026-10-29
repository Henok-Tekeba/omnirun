import type { IssueLike } from "../lib/issues";
import { AlertTriangle, Info, OctagonAlert } from "./Icons";

const ICON = {
  info: Info,
  warning: AlertTriangle,
  risk: OctagonAlert,
} as const;

export function ReasonList({
  issues,
  limit,
  className = "",
}: {
  issues: IssueLike[];
  limit?: number;
  className?: string;
}) {
  const shown = limit ? issues.slice(0, limit) : issues;
  if (shown.length === 0) return null;

  return (
    <ul className={`space-y-0 ${className}`}>
      {shown.map((issue) => {
        const Icon = ICON[issue.severity];
        return (
          <li
            key={`${issue.code}-${issue.message}`}
            className={`reason-item severity-${issue.severity}`}
          >
            <Icon size={14} className="severity-icon" />
            <span className="min-w-0">
              <span className="block text-[12px] leading-relaxed text-[var(--text-2)]">
                {issue.message}
              </span>
              <span className="mt-0.5 block font-mono text-[8.5px] uppercase tracking-[0.07em] text-[var(--faint)]">
                {issue.severity} · {issue.code}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
