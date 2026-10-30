import type { CSSProperties } from "react";
import type { CheckResponse, RangeBytes } from "../api/types";
import {
  formatBytesRange,
  formatGB,
  formatInteger,
  formatPercent,
} from "../lib/format";
import { Gauge } from "./Icons";
import { ConfidenceMeter, EmptyLine, SectionHeading } from "./ui";

function clampPercent(value: number, max: number): number {
  if (!Number.isFinite(value) || max <= 0) return 0;
  return Math.min(100, Math.max(0, (value / max) * 100));
}

function weightRange(result: CheckResponse): RangeBytes | null {
  const weights = result.memory.weights;
  if (weights.range) return weights.range;
  if (weights.actual_bytes !== null) {
    return {
      min: weights.actual_bytes,
      likely: weights.actual_bytes,
      max: weights.actual_bytes,
    };
  }
  return null;
}

function GaugeRow({
  label,
  range,
  budget,
  scaleMax,
  color,
  detail,
  badge,
  delay,
  tall = false,
}: {
  label: string;
  range: RangeBytes | null;
  budget: number | null;
  scaleMax: number;
  color: string;
  detail?: string;
  badge?: string;
  delay: number;
  tall?: boolean;
}) {
  const min = range ? clampPercent(range.min, scaleMax) : 0;
  const max = range ? clampPercent(range.max, scaleMax) : 0;
  const likely = range ? clampPercent(range.likely, scaleMax) : 0;
  const width = range ? Math.max(max - min, 0.6) : 0;
  const budgetPct = budget !== null ? clampPercent(budget, scaleMax) : null;
  const aria = range
    ? `${label}: ${formatBytesRange(range)}, likely ${formatGB(range.likely)}${
        budget !== null ? `, budget ${formatGB(budget)}` : ""
      }`
    : `${label}: not available`;

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-[var(--text-2)]">{label}</span>
          {badge ? <span className="badge">{badge}</span> : null}
        </div>
        <span className="font-mono text-[11px] text-[var(--text-2)]">
          {range ? formatBytesRange(range) : "—"}
        </span>
      </div>
      <div
        className={`gauge-track mt-1.5 ${tall ? "gauge-track-tall" : ""}`}
        role="img"
        aria-label={aria}
      >
        {range ? (
          <>
            <span
              className="gauge-band"
              style={
                {
                  left: `${min}%`,
                  width: `${width}%`,
                  "--gauge-color": color,
                  "--delay": `${delay}ms`,
                } as CSSProperties
              }
            />
            <span
              className="gauge-likely"
              style={
                {
                  left: `${likely}%`,
                  "--gauge-color": color,
                  "--delay": `${delay}ms`,
                } as CSSProperties
              }
            />
          </>
        ) : null}
        {budgetPct !== null ? (
          <span className="gauge-budget" style={{ left: `${budgetPct}%` }} />
        ) : null}
      </div>
      {detail ? (
        <p className="mt-1 text-[10.5px] leading-relaxed text-[var(--faint)]">{detail}</p>
      ) : null}
    </div>
  );
}

