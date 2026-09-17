import type { ReactNode } from "react";
import { useState } from "react";
import { IconAlert, IconCheck } from "./Icons";
import type { ConfidenceLevel } from "../../types";

export function StatusPill({
  tone,
  children,
}: {
  tone: "success" | "warning" | "error" | "pending" | "info";
  children: ReactNode;
}) {
  return (
    <span className={`status-pill ${tone}`}>
      <span className="dot" />
      {children}
    </span>
  );
}

export function ConfidencePill({ level }: { level: ConfidenceLevel | null | undefined }) {
  if (!level) return <StatusPill tone="pending">N/A</StatusPill>;
  const tone = level === "HIGH" ? "success" : level === "MEDIUM" ? "warning" : "error";
  return <StatusPill tone={tone}>{level} CONFIDENCE</StatusPill>;
}

export function MetricCard({
  label,
  value,
  sub,
  tone,
  tooltip,
}: {
  label: string;
  value: string | number | null | undefined;
  sub?: string;
  tone?: "success" | "warning" | "error";
  tooltip?: string;
}) {
  const isNA = value === null || value === undefined || value === "N/A";
  return (
    <div className="metric-card">
      <div className="metric-label">
        {label}
        {tooltip && <InfoTooltip text={tooltip} />}
      </div>
      <div className={`metric-value${isNA ? " na" : tone ? ` ${tone}` : ""}`}>{isNA ? "N/A" : value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="info-tooltip">
      <span className="info-icon">i</span>
      <span className="tooltip-bubble">{text}</span>
    </span>
  );
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="tabs">
      {tabs.map((t) => (
        <div key={t.key} className={`tab${active === t.key ? " active" : ""}`} onClick={() => onChange(t.key)}>
          {t.label}
        </div>
      ))}
    </div>
  );
}

export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state-block">
      <div className="spinner" />
      <div className="state-desc">{label}</div>
    </div>
  );
}

export function EmptyState({ title, desc, action }: { title: string; desc: string; action?: ReactNode }) {
  return (
    <div className="state-block">
      <div className="state-icon">
        <IconCheck />
      </div>
      <div className="state-title">{title}</div>
      <div className="state-desc">{desc}</div>
      {action}
    </div>
  );
}

export function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return (
    <div className="state-block error">
      <div className="state-icon">
        <IconAlert />
      </div>
      <div className="state-title">{title}</div>
      <div className="state-code">{message}</div>
      {onRetry && (
        <button className="btn btn-secondary btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Badge({ children, locked }: { children: ReactNode; locked?: boolean }) {
  return <span className={`badge${locked ? " locked" : ""}`}>{children}</span>;
}

export function ImageFrame({ src, label, alt, empty, aspect }: { src: string | null | undefined; label?: string; alt?: string; empty?: string; aspect?: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="image-frame" style={{ minHeight: 180, aspectRatio: aspect || "4 / 3.2" }}>
      {label && <div className="image-frame-label">{label}</div>}
      {src && !failed ? (
        <img src={src} alt={alt || label || "diagnostic image"} onError={() => setFailed(true)} />
      ) : (
        <div className="image-empty">{empty || "Image not available from backend for this run."}</div>
      )}
    </div>
  );
}
