import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { datasetApi } from "../api/dataset";
import { useRun } from "../context/RunContext";
import { resolveAssetUrl } from "../api/client";
import { MetricCard, StatusPill, ConfidencePill, Loader, ErrorState } from "../components/common/Primitives";
import { IconPlay, IconArrowRight } from "../components/common/Icons";
import type { DatasetAnalysisResponse } from "../types";
import { formatPercent, formatPixels } from "../utils/format";

export default function MissionControl() {
  const navigate = useNavigate();
  const { runId, summary, status, isPolling, error, startRun } = useRun();
  const [dataset, setDataset] = useState<DatasetAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    datasetApi
      .getAnalysis()
      .then(setDataset)
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load dataset."));
  }, []);

  const ohrcPreview = dataset?.manifest.sensors["OHRC"]?.preview_url;

  const successCount = summary
    ? Object.values(summary.sensor_results).filter((r) => r.status === "SUCCESS").length
    : null;
  const totalSensors = summary ? Object.keys(summary.sensor_results).length : 4;

  const rmses = summary
    ? Object.values(summary.sensor_results)
        .filter((r): r is Extract<typeof r, { status: "SUCCESS" }> => r.status === "SUCCESS")
        .map((r) => r.metrics.checkpoint_rmse_final)
        .filter((v): v is number => v !== null)
    : [];
  const meanRmse = rmses.length ? rmses.reduce((a, b) => a + b, 0) / rmses.length : null;

  const confidences = summary
    ? Object.values(summary.sensor_results)
        .filter((r): r is Extract<typeof r, { status: "SUCCESS" }> => r.status === "SUCCESS")
        .map((r) => r.confidence.level)
    : [];
  const rank = { LOW: 0, MEDIUM: 1, HIGH: 2 } as const;
  const overallConfidence = confidences.length
    ? confidences.reduce((worst, c) => (rank[c] < rank[worst] ? c : worst))
    : null;

  async function handleRun() {
    await startRun({});
    navigate("/registration");
  }

  return (
    <div className="page">
      {/* HERO */}
      <div className="hero">
        <div className="hero-starfield" />
        <div className="hero-content">
          <div className="hero-eyebrow">● Chandrayaan-2 Multi-Sensor Analysis</div>
          <h1 className="hero-title">
            Multi-Modal Lunar<br />Image <span className="accent">Registration</span>
          </h1>
          <p className="hero-desc">
            Registering Chandrayaan-2 multi-sensor observations — TMC-Azimuth, TMC-Slope, IIRS and
            SAR — into a common OHRC lunar reference framework, with quantitative, independently
            validated accuracy at every stage.
          </p>
          <div className="hero-actions">
            <button className="btn btn-primary" onClick={handleRun} disabled={isPolling}>
              <IconPlay style={{ width: 14, height: 14 }} />
              {isPolling ? "ANALYSIS RUNNING…" : "RUN FULL ANALYSIS"}
            </button>
            <button className="btn btn-secondary" onClick={() => navigate("/dataset")}>
              EXPLORE DATASET
              <IconArrowRight style={{ width: 14, height: 14 }} />
            </button>
          </div>
        </div>
        <div className="hero-visual">
          {ohrcPreview ? (
            <img src={resolveAssetUrl(ohrcPreview) || ""} alt="OHRC reference" />
          ) : (
            <div className="image-empty">OHRC preview unavailable</div>
          )}
          <div className="hero-visual-frame" />
          <div className="hero-visual-label">
            <span>OHRC · REFERENCE FRAME</span>
            <span>ORBITER HIGH RESOLUTION CAMERA</span>
          </div>
        </div>
      </div>

      {/* STATUS STRIP */}
      <div className="grid grid-4 mt-24">
        <MetricCard
          label="Dataset Readiness"
          value={dataset ? (Object.values(dataset.readiness_report).every(Boolean) ? "READY" : "PARTIAL") : undefined}
          tone={dataset && Object.values(dataset.readiness_report).every(Boolean) ? "success" : "warning"}
          sub="5/5 sensors located & characterized"
        />
        <MetricCard
          label="Sensors Registered"
          value={summary ? `${successCount} / ${totalSensors}` : null}
          sub={summary ? "Latest run" : "No run yet"}
          tone={summary && successCount === totalSensors ? "success" : undefined}
        />
        <MetricCard
          label="Mean Checkpoint RMSE"
          value={meanRmse !== null ? formatPixels(meanRmse) : null}
          sub="Independent, held-out points"
        />
        <div className="metric-card">
          <div className="metric-label">Overall Confidence</div>
          <div className="mt-8">
            <ConfidencePill level={overallConfidence} />
          </div>
          <div className="metric-sub mt-8">{runId ? `Run ${runId.slice(0, 10)}…` : "No completed run"}</div>
        </div>
      </div>

      {error && (
        <div className="mt-24">
          <ErrorState title="Registration run reported an error" message={error} />
        </div>
      )}

      {/* SENSOR STRIP */}
      <div className="panel panel-padded mt-24">
        <div className="panel-header">
          <div>
            <div className="panel-title">Sensor Pipeline Status</div>
            <div className="panel-title-sub">
              All transformations are mapped into the OHRC reference frame — OHRC itself is never a
              source.
            </div>
          </div>
          <StatusPill tone={status === "RUNNING" ? "info" : status === "COMPLETE" ? "success" : "pending"}>
            {status === "RUNNING" ? "PROCESSING" : status === "COMPLETE" ? "COMPLETE" : "IDLE"}
          </StatusPill>
        </div>

        {loadError && <ErrorState title="Could not load dataset" message={loadError} />}
        {!dataset && !loadError && <Loader label="Loading dataset manifest…" />}

        {dataset && (
          <div className="grid grid-5">
            {Object.entries(dataset.manifest.sensors).map(([key, entry]) => {
              const res = summary?.sensor_results[key];
              const isRef = entry.role === "REFERENCE";
              return (
                <div key={key} className="panel panel-padded" style={{ background: "var(--bg-panel-raised)" }}>
                  <div className="flex justify-between items-center">
                    <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{key}</span>
                    {isRef ? (
                      <StatusPill tone="info">LOCKED</StatusPill>
                    ) : res ? (
                      <StatusPill tone={res.status === "SUCCESS" ? "success" : "error"}>{res.status}</StatusPill>
                    ) : (
                      <StatusPill tone="pending">PENDING</StatusPill>
                    )}
                  </div>
                  <div className="text-tertiary mt-8" style={{ fontSize: 11.5 }}>
                    {isRef ? "Reference frame" : entry.sensor_full_name}
                  </div>
                  {res?.status === "SUCCESS" && (
                    <div className="mono mt-12" style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
                      RMSE {formatPixels(res.metrics.checkpoint_rmse_final)} · {formatPercent(res.metrics.inlier_ratio)} inliers
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
