import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { registrationApi, type RegisterOptions } from "../api/registration";
import type { RegistrationStatusResponse, RunSummary } from "../types";

const STORAGE_KEY = "invincibles.currentRunId";

interface RunContextValue {
  runId: string | null;
  setRunId: (id: string | null) => void;
  status: RegistrationStatusResponse["status"] | "IDLE" | "NOT_FOUND";
  summary: RunSummary | null;
  isPolling: boolean;
  error: string | null;
  startRun: (options?: RegisterOptions) => Promise<void>;
  refresh: () => Promise<void>;
}

const RunContext = createContext<RunContextValue | undefined>(undefined);

export function RunProvider({ children }: { children: ReactNode }) {
  const [runId, setRunIdState] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const [status, setStatus] = useState<RunContextValue["status"]>("IDLE");
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setRunId = useCallback((id: string | null) => {
    setRunIdState(id);
    setSummary(null);
    setError(null);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  }, []);

  const fetchSummary = useCallback(async (id: string) => {
    try {
      const s = await registrationApi.results(id);
      setSummary(s);
      setStatus("COMPLETE");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run results.");
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!runId) return;
    await fetchSummary(runId);
  }, [runId, fetchSummary]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    let poller: ReturnType<typeof setInterval> | null = null;

    async function poll() {
      try {
        const st = await registrationApi.status(runId!);
        if (cancelled) return;
        setStatus(st.status);
        if (st.status === "COMPLETE") {
          setIsPolling(false);
          if (poller) clearInterval(poller);
          await fetchSummary(runId!);
        } else if (st.status === "ERROR") {
          setIsPolling(false);
          if (poller) clearInterval(poller);
          setError("Registration run failed on the backend. See server logs for details.");
        } else {
          setIsPolling(true);
        }
      } catch {
        if (!cancelled) {
          setStatus("NOT_FOUND");
          setIsPolling(false);
          if (poller) clearInterval(poller);
        }
      }
    }

    poll();
    poller = setInterval(poll, 2500);
    return () => {
      cancelled = true;
      if (poller) clearInterval(poller);
    };
  }, [runId, fetchSummary]);

  const startRun = useCallback(
    async (options?: RegisterOptions) => {
      setError(null);
      setSummary(null);
      try {
        const res = await registrationApi.start(options);
        setRunId(res.run_id);
        setStatus(res.status === "COMPLETE" ? "COMPLETE" : "RUNNING");
        if (res.status === "COMPLETE") {
          await fetchSummary(res.run_id);
        } else {
          setIsPolling(true);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start registration run.");
      }
    },
    [setRunId, fetchSummary]
  );

  const value = useMemo(
    () => ({ runId, setRunId, status, summary, isPolling, error, startRun, refresh }),
    [runId, setRunId, status, summary, isPolling, error, startRun, refresh]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used within a RunProvider");
  return ctx;
}
