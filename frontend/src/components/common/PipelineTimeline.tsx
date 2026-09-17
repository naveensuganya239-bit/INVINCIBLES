import { IconCheck } from "./Icons";

export interface TimelineStageState {
  label: string;
  state: "pending" | "active" | "done" | "failed";
}

export function PipelineTimeline({ stages }: { stages: TimelineStageState[] }) {
  return (
    <div className="timeline">
      {stages.map((stage, i) => (
        <div key={stage.label} className={`timeline-step ${stage.state}`}>
          <span className="timeline-index mono">{String(i + 1).padStart(2, "0")}</span>
          <span className="timeline-icon">
            {stage.state === "done" ? <IconCheck style={{ width: 12, height: 12 }} /> : stage.state === "failed" ? "✕" : stage.state === "active" ? "→" : "○"}
          </span>
          <span className="timeline-label">{stage.label}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Maps the ACTUAL backend pipeline stage sequence (src/registration/pipeline.py)
 * to a display list. If a sensor result carries `failed_stage`, everything up
 * to that stage is marked done, the failing stage is marked failed, and
 * later stages stay pending — this is not a fake progress bar, it reflects
 * exactly what the backend reported.
 */
const PIPELINE_STAGE_ORDER = [
  { key: "INPUT_VALIDATION", label: "Input validation" },
  { key: "PREPROCESSING", label: "Sensor-aware preprocessing" },
  { key: "PHASE_CONGRUENCY", label: "Phase congruency (illumination-invariant features)" },
  { key: "KEYPOINT_DETECTION", label: "Keypoint detection + ANMS" },
  { key: "COARSE_ALIGNMENT", label: "Coarse geometric alignment" },
  { key: "DESCRIPTOR_EXTRACTION", label: "Multi-modal descriptor (RIFT / CFOG / area-based)" },
  { key: "FEATURE_MATCHING", label: "Feature matching" },
  { key: "ROBUST_OUTLIER_REJECTION", label: "Robust outlier rejection (FSC)" },
  { key: "INDEPENDENT_VALIDATION_SPLIT", label: "Independent checkpoint split" },
  { key: "TRANSFORMATION", label: "Transformation model selection" },
  { key: "LOCAL_REFINEMENT", label: "Local terrain-relief refinement" },
  { key: "SUBPIXEL_REFINEMENT", label: "Sub-pixel refinement" },
  { key: "WARPING", label: "Warping + checkerboard validation" },
  { key: "EVALUATION", label: "Quantitative evaluation + confidence" },
  { key: "OUTPUT", label: "Multi-sensor output" },
];

export function buildStagesForSensor(status?: string, failedStage?: string | null): TimelineStageState[] {
  if (status === "SUCCESS") {
    return PIPELINE_STAGE_ORDER.map((s) => ({ label: s.label, state: "done" as const }));
  }
  if (status === "FAILED" && failedStage) {
    const idx = PIPELINE_STAGE_ORDER.findIndex((s) => failedStage.includes(s.key));
    return PIPELINE_STAGE_ORDER.map((s, i) => ({
      label: s.label,
      state: idx === -1 ? "pending" : i < idx ? "done" : i === idx ? "failed" : "pending",
    }));
  }
  return PIPELINE_STAGE_ORDER.map((s) => ({ label: s.label, state: "pending" as const }));
}