export function MemoryPanel({ result }: { result: CheckResponse }) {
  const memory = result.memory;
  const weights = memory.weights;
  const kv = memory.kv_cache;
  const peak = memory.peak;
  const budget = memory.budget_bytes;
  const fit = result.claims.fits;

  const ranges = [weightRange(result), kv.bytes_range, memory.overhead, peak].filter(
    (range): range is RangeBytes => range !== null,
  );
  const rawMax = Math.max(
    budget ?? 0,
    ...ranges.map((range) => range.max),
    0,
  );
  const scaleMax = rawMax > 0 ? rawMax * 1.08 : 1;

  const peakColor =
    fit.status === "yes" ? "var(--go)" : fit.status === "no" ? "var(--no)" : "var(--unknown)";
  const kvDetail = kv.available
    ? `For ${formatInteger(kv.context_effective ?? kv.context_requested)} tokens.`
    : "Not available for this model.";
  const weightsDetail =
    weights.kind === "exact"
      ? "From model headers."
      : weights.kind === "upper_bound"
        ? "Upper bound from file sizes."
        : "Weight size is unknown.";

  return (
    <section className="console" aria-labelledby="memory-title">
      <div className="console-label">
        <span>
          <strong>Memory</strong>
        </span>
        <span>GB</span>
        <ConfidenceMeter value={memory.confidence} />
      </div>

      <div className="p-4 md:p-6">
      <SectionHeading
        id="memory-title"
        eyebrow="Estimate"
        title="Budget and peak"
        aside={<span className="badge">estimate</span>}
      />

      <div className="grid grid-cols-2 border border-[var(--line)] bg-[var(--bg-elevated)]">
        <div className="border-r border-[var(--line)] p-3">
          <p className="micro">Budget</p>
          <p className="mt-1 font-mono text-[22px] leading-none text-[var(--text)]">
            {formatGB(budget)}
          </p>
          <p className="mt-1 text-[10px] text-[var(--faint)]">
            {result.hardware.memory_source.replaceAll("_", " ")}
          </p>
        </div>
        <div className="p-3">
          <p className="micro">Peak range</p>
          <p className="mt-1 font-mono text-[22px] leading-none" style={{ color: peakColor }}>
            {formatBytesRange(peak)}
          </p>
          <p className="mt-1 text-[10px] text-[var(--faint)]">
            {fit.headroom_bytes === null
              ? "headroom unknown"
              : fit.headroom_bytes < 0
                ? `over by ${formatGB(Math.abs(fit.headroom_bytes))}`
                : `${formatGB(fit.headroom_bytes)} headroom (${formatPercent(fit.headroom_ratio)})`}
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        <GaugeRow
          label="Weights"
          range={weightRange(result)}
          budget={budget}
          scaleMax={scaleMax}
          color="var(--accent)"
          badge={weights.kind === "upper_bound" ? "upper bound" : weights.kind}
          detail={weightsDetail}
          delay={40}
        />
        <GaugeRow
          label="Context cache"
          range={kv.bytes_range}
          budget={budget}
          scaleMax={scaleMax}
          color="var(--unknown)"
          badge={kv.available ? "estimated" : "unknown"}
          detail={kvDetail}
          delay={110}
        />
        <GaugeRow
          label="Runtime overhead"
          range={memory.overhead}
          budget={budget}
          scaleMax={scaleMax}
          color="var(--muted)"
          badge="assumption"
          detail="Runtime and allocator."
          delay={180}
        />
        <GaugeRow
          label="Peak"
          range={peak}
          budget={budget}
          scaleMax={scaleMax}
          color={peakColor}
          badge={fit.status === "yes" ? "fits" : fit.status === "no" ? "over budget" : "straddles"}
          detail={
            peak
              ? `Worst case ${formatGB(peak.max)}.`
              : "Peak is unknown until weights and context memory are both known."
          }
          delay={250}
          tall
        />
      </div>

      <div className="mt-1 flex justify-between border-t border-[var(--line)] pt-1.5 font-mono text-[8px] text-[var(--faint)]">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>{formatGB(scaleMax)}</span>
      </div>

      <div className="mt-3 flex items-start gap-2 text-[10px] leading-relaxed text-[var(--faint)]">
        <Gauge size={12} className="mt-0.5 flex-none text-[var(--accent)]" />
        <span>
          The band shows the estimated range. The bright tick is the likely value, and the
          vertical line is your budget. The chart uses binary GB.
        </span>
      </div>

      {!budget ? (
        <div className="mt-2">
          <EmptyLine>No memory budget is available, so FITS cannot be evaluated.</EmptyLine>
        </div>
      ) : null}
      {!kv.available ? (
        <div className="mt-2">
          <EmptyLine>{kvDetail}</EmptyLine>
        </div>
      ) : null}
      </div>
    </section>
  );
}
