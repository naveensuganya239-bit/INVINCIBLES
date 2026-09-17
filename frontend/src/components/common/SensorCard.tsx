import { Badge } from "./Primitives";
import { IconLock } from "./Icons";
import type { SensorManifestEntry } from "../../types";
import { resolveAssetUrl } from "../../api/client";

export function SensorCard({ sensorKey, entry }: { sensorKey: string; entry: SensorManifestEntry }) {
  const isReference = entry.role === "REFERENCE";
  const s = entry.stats;
  return (
    <div className={`sensor-card${isReference ? " reference" : ""}`}>
      <div className="sensor-thumb">
        <div className="role-tag">
          {isReference ? (
            <Badge locked>
              <span className="flex items-center gap-8">
                <IconLock style={{ width: 10, height: 10 }} /> REFERENCE · LOCKED
              </span>
            </Badge>
          ) : (
            <Badge>SOURCE</Badge>
          )}
        </div>
        <img src={resolveAssetUrl(entry.preview_url) || ""} alt={sensorKey} loading="lazy" />
      </div>
      <div className="sensor-body">
        <div>
          <div className="sensor-name">{sensorKey}</div>
          <div className="sensor-fullname">{entry.sensor_full_name}</div>
        </div>
        <div className="sensor-stats">
          <span className="sensor-stat-label">Dimensions</span>
          <span className="sensor-stat-value">{s.width} × {s.height}</span>
          <span className="sensor-stat-label">Channels</span>
          <span className="sensor-stat-value">{s.channels}</span>
          <span className="sensor-stat-label">Dtype</span>
          <span className="sensor-stat-value">{s.dtype}</span>
          <span className="sensor-stat-label">Mean / Std</span>
          <span className="sensor-stat-value">{s.mean.toFixed(1)} / {s.std.toFixed(1)}</span>
          <span className="sensor-stat-label">Noise σ</span>
          <span className="sensor-stat-value">{s.estimated_noise_sigma.toFixed(2)}</span>
          {s.speckle_index_mean_cv !== undefined && (
            <>
              <span className="sensor-stat-label">Speckle CV</span>
              <span className="sensor-stat-value">{s.speckle_index_mean_cv.toFixed(3)}</span>
            </>
          )}
          {s.behaves_as_categorical !== undefined && (
            <>
              <span className="sensor-stat-label">Terrain type</span>
              <span className="sensor-stat-value">{s.behaves_as_categorical ? "Categorical" : "Continuous"}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
