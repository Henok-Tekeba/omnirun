import { useEffect, useState } from "react";
import {
  API_DOCS_URL,
  IS_STATIC_PREVIEW,
  METHODOLOGY_URL,
  REPO_URL,
  SITE_BASE,
} from "../lib/env";
import {
  ArrowRight,
  CheckCircle,
  Cpu,
  FileCode,
  Gauge,
  HelpCircle,
  Layers,
  Menu,
  Search,
  ShieldCheck,
  Sliders,
  Spark,
  X,
} from "./Icons";
import { SiteFooter } from "./SiteFooter";

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

const SIDE_ASCII = String.raw`  ╭──────────────╮
  │ 01 10 11 00  │
  │ 10 01 00 11  │
  │ 11 00 01 10  │
  │ 00 11 10 01  │
  ╰──────────────╯
     ▲    ▲    ▲
    ╱ ╲  ╱ ╲  ╱ ╲
   ▔▔▔▔▔▔▔▔▔▔▔▔▔
   SIGNAL / 0.93
   MEMORY / 200 GB/s
   PROMPT / —`;

export function MarketingLanding({ onStart }: MarketingLandingProps) {
  const [dialog, setDialog] = useState<DialogKind | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const apiHref = IS_STATIC_PREVIEW ? `${REPO_URL}#api-contract` : API_DOCS_URL;

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

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const openDialog = (kind: DialogKind) => {
    setMobileOpen(false);
    setDialog(kind);
  };

  const start = () => {
    setMobileOpen(false);
    onStart();
  };

  return (
    <div className="marketing">
      <a className="skip-link" href="#marketing-hero">
        Skip to content
      </a>
      <div className="marketing-shell">
        <div className="marketing-left">
          <header className="marketing-nav">
            <a href={SITE_BASE} className="marketing-logo" aria-label="OmniRun home">
              <Spark size={17} />
              <span>OmniRun</span>
            </a>
            <nav className="marketing-links" aria-label="Main">
              <button type="button" onClick={start}>
                Preflight
              </button>
              <button type="button" onClick={() => openDialog("claims")}>
                Checks
              </button>
              <button type="button" onClick={start}>
                Hardware
              </button>
              <button type="button" onClick={() => openDialog("method")}>
                Method
              </button>
              <a href={apiHref} target="_blank" rel="noreferrer">
                API
              </a>
            </nav>
            <button
              type="button"
              className="marketing-menu-toggle"
              aria-expanded={mobileOpen}
              aria-controls="marketing-mobile-menu"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              onClick={() => setMobileOpen((open) => !open)}
            >
              {mobileOpen ? <X size={17} /> : <Menu size={17} />}
            </button>
            <button type="button" className="marketing-login" onClick={start}>
              Open app
            </button>
            {mobileOpen ? (
              <div
                id="marketing-mobile-menu"
                className="marketing-mobile-menu"
                role="navigation"
                aria-label="Mobile"
              >
                <button type="button" onClick={start}>
                  Preflight
                </button>
                <button type="button" onClick={() => openDialog("claims")}>
                  Checks
                </button>
                <button type="button" onClick={start}>
                  Hardware
                </button>
                <button type="button" onClick={() => openDialog("method")}>
                  Method
                </button>
                <a href={apiHref} target="_blank" rel="noreferrer">
                  API
                </a>
                <a href="?page=privacy">Privacy</a>
                <a href="?page=terms">Terms</a>
              </div>
            ) : null}
          </header>

          <main id="marketing-hero" className="marketing-hero" tabIndex={-1}>
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
              <button type="button" className="marketing-primary" onClick={start}>
                Run a preflight
                <ArrowRight size={14} />
              </button>
              <button
                type="button"
                className="marketing-secondary"
                onClick={() => openDialog("method")}
              >
                See how it works
              </button>
            </div>
          </main>
        </div>

        <div
          className="marketing-visual"
          role="img"
          aria-label="OmniRun console preview"
        >
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
                  <ShieldCheck size={12} /> Checks
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
                  <span className="mock-dot" /> Weights stay remote
                </div>
                <p>Metadata and headers only. Unknown stays unknown.</p>
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

              <div className="mock-greeting">Preflight console</div>
              <p className="mock-sub">
                Memory, runtime, and speed estimates.
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
                  <span>Preflight signal</span>
                  <span className="mock-live">
                    <span className="mock-dot" /> live
                  </span>
                </div>
                <div className="mock-ascii-body">
                  <pre>{ASCII}</pre>
                  <pre className="mock-ascii-side">{SIDE_ASCII}</pre>
                </div>
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
                <div className="mock-row">
                  <span>Qwen2.5-0.5B</span>
                  <span className="mock-verdict">GO</span>
                  <span>0.71 GB</span>
                  <span>180–290</span>
                </div>
                <div className="mock-row">
                  <span>Llama-3.2-1B</span>
                  <span className="mock-verdict is-unknown">GATED</span>
                  <span>—</span>
                  <span>—</span>
                </div>
              </div>

              <div className="mock-bottom">
                <div>
                  <span>FITS</span>
                  <strong className="is-go">YES</strong>
                </div>
                <div>
                  <span>SUPPORTED</span>
                  <strong className="is-go">YES</strong>
                </div>
                <div>
                  <span>VERIFIED</span>
                  <strong>NONE</strong>
                </div>
              </div>

              <div className="mock-runtime">
                <div className="mock-subhead">
                  Runtime paths <span>v1</span>
                </div>
                <div className="mock-runtime-row">
                  <span>transformers</span>
                  <span className="mock-verdict">available</span>
                  <span>≥ 4.28</span>
                </div>
                <div className="mock-runtime-row">
                  <span>llama.cpp</span>
                  <span className="mock-verdict is-opt">conversion</span>
                  <span>≥ b1500</span>
                </div>
                <div className="mock-runtime-row">
                  <span>whisper.cpp</span>
                  <span className="mock-verdict is-unknown">missing</span>
                  <span>≥ 1.5</span>
                </div>
              </div>

              <div className="mock-notes">
                <div className="mock-subhead">Methodology</div>
                <p>Single device / metadata only / estimates are not guarantees.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <SiteFooter onStart={onStart} />

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
                <div className="marketing-dialog-kicker">Checks / kept separate</div>
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
                    <strong>One device at a time.</strong> Multi-GPU, offload, and distributed
                    serving are out of scope.
                  </p>
                  <p>
                    <strong>Ranges are real.</strong> Exact data stays exact. Uncertainty is
                    shown separately instead of being invented.
                  </p>
                  <p>
                    <strong>Unknown is reported.</strong> Speech models, unsupported
                    architectures, missing RAM, and unusual model layouts stay UNKNOWN
                    instead of becoming guesses.
                  </p>
                  <p>
                    <strong>Estimates are not guarantees.</strong> Speed is a range, not a
                    benchmark. Prompt processing and first-token time are not estimated.
                  </p>
                </div>
              </>
            )}

            <div className="marketing-dialog-footer">
              <span>
                Methodology:{" "}
                <a href={METHODOLOGY_URL} target="_blank" rel="noreferrer">
                  docs/methodology.md
                </a>
                .
              </span>
              <button type="button" className="marketing-primary" onClick={start}>
                Open preflight
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
