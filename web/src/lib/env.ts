const rawApiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();

/** API root. Local dev uses the Vite /api proxy; a hosted API can be set at build time. */
export const API_BASE = rawApiBase ? rawApiBase.replace(/\/+$/, "") : "/api";
export const API_DOCS_URL = `${API_BASE}/docs`;

/** Base path injected by Vite, e.g. /omnirun/ on GitHub Pages. */
export const SITE_BASE = import.meta.env.BASE_URL;
export const SITE_URL = "https://henok-tekeba.github.io/omnirun/";

export const REPO_URL = "https://github.com/Henok-Tekeba/omnirun";
export const ISSUES_URL = `${REPO_URL}/issues`;
export const METHODOLOGY_URL = `${REPO_URL}/blob/main/docs/methodology.md`;
export const README_URL = `${REPO_URL}#quick-start`;
export const SECURITY_URL = `${REPO_URL}/blob/main/SECURITY.md`;

/** A production build without an API base is the static GitHub Pages preview. */
export const IS_STATIC_PREVIEW = import.meta.env.PROD && !rawApiBase;
