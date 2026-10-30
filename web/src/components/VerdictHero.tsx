import type { CheckResponse } from "../api/types";
import {
  formatDateTime,
  formatGB,
  formatInteger,
  hardwareKindLabel,
  shortRevision,
} from "../lib/format";
import { basisLabel, verdictNote, verdictTone } from "../lib/verdict";
import {
  CheckCircle,
  HelpCircle,
  Minus,
  ShieldCheck,
  Sliders,
  XCircle,
} from "./Icons";
import { ConfidenceMeter } from "./ui";

const VERDICT_ICON = {
  GO: CheckCircle,
  OPTIMIZE: Sliders,
  NO: XCircle,
  UNKNOWN: HelpCircle,
} as const;

export function VerdictHero({ result }: { result: CheckResponse }) {
  const verdict = result.verdict;
  const tone = verdictTone(verdict.value);
  const Icon = VERDICT_ICON[verdict.value];
  const basis = verdict.basis_claims;
  const context = result.memory.context_effective ?? result.inputs.context_effective;
  const note =
    verdict.value === "UNKNOWN" &&
    (result.model.model_class === "asr" || result.model.model_class === "tts")
      ? "We can inspect this model, but this build can’t judge ASR/TTS yet."
      : verdictNote(verdict.value);

  return (
    <section className={`verdict-hero verdict-${tone}`} aria-labelledby="verdict-word">
      <div className="console-label">
        <span>
          <strong>Verdict</strong> / preflight
        </span>
        <span className="flex items-center gap-2 text-[var(--verdict)]">
          <span className={`led led-${tone}`} />
          {verdict.value}
        </span>
        <ConfidenceMeter value={verdict.confidence} />
      </div>

      <div className="grid gap-7 p-4 md:p-7 lg:grid-cols-[1.45fr_1fr]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <span className="verdict-icon">
              <Icon size={21} />
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)]">
              Decision
            </span>
          </div>

          <h1 id="verdict-word" className="verdict-word mt-3">
            {verdict.value}
          </h1>
          <p className="mt-2 text-[11px] font-medium text-[var(--verdict)]">{note}</p>

          <p className="mt-3 max-w-2xl text-[13px] leading-relaxed text-[var(--text-2)]">
            {verdict.summary}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="font-mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--faint)]">
              Basis
            </span>
            {basis.length ? (
              basis.map((item) => {
                const BasisIcon = item === "verified" ? ShieldCheck : CheckCircle;
                return (
                  <span key={item} className="badge badge-go">
                    <BasisIcon size={10} />
                    {basisLabel(item)}
                  </span>
                );
              })
            ) : (
              <span className="badge badge-unknown">
                <Minus size={10} /> No basis claim
              </span>
            )}
            <span className="badge badge-unknown">
              <Minus size={10} /> VERIFIED not recorded
            </span>
          </div>

          <p className="mt-3 max-w-xl text-[10px] leading-relaxed text-[var(--faint)]">
            A GO means FITS + a directly usable SUPPORTED path. It never means a real run was
            recorded. Claims stay separate below.
          </p>
        </div>

        <div className="border-t border-[var(--line)] pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <div className="mb-2 flex items-center justify-between gap-2 font-mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--faint)]">
            <span>Run sheet</span>
            <span>schema {result.schema_version}</span>
          </div>
          <dl className="readout-grid grid-cols-2">
            <div className="readout-cell col-span-2">
              <dt>Model</dt>
              <dd>{result.model.repo_id}</dd>
            </div>
            <div className="readout-cell">
              <dt>Class / arch</dt>
              <dd>
                {result.model.model_class.toUpperCase()}
                {result.model.architecture ? ` / ${result.model.architecture}` : ""}
              </dd>
            </div>
            <div className="readout-cell">
              <dt>Format</dt>
              <dd>{result.model.format}</dd>
            </div>
            <div className="readout-cell">
              <dt>Revision</dt>
              <dd title={result.model.revision}>{shortRevision(result.model.revision, 10)}</dd>
            </div>
            <div className="readout-cell">
              <dt>Hardware</dt>
              <dd>
                {result.hardware.device_name}
                <span className="mt-0.5 block text-[8.5px] uppercase tracking-[0.05em] text-[var(--faint)]">
                  {hardwareKindLabel(result.hardware.kind)} / {result.hardware.source}
                </span>
              </dd>
            </div>
            <div className="readout-cell">
              <dt>Memory budget</dt>
              <dd>{formatGB(result.hardware.memory_budget_bytes)}</dd>
            </div>
            <div className="readout-cell">
              <dt>Context / batch</dt>
              <dd>
                {formatInteger(context)}
                {result.inputs.context_clamped ? " (clamped)" : ""} / {result.inputs.batch}
              </dd>
            </div>
            <div className="readout-cell col-span-2">
              <dt>Checked</dt>
              <dd>{formatDateTime(result.checked_at)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}
