import { README_URL, REPO_URL } from "../lib/env";
import { ArrowRight, Info } from "./Icons";

export function StaticPreviewBanner({ onSample }: { onSample: () => void }) {
  return (
    <div className="preview-banner" role="note">
      <div className="preview-banner-copy">
        <span className="preview-banner-label">
          <Info size={12} /> Static preview
        </span>
        <p>
          This is a static product preview. Live preflights require the OmniRun API.
        </p>
      </div>
      <div className="preview-banner-actions">
        <a href={README_URL} target="_blank" rel="noreferrer">
          Run locally <ArrowRight size={11} />
        </a>
        <button type="button" onClick={onSample}>
          Sample report
        </button>
        <a
          href={`${REPO_URL}#api-contract`}
          target="_blank"
          rel="noreferrer"
          className="preview-banner-api"
        >
          API contract
        </a>
      </div>
    </div>
  );
}
