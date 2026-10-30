import { useEffect, useState } from "react";
import {
  COOKIE_SETTINGS_EVENT,
  readCookieChoice,
  saveCookieChoice,
  type CookieChoice,
} from "../lib/consent";

export function CookieConsent() {
  const [open, setOpen] = useState(() => readCookieChoice() === null);
  const [choice, setChoice] = useState<CookieChoice | null>(() => readCookieChoice());

  useEffect(() => {
    const openSettings = () => setOpen(true);
    window.addEventListener(COOKIE_SETTINGS_EVENT, openSettings);
    return () => window.removeEventListener(COOKIE_SETTINGS_EVENT, openSettings);
  }, []);

  function choose(value: CookieChoice) {
    saveCookieChoice(value);
    setChoice(value);
    setOpen(false);
  }

  if (!open) return null;

  return (
    <section className="cookie-consent" aria-label="Cookie and storage notice">
      <div className="cookie-consent-copy">
        <p className="cookie-consent-kicker">Cookies &amp; storage</p>
        <p>
          OmniRun uses essential browser storage only. No analytics, advertising, or
          cross-site tracking cookies.{" "}
          <a href="?page=privacy#cookies">Privacy policy</a>
          {choice ? " You can change this choice at any time." : ""}
        </p>
      </div>
      <div className="cookie-consent-actions">
        <button type="button" className="cookie-btn cookie-btn-primary" onClick={() => choose("accepted")}>
          Accept
        </button>
        <button type="button" className="cookie-btn" onClick={() => choose("essential")}>
          Essential only
        </button>
      </div>
    </section>
  );
}
