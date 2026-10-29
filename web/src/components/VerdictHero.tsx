import type { ReactNode } from "react";
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

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-[var(--line)] py-2 first:border-t-0 first:pt-0">
      <dt className="micro">{label}</dt>
      <dd className="text-right text-[12px] text-[var(--text-2)]">{children}</dd>
    </div>
  );
}

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
    <section className={`verdict-hero verdict-${tone} p-5 md:p-7`} aria-labelledby="verdict-word">
      <div className="grid gap-7 lg:grid-cols-[1.45fr_1fr]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <span className="verdict-icon">
              <Icon size={23} />
            </span>
            <p className="micro">Preflight verdict</p>
            <ConfidenceMeter value={verdict.confidence} />
          </div>

          <h1 id="verdict-word" className="verdict-word mt-4">
            {verdict.value}
          </h1>
          <p className="mt-2 text-[12px] font-medium text-[var(--verdict)]">{note}</p>

          <p className="mt-3 max-w-2xl text-[13.5px] leading-relaxed text-[var(--text-2)]">
            {verdict.summary}
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="micro">Basis</span>
            {basis.length ? (
              basis.map((item) => {
                const BasisIcon = item === "verified" ? ShieldCheck : CheckCircle;
                return (
                  <span key={item} className="badge badge-go">
                    <BasisIcon size={11} />
                    {basisLabel(item)}
                  </span>
                );
              })
            ) : (
              <span className="badge badge-unknown">
                <Minus size={11} /> No basis claim
              </span>
            )}
            <span className="badge badge-unknown">
              <Minus size={11} /> VERIFIED not recorded
            </span>
          </div>

          <p className="mt-3 max-w-xl text-[11px] leading-relaxed text-[var(--faint)]">
            A GO means FITS + a directly usable SUPPORTED path. It never means a real run
            was recorded. Claims stay separate below.
          </p>
        </div>

        <div className="border-t border-[var(--line)] pt-4 lg:border-l lg:border-t-0 lg:pl-7 lg:pt-0">
          <p className="micro">At a glance</p>
          <dl className="mt-2">
            <MetaRow label="Model">
              <span className="font-mono text-[11px]">{result.model.repo_id}</span>
            </MetaRow>
            <MetaRow label="Class / arch">
              {result.model.model_class.toUpperCase()}
              {result.model.architecture ? ` · ${result.model.architecture}` : ""}
            </MetaRow>
            <MetaRow label="Format">
              <span className="font-mono text-[11px]">{result.model.format}</span>
            </MetaRow>
            <MetaRow label="Revision">
              <span className="font-mono text-[11px]" title={result.model.revision}>
                {shortRevision(result.model.revision, 10)}
              </span>
            </MetaRow>
            <MetaRow label="Hardware">
              {result.hardware.device_name}
              <span className="block font-mono text-[9.5px] uppercase tracking-[0.06em] text-[var(--faint)]">
                {hardwareKindLabel(result.hardware.kind)} · {result.hardware.source}
              </span>
            </MetaRow>
            <MetaRow label="Memory budget">
              <span className="font-mono">{formatGB(result.hardware.memory_budget_bytes)}</span>
            </MetaRow>
            <MetaRow label="Context">
              <span className="font-mono">
                {formatInteger(context)} {result.inputs.context_clamped ? "(clamped)" : ""}
              </span>
            </MetaRow>
            <MetaRow label="Batch">
              <span className="font-mono">{result.inputs.batch}</span>
            </MetaRow>
            <MetaRow label="Checked">
              <span className="text-[11px]">{formatDateTime(result.checked_at)}</span>
            </MetaRow>
          </dl>
        </div>
      </div>
    </section>
  );
}
