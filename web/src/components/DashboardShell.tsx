import type { ReactNode } from "react";
import {
  ArrowRight,
  ExternalLink,
  FileCode,
  Gauge,
  HelpCircle,
  ShieldCheck,
  Spark,
} from "./Icons";

interface DashboardShellProps {
  children: ReactNode;
  active: "preflight" | "result";
  title: string;
  subtitle: string;
  actions?: ReactNode;
  onLanding: () => void;
  onNewCheck: () => void;
}

export function DashboardShell({
  children,
  active,
  title,
  subtitle,
  actions,
  onLanding,
  onNewCheck,
}: DashboardShellProps) {
  return (
    <div className="dashboard-app">
      <a className="skip-link" href="#dashboard-content">
        Skip to content
      </a>
      <aside className="dashboard-sidebar">
        <button type="button" className="dashboard-brand" onClick={onLanding}>
          <Spark size={15} />
          <span>OmniRun</span>
        </button>

        <div className="dashboard-menu-label">Menu</div>
        <nav className="dashboard-menu" aria-label="App">
          <button
            type="button"
            className={`dashboard-menu-item ${active === "preflight" ? "is-active" : ""}`}
            onClick={onNewCheck}
          >
            <FileCode size={13} /> Preflight
          </button>
          <button
            type="button"
            className={`dashboard-menu-item ${active === "result" ? "is-active" : ""}`}
            onClick={() => document.getElementById("verdict-word")?.scrollIntoView({ behavior: "smooth" })}
            disabled={active !== "result"}
          >
            <ShieldCheck size={13} /> Results
          </button>
          <a className="dashboard-menu-item" href="/api/docs" target="_blank" rel="noreferrer">
            <Gauge size={13} /> API docs <ExternalLink size={9} className="ml-auto" />
          </a>
        </nav>

        <div className="dashboard-menu-label">General</div>
        <nav className="dashboard-menu" aria-label="General">
          <button type="button" className="dashboard-menu-item" onClick={onLanding}>
            <HelpCircle size={13} /> Landing page
          </button>
        </nav>

        <div className="dashboard-note">
          <div className="dashboard-note-title">
            <span className="dashboard-dot" /> No weight downloads
          </div>
          <p>Metadata and headers only. Unknown is a valid answer.</p>
          <div className="dashboard-note-bar">
            <span />
          </div>
        </div>
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="dashboard-topbar-left">
            <span className="dashboard-crumb">OmniRun / {title}</span>
            <h1 className="dashboard-title">{title}</h1>
            <p className="dashboard-subtitle">{subtitle}</p>
          </div>
          <div className="dashboard-topbar-actions">
            <span className="dashboard-local">
              <span className="dashboard-dot" /> local console
            </span>
            {actions}
            <button type="button" className="dashboard-btn dashboard-btn-secondary" onClick={onLanding}>
              Landing
            </button>
          </div>
        </header>

        <nav className="dashboard-mobile-nav" aria-label="App">
          <button
            type="button"
            className={active === "preflight" ? "is-active" : ""}
            onClick={onNewCheck}
          >
            Preflight
          </button>
          <button
            type="button"
            className={active === "result" ? "is-active" : ""}
            onClick={() => document.getElementById("verdict-word")?.scrollIntoView({ behavior: "smooth" })}
            disabled={active !== "result"}
          >
            Results
          </button>
          <button type="button" onClick={onLanding}>
            Landing
          </button>
        </nav>

        <main id="dashboard-content" className="dashboard-content">
          {children}
        </main>

        <footer className="dashboard-footer">
          <span>Estimates are not guarantees. GO does not mean VERIFIED.</span>
          <a href="/api/docs" target="_blank" rel="noreferrer" className="dashboard-footer-link">
            API schema 1.0 <ArrowRight size={10} />
          </a>
        </footer>
      </div>
    </div>
  );
}
