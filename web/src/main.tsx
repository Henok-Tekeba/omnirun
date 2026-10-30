import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { CookieConsent } from "./components/CookieConsent";
import { LegalPage } from "./components/LegalPage";
import "./index.css";

function Root() {
  const page = new URLSearchParams(window.location.search).get("page");
  if (page === "privacy" || page === "terms") {
    return <LegalPage page={page} />;
  }
  return <App />;
}

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
  <StrictMode>
    <Root />
    <CookieConsent />
  </StrictMode>,
);
