import { LogoMark } from "./Icons";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--line)]">
      <div className="container-wide grid gap-7 py-8 md:grid-cols-[1.6fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5">
            <LogoMark size={20} className="text-[var(--accent)]" />
            <span className="font-display text-[14px] font-bold uppercase tracking-[0.02em]">
              OmniRun
            </span>
            <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-[var(--faint)]">
              v1 / preflight console
            </span>
          </div>
          <p className="mt-3 max-w-md text-[11px] leading-relaxed text-[var(--muted)]">
            Estimates are not guarantees. OmniRun reads repository metadata and
            safetensors/GGUF headers, never tensor payloads. Results can be wrong when the
            model, runtime, or machine differs from the stated assumptions.
          </p>
        </div>
        <div>
          <p className="micro">Reference</p>
          <ul className="mt-2 space-y-1.5 text-[11px] text-[var(--text-2)]">
            <li>
              <a className="subtle-link" href="/#how-it-works">
                How it works / limitations
              </a>
            </li>
            <li>
              <a
                className="subtle-link"
                href="https://huggingface.co"
                target="_blank"
                rel="noreferrer"
              >
                Hugging Face
              </a>
            </li>
          </ul>
        </div>
        <div>
          <p className="micro">Contract</p>
          <ul className="mt-2 space-y-1.5 font-mono text-[9px] uppercase tracking-[0.06em] text-[var(--muted)]">
            <li>schema 1.0</li>
            <li>no weight downloads</li>
            <li>single device only</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-[var(--line)]">
        <div className="container-wide flex flex-col gap-1.5 py-3 font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)] sm:flex-row sm:items-center sm:justify-between">
          <p>Not affiliated with Hugging Face / no analytics in this build</p>
          <p className="flex items-center gap-1.5">
            <span className="led" /> estimates, not guarantees
          </p>
        </div>
      </div>
    </footer>
  );
}
