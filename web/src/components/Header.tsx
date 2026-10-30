import type { Theme } from "../lib/storage";
import { LogoMark, Moon, Sun } from "./Icons";

interface HeaderProps {
  theme: Theme;
  onToggleTheme: () => void;
  isResult: boolean;
}

export function Header({ theme, onToggleTheme, isResult }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-[var(--bg)]">
      <div className="container-wide flex h-[54px] items-center justify-between gap-4">
        <a
          href="/"
          className="flex items-center gap-2.5 text-[var(--text)] no-underline"
          aria-label="OmniRun home"
        >
          <LogoMark size={22} className="text-[var(--accent)]" />
          <span className="font-display text-[17px] font-bold uppercase tracking-[0.02em]">
            OmniRun
          </span>
          <span className="hidden font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--faint)] sm:inline">
            Model preflight
          </span>
        </a>

        <nav className="flex items-center gap-2" aria-label="Main">
          <span className="hidden items-center gap-1.5 border border-[var(--line)] px-2 py-1 font-mono text-[8.5px] uppercase tracking-[0.1em] text-[var(--faint)] md:flex">
            <span className="led" />
            local console
          </span>
          <a
            href={isResult ? "/#how-it-works" : "#how-it-works"}
            className="hidden font-mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)] underline-offset-4 hover:text-[var(--text)] hover:underline sm:inline"
          >
            Method
          </a>
          {isResult ? (
            <a href="/" className="btn btn-secondary btn-sm hidden sm:inline-flex">
              New check
            </a>
          ) : null}
          <button
            type="button"
            className="icon-button"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </nav>
      </div>
    </header>
  );
}
