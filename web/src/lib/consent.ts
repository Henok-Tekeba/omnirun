export const COOKIE_CHOICE_KEY = "omnirun.cookie-consent";
export const COOKIE_SETTINGS_EVENT = "omnirun:open-cookie-settings";

export type CookieChoice = "accepted" | "essential";

export function readCookieChoice(): CookieChoice | null {
  try {
    const value = localStorage.getItem(COOKIE_CHOICE_KEY);
    return value === "accepted" || value === "essential" ? value : null;
  } catch {
    return null;
  }
}

export function saveCookieChoice(choice: CookieChoice): void {
  try {
    localStorage.setItem(COOKIE_CHOICE_KEY, choice);
  } catch {
    /* The choice still applies for this session. */
  }
}

export function openCookieSettings(): void {
  window.dispatchEvent(new Event(COOKIE_SETTINGS_EVENT));
}
