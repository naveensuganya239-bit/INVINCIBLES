import { useEffect, useState } from "react";
import { useRun } from "../context/RunContext";
import { registrationApi } from "../api/registration";
import { resolveAssetUrl } from "../api/client";
import { ImageFrame, Loader, ErrorState, EmptyState, Tabs } from "../components/common/Primitives";
import type { RegistrationImagesResponse } from "../types";
import { formatNumber, formatPercent } from "../utils/format";

const MATCH_VIEWS = [
  { key: "candidate", label: "CANDIDATE MATCHES" },
  { key: "inlier", label: "INLIER / OUTLIER CLASSIFICATION" },
];

export default function Correspondence() {
  const { runId, summary } = useRun();
  const [images, setImages] = useState<RegistrationImagesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sensor, setSensor] = useState("");
  const [view, setView] = useState("candidate");

  useEffect(() => {
    if (!runId) return;
    registrationApi
      .images(runId)
      .then((imgs) => {
        setImages(imgs);
        const first = Object.keys(imgs).find((k) => k !== "OHRC");
        if (first) setSensor(first);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load match images."));
  }, [runId]);

  if (!runId) {
    return (
      <div className="page">
        <Header />
        <EmptyState title="No analysis run selected" desc="Run an analysis to inspect candidate and inlier correspondences between OHRC and each source sensor." />
      </div>
    );
  }
  if (error) {
    return (
      <div className="page">
        <Header />
        <ErrorState title="Could not load correspondence images" message={error} />
      </div>
    );
  }
  if (!images || !summary) {
    return (
      <div className="page">
        <Header />
        <Loader label="Loading correspondence diagnostics…" />
      </div>
    );
  }

  const sensors = Object.keys(images).filter((k) => k !== "OHRC");
  const set = images[sensor];
  const res = summary.sensor_results[sensor];
  const activeImg = view === "candidate" ? set?.candidate_matches : set?.inlier_matches;

  return (
    <div className="page">
      <Header />
      <div className="tabs">
        {sensors.map((s) => (
          <div key={s} className={`tab${sensor === s ? " active" : ""}`} onClick={() => setSensor(s)}>
            {s}
          </div>
        ))}
      </div>

      {res?.status === "SUCCESS" && (
        <div className="grid grid-4 mt-16 mb-16" style={{ marginBottom: 20 }}>
          <MiniStat label="Keypoints (ref/src)" value={`${formatNumber(res.metrics.n_keypoints_reference)} / ${formatNumber(res.metrics.n_keypoints_source)}`} />
          <MiniStat label="Accepted Correspondences" value={formatNumber(res.metrics.n_accepted_matches)} />
          <MiniStat label="Inliers" value={`${formatNumber(res.metrics.n_inliers)} / ${formatNumber(res.metrics.n_total_fit)}`} />
          <MiniStat label="Inlier Ratio" value={formatPercent(res.metrics.inlier_ratio)} />
        </div>
      )}

      <Tabs tabs={MATCH_VIEWS} active={view} onChange={setView} />

      <div className="panel panel-padded">
        <div className="panel-title-sub mb-8" style={{ marginBottom: 10 }}>
          {view === "candidate"
            ? "OHRC (left) vs " + sensor + " (right) — all correspondences that passed the ratio test and mutual cross-check."
            : "Green = FSC inlier · Red = rejected outlier. Shown for the model-fitting subset used to estimate the transformation."}
        </div>
        <ImageFrame src={resolveAssetUrl(activeImg)} label={view === "candidate" ? "CANDIDATE MATCHES" : "INLIER / OUTLIER"} empty="Match visualization not available (registration may have failed before this stage)." aspect="1.85 / 1" />
      </div>

      {res?.status === "FAILED" && (
        <div className="state-code mt-16">
          Stage: {(res as { failed_stage?: string }).failed_stage} — {(res as { failure_reason?: string }).failure_reason}
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value mono" style={{ fontSize: 20 }}>{value}</div>
    </div>
  );
}

function Header() {
  return (
    <div className="page-header">
      <div>
        <span className="page-eyebrow">Correspondence</span>
        <h1 className="page-title">Match Analysis</h1>
        <p className="page-subtitle">
          Every line drawn corresponds to an actual computed correspondence — never fabricated for
          display.
        </p>
      </div>
    </div>
  );
}
