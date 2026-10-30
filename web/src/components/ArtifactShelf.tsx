import { useState } from "react";
import type { ArtifactReport, CheckResponse } from "../api/types";
import { formatBytesRange, formatGB, formatInteger } from "../lib/format";
import { Box, Cpu, Download } from "./Icons";
import { CopyButton } from "./CopyButton";
import { ConfidenceMeter, EmptyLine, SectionHeading, StatusPill } from "./ui";

function formatLabel(format: ArtifactReport["format"]): string {
  switch (format) {
    case "gguf":
      return "GGUF";
    case "safetensors":
      return "Safetensors";
    case "pytorch_pickle":
      return "Pickle";
    case "ctranslate2":
      return "CTranslate2";
    case "onnx":
      return "ONNX";
    case "adapter":
      return "Adapter";
    default:
      return "Unknown";
  }
}

function quantLabel(artifact: ArtifactReport): string {
  if (artifact.quantization) return artifact.quantization;
  if (artifact.format === "safetensors") return "Base";
  return "—";
}

function downloadCommand(result: CheckResponse, artifact: ArtifactReport): string {
  const paths = artifact.files.length > 1 ? artifact.files.join(" ") : artifact.path;
  return `huggingface-cli download ${result.model.repo_id} ${paths}`;
}

function runCommand(result: CheckResponse, artifact: ArtifactReport): string | null {
  if (artifact.format !== "gguf") return null;
  const context = result.inputs.context_effective ?? result.inputs.context_requested;
  const gpuLayers = result.hardware.kind === "cpu" ? 0 : 99;
  return `llama-cli -m ${artifact.path} -c ${context} -ngl ${gpuLayers}`;
}

function ArtifactRow({
  result,
  artifact,
}: {
  result: CheckResponse;
  artifact: ArtifactReport;
}) {
  const command = runCommand(result, artifact);
  const download = downloadCommand(result, artifact);
  const weightsOnly = artifact.peak === null && artifact.weights_peak !== null;
  const weightsFit = artifact.fits === "unknown" && artifact.weights_fit === "yes";

  return (
    <article className="artifact-row">
      <div className="artifact-grid">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="artifact-quant">{quantLabel(artifact)}</span>
            <span className="badge">{formatLabel(artifact.format)}</span>
            {!artifact.direct ? (
              <span className="badge badge-optimize">runtime check</span>
            ) : null}
          </div>
          <p className="artifact-path mt-1.5" title={artifact.path}>
            {artifact.path}
          </p>
        </div>

        <div className="artifact-meta">
          <span>Size</span>
          <strong>{formatGB(artifact.size_bytes)}</strong>
        </div>
        <div className="artifact-meta">
          <span>{weightsOnly ? "Weights only" : "Peak"}</span>
          <strong>{formatBytesRange(artifact.peak ?? artifact.weights_peak)}</strong>
        </div>
        <div className="artifact-meta">
          <span>Runtime</span>
          <strong>{artifact.runtime_hint ?? "Unknown"}</strong>
        </div>
        <div className="flex justify-start sm:justify-end">
          {weightsFit ? (
            <span className="badge badge-go">Weights fit</span>
          ) : (
            <StatusPill status={artifact.fits} />
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-[var(--line)] pt-2">
        <CopyButton value={download} label="Copy download" />
        <details className="min-w-0">
          <summary className="cursor-pointer list-none font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)] hover:text-[var(--text-2)] [&::-webkit-details-marker]:hidden">
            Details
          </summary>
          <div className="mt-2 space-y-2">
            <p className="text-[10.5px] leading-relaxed text-[var(--muted)]">
              {artifact.note}
              {weightsOnly
                ? " Context memory is unknown, so this is a weights-only fit."
                : ""}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <CopyButton value={artifact.path} label="Copy path" />
              {command ? <CopyButton value={command} label="Copy run command" /> : null}
              <ConfidenceMeter value={artifact.confidence} compact />
              <span className="font-mono text-[8.5px] text-[var(--faint)]">
                {formatInteger(artifact.files.length)} file
                {artifact.files.length === 1 ? "" : "s"}
              </span>
            </div>
            {artifact.files.length > 1 ? (
              <ul className="space-y-0.5">
                {artifact.files.map((file) => (
                  <li key={file} className="break-all font-mono text-[9px] text-[var(--muted)]">
                    {file}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </details>
      </div>
    </article>
  );
}

export function ArtifactShelf({ result }: { result: CheckResponse }) {
  const artifacts = result.artifacts ?? [];
  const [showAll, setShowAll] = useState(false);
  const visibleArtifacts = showAll ? artifacts : artifacts.slice(0, 6);

  return (
    <section className="console" aria-labelledby="artifacts-title">
      <div className="console-label">
        <span>
          <strong>Artifacts</strong>
        </span>
        <span>{artifacts.length} actual files</span>
        <span>from the HF tree</span>
      </div>
      <div className="p-4 md:p-6">
        <SectionHeading
          id="artifacts-title"
          eyebrow="Real files in this repository"
          title="Artifacts"
          aside={
            <span className="badge">
              <Box size={10} /> metadata only
            </span>
          }
        />

        {artifacts.length === 0 ? (
          <EmptyLine>
            No downloadable model artifacts were found in this repository. The smaller-weight
            estimates below are hypothetical.
          </EmptyLine>
        ) : (
          <>
            <div className="artifact-list">
              {visibleArtifacts.map((artifact) => (
                <ArtifactRow key={artifact.path} result={result} artifact={artifact} />
              ))}
            </div>
            {artifacts.length > 6 ? (
              <button
                type="button"
                className="btn btn-ghost btn-sm mt-2"
                onClick={() => setShowAll((value) => !value)}
              >
                {showAll ? "Show fewer" : `Show all ${artifacts.length} artifacts`}
              </button>
            ) : null}
          </>
        )}

        <p className="mt-3 flex items-start gap-2 border-t border-[var(--line)] pt-2 text-[10px] leading-relaxed text-[var(--faint)]">
          <Download size={12} className="mt-0.5 flex-none" />
          Sizes are file sizes from Hugging Face, not tensor math. Peak estimates are
          upper-bound planning numbers. Download commands are for you to run; OmniRun does not
          download weights.
        </p>
        <p className="mt-1 flex items-center gap-1.5 text-[10px] text-[var(--faint)]">
          <Cpu size={11} /> Runtime hints are not a guarantee that the artifact loads.
        </p>
      </div>
    </section>
  );
}
