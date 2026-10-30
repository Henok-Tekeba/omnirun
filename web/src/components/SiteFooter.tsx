import {
  ASSUMPTIONS_URL,
  ISSUES_URL,
  REPO_URL,
  SECURITY_URL,
  SITE_BASE,
} from "../lib/env";
import { openCookieSettings } from "../lib/consent";
import { ExternalLink, Spark } from "./Icons";

export function SiteFooter({ onStart }: { onStart?: () => void }) {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-brand">
          <a href={SITE_BASE} className="site-footer-logo" aria-label="OmniRun home">
            <Spark size={15} />
            <span>OmniRun</span>
          </a>
          <p>
            Model preflight without weight downloads. Estimates are ranges, not
            guarantees.
          </p>
        </div>

        <nav className="site-footer-column" aria-label="Product">
          <p className="site-footer-heading">Product</p>
          {onStart ? (
            <button type="button" onClick={onStart}>
              Preflight
            </button>
          ) : (
            <a href={SITE_BASE}>Preflight</a>
          )}
          <a href="?sample=1">Sample result</a>
          <a href={REPO_URL} target="_blank" rel="noreferrer">What OmniRun does</a>
          <a href={ASSUMPTIONS_URL} target="_blank" rel="noreferrer">
            Method &amp; assumptions
          </a>
        </nav>

        <nav className="site-footer-column" aria-label="Resources">
          <p className="site-footer-heading">Resources</p>
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub <ExternalLink size={9} />
          </a>
          <a href={ISSUES_URL} target="_blank" rel="noreferrer">
            Report an issue <ExternalLink size={9} />
          </a>
          <a href={SECURITY_URL} target="_blank" rel="noreferrer">
            Security <ExternalLink size={9} />
          </a>
        </nav>

        <nav className="site-footer-column" aria-label="Legal">
          <p className="site-footer-heading">Legal</p>
          <a href="?page=privacy">Privacy</a>
          <a href="?page=terms">Terms</a>
          <button type="button" onClick={openCookieSettings}>
            Cookie settings
          </button>
        </nav>
      </div>

      <div className="site-footer-bottom">
        <span>© 2026 OmniRun. Source on GitHub.</span>
        <span>Estimates are not guarantees. GO does not mean verified.</span>
      </div>
    </footer>
  );
}
