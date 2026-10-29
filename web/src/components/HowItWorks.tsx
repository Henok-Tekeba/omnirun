import { ArrowRight } from "./Icons";

const items = [
  {
    n: "01",
    title: "Metadata, not weights",
    body: "OmniRun reads repository metadata, config.json, safetensors headers, and GGUF metadata over HTTP range requests. It never downloads tensor payloads and never opens pickle files.",
  },
  {
    n: "02",
    title: "Three claims, kept separate",
    body: "FITS is about memory. SUPPORTED is a documented runtime path with a minimum version. VERIFIED would require a recorded real run. GO means FITS + a directly usable SUPPORTED path; it does not mean VERIFIED.",
  },
  {
    n: "03",
    title: "FITS is deliberately strict",
    body: "FITS is yes only when the worst-case peak fits the budget. It is no only when the best-case peak exceeds it. A range that straddles the budget is UNKNOWN, not “probably yes”.",
  },
  {
    n: "04",
    title: "One device only",
    body: "v1 is single-device: one GPU, one unified-memory chip, or CPU. Multi-GPU, tensor/pipeline parallelism, CPU+GPU offload, and distributed serving are out of scope.",
  },
  {
    n: "05",
    title: "Exact math is not padded",
    body: "When headers give exact weight bytes and the KV formula has no unresolved inputs, the range collapses to min = likely = max. Uncertainty lives in confidence and named assumptions, not invented spread.",
  },
  {
    n: "06",
    title: "Unknown is a valid answer",
    body: "ASR and TTS models currently return UNKNOWN: OmniRun can inspect them but cannot judge them yet. Architectures outside the support matrix, missing RAM, and unrecognized MoE layouts also stay UNKNOWN instead of becoming guesses.",
  },
  {
    n: "07",
    title: "Quantization alternatives are hypothetical",
    body: "FP16/INT8/4-bit alternatives are weights-only memory arithmetic. They do not claim an artifact exists, is supported, or has a particular quality. KV cache stays at checkpoint dtype in v1.",
  },
  {
    n: "08",
    title: "Estimates, not guarantees",
    body: "Decode speed is a range based on bandwidth, a documented efficiency range, and bytes read per token. Prefill and time-to-first-token are not estimated. Real runtimes, allocator behavior, and other apps can move the result.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-t border-[var(--line)]">
      <div className="container-wide py-14 md:py-20">
        <div className="grid gap-8 md:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="micro micro-accent">Method / limitations</p>
            <h2 className="display mt-3 text-[clamp(2.6rem,5vw,4.2rem)] leading-[0.95]">
              How it works,
              <br />
              and what it won’t do.
            </h2>
            <p className="mt-5 max-w-md text-[14px] leading-relaxed text-[var(--muted)]">
              This is a preflight, not a benchmark. Every number below is traceable to an
              input or a named assumption in the response. The full decisions live in{" "}
              <span className="font-mono text-[12px] text-[var(--text-2)]">ASSUMPTIONS.md</span>{" "}
              in the repository.
            </p>
            <div className="note-box note-box-accent mt-6">
              <strong className="text-[var(--text-2)]">Units.</strong> This UI labels memory
              as GB and defines 1 GB = 2³⁰ bytes (GiB). The API returns raw bytes; device
              capacities in <span className="font-mono text-[11px]">devices.yaml</span> are
              binary GiB. Bandwidth is decimal GB/s (10⁹ bytes/s), matching vendor specs.
            </div>
          </div>

          <div className="grid gap-x-10 sm:grid-cols-2">
            {items.map((item) => (
              <article key={item.n} className="how-card">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[10px] text-[var(--accent)]">{item.n}</span>
                  <h3 className="text-[15px] font-semibold leading-snug">{item.title}</h3>
                </div>
                <p className="mt-2 pl-7 text-[13px] leading-relaxed text-[var(--muted)]">
                  {item.body}
                </p>
              </article>
            ))}
          </div>
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-[var(--line)] pt-6">
          <p className="max-w-xl text-[12px] leading-relaxed text-[var(--faint)]">
            Open questions from the repo’s assumptions still apply: the Apple Silicon 75%
            usable-memory fraction, per-request-only HF tokens, and the v1 model-class scope.
          </p>
          <a href="#top" className="btn btn-secondary btn-sm">
            Back to top <ArrowRight size={13} />
          </a>
        </div>
      </div>
    </section>
  );
}
