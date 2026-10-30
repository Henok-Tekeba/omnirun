import type { CSSProperties } from "react";
import type { CheckResponse, RangeFloat } from "../api/types";
import {
  bandwidthSourceKind,
  bandwidthSourceLabel,
  formatFloat,
  formatGB,
  formatRangeFloat,
  speedClassLabel,
} from "../lib/format";
import { Database, Gauge, HelpCircle } from "./Icons";
import { ConfidenceMeter, EmptyLine, SectionHeading } from "./ui";

function SpeedBar({ range, label }: { range: RangeFloat; label: string }) {
  const max = Math.max(range.max * 1.15, 1);
  const minPct = Math.max(0, Math.min(100, (range.min / max) * 100));
  const maxPct = Math.max(minPct, Math.min(100, (range.max / max) * 100));
  const likelyPct = Math.max(0, Math.min(100, (range.likely / max) * 100));
  const width = Math.max(maxPct - minPct, 0.8);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="micro">{label}</span>
        <span className="font-mono text-[10px] text-[var(--text-2)]">
          {formatRangeFloat(range, "tok/s")}
        </span>
      </div>
      <div
        className="gauge-track gauge-track-tall mt-1.5"
        role="img"
        aria-label={`${label}: ${formatRangeFloat(range, "tokens per second")}, likely ${range.likely.toFixed(1)}`}
      >
        <span
          className="gauge-band"
          style={
            {
              left: `${minPct}%`,
              width: `${width}%`,
              "--gauge-color": "var(--accent)",
              "--delay": "80ms",
            } as CSSProperties
          }
        />
        <span
          className="gauge-likely"
          style={
            {
              left: `${likelyPct}%`,
              "--gauge-color": "var(--accent)",
              "--delay": "80ms",
            } as CSSProperties
          }
        />
      </div>
    </div>
  );
}

function activeWeightSource(value: string | null): string {
  switch (value) {
    case "safetensors_headers":
      return "safetensors headers";
    case "expert_tensor_names":
      return "MoE expert tensor names";
    case "file_sizes":
      return "file sizes / upper bound";
    default:
      return value ? value.replaceAll("_", " ") : "unknown";
  }
}

