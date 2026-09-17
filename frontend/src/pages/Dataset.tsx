import { useEffect, useState } from "react";
import { datasetApi } from "../api/dataset";
import type { DatasetAnalysisResponse } from "../types";
import { Loader, ErrorState, StatusPill } from "../components/common/Primitives";
import { SensorCard } from "../components/common/SensorCard";
import { formatDate } from "../utils/format";

const SENSOR_ORDER = ["OHRC", "TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"];

export default function Dataset() {
  const [data, setData] = useState<DatasetAnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    setError(null);
    datasetApi
      .getAnalysis()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load dataset."))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <span className="page-eyebrow">Dataset</span>
          <h1 className="page-title">Multi-Sensor Lunar Dataset</h1>
          <p className="page-subtitle">
            Five sensor layers of a single Chandrayaan-2 demonstration region. OHRC is the fixed
            reference frame — it can never be selected as a source.
          </p>
        </div>
        {data && (
          <StatusPill tone={Object.values(data.readiness_report).every(Boolean) ? "success" : "warning"}>
            {Object.values(data.readiness_report).every(Boolean) ? "ALL SYSTEMS READY" : "PARTIAL READINESS"}
          </StatusPill>
        )}
      </div>

      {loading && <Loader label="Fetching dataset manifest from backend…" />}
      {error && <ErrorState title="Unable to retrieve dataset" message={error} onRetry={load} />}

      {data && (
        <>
          <div className="grid grid-5">
            {SENSOR_ORDER.filter((k) => data.manifest.sensors[k]).map((key) => (
              <SensorCard key={key} sensorKey={key} entry={data.manifest.sensors[key]} />
            ))}
          </div>

          <div className="panel panel-padded mt-24">
            <div className="panel-header">
              <div className="panel-title">Technical Readiness Report</div>
            </div>
            <div className="grid grid-3">
              {Object.entries(data.readiness_report).map(([key, ok]) => (
                <div key={key} className="flex justify-between items-center" style={{ padding: "10px 4px", borderBottom: "1px solid var(--border-hairline)" }}>
                  <span className="mono" style={{ fontSize: 12.5 }}>{key.replace(/_/g, " ")}</span>
                  <StatusPill tone={ok ? "success" : "error"}>{ok ? "OK" : "BLOCKED"}</StatusPill>
                </div>
              ))}
            </div>
          </div>

          <div className="panel panel-padded mt-24">
            <div className="panel-title">Manifest Metadata</div>
            <div className="grid grid-3 mt-12">
              <div>
                <div className="metric-label">Reference Sensor</div>
                <div className="mono mt-8" style={{ fontSize: 15 }}>{data.manifest.reference_sensor}</div>
              </div>
              <div>
                <div className="metric-label">Region Scope</div>
                <div className="mt-8" style={{ fontSize: 13.5 }}>{data.manifest.region_scope}</div>
              </div>
              <div>
                <div className="metric-label">Manifest Generated</div>
                <div className="mt-8" style={{ fontSize: 13.5 }}>{formatDate(data.manifest.generated_at)}</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
