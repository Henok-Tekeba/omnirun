import { LogoMark } from "./Icons";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-[var(--line)]">
      <div className="container-wide grid gap-8 py-10 md:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5">
            <LogoMark size={22} className="text-[var(--accent)]" />
            <span className="text-[15px] font-semibold">OmniRun</span>
          </div>
          <p className="mt-3 max-w-md text-[13px] leading-relaxed text-[var(--muted)]">
            Estimates are not guarantees. OmniRun reads repository metadata and
            safetensors/GGUF headers, never tensor payloads. Results can be wrong when
            the model, runtime, or machine differs from the stated assumptions.
          </p>
        </div>
        <div>
          <p className="micro">Read</p>
          <ul className="mt-3 space-y-2 text-[13px] text-[var(--text-2)]">
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
          <ul className="mt-3 space-y-2 font-mono text-[11.5px] text-[var(--muted)]">
            <li>schema 1.0</li>
            <li>no weight downloads</li>
            <li>single device only</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-[var(--line)]">
        <div className="container-wide flex flex-col gap-2 py-4 text-[11px] text-[var(--faint)] sm:flex-row sm:items-center sm:justify-between">
          <p>Not affiliated with Hugging Face. No analytics in this build.</p>
          <p className="font-mono uppercase tracking-[0.08em]">
            estimates, not guarantees
          </p>
        </div>
      </div>
    </footer>
  );
}
