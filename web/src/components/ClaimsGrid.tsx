import type { ReactNode } from "react";
import type { CheckResponse, RuntimePath } from "../api/types";
import { formatBytesRange, formatGB, formatInteger, formatPercent } from "../lib/format";
import { Check, FileCode, Minus, ShieldCheck } from "./Icons";
import { ConfidenceMeter, EmptyLine, StatusPill } from "./ui";

function RuntimeBadge({ path }: { path: RuntimePath }) {
  if (path.status === "available") {
    return <span className="badge badge-go">available</span>;
  }
  if (path.status === "requires_conversion") {
    return <span className="badge badge-optimize">conversion</span>;
  }
  return <span className="badge badge-no">missing</span>;
}

function SupportRuntimeList({ runtimes }: { runtimes: RuntimePath[] }) {
  if (runtimes.length === 0) {
    return <EmptyLine>No runtime paths were returned.</EmptyLine>;
  }
  return (
    <ul className="mt-2 space-y-1.5">
      {runtimes.map((path) => (
        <li
          key={`${path.name}-${path.artifact}`}
          className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-[var(--line)] pt-1.5 first:border-t-0 first:pt-0"
        >
          <span className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-[var(--text-2)]">{path.name}</span>
            <RuntimeBadge path={path} />
          </span>
          <span className="font-mono text-[8.5px] text-[var(--faint)]">
            {path.artifact} / {path.min_version}
          </span>
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
      <div className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1 border-t border-[var(--line)] pt-2">
        <div>
          <p className="micro">Budget</p>
          <p className="mt-0.5 font-mono text-[10px] text-[var(--text-2)]">
            {formatGB(fit.budget_bytes)}
          </p>
        </div>
        <div>
          <p className="micro">Peak</p>
          <p className="mt-0.5 font-mono text-[10px] text-[var(--text-2)]">
            {formatBytesRange(fit.peak)}
          </p>
        </div>
        <div>
          <p className="micro">Headroom</p>
          <p className="mt-0.5 font-mono text-[10px] text-[var(--text-2)]">
            {headroom === null
              ? "—"
              : headroom < 0
                ? `-${formatGB(Math.abs(headroom))}`
                : `${formatGB(headroom)} (${formatPercent(fit.headroom_ratio)})`}
          </p>
        </div>
      </div>
    </>
  );
}

function SupportedBody({ result }: { result: CheckResponse }) {
  const supported = result.claims.supported;
  const tested = result.claims.verified.runs.length;
  return (
    <>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[var(--line)] pt-2">
        <div>
          <p className="micro">Documented</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[var(--text-2)]">
            {supported.matrix_entry_found ? (
              <>
                <Check size={11} className="text-[var(--go)]" /> Yes
              </>
            ) : (
              <>
                <Minus size={11} className="text-[var(--faint)]" /> No
              </>
            )}
          </p>
        </div>
        <div>
          <p className="micro">Tested</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[var(--text-2)]">
            {tested > 0 ? (
              <>
                <ShieldCheck size={11} className="text-[var(--go)]" /> {tested} run
                {tested === 1 ? "" : "s"}
              </>
            ) : (
              <>
                <Minus size={11} className="text-[var(--faint)]" /> none
              </>
            )}
          </p>
        </div>
        <div>
          <p className="micro">Matched by</p>
          <p className="mt-0.5 font-mono text-[9px] text-[var(--text-2)]">
            {supported.matched_by ?? "—"}
          </p>
        </div>
        <div>
          <p className="micro">Runs directly</p>
          <p className="mt-0.5 text-[10px] text-[var(--text-2)]">
            {supported.direct_runtime_available ? "Yes" : "No"}
          </p>
        </div>
      </div>
      {supported.custom_code_risk ? (
        <p className="mt-2 flex items-start gap-2 border-l-2 border-[var(--optimize)] bg-[var(--optimize-soft)] p-2 text-[10px] leading-relaxed text-[var(--text-2)]">
          <FileCode size={12} className="mt-0.5 flex-none text-[var(--optimize)]" />
          This model needs custom code. The support matrix does not cover that code.
        </p>
      ) : null}
      <SupportRuntimeList runtimes={supported.runtimes} />
      <p className="mt-2 font-mono text-[8.5px] leading-relaxed text-[var(--faint)]">
        Documented path, not a recorded run.
      </p>
    </>
  );
}

function VerifiedBody({ result }: { result: CheckResponse }) {
  const verified = result.claims.verified;
  if (verified.runs.length === 0) {
    return (
      <div className="mt-2 border-t border-[var(--line)] pt-2">
        <div className="flex items-start gap-2.5 border border-dashed border-[var(--line-strong)] bg-[var(--bg-elevated)] p-2.5">
          <Minus size={13} className="mt-0.5 flex-none text-[var(--faint)]" />
          <div>
            <p className="text-[11px] font-medium text-[var(--text-2)]">No recorded runs yet</p>
            <p className="mt-0.5 text-[10px] leading-relaxed text-[var(--muted)]">
              The model can be inspected, but no run has been recorded on this hardware.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ul className="mt-2 space-y-1.5 border-t border-[var(--line)] pt-2">
      {verified.runs.map((run) => (
        <li key={run.run_id} className="text-[10px] leading-relaxed text-[var(--text-2)]">
          <span className="font-mono text-[9px]">{run.runtime}</span> on{" "}
          {run.hardware_device_name} / {formatInteger(run.decode_tokens_per_second)} tok/s / peak{" "}
          {formatGB(run.peak_memory_bytes)}
        </li>
      ))}
    </ul>
  );
}

function ClaimRow({
  name,
  label,
  status,
  confidence,
  summary,
  children,
}: {
  name: string;
  label: string;
  status: "yes" | "no" | "unknown";
  confidence: "high" | "medium" | "low";
  summary: string;
  children: ReactNode;
}) {
  return (
    <div className="claim-row">
      <div>
        <h3 className="module-title">{name}</h3>
        <p className="mt-0.5 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)]">
          {label}
        </p>
      </div>
      <div>
        <StatusPill status={status} />
      </div>
      <div>
        <p className="text-[11px] leading-relaxed text-[var(--text-2)]">{summary}</p>
        {children}
      </div>
      <div>
        <ConfidenceMeter value={confidence} compact />
      </div>
    </div>
  );
}

export function ClaimsGrid({ result }: { result: CheckResponse }) {
  const { fits, supported, verified } = result.claims;
  return (
    <section aria-labelledby="claims-title">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="claims-title" className="module-title">
            Checks
          </h2>
          <p className="mt-1 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)]">
            Three separate checks
          </p>
        </div>
        <p className="max-w-sm text-right text-[10px] leading-relaxed text-[var(--muted)]">
          Memory, runtime, and recorded run.
        </p>
      </div>

      <div className="claims-table">
        <div className="claims-head">
          <span>Claim</span>
          <span>State</span>
          <span>Basis / reason</span>
          <span>Confidence</span>
        </div>

        <ClaimRow
          name="FITS"
          label="memory"
          status={fits.status}
          confidence={fits.confidence}
          summary={
            fits.status === "yes"
              ? "Fits within your memory budget."
              : fits.status === "no"
                ? "Does not fit within your memory budget."
                : "The memory estimate is inconclusive."
          }
        >
          <FitBody result={result} />
        </ClaimRow>

        <ClaimRow
          name="SUPPORTED"
          label="runtime"
          status={supported.status}
          confidence={supported.confidence}
          summary={
            supported.status === "yes"
              ? supported.direct_runtime_available
                ? "A direct runtime is documented."
                : "Only a conversion path is documented."
              : supported.status === "no"
                ? "No usable runtime path was found."
                : "Runtime support is not confirmed."
          }
        >
          <SupportedBody result={result} />
        </ClaimRow>

        <ClaimRow
          name="VERIFIED"
          label="real run"
          status={verified.status}
          confidence={verified.confidence}
          summary={
            verified.runs.length > 0
              ? "Recorded runs match this model."
              : "No recorded run yet."
          }
        >
          <VerifiedBody result={result} />
        </ClaimRow>
      </div>
    </section>
  );
}
