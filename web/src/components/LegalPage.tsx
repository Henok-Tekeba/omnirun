import { useEffect } from "react";
import { REPO_URL, SITE_BASE, SITE_URL } from "../lib/env";
import { openCookieSettings } from "../lib/consent";
import { Spark } from "./Icons";
import { SiteFooter } from "./SiteFooter";

type LegalPageKind = "privacy" | "terms";

const TITLES: Record<LegalPageKind, string> = {
  privacy: "Privacy policy",
  terms: "Terms & conditions",
};

function LegalHeader({ page }: { page: LegalPageKind }) {
  return (
    <header className="legal-header">
      <a href={SITE_BASE} className="legal-logo" aria-label="OmniRun home">
        <Spark size={16} />
        <span>OmniRun</span>
      </a>
      <nav className="legal-nav" aria-label="Legal pages">
        <a href={SITE_BASE}>Preflight</a>
        <a href="?page=privacy" aria-current={page === "privacy" ? "page" : undefined}>
          Privacy
        </a>
        <a href="?page=terms" aria-current={page === "terms" ? "page" : undefined}>
          Terms
        </a>
        <a href={REPO_URL} target="_blank" rel="noreferrer">
          GitHub
        </a>
      </nav>
    </header>
  );
}

function PrivacyPolicy() {
  return (
    <>
      <div className="legal-kicker">Legal / Privacy</div>
      <h1>Privacy policy</h1>
      <p className="legal-updated">Last updated: October 30, 2026</p>
      <p className="legal-lede">
        OmniRun is a metadata-only model preflight tool. This page explains what the
        website and API process, what stays in your browser, and what we do not collect.
      </p>

      <section id="overview">
        <h2>1. Overview</h2>
        <p>
          OmniRun does not have accounts, profiles, analytics, advertising, or tracking
          cookies. The public website is a static interface. The optional API reads
          public model metadata from Hugging Face and returns an estimate.
        </p>
        <p>
          This policy covers the OmniRun website and API. Hugging Face and GitHub are
          separate services with their own privacy policies.
        </p>
      </section>

      <section id="data">
        <h2>2. What we process</h2>
        <p>When you run a preflight, the API may receive:</p>
        <ul>
          <li>The model reference you enter (for example, a Hugging Face repo id).</li>
          <li>Your hardware selection, context length, and batch size.</li>
          <li>
            An optional Hugging Face token, only if you provide one for a gated or
            private model.
          </li>
          <li>Your IP address for a short-lived, in-memory rate-limit counter.</li>
        </ul>
        <p>
          The API reads repository metadata, configuration files, safetensors headers,
          and GGUF headers. It does not download model weights.
        </p>
        <p>
          If you provide a token, it is sent with the request and, where needed, to
          Hugging Face. OmniRun does not store the token in the browser, in local
          storage, or in a share link. The API does not log request bodies.
        </p>
      </section>

      <section id="cookies">
        <h2>3. Cookies and local storage</h2>
        <p>
          OmniRun does not set advertising or analytics cookies. The site uses browser
          local storage for two essential preferences:
        </p>
        <ul>
          <li>
            <code>omnirun.hardware</code> — remembers the hardware choice you selected.
          </li>
          <li>
            <code>omnirun.cookie-consent</code> — remembers your cookie notice choice.
          </li>
        </ul>
        <p>
          The model id and Hugging Face token are not saved. You can clear these values
          in your browser settings at any time. The cookie notice lets you accept or
          keep essential storage only; because no non-essential cookies are used, both
          choices have the same practical effect today.
        </p>
        <p>
          <button type="button" className="legal-inline-button" onClick={openCookieSettings}>
            Open cookie settings
          </button>
        </p>
      </section>

      <section id="third-parties">
        <h2>4. Third parties</h2>
        <p>
          <strong>Hugging Face.</strong> Model metadata requests go to{" "}
          <a href="https://huggingface.co/privacy" target="_blank" rel="noreferrer">
            Hugging Face
          </a>
          . If you submit a gated model, Hugging Face may require a token and may log the
          request under its own policies.
        </p>
        <p>
          <strong>GitHub Pages.</strong> The public frontend is hosted by GitHub Pages.
          GitHub may collect standard request logs such as IP address and user agent
          when serving the site. See{" "}
          <a
            href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"
            target="_blank"
            rel="noreferrer"
          >
            GitHub’s privacy statement
          </a>
          .
        </p>
        <p>
          <strong>API hosting.</strong> If you use a hosted OmniRun API, that provider
          processes the request data described above. The local development API runs on
          your machine.
        </p>
        <p>OmniRun does not sell personal information.</p>
      </section>

      <section id="retention">
        <h2>5. Retention</h2>
        <p>
          OmniRun does not create user accounts or store preflight results on a server.
          The API keeps a short-lived in-memory rate-limit counter and may cache public
          Hugging Face metadata to avoid repeat requests. Browser preferences remain in
          local storage until you clear them.
        </p>
      </section>

      <section id="security">
        <h2>6. Security</h2>
        <p>
          The hosted site uses HTTPS. Tokens are not persisted by the frontend. No
          service can promise absolute security; use a scoped, revocable token and do
          not submit credentials you do not want processed by Hugging Face.
        </p>
      </section>

      <section id="choices">
        <h2>7. Your choices</h2>
        <ul>
          <li>Clear local storage to remove the saved hardware and cookie choice.</li>
          <li>Use the cookie notice to review or change your choice.</li>
          <li>Do not provide a Hugging Face token unless you need a gated model.</li>
          <li>Use the local API if you do not want a hosted API to process a request.</li>
        </ul>
      </section>

      <section id="children">
        <h2>8. Children</h2>
        <p>
          OmniRun is a developer tool and is not directed to children. We do not
          knowingly collect personal information from children.
        </p>
      </section>

      <section id="changes">
        <h2>9. Changes and contact</h2>
        <p>
          This policy may change as the project changes. The date at the top shows the
          current version. Questions or corrections can be raised in the public issue
          tracker.
        </p>
        <p>
          <a href={`${REPO_URL}/issues`} target="_blank" rel="noreferrer">
            Open an issue on GitHub
          </a>
        </p>
      </section>
    </>
  );
}

