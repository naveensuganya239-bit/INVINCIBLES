import { useEffect, useState } from "react";
import { useRun } from "../context/RunContext";
import { registrationApi } from "../api/registration";
import { datasetApi } from "../api/dataset";
import { resolveAssetUrl } from "../api/client";
import { Tabs, ImageFrame, Loader, ErrorState, EmptyState } from "../components/common/Primitives";
import { CompareSlider } from "../components/common/CompareSlider";
import type { RegistrationImagesResponse, DatasetManifest } from "../types";

const VIEW_TABS = [
  { key: "original", label: "ORIGINAL" },
  { key: "preprocessed", label: "PREPROCESSED" },
  { key: "phase_congruency", label: "PHASE CONGRUENCY" },
  { key: "coarse_alignment", label: "COARSE ALIGNMENT" },
];

export default function FeatureAnalysis() {
  const { runId, summary } = useRun();
  const [images, setImages] = useState<RegistrationImagesResponse | null>(null);
  const [manifest, setManifest] = useState<DatasetManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sensor, setSensor] = useState<string>("");
  const [view, setView] = useState("original");

  useEffect(() => {
    if (!runId) return;
    registrationApi
      .images(runId)
      .then((imgs) => {
        setImages(imgs);
        const first = Object.keys(imgs).find((k) => k !== "OHRC");
        if (first) setSensor(first);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load images."));
    datasetApi.getDataset().then(setManifest).catch(() => {});
  }, [runId]);

  if (!runId) {
    return (
      <div className="page">
        <PageHeader />
        <EmptyState title="No analysis run selected" desc="Run or select an analysis from Mission Control / Run History to inspect feature-extraction diagnostics." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <PageHeader />
        <ErrorState title="Could not load diagnostic images" message={error} />
      </div>
    );
  }

  if (!images || !summary) {
    return (
      <div className="page">
        <PageHeader />
        <Loader label="Loading diagnostic imagery…" />
      </div>
    );
  }

  const sensors = Object.keys(images).filter((k) => k !== "OHRC");
  const set = images[sensor];
  const rawOriginal = manifest?.sensors[sensor]?.preview_url;

  return (
    <div className="page">
      <PageHeader />
      <div className="tabs">
        {sensors.map((s) => (
          <div key={s} className={`tab${sensor === s ? " active" : ""}`} onClick={() => setSensor(s)}>
            {s}
          </div>
        ))}
      </div>

      <Tabs tabs={VIEW_TABS} active={view} onChange={setView} />

      <div className="panel panel-padded">
        {view === "original" && (
          <div className="grid grid-2">
            <ImageFrame src={resolveAssetUrl(rawOriginal)} label={`${sensor} · RAW`} aspect="0.85 / 1" />
            <ImageFrame src={resolveAssetUrl("/static/data/OHRC.png")} label="OHRC · RAW REFERENCE" aspect="0.85 / 1" />
          </div>
        )}
        {view === "preprocessed" && (
          <div className="grid grid-2">
            <ImageFrame src={resolveAssetUrl(set?.source_analysis_view)} label={`${sensor} · ANALYSIS VIEW`} aspect="0.85 / 1" />
            <ImageFrame src={resolveAssetUrl(set?.reference_analysis_view)} label="OHRC · ANALYSIS VIEW" aspect="0.85 / 1" />
          </div>
        )}
        {view === "phase_congruency" && (
          <div className="grid grid-2">
            <ImageFrame src={resolveAssetUrl(set?.source_phase_congruency)} label={`${sensor} · PHASE CONGRUENCY`} aspect="0.85 / 1" />
            <ImageFrame src={resolveAssetUrl(set?.reference_phase_congruency)} label="OHRC · PHASE CONGRUENCY" aspect="0.85 / 1" />
          </div>
        )}
        {view === "coarse_alignment" && (
          <>
            {set?.before_coarse_alignment && set?.after_coarse_alignment ? (
              <CompareSlider
                beforeSrc={resolveAssetUrl(set.before_coarse_alignment) || ""}
                afterSrc={resolveAssetUrl(set.after_coarse_alignment) || ""}
                beforeLabel="BEFORE COARSE ALIGNMENT"
                afterLabel="AFTER COARSE ALIGNMENT"
              />
            ) : (
              <ImageFrame src={null} empty="Coarse alignment diagnostic not available for this sensor." />
            )}
          </>
        )}
      </div>

      {summary.sensor_results[sensor]?.status === "SUCCESS" && (
        <div className="panel panel-padded mt-24">
          <div className="panel-title">Descriptor & Preprocessing Notes</div>
          <p className="mt-12" style={{ fontSize: 13 }}>
            <strong style={{ color: "var(--text-primary)" }}>Preprocessing: </strong>
            {(summary.sensor_results[sensor] as { preprocessing_method: string }).preprocessing_method}
          </p>
          <p className="mt-8" style={{ fontSize: 13 }}>
            <strong style={{ color: "var(--text-primary)" }}>Descriptor method: </strong>
            {(summary.sensor_results[sensor] as { descriptor_method: string }).descriptor_method}
          </p>
        </div>
      )}
    </div>
  );
}

function PageHeader() {
  return (
    <div className="page-header">
      <div>
        <span className="page-eyebrow">Feature Analysis</span>
        <h1 className="page-title">Feature Extraction Workspace</h1>
        <p className="page-subtitle">
          Original, preprocessed, phase-congruency and coarse-alignment representations, as
          actually generated by the backend for the selected run.
        </p>
      </div>
    </div>
  );
}
