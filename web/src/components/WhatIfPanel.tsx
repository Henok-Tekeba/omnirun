import type { CheckResponse, SweepPointReport } from "../api/types";
import { formatBytesRange, formatGB, formatInteger } from "../lib/format";
import { ArrowRight, Gauge, Sliders } from "./Icons";
import { EmptyLine, SectionHeading, StatusPill } from "./ui";

function FrontierChart({
  points,
  budget,
  maxContext,
}: {
  points: SweepPointReport[];
  budget: number | null;
  maxContext: number | null;
}) {
  const usable = points.filter(
    (point): point is SweepPointReport & { peak: NonNullable<SweepPointReport["peak"]> } =>
      point.peak !== null,
  );
  if (usable.length === 0) {
    return <EmptyLine>No context frontier is available for this model.</EmptyLine>;
  }

  const width = 680;
  const height = 190;
  const padLeft = 44;
  const padRight = 14;
  const padTop = 16;
  const padBottom = 30;
  const maxX = Math.max(...usable.map((point) => point.context), 1);
  const maxY = Math.max(
    budget ?? 0,
    ...usable.map((point) => point.peak.max),
    1,
  ) * 1.08;
  const x = (value: number) => padLeft + (value / maxX) * (width - padLeft - padRight);
  const y = (value: number) => height - padBottom - (value / maxY) * (height - padTop - padBottom);
  const line = usable
    .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.context)},${y(point.peak.max)}`)
    .join(" ");
  const area = `${line} L${x(usable[usable.length - 1].context)},${height - padBottom} L${x(
    usable[0].context,
  )},${height - padBottom} Z`;
  const budgetY = budget !== null ? y(budget) : null;

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label="Context length versus estimated peak memory, with the memory budget line"
      >
        <line
          x1={padLeft}
          y1={height - padBottom}
          x2={width - padRight}
          y2={height - padBottom}
          stroke="var(--line-strong)"
          strokeWidth="1"
        />
        <line
          x1={padLeft}
          y1={padTop}
          x2={padLeft}
          y2={height - padBottom}
          stroke="var(--line)"
          strokeWidth="1"
        />
        <path d={area} fill="var(--panel-2)" />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth="2" />
        {usable.map((point) => (
          <circle
            key={point.context}
            cx={x(point.context)}
            cy={y(point.peak.max)}
            r="3"
            fill="var(--accent)"
          />
        ))}
        {budgetY !== null ? (
          <>
            <line
              x1={padLeft}
              y1={budgetY}
              x2={width - padRight}
              y2={budgetY}
              stroke="var(--text)"
              strokeDasharray="3 3"
              strokeWidth="1"
            />
            <text
              x={width - padRight}
              y={budgetY - 5}
              textAnchor="end"
              fill="var(--faint)"
              fontFamily="var(--font-mono)"
              fontSize="8"
            >
              budget {formatGB(budget)}
            </text>
          </>
        ) : null}
        {maxContext !== null ? (
          <line
            x1={x(maxContext)}
            y1={padTop}
            x2={x(maxContext)}
            y2={height - padBottom}
            stroke="var(--go)"
            strokeWidth="1"
            opacity="0.5"
          />
        ) : null}
        <text
          x={padLeft}
          y={height - 10}
          fill="var(--faint)"
          fontFamily="var(--font-mono)"
          fontSize="8"
        >
          0
        </text>
        <text
          x={width - padRight}
          y={height - 10}
          textAnchor="end"
          fill="var(--faint)"
          fontFamily="var(--font-mono)"
          fontSize="8"
        >
          {formatInteger(maxX)} tokens
        </text>
        <text
          x={padLeft - 6}
          y={padTop + 4}
          textAnchor="end"
          fill="var(--faint)"
          fontFamily="var(--font-mono)"
          fontSize="8"
        >
          {formatGB(maxY)}
        </text>
      </svg>
      <p className="mt-1 text-[10px] text-[var(--faint)]">
        Peak memory by context. The dashed line is your budget.
        {maxContext !== null ? " The green line is the largest context that fits." : ""}
      </p>
    </div>
  );
}

function quantLabel(name: string): string {
  const normalized = name.toLowerCase();
  if (normalized === "fp16" || normalized === "bf16") return "16-bit";
  if (normalized === "int8") return "8-bit";
  if (normalized === "4bit") return "4-bit";
  return name;
}

export function WhatIfPanel({ result }: { result: CheckResponse }) {
  const sweep = result.sweep;
  const best = sweep.best_quantization;
  const hasContext = sweep.max_context_that_fits !== null;
  const hasBatch = sweep.max_batch_that_fits !== null;

  return (
    <section className="console" aria-labelledby="what-if-title">
      <div className="console-label">
        <span>
          <strong>What-if</strong>
        </span>
        <span>context / batch / memory</span>
        <span>modeled</span>
      </div>
      <div className="p-4 md:p-6">
        <SectionHeading
          id="what-if-title"
          eyebrow="What-if analysis"
          title="Capacity planning"
          aside={<span className="badge">current setup</span>}
        />

        <div className="grid grid-cols-2 border border-[var(--line)] bg-[var(--bg-elevated)] sm:grid-cols-3">
          <div className="border-r border-[var(--line)] p-3">
            <p className="micro">Max context that fits</p>
            <p className="mt-1 font-mono text-[20px] leading-none text-[var(--text)]">
              {hasContext ? formatInteger(sweep.max_context_that_fits) : "—"}
            </p>
            <p className="mt-1 text-[10px] text-[var(--faint)]">tokens</p>
          </div>
          <div className="border-r border-[var(--line)] p-3">
            <p className="micro">Max batch that fits</p>
            <p className="mt-1 font-mono text-[20px] leading-none text-[var(--text)]">
              {hasBatch ? formatInteger(sweep.max_batch_that_fits) : "—"}
            </p>
            <p className="mt-1 text-[10px] text-[var(--faint)]">sequences</p>
          </div>
          <div className="col-span-2 p-3 sm:col-span-1">
            <p className="micro">Best fitting quantization</p>
            <p className="mt-1 text-[13px] font-medium text-[var(--text)]">
              {best ? quantLabel(best.name) : "No fit"}
            </p>
            <p className="mt-1 text-[10px] text-[var(--faint)]">
              {best ? formatBytesRange(best.peak) : "No alternative fits this budget."}
            </p>
          </div>
        </div>

        <div className="mt-4 border border-[var(--line)] p-3">
          <div className="mb-1 flex items-center justify-between gap-2">
            <p className="micro">Memory frontier</p>
            <span className="font-mono text-[8.5px] text-[var(--faint)]">
              {sweep.model_max_context ? `model max ${formatInteger(sweep.model_max_context)}` : "max unknown"}
            </span>
          </div>
          <FrontierChart
            points={sweep.context_points}
            budget={sweep.budget_bytes}
            maxContext={sweep.max_context_that_fits}
          />
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between gap-2">
            <p className="micro">Scenarios</p>
            <span className="font-mono text-[8.5px] text-[var(--faint)]">
              estimates / not guarantees
            </span>
          </div>
          <div className="mt-2 border border-[var(--line)]">
            {sweep.scenarios.length === 0 ? (
              <div className="p-3">
                <EmptyLine>No scenario data is available.</EmptyLine>
              </div>
            ) : (
              sweep.scenarios.map((scenario) => (
                <div
                  key={scenario.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--line)] px-3 py-2 first:border-t-0"
                >
                  <div className="flex items-center gap-2">
                    <Sliders size={12} className="text-[var(--faint)]" />
                    <span className="text-[11px] text-[var(--text-2)]">{scenario.label}</span>
                    <span className="font-mono text-[8.5px] text-[var(--faint)]">
                      {formatInteger(scenario.context)} tokens / batch {scenario.batch}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[10px] text-[var(--text-2)]">
                      {formatBytesRange(scenario.peak)}
                    </span>
                    <StatusPill status={scenario.fits} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--line)] pt-2 font-mono text-[9px] text-[var(--faint)]">
          <span className="flex items-center gap-1.5">
            <Gauge size={11} /> budget {formatGB(sweep.budget_bytes)}
          </span>
          <span className="flex items-center gap-1.5">
            <ArrowRight size={10} /> context and batch are evaluated with the same model
          </span>
        </div>
      </div>
    </section>
  );
}
