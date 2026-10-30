import { useState } from "react";
import { ApiError, findModels } from "../api/client";
import type { DeviceEntry, FindCandidate, FindResponse } from "../api/types";
import { validateForm, hardwareDescription, type FormState } from "../lib/form";
import {
  formatBytesRange,
  formatGB,
  formatInteger,
  formatRangeFloat,
} from "../lib/format";
import {
  ArrowRight,
  Cpu,
  ExternalLink,
  Search,
  ShieldCheck,
} from "./Icons";
import { CopyButton } from "./CopyButton";
import { ConfidenceMeter, EmptyLine, SectionHeading, StatusPill } from "./ui";

type Task = "text-generation" | "automatic-speech-recognition" | "text-to-speech";
type FindStatus = "idle" | "loading" | "success" | "error";

const TASKS: { value: Task; label: string }[] = [
  { value: "text-generation", label: "Text generation" },
  { value: "automatic-speech-recognition", label: "Speech recognition" },
  { value: "text-to-speech", label: "Text to speech" },
];

function taskLabel(value: string): string {
  return TASKS.find((task) => task.value === value)?.label ?? value;
}

function verdictTone(value: FindCandidate["verdict"]): string {
  switch (value) {
    case "GO":
      return "badge-go";
    case "OPTIMIZE":
      return "badge-optimize";
    case "NO":
      return "badge-no";
    default:
      return "badge-unknown";
  }
}

function CandidateCard({
  candidate,
  onOpenModel,
}: {
  candidate: FindCandidate;
  onOpenModel: (repoId: string) => void;
}) {
  return (
    <article className="finder-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`badge ${verdictTone(candidate.verdict)}`}>
              {candidate.verdict}
            </span>
            <span className="badge">{candidate.format}</span>
            {candidate.license ? (
              <span className="badge">{candidate.license}</span>
            ) : (
              <span className="badge">license unknown</span>
            )}
            {candidate.gated ? <span className="badge badge-optimize">gated</span> : null}
            {candidate.private ? <span className="badge">private</span> : null}
            {candidate.trust_remote_code_required ? (
              <span className="badge badge-optimize">custom code</span>
            ) : null}
          </div>
          <h3 className="finder-repo mt-2">{candidate.repo_id}</h3>
          <p className="mt-1 text-[11px] text-[var(--muted)]">
            {candidate.reason} {candidate.pipeline_tag ? `/ ${taskLabel(candidate.pipeline_tag)}` : ""}
          </p>
        </div>
        <ConfidenceMeter value={candidate.confidence} compact />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--line)] pt-2 sm:grid-cols-4">
        <div>
          <p className="micro">Memory</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--text-2)]">
            {formatBytesRange(candidate.peak)}
          </p>
        </div>
        <div>
          <p className="micro">Speed</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--text-2)]">
            {candidate.speed ? formatRangeFloat(candidate.speed, "tok/s") : "—"}
          </p>
        </div>
        <div>
          <p className="micro">Artifacts</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--text-2)]">
            {formatInteger(candidate.artifacts_count)}
          </p>
        </div>
        <div>
          <p className="micro">Best file</p>
          <p className="mt-0.5 font-mono text-[11px] text-[var(--text-2)]">
            {formatGB(candidate.best_artifact_size_bytes)}
          </p>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <StatusPill status={candidate.fits} />
        <span className="badge">runtime {candidate.supported}</span>
        <span className="badge">verified {candidate.verified}</span>
        {candidate.direct_runtime_available ? (
          <span className="badge badge-go">
            <ShieldCheck size={10} /> direct
          </span>
        ) : null}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--line)] pt-2">
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={() => onOpenModel(candidate.repo_id)}
        >
          Open in preflight <ArrowRight size={11} />
        </button>
        <CopyButton value={candidate.repo_id} label="Copy repo ID" />
        <a
          className="btn btn-ghost btn-sm"
          href={`https://huggingface.co/${candidate.repo_id}`}
          target="_blank"
          rel="noreferrer"
        >
          Hugging Face <ExternalLink size={10} />
        </a>
      </div>
    </article>
  );
}

