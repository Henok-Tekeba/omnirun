import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CheckResponse } from "./api/types";
import type { FieldErrors, FormState } from "./lib/form";
import {
  DEFAULT_FORM,
  hardwareDescription,
  validateForm,
} from "./lib/form";
import { clearRunFlag, clearSampleFlag, readQuery, setSampleFlag, writeQuery } from "./lib/query";
import { loadHardware, saveHardware } from "./lib/storage";
import { useCheck } from "./hooks/useCheck";
import { useDevices } from "./hooks/useDevices";
import { CheckForm } from "./components/CheckForm";
import { DashboardShell } from "./components/DashboardShell";
import { FinderView } from "./components/FinderView";
import { LoadingView } from "./components/LoadingView";
import { MarketingLanding } from "./components/MarketingLanding";
import { ResultView } from "./components/ResultView";
import { StaticPreviewBanner } from "./components/StaticPreviewBanner";
import { SAMPLE_RESULT } from "./demo/sample";
import { IS_STATIC_PREVIEW } from "./lib/env";

type Phase = "landing" | "form" | "loading" | "result" | "finder";

function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

function focusFirstError(form: FormState, errors: FieldErrors) {
  let id: string | null = null;
  if (errors.model) id = "model";
  else if (errors.helperCode) id = "helper-code";
  else if (errors.hardware) id = "device-search";
  else if (errors.ramGib) id = form.mode === "manual" ? "ram-manual" : "ram-cpu";
  else if (errors.context) id = "context";
  else if (errors.batch) id = "batch";
  if (!id) return;
  requestAnimationFrame(() => {
    const element = document.getElementById(id);
    if (element instanceof HTMLElement) {
      element.focus({ preventScroll: true });
      element.scrollIntoView({
        behavior: prefersReducedMotion() ? "auto" : "smooth",
        block: "center",
      });
    }
  });
}

