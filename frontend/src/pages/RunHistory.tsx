import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { runsApi } from "../api/runs";
import { useRun } from "../context/RunContext";
import { EmptyState, Loader, ErrorState, ConfidencePill, StatusPill } from "../components/common/Primitives";
import type { RunHistoryEntry } from "../types";
import { formatDate, formatPercent, formatPixels } from "../utils/format";

export default function RunHistory() {
  const navigate = useNavigate();
  const { setRunId } = useRun();
  const [runs, setRuns] = useState<RunHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    runsApi
      .list()
      .then((r) => setRuns(r.runs))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load run history."));
  }

  useEffect(load, []);

  function openRun(runId: string) {
    setRunId(runId);
    navigate("/results");
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="page-eyebrow">Run History</span>
          <h1 className="page-title">Analysis History</h1>
          <p className="page-subtitle">Every entry is a real cached run from the backend's output/cache directory.</p>
        </div>
      </div>

      {error && <ErrorState title="Could not load run history" message={error} onRetry={load} />}
      {!runs && !error && <Loader label="Loading run history…" />}

      {runs && runs.length === 0 && (
        <EmptyState title="No completed analyses yet" desc="Run an analysis from Mission Control to generate results." />
      )}

      {runs && runs.length > 0 && (
        <div className="panel panel-padded">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Date</th>
                  <th>Reference</th>
                  <th>Sensors Succeeded</th>
                  <th>Mean RMSE</th>
                  <th>Mean Inlier Ratio</th>
                  <th>Confidence</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="clickable" onClick={() => openRun(r.run_id)}>
                    <td className="mono">{r.run_id}</td>
                    <td>{formatDate(r.generated_at)}</td>
                    <td className="mono">{r.reference_sensor}</td>
                    <td>
                      {r.sensors_succeeded.length} / {r.sensors_succeeded.length + r.sensors_failed.length}
                    </td>
                    <td className="mono">{formatPixels(r.mean_checkpoint_rmse)}</td>
                    <td className="mono">{formatPercent(r.mean_inlier_ratio)}</td>
                    <td><ConfidencePill level={r.overall_confidence} /></td>
                    <td><StatusPill tone="success">{r.status}</StatusPill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
