import type { ReactNode } from "react";
import { openCookieSettings } from "../lib/consent";
import { FileCode, Search, ShieldCheck, Spark } from "./Icons";

interface DashboardShellProps {
  children: ReactNode;
  active: "preflight" | "result" | "finder";
  title: string;
  subtitle: string;
  actions?: ReactNode;
  onLanding: () => void;
  onNewCheck: () => void;
  onFind: () => void;
}

export function DashboardShell({
  children,
  active,
  title,
  subtitle,
  actions,
  onLanding,
  onNewCheck,
  onFind,
}: DashboardShellProps) {
  return (
    <div className="dashboard-app">
      <a className="skip-link" href="#dashboard-content">
        Skip to content
      </a>
      <aside className="dashboard-sidebar">
        <button
          type="button"
          className="dashboard-brand"
          onClick={onLanding}
          title="Back to the landing page"
        >
          <Spark size={15} />
          <span>OmniRun</span>
        </button>

        <div className="dashboard-menu-label">Workspace</div>
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
            className={`dashboard-menu-item ${active === "finder" ? "is-active" : ""}`}
            onClick={onFind}
          >
            <Search size={13} /> Find models
          </button>
          <button
            type="button"
            className={`dashboard-menu-item ${active === "result" ? "is-active" : ""}`}
            onClick={() =>
              document.getElementById("verdict-word")?.scrollIntoView({ behavior: "smooth" })
            }
            disabled={active !== "result"}
          >
            <ShieldCheck size={13} /> Results
          </button>
        </nav>

      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="dashboard-topbar-left">
            <span className="dashboard-crumb">OmniRun / {title}</span>
            <h1 className="dashboard-title">{title}</h1>
            <p className="dashboard-subtitle">{subtitle}</p>
          </div>
          <div className="dashboard-topbar-actions">{actions}</div>
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
            className={active === "finder" ? "is-active" : ""}
            onClick={onFind}
          >
            Find models
          </button>
          <button
            type="button"
            className={active === "result" ? "is-active" : ""}
            onClick={() =>
              document.getElementById("verdict-word")?.scrollIntoView({ behavior: "smooth" })
            }
            disabled={active !== "result"}
          >
            Results
          </button>
        </nav>

        <main id="dashboard-content" className="dashboard-content">
          {children}
        </main>

        <footer className="dashboard-footer">
          <span>Estimates are not guarantees. GO does not mean verified.</span>
          <div className="dashboard-footer-links">
            <a href="?page=privacy">Privacy</a>
            <a href="?page=terms">Terms</a>
            <button type="button" onClick={openCookieSettings}>
              Cookies
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
