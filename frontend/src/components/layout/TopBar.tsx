import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useRun } from "../../context/RunContext";

export function TopBar() {
  const { runId, summary } = useRun();
  const [backendReady, setBackendReady] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<{ project: string; status: string }>("/api/health")
      .then((r) => !cancelled && setBackendReady(r.status === "READY"))
      .catch(() => !cancelled && setBackendReady(false));
    const interval = setInterval(() => {
      api
        .get<{ project: string; status: string }>("/api/health")
        .then((r) => !cancelled && setBackendReady(r.status === "READY"))
        .catch(() => !cancelled && setBackendReady(false));
    }, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const regionLabel = summary ? "Chandrayaan-2 Sample Region" : "No active dataset run";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">
          INVINCIBLES <span>/ Multi-Modal Lunar Registration</span>
        </div>
      </div>
      <div className="topbar-meta">
        <div className="topbar-meta-item">
          <span className="topbar-meta-label">REFERENCE</span>
          <span className="topbar-meta-value mono">OHRC</span>
        </div>
        <div className="topbar-meta-item">
          <span className="topbar-meta-label">REGION</span>
          <span className="topbar-meta-value">{regionLabel}</span>
        </div>
        {runId && (
          <div className="topbar-meta-item">
            <span className="topbar-meta-label">RUN</span>
            <span className="topbar-meta-value mono">{runId.slice(0, 14)}…</span>
          </div>
        )}
      </div>
      <div className="topbar-right">
        {backendReady === null ? (
          <span className="status-pill pending"><span className="dot" />CONNECTING</span>
        ) : backendReady ? (
          <span className="status-pill success"><span className="dot" />SYSTEM READY</span>
        ) : (
          <span className="status-pill error"><span className="dot" />BACKEND UNREACHABLE</span>
        )}
      </div>
    </header>
  );
}
