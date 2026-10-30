import type { CheckResponse } from "../api/types";
import { CopyButton } from "./CopyButton";
import { ChevronDown, RotateCcw } from "./Icons";

export function AssumptionsPanel({
  result,
  sample = false,
}: {
  result: CheckResponse;
  sample?: boolean;
}) {
  const cache = result.cache;
  return (
    <section className="console" aria-labelledby="assumptions-title">
      <div className="console-label">
        <span>
          <strong>Assumptions</strong>
        </span>
      </div>
      <div className="p-4 md:p-6">
      <div>
        <h2 id="assumptions-title" className="module-title">
          Assumptions
        </h2>
        <p className="mt-1 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)]">
          Estimates are not guarantees
        </p>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[9.5px] text-[var(--faint)]">
        <span>Request ID: {result.request_id}</span>
        <span>
          {sample ? "Recorded sample" : cache.result_cache_hit ? "Cached result" : "Fresh result"}
        </span>
      </div>

      <details className="mt-3 border-t border-[var(--line)] pt-2">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-[11px] text-[var(--muted)] [&::-webkit-details-marker]:hidden">
          <span>Show assumptions</span>
          <ChevronDown size={14} className="text-[var(--faint)]" />
        </summary>
        <ul className="mt-2 space-y-2">
          {result.assumptions.map((assumption) => (
            <li
              key={assumption.id}
              className="border-t border-[var(--line)] pt-2 text-[11px] leading-relaxed text-[var(--muted)] first:border-t-0 first:pt-0"
            >
              <span className="font-mono text-[9px] uppercase tracking-[0.07em] text-[var(--faint)]">
                {assumption.id}
              </span>
              <span className="mt-0.5 block">{assumption.text}</span>
            </li>
          ))}
        </ul>
      </details>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] pt-3">
        <p className="max-w-xl text-[10.5px] leading-relaxed text-[var(--faint)]">
          Estimates are not guarantees. A GO is not a recorded run.
        </p>
        <div className="flex items-center gap-2">
          <CopyButton value={result.request_id} label="Copy request ID" />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          >
            <RotateCcw size={12} /> Top
          </button>
        </div>
      </div>
      </div>
    </section>
  );
}
