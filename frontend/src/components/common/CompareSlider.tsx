import { useState } from "react";

export function CompareSlider({
  beforeSrc,
  afterSrc,
  beforeLabel = "BEFORE",
  afterLabel = "AFTER",
}: {
  beforeSrc: string;
  afterSrc: string;
  beforeLabel?: string;
  afterLabel?: string;
}) {
  const [pos, setPos] = useState(50);

  return (
    <div className="compare-slider-wrap">
      <img src={beforeSrc} alt={beforeLabel} />
      <div className="compare-slider-overlay" style={{ width: `${pos}%` }}>
        <img src={afterSrc} alt={afterLabel} style={{ width: `${10000 / pos}%`, maxWidth: "none" }} />
      </div>
      <div className="compare-slider-handle" style={{ left: `${pos}%` }} />
      <input
        type="range"
        min={1}
        max={99}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        className="compare-slider-input"
        aria-label="Comparison slider"
      />
      <div className="image-frame-label" style={{ left: 8 }}>{afterLabel}</div>
      <div className="image-frame-label" style={{ left: "auto", right: 8 }}>{beforeLabel}</div>
    </div>
  );
}
