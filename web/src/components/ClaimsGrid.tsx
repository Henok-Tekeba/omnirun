import type { CheckResponse, RuntimePath } from "../api/types";
import {
  formatBytesRange,
  formatGB,
  formatInteger,
  formatPercent,
} from "../lib/format";
import { Check, FileCode, Minus, ShieldCheck } from "./Icons";
import { ReasonList } from "./ReasonList";
import { ConfidenceMeter, EmptyLine, StatusPill } from "./ui";

function RuntimeBadge({ path }: { path: RuntimePath }) {
  if (path.status === "available") {
    return <span className="badge badge-go">available</span>;
  }
  if (path.status === "requires_conversion") {
    return <span className="badge badge-optimize">conversion</span>;
  }
  return <span className="badge badge-no">artifact missing</span>;
}

function SupportRuntimeList({ runtimes }: { runtimes: RuntimePath[] }) {
  if (runtimes.length === 0) {
    return <EmptyLine>No runtime paths were returned for this repo.</EmptyLine>;
  }
  return (
    <ul className="mt-2 space-y-2">
      {runtimes.map((path) => (
        <li
          key={`${path.name}-${path.artifact}`}
          className="border-t border-[var(--line)] pt-2 first:border-t-0 first:pt-0"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-[var(--text-2)]">{path.name}</span>
              <RuntimeBadge path={path} />
            </div>
            <span className="font-mono text-[9.5px] text-[var(--faint)]">
              {path.min_version}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--muted)]">
            artifact: <span className="font-mono text-[10px]">{path.artifact}</span>
            {path.direct ? " · directly usable" : " · not directly usable"}
          </p>
          {path.notes ? (
            <p className="mt-1 text-[10.5px] leading-relaxed text-[var(--faint)]">{path.notes}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function FitBody({ result }: { result: CheckResponse }) {
  const fit = result.claims.fits;
  const headroom = fit.headroom_bytes;
  return (
    <>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--line)] pt-3">
        <div>
          <dt className="micro">Budget</dt>
          <dd className="mt-0.5 font-mono text-[12px] text-[var(--text-2)]">
            {formatGB(fit.budget_bytes)}
          </dd>
        </div>
        <div>
          <dt className="micro">Peak range</dt>
          <dd className="mt-0.5 font-mono text-[12px] text-[var(--text-2)]">
            {formatBytesRange(fit.peak)}
          </dd>
        </div>
        <div>
          <dt className="micro">Worst-case headroom</dt>
          <dd className="mt-0.5 font-mono text-[12px] text-[var(--text-2)]">
            {headroom === null
              ? "—"
              : headroom < 0
                ? `over by ${formatGB(Math.abs(headroom))}`
                : `${formatGB(headroom)} (${formatPercent(fit.headroom_ratio)})`}
          </dd>
        </div>
        <div>
          <dt className="micro">Rule</dt>
          <dd className="mt-0.5 text-[11px] text-[var(--muted)]">
            yes only if worst case fits
          </dd>
        </div>
      </dl>
      <ReasonList issues={fit.reasons} limit={3} className="mt-2" />
    </>
  );
}

function SupportedBody({ result }: { result: CheckResponse }) {
  const supported = result.claims.supported;
  const tested = result.claims.verified.runs.length;
  return (
    <>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--line)] pt-3">
        <div>
          <dt className="micro">Documented</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-[var(--text-2)]">
            {supported.matrix_entry_found ? (
              <>
                <Check size={12} className="text-[var(--go)]" /> support matrix
              </>
            ) : (
              <>
                <Minus size={12} className="text-[var(--faint)]" /> no matrix entry
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="micro">Tested</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-[var(--text-2)]">
            {tested > 0 ? (
              <>
                <ShieldCheck size={12} className="text-[var(--go)]" /> {tested} recorded run
                {tested === 1 ? "" : "s"}
              </>
            ) : (
              <>
                <Minus size={12} className="text-[var(--faint)]" /> no recorded runs
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="micro">Matched by</dt>
          <dd className="mt-0.5 font-mono text-[10.5px] text-[var(--text-2)]">
            {supported.matched_by ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="micro">Direct runtime</dt>
          <dd className="mt-0.5 text-[11.5px] text-[var(--text-2)]">
            {supported.direct_runtime_available ? "yes" : "no"}
          </dd>
        </div>
      </dl>
      {supported.custom_code_risk ? (
        <p className="mt-2 flex items-start gap-2 rounded border border-[color-mix(in_srgb,var(--optimize)_35%,var(--line))] bg-[var(--optimize-soft)] p-2 text-[10.5px] leading-relaxed text-[var(--text-2)]">
          <FileCode size={13} className="mt-0.5 flex-none text-[var(--optimize)]" />
          trust_remote_code is required. The matrix covers the architecture/runtime pair,
          not this repo’s custom code.
        </p>
      ) : null}
      <SupportRuntimeList runtimes={supported.runtimes} />
      <p className="mt-2 font-mono text-[9px] leading-relaxed text-[var(--faint)]">
        Documented path, not a test run. A GO never implies VERIFIED.
      </p>
    </>
  );
}

function VerifiedBody({ result }: { result: CheckResponse }) {
  const verified = result.claims.verified;
  if (verified.runs.length === 0) {
    return (
      <div className="mt-3 border-t border-[var(--line)] pt-3">
        <div className="flex items-start gap-2.5 rounded border border-dashed border-[var(--line-strong)] bg-[var(--bg-elevated)] p-3">
          <Minus size={15} className="mt-0.5 flex-none text-[var(--faint)]" />
          <div>
            <p className="text-[12px] font-medium text-[var(--text-2)]">No recorded runs yet</p>
            <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
              v1 ships with an empty verified-runs record. OmniRun can inspect this model
              but cannot claim that anyone ran it on this hardware.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ul className="mt-3 space-y-2 border-t border-[var(--line)] pt-3">
      {verified.runs.map((run) => (
        <li key={run.run_id} className="text-[11.5px] leading-relaxed text-[var(--text-2)]">
          <span className="font-mono text-[10px]">{run.runtime}</span> on{" "}
          {run.hardware_device_name} · {formatInteger(run.decode_tokens_per_second)} tok/s ·
          peak {formatGB(run.peak_memory_bytes)}
        </li>
      ))}
    </ul>
  );
}

export function ClaimsGrid({ result }: { result: CheckResponse }) {
  const { fits, supported, verified } = result.claims;
  return (
    <section aria-labelledby="claims-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="micro micro-accent">Claims</p>
          <h2 id="claims-title" className="mt-1 text-[18px] font-semibold">
            Three questions, answered separately.
          </h2>
        </div>
        <p className="max-w-sm text-right text-[11px] leading-relaxed text-[var(--muted)]">
          FITS is memory. SUPPORTED is a documented runtime path. VERIFIED needs a recorded
          real run.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <article className={`claim-card claim-${fits.status}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="micro">Memory fit</p>
              <h3 className="mt-0.5 text-[16px] font-semibold">FITS</h3>
            </div>
            <StatusPill status={fits.status} />
          </div>
          <div className="mt-2">
            <ConfidenceMeter value={fits.confidence} />
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-[var(--muted)]">{fits.summary}</p>
          <FitBody result={result} />
        </article>

        <article className={`claim-card claim-${supported.status}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="micro">Runtime path</p>
              <h3 className="mt-0.5 text-[16px] font-semibold">SUPPORTED</h3>
            </div>
            <StatusPill status={supported.status} />
          </div>
          <div className="mt-2">
            <ConfidenceMeter value={supported.confidence} />
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-[var(--muted)]">
            {supported.summary}
          </p>
          <SupportedBody result={result} />
        </article>

        <article className={`claim-card claim-${verified.status}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="micro">Recorded run</p>
              <h3 className="mt-0.5 text-[16px] font-semibold">VERIFIED</h3>
            </div>
            <StatusPill status={verified.status} />
          </div>
          <div className="mt-2">
            <ConfidenceMeter value={verified.confidence} />
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-[var(--muted)]">
            {verified.summary}
          </p>
          <VerifiedBody result={result} />
        </article>
      </div>
    </section>
  );
}