export function SpeedPanel({ result }: { result: CheckResponse }) {
  const speed = result.speed;
  const kind = bandwidthSourceKind(result.hardware.bandwidth_source);
  const SourceIcon = kind === "table" ? Database : kind === "measured" ? Gauge : HelpCircle;
  const sourceDetail =
    kind === "measured"
      ? "Measured by the helper on this machine. The strongest bandwidth source in v1."
      : kind === "table"
        ? "Curated device-table value, not a measurement on this machine. Manual profiles are MEDIUM confidence."
        : kind === "assumed"
          ? "Conservative default because no better number was available. LOW confidence."
          : "No bandwidth value was available, so speed cannot be estimated.";

  return (
    <section className="console" aria-labelledby="speed-title">
      <div className="console-label">
        <span>
          <strong>Speed</strong> / decode throughput
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className={`led ${
              kind === "measured" ? "led-go" : kind === "table" ? "led-optimize" : "led-unknown"
            }`}
          />
          {kind === "measured" ? "measured" : kind === "table" ? "table" : "assumed"}
        </span>
        <ConfidenceMeter value={speed.confidence} />
      </div>

      <div className="p-4 md:p-6">
        <SectionHeading
          id="speed-title"
          eyebrow="Decode only / tok/s range"
          title="Throughput"
          aside={<span className="badge">estimate</span>}
        />

        {speed.available && speed.aggregate ? (
          <>
            <div className="border border-[var(--line)] bg-[var(--bg-elevated)]">
              <div className="border-b border-[var(--line)] p-3">
                <p className="micro">Aggregate decode</p>
                <p className="mt-1 font-mono text-[28px] leading-none text-[var(--text)]">
                  {formatRangeFloat(speed.aggregate, "tok/s")}
                </p>
              </div>
              <div className="grid grid-cols-2">
                <div className="border-r border-[var(--line)] p-3">
                  <p className="micro">Likely</p>
                  <p className="mt-1 font-mono text-[12px] text-[var(--text-2)]">
                    {speed.aggregate.likely.toFixed(1)} tok/s
                  </p>
                </div>
                <div className="p-3">
                  <p className="micro">Class</p>
                  <p className="mt-1 font-mono text-[12px] text-[var(--text-2)]">
                    {speedClassLabel(speed.speed_class)}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 space-y-4">
              <SpeedBar range={speed.aggregate} label="Aggregate" />
              {speed.batch > 1 && speed.per_sequence ? (
                <SpeedBar range={speed.per_sequence} label="Per sequence" />
              ) : null}
            </div>

            <div className="mt-4 border border-[var(--line)] bg-[var(--bg-elevated)] p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="micro">Bandwidth source</p>
                <span className="flex items-center gap-1.5 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--text-2)]">
                  <SourceIcon size={10} />
                  {kind === "measured" ? "measured" : kind === "table" ? "table" : "assumed"}
                </span>
              </div>
              <p className="mt-1 font-mono text-[16px] text-[var(--text-2)]">
                {speed.bandwidth_gbps === null ? "—" : `${formatFloat(speed.bandwidth_gbps, 1)} GB/s`}
              </p>
              <p className="mt-1 text-[10px] leading-relaxed text-[var(--faint)]">
                {sourceDetail}
              </p>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--line)] pt-3">
              <div>
                <dt className="micro">Efficiency</dt>
                <dd className="mt-0.5 font-mono text-[10px] text-[var(--text-2)]">
                  {speed.efficiency.min.toFixed(2)}–{speed.efficiency.max.toFixed(2)}
                </dd>
                <dd className="text-[9px] text-[var(--faint)]">documented range</dd>
              </div>
              <div>
                <dt className="micro">Active weights</dt>
                <dd className="mt-0.5 font-mono text-[10px] text-[var(--text-2)]">
                  {formatGB(speed.active_weight_bytes)}
                </dd>
                <dd className="text-[9px] text-[var(--faint)]">
                  {activeWeightSource(speed.active_weight_source)}
                </dd>
              </div>
            </dl>

            <details className="mt-3 border-t border-[var(--line)] pt-2">
              <summary className="cursor-pointer list-none py-1 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)] hover:text-[var(--text-2)] [&::-webkit-details-marker]:hidden">
                Method notes ({speed.notes.length})
              </summary>
              <ul className="mt-1 space-y-1.5">
                {speed.notes.map((note) => (
                  <li key={note} className="text-[10px] leading-relaxed text-[var(--muted)]">
                    {note}
                  </li>
                ))}
              </ul>
            </details>
          </>
        ) : (
          <div>
            <div className="border border-dashed border-[var(--line-strong)] bg-[var(--bg-elevated)] p-4">
              <div className="flex items-start gap-2.5">
                <HelpCircle size={15} className="mt-0.5 flex-none text-[var(--unknown)]" />
                <div>
                  <p className="text-[12px] font-medium">Speed estimate not available</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
                    {result.model.model_class === "asr" || result.model.model_class === "tts"
                      ? "OmniRun can inspect this model but cannot judge its speed yet. v1’s decode-speed formula covers causal LLMs only; no RTF is invented."
                      : "OmniRun will not turn an unknown bandwidth or KV layout into a speed number."}
                  </p>
                </div>
              </div>
            </div>
            <div className="mt-3">
              {speed.notes.map((note) => (
                <p key={note} className="mt-1 text-[10px] leading-relaxed text-[var(--muted)]">
                  {note}
                </p>
              ))}
            </div>
            {speed.bandwidth_gbps !== null ? (
              <p className="mt-3 font-mono text-[9px] text-[var(--faint)]">
                bandwidth {formatFloat(speed.bandwidth_gbps, 1)} GB/s /{" "}
                {bandwidthSourceLabel(result.hardware.bandwidth_source)}
              </p>
            ) : null}
          </div>
        )}

        <div className="mt-3 flex items-start gap-2 border-t border-[var(--line)] pt-2 text-[10px] leading-relaxed text-[var(--faint)]">
          <Gauge size={12} className="mt-0.5 flex-none text-[var(--accent)]" />
          <span>
            Decode only. Prefill and time-to-first-token are not estimated. Efficiency is a
            documented engineering range, not a measured constant.
          </span>
        </div>

        {speed.available && speed.aggregate && speed.batch > 1 ? (
          <div className="mt-2">
            <EmptyLine>
              Aggregate throughput assumes perfect continuous batching; small-batch real
              runtimes can be lower.
            </EmptyLine>
          </div>
        ) : null}
      </div>
    </section>
  );
}
