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
          GitHub Pages hosts the interface only. The Python API is not running here, so
          live preflights need the local API.
        </p>
      </div>
      <div className="preview-banner-actions">
        <a href={README_URL} target="_blank" rel="noreferrer">
          Run locally <ArrowRight size={11} />
        </a>
        <button type="button" onClick={onSample}>
          View sample result
        </button>
        <a href={`${REPO_URL}#api-contract`} target="_blank" rel="noreferrer">
          API contract
        </a>
      </div>
    </div>
  );
}
