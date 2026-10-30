import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FieldErrors, FormState } from "./lib/form";
import {
  DEFAULT_FORM,
  hardwareDescription,
  validateForm,
} from "./lib/form";
import { clearRunFlag, readQuery, writeQuery } from "./lib/query";
import { loadHardware, saveHardware } from "./lib/storage";
import { useCheck } from "./hooks/useCheck";
import { useDevices } from "./hooks/useDevices";
import { useTheme } from "./hooks/useTheme";
import { CheckForm } from "./components/CheckForm";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { LoadingView } from "./components/LoadingView";
import { MarketingLanding } from "./components/MarketingLanding";
import { ResultView } from "./components/ResultView";
import { ArrowLeft } from "./components/Icons";

type Phase = "landing" | "form" | "loading" | "result";

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
  const { theme, toggleTheme } = useTheme();
  const initialQuery = useMemo(() => readQuery(), []);
  const storedHardware = useMemo(() => loadHardware(), []);
  const [form, setForm] = useState<FormState>(() =>
    initialQuery.form.model
      ? initialQuery.form
      : { ...DEFAULT_FORM, ...storedHardware },
  );
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [phase, setPhase] = useState<Phase>(() =>
    initialQuery.form.model ? "form" : "landing",
  );
  const [shareUrl, setShareUrl] = useState("");
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
      setPhase("loading");
      setShareUrl("");
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
    clearRunFlag();
    scrollToTop();
  }, [cancelCheck]);

  const handleEdit = useCallback(() => {
    resetCheck();
    setPhase("form");
    clearRunFlag();
    scrollToTop();
  }, [resetCheck]);

  const handleStart = useCallback(() => {
    setPhase("form");
    scrollToTop();
  }, []);

  const handleBackToLanding = useCallback(() => {
    resetCheck();
    setPhase("landing");
    window.history.replaceState(null, "", window.location.pathname);
    scrollToTop();
  }, [resetCheck]);

  const result = phase === "result" ? check.result : null;
  const showResult = result !== null;
  const error = phase === "form" ? check.error : null;

  if (phase === "landing") {
    return <MarketingLanding onStart={handleStart} />;
  }

  return (
    <div className="site-shell" id="top">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header theme={theme} onToggleTheme={toggleTheme} isResult={showResult} />

      <main id="main" className="flex-1">
        {phase === "loading" ? (
          <div className="container-wide py-6 md:py-10">
            <LoadingView
              model={form.model}
              hardware={hardwareDescription(form, devicesState.devices)}
              onCancel={handleCancel}
            />
          </div>
        ) : showResult ? (
          <div className="container-wide py-6 md:py-10">
            <ResultView result={result} shareUrl={shareUrl} onEdit={handleEdit} />
          </div>
        ) : (
          <div className="container-wide py-6 md:py-9">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="micro micro-accent">Preflight console</p>
                <h1 className="bench-title mt-1 text-[clamp(2.6rem,5vw,4.2rem)]">
                  Run a model.
                </h1>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleBackToLanding}
              >
                <ArrowLeft size={12} /> Landing
              </button>
            </div>
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
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
