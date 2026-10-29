import type { Theme } from "../lib/storage";
import { LogoMark, Moon, Sun } from "./Icons";

interface HeaderProps {
  theme: Theme;
  onToggleTheme: () => void;
  isResult: boolean;
}

export function Header({ theme, onToggleTheme, isResult }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--bg)_94%,transparent)] backdrop-blur-sm">
      <div className="container-wide flex h-[62px] items-center justify-between gap-4">
        <a
          href="/"
          className="flex items-center gap-2.5 text-[var(--text)] no-underline"
          aria-label="OmniRun home"
        >
          <LogoMark size={25} className="text-[var(--accent)]" />
          <span className="text-[17px] font-semibold tracking-[-0.01em]">OmniRun</span>
          <span className="badge hidden sm:inline-flex">v1</span>
        </a>

        <nav className="flex items-center gap-1.5" aria-label="Main">
          <a
            href={isResult ? "/#how-it-works" : "#how-it-works"}
            className="btn btn-ghost hidden min-h-9 px-2.5 text-[12px] sm:inline-flex"
          >
            How it works
          </a>
          {isResult ? (
            <a href="/" className="btn btn-secondary btn-sm hidden sm:inline-flex">
              New preflight
            </a>
          ) : null}
          <button
            type="button"
            className="icon-button"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </nav>
      </div>
    </header>
  );
}