export function FinderView({
  form,
  devices,
  onOpenModel,
  onEditHardware,
}: {
  form: FormState;
  devices: DeviceEntry[];
  onOpenModel: (repoId: string) => void;
  onEditHardware: () => void;
}) {
  const [query, setQuery] = useState("");
  const [task, setTask] = useState<Task>("text-generation");
  const [limit, setLimit] = useState("5");
  const [status, setStatus] = useState<FindStatus>("idle");
  const [response, setResponse] = useState<FindResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hardware = hardwareDescription(form, devices);

  async function search() {
    const validation = validateForm({ ...form, model: "placeholder/model" }, devices);
    if (!validation.ok || !validation.payload) {
      setError(
        "Choose a complete hardware profile in Preflight first. The finder uses the same hardware.",
      );
      setStatus("error");
      return;
    }

    setStatus("loading");
    setError(null);
    setResponse(null);
    try {
      const result = await findModels({
        query: query.trim(),
        task,
        hardware: validation.payload.hardware,
        context: validation.payload.context,
        batch: validation.payload.batch,
        limit: Number(limit),
        ...(validation.payload.hf_token ? { hf_token: validation.payload.hf_token } : {}),
      });
      setResponse(result);
      setStatus("success");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "The model search failed. Try again.",
      );
      setStatus("error");
    }
  }

  return (
    <div className="space-y-5">
      <section className="console">
        <div className="console-label">
          <span>
            <strong>Find models</strong>
          </span>
          <span>hardware first</span>
          <span>not a quality leaderboard</span>
        </div>
        <div className="p-4 md:p-6">
          <SectionHeading
            eyebrow="Start with your machine"
            title="Find models"
            aside={<span className="badge">ranked by fit</span>}
          />

          <div className="border border-[var(--line)] bg-[var(--bg-elevated)] p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Cpu size={13} className="text-[var(--faint)]" />
                <span className="text-[12px] text-[var(--text-2)]">{hardware}</span>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={onEditHardware}>
                Change hardware
              </button>
            </div>
            <p className="mt-1 text-[10px] text-[var(--faint)]">
              Candidates are ranked by fit, runtime support, artifact availability, and size.
              Model quality is not ranked.
            </p>
          </div>

          <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_180px_90px_auto]">
            <div className="relative">
              <Search
                size={14}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--faint)]"
              />
              <input
                className="field pl-8"
                placeholder="Search models (optional)"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void search();
                  }
                }}
              />
            </div>
            <select
              className="field"
              value={task}
              onChange={(event) => setTask(event.target.value as Task)}
              aria-label="Task"
            >
              {TASKS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <select
              className="field"
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              aria-label="Result limit"
            >
              <option value="3">3</option>
              <option value="5">5</option>
              <option value="8">8</option>
            </select>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void search()}
              disabled={status === "loading"}
            >
              {status === "loading" ? "Searching…" : "Find models"}
              <ArrowRight size={13} />
            </button>
          </div>
          <p className="mt-2 text-[10px] text-[var(--faint)]">
            An empty search uses a broad candidate pool, not a recommendation. Up to{" "}
            {limit} candidates are returned after inspection. Usually 5–20 seconds; slow
            candidates are skipped so one model cannot block the search.
          </p>

          {status === "loading" ? (
            <div className="mt-4">
              <div className="progress-line" aria-hidden="true" />
              <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.08em] text-[var(--muted)]">
                Searching Hugging Face and inspecting candidates…
              </p>
            </div>
          ) : null}

          {error ? (
            <div className="mt-4 border border-[color-mix(in_srgb,var(--no)_45%,var(--line))] bg-[var(--no-soft)] p-3">
              <p className="text-[12px] font-medium text-[var(--no)]">Search failed</p>
              <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">{error}</p>
            </div>
          ) : null}
        </div>
      </section>

      {response ? (
        <section className="console">
          <div className="console-label">
            <span>
              <strong>Candidates</strong>
            </span>
            <span>
              {response.candidates.length} shown / {response.searched} inspected
            </span>
            <span>fit first</span>
          </div>
          <div className="p-4 md:p-6">
            {response.candidates.length === 0 ? (
              <EmptyLine>
                No candidates were returned. Try a broader query or a different task.
              </EmptyLine>
            ) : (
              <div className="finder-list">
                {response.candidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.repo_id}
                    candidate={candidate}
                    onOpenModel={onOpenModel}
                  />
                ))}
              </div>
            )}
            {response.errors.length > 0 ? (
              <details className="mt-3 border-t border-[var(--line)] pt-2">
                <summary className="cursor-pointer list-none font-mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--faint)] hover:text-[var(--text-2)] [&::-webkit-details-marker]:hidden">
                  {response.errors.length} candidates could not be inspected
                </summary>
                <ul className="mt-2 space-y-1">
                  {response.errors.map((item) => (
                    <li key={item.repo_id} className="text-[10px] text-[var(--muted)]">
                      <span className="font-mono text-[9px]">{item.repo_id}</span>:{" "}
                      {item.message}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
