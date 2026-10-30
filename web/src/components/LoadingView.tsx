import { useEffect, useMemo, useState } from "react";
import { Check, Clock, Cpu, X } from "./Icons";

const STAGES = [
  {
    at: 0,
    title: "Reading repository metadata",
    detail: "Resolving the repo and pinning a commit.",
  },
  {
    at: 1500,
    title: "Reading config and weight headers",
    detail: "Config, safetensors headers, GGUF metadata — no tensor payloads.",
  },
  {
    at: 3600,
    title: "Estimating memory and decode speed",
    detail: "Weights, KV cache, overhead, and a bandwidth-based range.",
  },
  {
    at: 5600,
    title: "Checking runtime support",
    detail: "Matching the architecture to documented runtime paths.",
  },
  {
    at: 7600,
    title: "Assembling the report",
    detail: "Keeping FITS, SUPPORTED, and VERIFIED separate.",
  },
];

interface LoadingViewProps {
  model: string;
  hardware: string;
  onCancel: () => void;
}

export function LoadingView({ model, hardware, onCancel }: LoadingViewProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = performance.now();
    const timer = window.setInterval(() => {
      setElapsed(performance.now() - started);
    }, 200);
    return () => window.clearInterval(timer);
  }, []);

  const activeIndex = useMemo(() => {
    let index = 0;
    for (let i = 0; i < STAGES.length; i += 1) {
      if (elapsed >= STAGES[i].at) index = i;
    }
    return index;
  }, [elapsed]);

  const active = STAGES[activeIndex];
  const slow = elapsed > 20_000;

  return (
    <section className="console" aria-labelledby="loading-title">
      <div className="console-label">
        <span>
          <strong>Preflight</strong> / in progress
        </span>
        <span>Live check</span>
        <span>{(elapsed / 1000).toFixed(0)}s elapsed</span>
      </div>

      <div className="p-4 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.11em] text-[var(--accent)]">
              Running
            </p>
            <h1 id="loading-title" className="bench-title mt-2 text-[clamp(2.8rem,6vw,4.8rem)]">
              Reading the model.
            </h1>
            <p className="mt-3 max-w-xl text-[12px] leading-relaxed text-[var(--muted)]">
              <span className="font-mono text-[11px] text-[var(--text-2)]">{model}</span>
              <span className="mx-2 text-[var(--faint)]">/</span>
              {hardware}
            </p>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>
            <X size={11} /> Cancel
          </button>
        </div>

        <div className="mt-5">
          <div className="progress-line" aria-hidden="true" />
          <p
            className="mt-3 flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--muted)]"
            aria-live="polite"
          >
            <Clock size={11} className="text-[var(--accent)]" />
            {active.title}
          </p>
        </div>

        <div className="mt-4 border-t border-[var(--line)]" aria-hidden="true">
          {STAGES.map((stage, index) => {
            const done = index < activeIndex;
            const isActive = index === activeIndex;
            return (
              <div
                key={stage.title}
                className={`stage-row ${done ? "stage-done" : ""} ${isActive ? "stage-active" : ""}`}
              >
                <span className="stage-dot">
                  {done ? <Check size={10} /> : String(index + 1).padStart(2, "0")}
                </span>
                <span className="stage-label text-[12px] text-[var(--faint)]">
                  {stage.title}
                  <span className="mt-0.5 block text-[10px] text-[var(--faint)]">
                    {stage.detail}
                  </span>
                </span>
                <span className="font-mono text-[8px] uppercase tracking-[0.08em] text-[var(--faint)]">
                  {done ? "done" : isActive ? "working" : "waiting"}
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-4 flex flex-col gap-2 border-t border-[var(--line)] pt-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl text-[10px] leading-relaxed text-[var(--faint)]">
            Stages are approximate. The API returns one report when it finishes.
          </p>
          {slow ? (
            <p className="flex items-center gap-1.5 font-mono text-[9px] text-[var(--optimize)]">
              <Cpu size={11} /> still working — this can take up to 30 seconds
            </p>
          ) : (
            <p className="font-mono text-[9px] text-[var(--faint)]">
              {(elapsed / 1000).toFixed(0)}s
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