function Terms() {
  return (
    <>
      <div className="legal-kicker">Legal / Terms</div>
      <h1>Terms &amp; conditions</h1>
      <p className="legal-updated">Last updated: October 30, 2026</p>
      <p className="legal-lede">
        These terms govern your use of the OmniRun website and API. By using the
        service, you agree to them. If you do not agree, do not use the service.
      </p>

      <section id="service">
        <h2>1. What OmniRun does</h2>
        <p>
          OmniRun estimates memory fit and decode-speed ranges for machine-learning
          models from repository metadata. It reports FITS, SUPPORTED, and VERIFIED as
          separate claims. It does not download model weights and does not run a model.
        </p>
        <p>
          A GO result means the estimated worst-case peak fits and a directly usable
          runtime path is documented. It is not a benchmark, a guarantee, or a
          verification. VERIFIED is empty in v1.
        </p>
      </section>

      <section id="estimates">
        <h2>2. Estimates and no warranty</h2>
        <p>
          Estimates can be wrong. Model files, runtime versions, drivers, quantization,
          KV-cache behavior, and your machine may differ from the assumptions. You are
          responsible for testing a model before relying on it.
        </p>
        <p>
          The service is provided “as is” and “as available”, without warranties of any
          kind, express or implied, including fitness for a particular purpose and
          non-infringement, to the maximum extent permitted by law.
        </p>
      </section>

      <section id="responsibilities">
        <h2>3. Your responsibilities</h2>
        <ul>
          <li>Use the service lawfully and do not abuse the API or Hugging Face.</li>
          <li>
            Only submit models, tokens, and hardware details you are allowed to use.
          </li>
          <li>
            Respect the licenses and acceptable-use terms of every model and runtime
            you evaluate.
          </li>
          <li>Do not attempt to disrupt, overload, or reverse-engineer the service.</li>
        </ul>
      </section>

      <section id="third-party">
        <h2>4. Third-party models and services</h2>
        <p>
          OmniRun does not endorse or control models, runtimes, or data hosted by Hugging
          Face or other third parties. Their licenses and terms apply. A model appearing
          in a search result is not a quality recommendation.
        </p>
      </section>

      <section id="availability">
        <h2>5. Availability and changes</h2>
        <p>
          The service may be changed, suspended, or discontinued at any time. The static
          GitHub Pages preview may not have a live API. We do not promise uptime or
          preservation of any result.
        </p>
      </section>

      <section id="liability">
        <h2>6. Limitation of liability</h2>
        <p>
          To the maximum extent permitted by law, OmniRun and its contributors are not
          liable for indirect, incidental, special, consequential, or punitive damages,
          or for lost data, profits, or business opportunities, arising from your use of
          the service. Nothing in these terms limits rights that cannot be limited by
          law.
        </p>
      </section>

      <section id="law">
        <h2>7. Governing law</h2>
        <p>
          These terms are governed by the laws applicable to the operator of OmniRun,
          without regard to conflict-of-law rules. Nothing in these terms removes
          mandatory protections you have under the law of your own country.
        </p>
      </section>

      <section id="general">
        <h2>8. General</h2>
        <p>
          If any provision is unenforceable, the remaining provisions remain in effect.
          These terms do not create a partnership, employment, or agency relationship.
          OmniRun is a software project, not a law firm; these terms are not legal advice.
        </p>
      </section>

      <section id="contact">
        <h2>9. Contact</h2>
        <p>
          Questions about these terms can be raised in the public issue tracker.
        </p>
        <p>
          <a href={`${REPO_URL}/issues`} target="_blank" rel="noreferrer">
            Open an issue on GitHub
          </a>
        </p>
      </section>
    </>
  );
}

export function LegalPage({ page }: { page: LegalPageKind }) {
  useEffect(() => {
    document.title = `${TITLES[page]} — OmniRun`;
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.setAttribute("href", `${SITE_URL}?page=${page}`);
    const description = document.querySelector('meta[name="description"]');
    if (description) {
      description.setAttribute(
        "content",
        page === "privacy"
          ? "OmniRun privacy policy: what the metadata-only preflight processes, what stays in your browser, and which third parties are involved."
          : "OmniRun terms and conditions for the metadata-only model preflight service.",
      );
    }
    window.scrollTo(0, 0);
  }, [page]);

  return (
    <div className="legal-page">
      <a className="skip-link" href="#legal-main">
        Skip to content
      </a>
      <LegalHeader page={page} />
      <main id="legal-main" className="legal-main">
        <article className="legal-article">
          {page === "privacy" ? <PrivacyPolicy /> : <Terms />}
          <div className="legal-note">
            This page describes the current v1 implementation. It is not legal advice.
          </div>
        </article>
      </main>
      <SiteFooter />
    </div>
  );
}
