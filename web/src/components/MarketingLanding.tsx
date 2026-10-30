import { useEffect, useState } from "react";
import {
  ArrowRight,
  CheckCircle,
  Cpu,
  FileCode,
  Gauge,
  HelpCircle,
  Layers,
  Search,
  ShieldCheck,
  Sliders,
  Spark,
  X,
} from "./Icons";

interface MarketingLandingProps {
  onStart: () => void;
}

type DialogKind = "claims" | "method";

const ASCII = String.raw`  ╭────────────────────────────────╮
  │  FITS        ████████████░░  97% │
  │  SUPPORTED   ██████████░░░  YES │
  │  VERIFIED    ░░░░░░░░░░░░  NONE │
  ╰────────────────────────────────╯
       ╭─╮       ╭─╮       ╭─╮
   ────┤ ├───────┤ ├───────┤ ├────
       ╰─╯       ╰─╯       ╰─╯
  > inspect smollm2-135m
  > weights  0.25 GB / exact
  > kv cache 0.09 GB / modeled
  > peak     0.60–0.64 GB
  > decode   302.7–467.8 tok/s
  > verdict  GO
  > _`;

export function MarketingLanding({ onStart }: MarketingLandingProps) {
  const [dialog, setDialog] = useState<DialogKind | null>(null);

  useEffect(() => {
    if (!dialog) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDialog(null);
    };
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [dialog]);

  return (
    <div className="marketing">
      <div className="marketing-shell">
        <div className="marketing-left">
          <header className="marketing-nav">
            <a href="/" className="marketing-logo" aria-label="OmniRun home">
              <Spark size={17} />
              <span>OmniRun</span>
            </a>
            <nav className="marketing-links" aria-label="Main">
              <button type="button" onClick={onStart}>
                Preflight
              </button>
              <button type="button" onClick={() => setDialog("claims")}>
                Claims
              </button>
              <button type="button" onClick={onStart}>
                Hardware
              </button>
              <button type="button" onClick={() => setDialog("method")}>
                Method
              </button>
              <a href="/api/docs" target="_blank" rel="noreferrer">
                API
              </a>
            </nav>
            <button type="button" className="marketing-login" onClick={onStart}>
              Console
            </button>
          </header>

          <div className="marketing-hero">
            <div className="marketing-pill">
              <Spark size={11} />
              Metadata-only model preflight
            </div>

            <h1 className="marketing-title">
              <span className="block text-[#0b0b0b]">The preflight layer</span>
              <span className="block text-[#8d8d8d]">
                For local AI
                <br />
                models.
              </span>
            </h1>

            <p className="marketing-copy">
              Paste a Hugging Face model. OmniRun estimates memory fit and decode speed —
              without downloading weights.
            </p>

            <div className="marketing-actions">
              <button type="button" className="marketing-primary" onClick={onStart}>
                Run a preflight
                <ArrowRight size={14} />
              </button>
              <button
                type="button"
                className="marketing-secondary"
                onClick={() => setDialog("method")}
              >
                See how it works
              </button>
            </div>
          </div>
        </div>

        <div className="marketing-visual" aria-label="OmniRun console preview">
          <div className="marketing-aurora" aria-hidden="true" />
          <div className="marketing-noise" aria-hidden="true" />
          <div className="marketing-ascii-bg" aria-hidden="true">
            <span>01001111 01001101 01001110 01001001</span>
            <span>MEMORY / BANDWIDTH / CLAIMS</span>
            <span>01100110 01101001 01110100 01110011</span>
          </div>

          <div className="mock-dashboard">
            <aside className="mock-sidebar">
              <div className="mock-brand">
                <Spark size={13} />
                <span>OmniRun</span>
              </div>
              <div className="mock-menu-label">Menu</div>
              <div className="mock-menu">
                <div className="mock-menu-item is-active">
                  <Gauge size={12} /> Overview
                </div>
                <div className="mock-menu-item">
                  <FileCode size={12} /> Preflight
                </div>
                <div className="mock-menu-item">
                  <ShieldCheck size={12} /> Claims
                </div>
                <div className="mock-menu-item">
                  <Cpu size={12} /> Hardware
                </div>
                <div className="mock-menu-item">
                  <Layers size={12} /> Memory
                </div>
              </div>
              <div className="mock-menu-label">General</div>
              <div className="mock-menu">
                <div className="mock-menu-item">
                  <Sliders size={12} /> Settings
                </div>
                <div className="mock-menu-item">
                  <HelpCircle size={12} /> Support
                </div>
              </div>
              <div className="mock-note">
                <div className="mock-note-title">
                  <span className="mock-dot" /> No weight downloads
                </div>
                <p>Metadata and headers only. Unknown is a valid answer.</p>
                <div className="mock-note-bar">
                  <span />
                </div>
              </div>
            </aside>

            <div className="mock-main">
              <div className="mock-topline">
                <span>Overview</span>
                <span>Preflight console / v1.0</span>
              </div>

              <div className="mock-greeting">Good evening, operator.</div>
              <p className="mock-sub">
                One model. One machine. One honest answer.
              </p>

              <div className="mock-stats">
                <div className="mock-stat">
                  <span className="mock-stat-label">Memory budget</span>
                  <strong>24.0 GB</strong>
                  <span className="mock-stat-foot">
                    <span className="mock-up">usable</span> 75% of 32 GB
                  </span>
                </div>
                <div className="mock-stat">
                  <span className="mock-stat-label">Peak range</span>
                  <strong>0.60–0.64 GB</strong>
                  <span className="mock-stat-foot">estimate / medium confidence</span>
                </div>
              </div>

              <div className="mock-chart">
                <div className="mock-chart-head">
                  <span>Memory by component</span>
                  <span>GB</span>
                </div>
                <div className="mock-bars" aria-hidden="true">
                  {[32, 48, 38, 62, 54, 76, 42, 58, 34, 66, 46, 72].map((height, index) => (
                    <span
                      key={index}
                      className={index === 5 ? "is-peak" : ""}
                      style={{ height: `${height}%` }}
                    />
                  ))}
                </div>
                <div className="mock-axis">
                  <span>weights</span>
                  <span>kv</span>
                  <span>overhead</span>
                  <span>peak</span>
                </div>
              </div>

              <div className="mock-ascii">
                <div className="mock-ascii-head">
                  <span>ASCII neural field</span>
                  <span className="mock-live">
                    <span className="mock-dot" /> live
                  </span>
                </div>
                <pre>{ASCII}</pre>
              </div>

              <div className="mock-table">
                <div className="mock-table-head">
                  <span>Recent checks</span>
                  <span className="mock-search">
                    <Search size={9} /> search
                  </span>
                </div>
                <div className="mock-row mock-row-head">
                  <span>Model</span>
                  <span>Verdict</span>
                  <span>Peak</span>
                  <span>Speed</span>
                </div>
                <div className="mock-row">
                  <span>SmolLM2-135M</span>
                  <span className="mock-verdict">GO</span>
                  <span>0.64 GB</span>
                  <span>302–467</span>
                </div>
                <div className="mock-row">
                  <span>Mistral-7B</span>
                  <span className="mock-verdict is-opt">OPT</span>
                  <span>14.8 GB</span>
                  <span>21–36</span>
                </div>
                <div className="mock-row">
                  <span>whisper-tiny</span>
                  <span className="mock-verdict is-unknown">?</span>
                  <span>0.42 GB</span>
                  <span>—</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {dialog ? (
        <div
          className="marketing-modal"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setDialog(null);
          }}
        >
          <div
            className="marketing-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="marketing-dialog-title"
          >
            <button
              type="button"
              className="marketing-dialog-close"
              onClick={() => setDialog(null)}
              aria-label="Close dialog"
            >
              <X size={16} />
            </button>

            {dialog === "claims" ? (
              <>
                <div className="marketing-dialog-kicker">Claims / kept separate</div>
                <h2 id="marketing-dialog-title" className="marketing-dialog-title">
                  Three questions. No conflation.
                </h2>
                <div className="marketing-claim-list">
                  <div>
                    <CheckCircle size={16} />
                    <div>
                      <h3>FITS</h3>
                      <p>
                        Memory only. Yes requires the worst-case peak to fit. A range that
                        straddles the budget is UNKNOWN, not “probably yes”.
                      </p>
                    </div>
                  </div>
                  <div>
                    <ShieldCheck size={16} />
                    <div>
                      <h3>SUPPORTED</h3>
                      <p>
                        A documented runtime path with a minimum version. It is not a real
                        run and does not imply VERIFIED.
                      </p>
                    </div>
                  </div>
                  <div>
                    <HelpCircle size={16} />
                    <div>
                      <h3>VERIFIED</h3>
                      <p>
                        A recorded real run on matching hardware. v1 ships empty, so this
                        claim is UNKNOWN for every model.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="marketing-dialog-kicker">Method / limitations</div>
                <h2 id="marketing-dialog-title" className="marketing-dialog-title">
                  A preflight, not a benchmark.
                </h2>
                <div className="marketing-method-list">
                  <p>
                    <strong>Metadata only.</strong> OmniRun reads repository metadata,
                    config.json, safetensors headers, and GGUF metadata over range requests.
                    It never downloads tensor payloads and never opens pickle files.
                  </p>
                  <p>
                    <strong>One device.</strong> v1 is single-device: one GPU, one unified
                    chip, or CPU. Multi-GPU, offload, and distributed serving are out of
                    scope.
                  </p>
                  <p>
                    <strong>Ranges are real.</strong> Exact header math collapses to
                    min = likely = max. Uncertainty lives in confidence, named assumptions,
                    and the parts that genuinely vary.
                  </p>
                  <p>
                    <strong>Unknown is valid.</strong> ASR/TTS models, unsupported
                    architectures, missing RAM, and unrecognized MoE layouts stay UNKNOWN
                    instead of becoming guesses.
                  </p>
                  <p>
                    <strong>Estimates are not guarantees.</strong> Decode speed is a range
                    based on bandwidth, a documented efficiency range, and bytes read per
                    token. Prefill and TTFT are not estimated.
                  </p>
                </div>
              </>
            )}

            <div className="marketing-dialog-footer">
              <span>Source: ASSUMPTIONS.md in the repository.</span>
              <button type="button" className="marketing-primary" onClick={onStart}>
                Open console
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
