import { CheckCircle, FileCode, Gauge, ShieldCheck } from "./Icons";

export function LandingHero() {
  return (
    <section className="border-b border-[var(--line)]" aria-labelledby="landing-title">
      <div className="container-wide grid gap-8 py-10 md:py-14 lg:grid-cols-[1.45fr_1fr] lg:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
            <p className="micro">Hugging Face preflight · v1</p>
          </div>
          <h1
            id="landing-title"
            className="display mt-4 text-[clamp(4.2rem,11vw,8.6rem)] leading-[0.78] tracking-[-0.045em]"
          >
            Will it
            <br />
            <span className="italic text-[var(--accent)]">run?</span>
          </h1>
          <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-[var(--text-2)]">
            Paste a Hugging Face model. OmniRun reads repository metadata and weight
            headers — never tensor payloads — and estimates memory fit and decode speed on
            your hardware.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="badge">
              <FileCode size={11} /> metadata only
            </span>
            <span className="badge">
              <Gauge size={11} /> ranges, not point guesses
            </span>
            <span className="badge">
              <ShieldCheck size={11} /> verified stays separate
            </span>
          </div>
        </div>

        <aside className="panel-flat p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="micro">Specimen sheet</p>
            <span className="font-mono text-[9.5px] text-[var(--faint)]">v1 / schema 1.0</span>
          </div>
          <dl className="mt-3 border-t border-[var(--line)]">
            <div className="border-b border-[var(--line)] py-3">
              <dt className="micro">Reads</dt>
              <dd className="mt-1 text-[12px] leading-relaxed text-[var(--text-2)]">
                repo metadata · config.json · safetensors headers · GGUF metadata
              </dd>
            </div>
            <div className="border-b border-[var(--line)] py-3">
              <dt className="micro">Never reads</dt>
              <dd className="mt-1 text-[12px] leading-relaxed text-[var(--text-2)]">
                tensor payloads · pickle files · full weight files
              </dd>
            </div>
            <div className="py-3">
              <dt className="micro">Claims</dt>
              <dd className="mt-2 space-y-1.5">
                <span className="flex items-center gap-2 text-[12px] text-[var(--text-2)]">
                  <CheckCircle size={13} className="text-[var(--go)]" /> FITS — memory
                </span>
                <span className="flex items-center gap-2 text-[12px] text-[var(--text-2)]">
                  <ShieldCheck size={13} className="text-[var(--accent)]" /> SUPPORTED —
                  documented runtime path
                </span>
                <span className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
                  <span className="flex h-[13px] w-[13px] items-center justify-center rounded-full border border-[var(--line-strong)] font-mono text-[8px]">
                    ?
                  </span>
                  VERIFIED — no recorded runs yet
                </span>
              </dd>
            </div>
          </dl>
          <p className="mt-2 border-t border-[var(--line)] pt-3 text-[10.5px] leading-relaxed text-[var(--faint)]">
            A preflight, not a benchmark. Unknown is a valid answer.
          </p>
        </aside>
      </div>
    </section>
  );
}
