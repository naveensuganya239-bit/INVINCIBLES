import { useEffect, useState } from "react";
import { useRun } from "../context/RunContext";
import { registrationApi } from "../api/registration";
import { resolveAssetUrl } from "../api/client";
import { EmptyState, Loader } from "../components/common/Primitives";
import type { RegistrationImagesResponse } from "../types";
import { formatPercent } from "../utils/format";

const LAYER_COLORS: Record<string, string> = {
  OHRC: "#eef2f6",
  "TMC-Azimuth": "#f0b860",
  "TMC-Slope": "#f0716d",
  IIRS: "#47d18c",
  SAR: "#6c8ef5",
};

export default function MultiSensor() {
  const { runId, summary } = useRun();
  const [images, setImages] = useState<RegistrationImagesResponse | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [opacity, setOpacity] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!runId) return;
    registrationApi.images(runId).then((imgs) => {
      setImages(imgs);
      const initVis: Record<string, boolean> = {};
      const initOp: Record<string, number> = {};
      Object.keys(imgs).forEach((k) => {
        initVis[k] = true;
        initOp[k] = k === "OHRC" ? 100 : 65;
      });
      setVisible(initVis);
      setOpacity(initOp);
    });
  }, [runId]);

  if (!runId) {
    return (
      <div className="page">
        <Header />
        <EmptyState title="No multi-sensor output yet" desc="Run a full analysis to generate the co-registered multi-sensor stack." />
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="page">
        <Header />
        <Loader label="Loading multi-sensor output…" />
      </div>
    );
  }
  if (!images) {
    return (
      <div className="page">
        <Header />
        <Loader label="Loading layer previews…" />
      </div>
    );
  }

  const layerKeys = Object.keys(images).filter((k) => images[k].multiband_layer_preview);
  const layers = summary.fusion_output?.metadata?.layers || {};

  return (
    <div className="page">
      <Header />

      <div className="grid" style={{ gridTemplateColumns: "1fr 320px", gap: 24 }}>
        <div className="panel panel-padded">
          <div className="panel-title">Layered Composite</div>
          <div className="panel-title-sub mt-4" style={{ marginBottom: 14 }}>
            Purely visual overlay for inspection — the underlying multi-band archive preserves
            every sensor layer independently (see right).
          </div>
          <div
            style={{
              position: "relative",
              width: "100%",
              aspectRatio: "621 / 730",
              background: "var(--bg-void)",
              border: "1px solid var(--border-hairline)",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
            }}
          >
            {layerKeys.map((k) =>
              visible[k] ? (
                <img
                  key={k}
                  src={resolveAssetUrl(images[k].multiband_layer_preview) || ""}
                  alt={k}
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    opacity: (opacity[k] ?? 100) / 100,
                    mixBlendMode: k === "OHRC" ? "normal" : "screen",
                  }}
                />
              ) : null
            )}
          </div>
        </div>

        <div className="panel panel-padded">
          <div className="panel-title">Layers</div>
          <div className="flex-col gap-16 mt-16">
            {layerKeys.map((k) => {
              const meta = layers[k];
              const failed = summary.sensor_results[k]?.status === "FAILED";
              return (
                <div key={k}>
                  <div className="flex justify-between items-center">
                    <label className="flex items-center gap-8" style={{ fontSize: 12.5, fontWeight: 600 }}>
                      <input
                        type="checkbox"
                        checked={visible[k] ?? true}
                        onChange={(e) => setVisible((v) => ({ ...v, [k]: e.target.checked }))}
                      />
                      <span className="swatch" style={{ background: LAYER_COLORS[k] || "#fff", width: 8, height: 8, borderRadius: 2, display: "inline-block" }} />
                      {k}
                    </label>
                    {failed && <span className="badge">NOT REGISTERED</span>}
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={opacity[k] ?? 100}
                    onChange={(e) => setOpacity((o) => ({ ...o, [k]: Number(e.target.value) }))}
                    className="w-full mt-8"
                    disabled={!visible[k]}
                  />
                  {meta && (
                    <div className="mono text-tertiary" style={{ fontSize: 10.5, marginTop: 4 }}>
                      {meta.interpolation} · {formatPercent(meta.valid_pixel_fraction)} valid
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="panel panel-padded mt-24">
        <div className="panel-title">Co-Registered Multi-Sensor Data</div>
        <div className="table-wrap mt-12">
          <table className="data-table">
            <thead>
              <tr>
                <th>Band</th>
                <th>Sensor</th>
                <th>Role</th>
                <th>Interpolation</th>
                <th>Dtype</th>
                <th>Shape</th>
                <th>Valid Pixels</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(layers).map(([key, meta], i) => (
                <tr key={key}>
                  <td className="mono">{`Band ${i + 1}`}</td>
                  <td>{key}</td>
                  <td>{meta.role}</td>
                  <td>{meta.interpolation}</td>
                  <td className="mono">{meta.dtype}</td>
                  <td className="mono">{meta.shape.join(" × ")}</td>
                  <td>{formatPercent(meta.valid_pixel_fraction)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex justify-between items-center mt-16">
          <span className="text-tertiary mono" style={{ fontSize: 11.5 }}>
            {summary.fusion_output?.npz_path?.split("/").pop()}
          </span>
        </div>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div className="page-header">
      <div>
        <span className="page-eyebrow">Multi-Sensor</span>
        <h1 className="page-title">Multi-Sensor Lunar View</h1>
        <p className="page-subtitle">
          The final output preserves every sensor layer independently — this view demonstrates
          that, it does not collapse sensors into one decorative blend.
        </p>
      </div>
    </div>
  );
}
