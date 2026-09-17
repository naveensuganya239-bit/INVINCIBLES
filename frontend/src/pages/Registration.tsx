import { useState } from "react";
import { useRun } from "../context/RunContext";
import { PipelineTimeline, buildStagesForSensor } from "../components/common/PipelineTimeline";
import { StatusPill, Loader, EmptyState, ErrorState } from "../components/common/Primitives";
import { IconPlay } from "../components/common/Icons";

const ALL_SENSORS = ["TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"];

export default function Registration() {
  const { runId, status, summary, isPolling, error, startRun } = useRun();
  const [selected, setSelected] = useState<string[]>(ALL_SENSORS);
  const [forceRerun, setForceRerun] = useState(false);

  function toggleSensor(s: string) {
    setSelected((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  async function handleRun() {
    await startRun({ sensors: selected.length ? selected : undefined, force_rerun: forceRerun });
  }

  const sensorEntries = summary ? Object.entries(summary.sensor_results) : [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="page-eyebrow">Registration</span>
          <h1 className="page-title">Lunar Registration Pipeline</h1>
          <p className="page-subtitle">
            Every stage below corresponds to an actual backend processing step. Progress reflects
            real job status polled from <code className="mono">GET /api/register/&#123;run_id&#125;/status</code>.
          </p>
        </div>
        <StatusPill tone={status === "RUNNING" ? "info" : status === "COMPLETE" ? "success" : status === "ERROR" ? "error" : "pending"}>
          {status === "IDLE" ? "IDLE" : status}
        </StatusPill>
      </div>

      <div className="panel panel-padded">
        <div className="panel-header">
          <div>
            <div className="panel-title">Run Configuration</div>
            <div className="panel-title-sub">Source sensors sent to the backend for this run.</div>
          </div>
        </div>
        <div className="chip-row">
          {ALL_SENSORS.map((s) => (
            <div key={s} className={`chip${selected.includes(s) ? " active" : ""}`} onClick={() => toggleSensor(s)}>
              {s}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-12 mt-16">
          <button className="btn btn-primary" onClick={handleRun} disabled={isPolling || selected.length === 0}>
            <IconPlay style={{ width: 14, height: 14 }} />
            {isPolling ? "RUNNING…" : "RUN SELECTED ANALYSIS"}
          </button>
          <label className="flex items-center gap-8" style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={forceRerun} onChange={(e) => setForceRerun(e.target.checked)} />
            Force re-run (ignore cache)
          </label>
        </div>
      </div>

      {error && (
        <div className="mt-24">
          <ErrorState title="Registration error" message={error} />
        </div>
      )}

      {!runId && !error && (
        <div className="mt-24">
          <EmptyState title="No analysis run yet" desc="Configure your source sensors above and run the pipeline to see live, per-sensor stage progress." />
        </div>
      )}

      {runId && isPolling && !summary && (
        <div className="panel panel-padded mt-24">
          <Loader label={`Processing run ${runId.slice(0, 14)}… this typically takes 30–90 seconds for 4 sensors.`} />
        </div>
      )}

      {summary && (
        <div className="grid grid-2 mt-24">
          {sensorEntries.map(([sensorKey, res]) => (
            <div key={sensorKey} className="panel panel-padded">
              <div className="panel-header">
                <div className="panel-title">{sensorKey} → OHRC</div>
                <StatusPill tone={res.status === "SUCCESS" ? "success" : "error"}>{res.status}</StatusPill>
              </div>
              <PipelineTimeline
                stages={buildStagesForSensor(res.status, res.status === "FAILED" ? (res as { failed_stage?: string }).failed_stage : null)}
              />
              {res.status === "FAILED" && (
                <div className="state-code mt-16">
                  Stage: {(res as { failed_stage?: string }).failed_stage} — {(res as { failure_reason?: string }).failure_reason}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
