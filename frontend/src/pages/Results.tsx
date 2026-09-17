import { useEffect, useState } from "react";
import { useRun } from "../context/RunContext";
import { registrationApi } from "../api/registration";
import { resolveAssetUrl } from "../api/client";
import { MetricCard, ConfidencePill, StatusPill, ImageFrame, EmptyState, Loader, ErrorState } from "../components/common/Primitives";
import { CompareSlider } from "../components/common/CompareSlider";
import type { RegistrationImagesResponse } from "../types";
import { formatNumber, formatPercent, formatPixels } from "../utils/format";

export default function Results() {
  const { runId, summary } = useRun();
  const [images, setImages] = useState<RegistrationImagesResponse | null>(null);
  const [sensor, setSensor] = useState("");
  const [compositeData, setCompositeData] = useState<{
    available: boolean;
    url: string | null;
    channels?: Record<string, string>;
    description?: string;
  } | null>(null);

  useEffect(() => {
    if (!runId) return;
    registrationApi
      .images(runId)
      .then((imgs) => {
        setImages(imgs);
        const first = Object.keys(imgs).find((k) => k !== "OHRC" && k !== "COMPOSITE");
        if (first) setSensor(first);
      })
      .catch(() => {});

    registrationApi
      .composite(runId)
      .then(setCompositeData)
      .catch(() => {});
  }, [runId]);

  if (!runId) {
    return (
      <div className="page">
        <Header />
        <EmptyState title="No results yet" desc="Run a full analysis from Mission Control to see registration results here." />
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="page">
        <Header />
        <Loader label="Loading registration results…" />
      </div>
    );
  }

  const sensorKeys = Object.keys(summary.sensor_results);
  const res = summary.sensor_results[sensor];
  const set = images?.[sensor];
  const ohrcLayer = images?.["OHRC"]?.multiband_layer_preview || images?.["OHRC"]?.original_input;
  const compositeUrl = compositeData?.url || images?.["COMPOSITE"]?.composite_registered;

  return (
    <div className="page">
      <Header />

      {/* =========================================================================
          SECTION 1: OVERALL COMPOSITE REGISTERED MULTI-SENSOR IMAGE
          ========================================================================= */}
      <div className="panel panel-padded" style={{ border: "1px solid rgba(79, 209, 232, 0.25)", background: "linear-gradient(180deg, rgba(13, 19, 27, 0.95) 0%, rgba(8, 11, 16, 0.98) 100%)" }}>
        <div className="flex justify-between items-center" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <div className="flex items-center gap-8">
              <span className="badge" style={{ background: "rgba(79, 209, 232, 0.15)", color: "var(--accent-cyan)", border: "1px solid rgba(79, 209, 232, 0.3)" }}>
                OVERALL MULTI-BAND FUSION
              </span>
              <div className="panel-title" style={{ fontSize: 16 }}>Composite Registered Image</div>
            </div>
            <div className="panel-title-sub mt-4">
              All multi-sensor layers warped and geometrically aligned to the sub-metre OHRC optical reference frame.
            </div>
          </div>
          {compositeUrl && (
            <a
              href={resolveAssetUrl(compositeUrl) || "#"}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              View Full Resolution ↗
            </a>
          )}
        </div>

        {/* Band Channel Legend */}
        <div className="flex items-center gap-12 mt-12" style={{ flexWrap: "wrap", padding: "8px 12px", background: "rgba(0,0,0,0.3)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-hairline)" }}>
          <span style={{ fontSize: 11.5, color: "var(--text-tertiary)", fontWeight: 600 }}>FALSE-COLOR CHANNELS:</span>
          <span style={{ fontSize: 12, color: "#ff6b6b", display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ff6b6b" }} />
            <strong>R:</strong> OHRC (Sub-metre Optical Ref)
          </span>
          <span style={{ fontSize: 12, color: "#51cf66", display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#51cf66" }} />
            <strong>G:</strong> IIRS (Infrared Spectral) / TMC-Slope
          </span>
          <span style={{ fontSize: 12, color: "#4dabf7", display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#4dabf7" }} />
            <strong>B:</strong> SAR (Radar Backscatter) / TMC-Azimuth
          </span>
        </div>

        <div className="mt-16" style={{ maxWidth: 860, margin: "16px auto 0" }}>
          {compositeUrl ? (
            <div style={{ position: "relative", borderRadius: "var(--radius-md)", overflow: "hidden", border: "1px solid var(--border-subtle)", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}>
              <img
                src={resolveAssetUrl(compositeUrl) || ""}
                alt="Composite Registered False-Color Output"
                style={{ width: "100%", height: "auto", display: "block" }}
              />
              <div style={{ padding: "8px 12px", background: "rgba(8, 11, 16, 0.9)", fontSize: 11.5, color: "var(--text-secondary)", borderTop: "1px solid var(--border-hairline)", display: "flex", justifyContent: "space-between" }}>
                <span>Aligned Spatial Reference: <strong>OHRC (Fixed Frame)</strong></span>
                <span>Format: <strong>Multi-Band False-Color Composite + Safe NPZ Stack</strong></span>
              </div>
            </div>
          ) : (
            <div className="image-empty" style={{ minHeight: 220 }}>
              Composite image will be available once full multi-sensor registration runs.
            </div>
          )}
        </div>
      </div>

      {/* =========================================================================
          SECTION 2: PER-SENSOR DETAILED ACCURACY & INDIVIDUAL COMPARISON
          ========================================================================= */}
      <div className="flex justify-between items-center mt-32" style={{ marginBottom: 12 }}>
        <div>
          <div className="section-title" style={{ marginBottom: 2 }}>Sensor Registration Analysis</div>
          <div style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
            Inspect raw input vs registered output, checkpoint RMSE accuracy, and geometric correspondences per sensor.
          </div>
        </div>
      </div>

      <div className="tabs">
        {sensorKeys.map((s) => {
          const r = summary.sensor_results[s];
          return (
            <div key={s} className={`tab${sensor === s ? " active" : ""}`} onClick={() => setSensor(s)}>
              {s} {r.status === "FAILED" ? "⚠" : ""}
            </div>
          );
        })}
      </div>

      {!res && <ErrorState title="Sensor not found" message="Select a sensor tab above." />}

      {res?.status === "FAILED" && (
        <div className="panel panel-padded">
          <div className="panel-header">
            <div className="panel-title">{sensor} → OHRC</div>
            <StatusPill tone="error">FAILED</StatusPill>
          </div>
          <p style={{ fontSize: 13.5 }}>
            Registration was not accepted for this sensor. The pipeline stopped rather than
            produce an unreliable result (honest failure over silent degradation).
          </p>
          <div className="state-code mt-16">
            Stage: {(res as { failed_stage?: string }).failed_stage}
            {"\n"}Reason: {(res as { failure_reason?: string }).failure_reason}
          </div>
        </div>
      )}

      {res?.status === "SUCCESS" && (
        <>
          <div className="flex justify-between items-center mt-8" style={{ marginBottom: 16 }}>
            <div className="section-title" style={{ marginBottom: 0 }}>{sensor} → OHRC Registration</div>
            <ConfidencePill level={res.confidence.level} />
          </div>

          {/* Quantitative Metrics Grid */}
          <div className="grid grid-4">
            <MetricCard label="Detected Features" value={formatNumber(res.metrics.n_keypoints)} tooltip="Total keypoints detected across reference and source (phase-congruency based, multiscale)." />
            <MetricCard label="Accepted Correspondences" value={formatNumber(res.metrics.n_accepted_matches)} tooltip="Correspondences passing ratio test + mutual cross-check (or area-based NCC fallback)." />
            <MetricCard label="Inliers" value={`${formatNumber(res.metrics.n_inliers)} / ${formatNumber(res.metrics.n_total_fit)}`} tooltip="Correspondences consistent with the FSC-estimated transformation." />
            <MetricCard label="Inlier Ratio" value={formatPercent(res.metrics.inlier_ratio)} />
          </div>

          <div className="grid grid-4 mt-16">
            <MetricCard label="Checkpoint RMSE (before)" value={formatPixels(res.metrics.checkpoint_rmse_before_refinement)} />
            <MetricCard label="Checkpoint RMSE (refined)" value={formatPixels(res.metrics.checkpoint_rmse_after_local_refinement)} />
            <MetricCard
              label="Final Checkpoint RMSE"
              value={formatPixels(res.metrics.checkpoint_rmse_final)}
              tone={res.confidence.level === "HIGH" ? "success" : res.confidence.level === "MEDIUM" ? "warning" : "error"}
              tooltip="Root Mean Square Error measured on independent checkpoint correspondences never used to fit the transform."
            />
            <MetricCard label="Transformation Model" value={res.metrics.transformation_model.toUpperCase()} sub={res.metrics.model_selection_justification.slice(0, 60) + "…"} />
          </div>

          {/* =========================================================================
              TRIPLE FORENSIC COMPARISON: RAW INPUT vs OHRC REFERENCE vs WARPED REGISTERED
              ========================================================================= */}
          <div className="panel panel-padded mt-24">
            <div className="panel-header">
              <div>
                <div className="panel-title">Forensic Visual Comparison: Input vs Target vs Registered</div>
                <div className="panel-title-sub mt-4">
                  Direct spatial comparison showing the raw unregistered source sensor, the fixed OHRC reference frame, and the registered output.
                </div>
              </div>
              <span className="badge" style={{ background: "rgba(71, 209, 140, 0.1)", color: "var(--status-success)" }}>
                VALID COVERAGE: {formatPercent(res.metrics.valid_pixel_fraction)}
              </span>
            </div>

            <div className="grid grid-3 mt-16" style={{ gap: 16 }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#6c8ef5", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                  <span>1. RAW INPUT ({sensor})</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>UNREGISTERED</span>
                </div>
                <ImageFrame
                  src={resolveAssetUrl(set?.original_input || set?.source_analysis_view)}
                  label={`${sensor} (Native Frame)`}
                  aspect="1 / 1"
                  empty="Original input image not available."
                />
              </div>

              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#51cf66", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                  <span>2. OHRC REFERENCE</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>LOCKED TARGET</span>
                </div>
                <ImageFrame
                  src={resolveAssetUrl(ohrcLayer || set?.reference_analysis_view)}
                  label="OHRC (Target Frame)"
                  aspect="1 / 1"
                  empty="OHRC reference not available."
                />
              </div>

              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent-cyan)", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                  <span>3. REGISTERED RESULT</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>WARPED TO OHRC</span>
                </div>
                <ImageFrame
                  src={resolveAssetUrl(set?.warped_registered)}
                  label={`${sensor} (Warped Aligned)`}
                  aspect="1 / 1"
                  empty="Warped registered image not available."
                />
              </div>
            </div>

            {/* Generated Comparison Strip Banner (if available) */}
            {set?.comparison_strip && (
              <div className="mt-16 pt-16" style={{ borderTop: "1px solid var(--border-hairline)" }}>
                <div className="flex justify-between items-center mb-8">
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)" }}>
                    Side-by-Side Comparison Strip (High-Definition Export):
                  </span>
                  <a
                    href={resolveAssetUrl(set.comparison_strip) || "#"}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: 11.5, color: "var(--accent-cyan)" }}
                  >
                    Open Strip ↗
                  </a>
                </div>
                <div style={{ borderRadius: "var(--radius-sm)", overflow: "hidden", border: "1px solid var(--border-subtle)" }}>
                  <img
                    src={resolveAssetUrl(set.comparison_strip) || ""}
                    alt={`Side-by-side comparison for ${sensor}`}
                    style={{ width: "100%", height: "auto", display: "block" }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* =========================================================================
              INTERACTIVE BEFORE / AFTER SLIDER
              ========================================================================= */}
          <div className="panel panel-padded mt-24">
            <div className="panel-title">Interactive Alignment Inspection (Before vs After)</div>
            <div className="panel-title-sub mt-4" style={{ marginBottom: 14 }}>
              Drag the slider to compare the original unregistered input against the final warped output aligned to the OHRC reference grid.
            </div>
            {set?.source_analysis_view && set?.warped_registered ? (
              <div className="mt-12">
                <CompareSlider
                  beforeSrc={resolveAssetUrl(set.original_input || set.source_analysis_view) || ""}
                  afterSrc={resolveAssetUrl(set.warped_registered) || ""}
                  beforeLabel="ORIGINAL INPUT (NATIVE FRAME)"
                  afterLabel="REGISTERED (WARPED TO OHRC)"
                />
              </div>
            ) : (
              <ImageFrame src={null} empty="Before/after comparison not available." />
            )}
          </div>

          {/* =========================================================================
              CHECKERBOARD & MATCH CORRESPONDENCES
              ========================================================================= */}
          <div className="grid grid-2 mt-24">
            <div className="panel panel-padded">
              <div className="panel-title">Checkerboard Validation</div>
              <div className="panel-title-sub mt-4" style={{ marginBottom: 12 }}>
                Interleaved tiles of OHRC and registered {sensor}. Continuous edge contours across tile borders verify sub-pixel alignment.
              </div>
              <ImageFrame
                src={resolveAssetUrl(set?.checkerboard)}
                label={`OHRC vs ${sensor} (CHECKERBOARD)`}
                empty="Checkerboard not available."
                aspect="1 / 1"
              />
            </div>

            <div className="panel panel-padded">
              <div className="panel-title">Inlier Feature Correspondences</div>
              <div className="panel-title-sub mt-4" style={{ marginBottom: 12 }}>
                Geometrically verified inlier ties ({res.metrics.n_inliers} points) selected by FSC consensus to compute the {res.metrics.transformation_model} transform.
              </div>
              <ImageFrame
                src={resolveAssetUrl(set?.inlier_matches || set?.candidate_matches)}
                label={`OHRC ↔ ${sensor} Inlier Matches`}
                empty="Inlier match plot not available."
                aspect="1 / 1"
              />
            </div>
          </div>

          {/* =========================================================================
              CONFIDENCE FACTORS & PIPELINE EVIDENCE
              ========================================================================= */}
          <div className="grid grid-2 mt-24">
            <div className="panel panel-padded">
              <div className="panel-title">Confidence Factors</div>
              <div className="factor-list mt-12">
                {res.confidence.factors.map((f, i) => (
                  <div key={i} className="factor-item">
                    <span className={`flag ${f[0] === "PASS" ? "pass" : "weak"}`}>{f[0]}</span>
                    <span>{f[1]}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel panel-padded">
              <div className="panel-title">Registration Engine Diagnostics</div>
              <p className="mt-12" style={{ fontSize: 13 }}>
                <strong style={{ color: "var(--text-primary)" }}>Descriptor Method: </strong>
                {res.descriptor_method}
              </p>
              {res.descriptor_deviation_reason && (
                <p className="mt-8" style={{ fontSize: 12.5 }}>{res.descriptor_deviation_reason}</p>
              )}
              {res.area_based_fallback && (
                <p className="mt-8" style={{ fontSize: 12.5 }}>
                  <strong style={{ color: "var(--text-primary)" }}>Area-based fallback: </strong>
                  {res.area_based_fallback.notes.split("|")[0]}
                </p>
              )}
              <p className="mt-8" style={{ fontSize: 12.5 }}>
                <strong style={{ color: "var(--text-primary)" }}>Local terrain refinement: </strong>
                {res.local_refinement.used ? "Applied" : "Not needed"} (residual CoV: {res.local_refinement.residual_coefficient_of_variation.toFixed(3)})
              </p>
              <p className="mt-8" style={{ fontSize: 12.5 }}>
                <strong style={{ color: "var(--text-primary)" }}>Transformation justification: </strong>
                {res.metrics.model_selection_justification}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Header() {
  return (
    <div className="page-header">
      <div>
        <span className="page-eyebrow">Results & Multi-Band Output</span>
        <h1 className="page-title">Registration & Fusion Output</h1>
        <p className="page-subtitle">
          Quantitative, independently validated accuracy for every source sensor with composite multi-sensor fusion.
        </p>
      </div>
    </div>
  );
}