export default function App() {
  const initialQuery = useMemo(() => readQuery(), []);
  const initialSample = useMemo(
    () => new URLSearchParams(window.location.search).get("sample") === "1",
    [],
  );
  const storedHardware = useMemo(() => loadHardware(), []);
  const [form, setForm] = useState<FormState>(() => {
    if (initialQuery.form.model) return initialQuery.form;
    const defaults = IS_STATIC_PREVIEW
      ? { ...DEFAULT_FORM, mode: "cpu" as const, ramGib: "32" }
      : DEFAULT_FORM;
    return { ...defaults, ...storedHardware };
  });
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [phase, setPhase] = useState<Phase>(() =>
    initialSample ? "result" : initialQuery.form.model ? "form" : "landing",
  );
  const [shareUrl, setShareUrl] = useState("");
  const [sampleResult, setSampleResult] = useState<CheckResponse | null>(() =>
    initialSample ? SAMPLE_RESULT : null,
  );
  const devicesState = useDevices();
  const check = useCheck();
  const autoRunRef = useRef(false);

  const { run: runCheck, cancel: cancelCheck, reset: resetCheck, clearError } = check;

  useEffect(() => {
    saveHardware(form);
  }, [form.mode, form.helperCode, form.deviceId, form.ramGib, form.cpuMode]);

  const submitForm = useCallback(
    async (candidate: FormState) => {
      const validation = validateForm(candidate, devicesState.devices);
      if (!validation.ok || !validation.payload) {
        setFieldErrors(validation.errors);
        setPhase("form");
        focusFirstError(candidate, validation.errors);
        return;
      }

      setFieldErrors({});
      saveHardware(candidate);
      setSampleResult(null);
      setPhase("loading");
      setShareUrl("");
      clearSampleFlag();
      clearRunFlag();
      const response = await runCheck(validation.payload);
      if (response) {
        const url = writeQuery(candidate, true);
        setShareUrl(url);
        setPhase("result");
        scrollToTop();
      } else {
        setPhase("form");
      }
    },
    [devicesState.devices, runCheck],
  );

  useEffect(() => {
    if (!initialQuery.autoRun || autoRunRef.current) return;
    const needsDevices = initialQuery.form.mode === "manual";
    if (needsDevices && devicesState.status === "loading") return;
    autoRunRef.current = true;
    void submitForm(initialQuery.form);
  }, [
    devicesState.status,
    initialQuery.autoRun,
    initialQuery.form,
    submitForm,
  ]);

  useEffect(() => {
    if (phase !== "form" || !check.error) return;
    const timer = window.setTimeout(() => {
      document.getElementById("check-error")?.scrollIntoView({
        behavior: prefersReducedMotion() ? "auto" : "smooth",
        block: "center",
      });
    }, 60);
    return () => window.clearTimeout(timer);
  }, [check.error, phase]);

  const handleChange = useCallback(
    (patch: Partial<FormState>) => {
      setForm((current) => ({ ...current, ...patch }));
      setFieldErrors((current) => {
        const next: FieldErrors = { ...current };
        for (const key of Object.keys(patch) as (keyof FormState)[]) {
          delete next[key];
        }
        if ("mode" in patch) {
          delete next.hardware;
          delete next.helperCode;
          delete next.ramGib;
        }
        if ("deviceId" in patch) delete next.hardware;
        if ("cpuMode" in patch) delete next.ramGib;
        return next;
      });
      if (check.error) clearError();
    },
    [check.error, clearError],
  );

  const handleExample = useCallback((model: string) => {
    setForm((current) => ({ ...current, model }));
    setFieldErrors((current) => {
      const next = { ...current };
      delete next.model;
      return next;
    });
    requestAnimationFrame(() => {
      const input = document.getElementById("model");
      if (input instanceof HTMLInputElement) input.focus();
    });
  }, []);

  const handleSubmit = useCallback(() => {
    void submitForm(form);
  }, [form, submitForm]);

  const handleCancel = useCallback(() => {
    cancelCheck();
    setPhase("form");
    clearSampleFlag();
    clearRunFlag();
    scrollToTop();
  }, [cancelCheck]);

  const handleEdit = useCallback(() => {
    resetCheck();
    setSampleResult(null);
    setPhase("form");
    clearSampleFlag();
    clearRunFlag();
    scrollToTop();
  }, [resetCheck]);

  const handleStart = useCallback(() => {
    setSampleResult(null);
    clearSampleFlag();
    setPhase("form");
    scrollToTop();
  }, []);

  const handleFind = useCallback(() => {
    setSampleResult(null);
    clearSampleFlag();
    setPhase("finder");
    scrollToTop();
  }, []);

  const handleSample = useCallback(() => {
    resetCheck();
    setSampleResult(SAMPLE_RESULT);
    setSampleFlag();
    setPhase("result");
    scrollToTop();
  }, [resetCheck]);

  const handleOpenModel = useCallback((repoId: string) => {
    setForm((current) => ({ ...current, model: repoId }));
    setFieldErrors({});
    setSampleResult(null);
    clearSampleFlag();
    setPhase("form");
    scrollToTop();
  }, []);

  const handleEditHardware = useCallback(() => {
    setPhase("form");
    scrollToTop();
  }, []);

  const handleBackToLanding = useCallback(() => {
    resetCheck();
    setSampleResult(null);
    clearSampleFlag();
    setPhase("landing");
    window.history.replaceState(null, "", window.location.pathname);
    scrollToTop();
  }, [resetCheck]);

  const result = phase === "result" ? (check.result ?? sampleResult) : null;
  const showResult = result !== null;
  const error = phase === "form" ? check.error : null;

  if (phase === "landing") {
    return <MarketingLanding onStart={handleStart} />;
  }

  const shellTitle = showResult
    ? "Results"
    : phase === "finder"
      ? "Find models"
      : "Preflight";
  const shellSubtitle = showResult
    ? "Three checks: memory, runtime, and recorded runs."
    : phase === "finder"
      ? "Find models that fit the hardware you have."
      : "Memory, runtime, and speed before you download.";

  return (
    <DashboardShell
      active={showResult ? "result" : phase === "finder" ? "finder" : "preflight"}
      title={shellTitle}
      subtitle={shellSubtitle}
      onLanding={handleBackToLanding}
      onNewCheck={handleEdit}
      onFind={handleFind}
      actions={
        showResult ? (
          <button
            type="button"
            className="dashboard-btn dashboard-btn-primary"
            onClick={handleEdit}
          >
            New preflight
          </button>
        ) : null
      }
    >
      {IS_STATIC_PREVIEW ? <StaticPreviewBanner onSample={handleSample} /> : null}

      {phase === "loading" ? (
        <LoadingView
          model={form.model}
          hardware={hardwareDescription(form, devicesState.devices)}
          onCancel={handleCancel}
        />
      ) : showResult ? (
        <ResultView
          result={result}
          shareUrl={shareUrl}
          sample={sampleResult !== null}
          onEdit={handleEdit}
        />
      ) : phase === "finder" ? (
        <FinderView
          form={form}
          devices={devicesState.devices}
          onOpenModel={handleOpenModel}
          onEditHardware={handleEditHardware}
        />
      ) : (
        <CheckForm
          form={form}
          onChange={handleChange}
          devices={devicesState.devices}
          devicesStatus={devicesState.status}
          devicesError={devicesState.error}
          onReloadDevices={() => void devicesState.reload()}
          errors={fieldErrors}
          error={error}
          onSubmit={handleSubmit}
          onRetry={handleSubmit}
          onDismissError={clearError}
          onExample={handleExample}
        />
      )}
    </DashboardShell>
  );
}
