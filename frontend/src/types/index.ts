// INVINCIBLES - Type definitions
// Every field here mirrors an actual field returned by the FastAPI backend
// (see api/main.py, src/registration/pipeline.py, src/registration/dataset.py).
// Nothing here is speculative UI-only data.

export type SensorKey = "OHRC" | "TMC-Azimuth" | "TMC-Slope" | "IIRS" | "SAR";

export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW";

export interface SensorStats {
  sensor: string;
  filename: string;
  source_path: string;
  width: number;
  height: number;
  channels: number;
  dtype: string;
  min: number;
  max: number;
  mean: number;
  std: number;
  median: number;
  percentile_1: number;
  percentile_5: number;
  percentile_95: number;
  percentile_99: number;
  dynamic_range: number;
  histogram_32bin: number[];
  estimated_noise_sigma: number;
  approx_feature_density_per_10k_px: number;
  has_nan_or_inf: boolean;
  orientation: string;
  aspect_ratio: number;
  visual_contrast_std_over_mean: number;
  saturated_high_fraction: number | null;
  saturated_low_fraction: number | null;
  speckle_index_mean_cv?: number;
  unique_value_count?: number;
  behaves_as_categorical?: boolean;
}

export interface SensorManifestEntry {
  role: "REFERENCE" | "SOURCE";
  sensor_full_name: string;
  kind: string;
  file: string;
  sha256: string;
  stats: SensorStats;
  preview_url?: string;
}

export interface DatasetManifest {
  project: string;
  generated_at: string;
  reference_sensor: string;
  reference_locked: boolean;
  region_scope: string;
  sensors: Record<string, SensorManifestEntry>;
}

export interface ReadinessReport {
  OHRC: boolean;
  "TMC-Azimuth": boolean;
  "TMC-Slope": boolean;
  IIRS: boolean;
  SAR: boolean;
  phase_congruency_feasible: boolean;
  rift_feasible: boolean;
  fsc_gtm_feasible: boolean;
  subpixel_feasible: boolean;
  multiband_output_feasible: boolean;
}

export interface DatasetAnalysisResponse {
  manifest: DatasetManifest;
  readiness_report: ReadinessReport;
}

export interface RegistrationMetrics {
  n_keypoints_reference: number;
  n_keypoints_source: number;
  n_keypoints: number;
  n_candidate_matches: number;
  n_accepted_matches: number;
  n_fit_points: number;
  n_checkpoint_points: number;
  n_inliers: number;
  n_total_fit: number;
  inlier_ratio: number;
  transformation_model: string;
  transformation_matrix: number[][];
  model_selection_justification: string;
  checkpoint_rmse_before_refinement: number | null;
  checkpoint_rmse_after_local_refinement: number | null;
  checkpoint_rmse_final: number | null;
  checkpoint_rmse_improvement_px: number | null;
  valid_pixel_fraction: number;
}

export interface ConfidenceFactor {
  0: "PASS" | "WEAK";
  1: string;
}

export interface Confidence {
  level: ConfidenceLevel;
  score: number;
  max_score: number;
  factors: [string, string][];
}

export interface GridDistribution {
  grid_size: number;
  counts: number[][];
  min_cell_count: number;
  max_cell_count: number;
  mean_cell_count: number;
  std_cell_count: number;
  coverage_percentage: number;
  empty_cell_percentage: number;
}

export interface AreaBasedFallback {
  pts_used?: number;
  method: string;
  quality: number;
  notes: string;
  ncc_threshold_used: number | null;
  n_correspondences: number;
  mean_ncc_score: number;
}

export interface SensorRegistrationSuccess {
  status: "SUCCESS";
  sensor: string;
  processing_time_sec: number;
  preprocessing_method: string;
  descriptor_method: string;
  descriptor_deviation_reason: string | null;
  correspondence_method?: string;
  area_based_fallback?: AreaBasedFallback | null;
  coarse_alignment: Record<string, unknown>;
  sensor_evidence_description: string;
  keypoint_grid_distribution: {
    reference: GridDistribution;
    source: GridDistribution;
    inliers: GridDistribution;
  };
  local_refinement: { used: boolean; residual_coefficient_of_variation: number };
  metrics: RegistrationMetrics;
  confidence: Confidence;
  diagnostics_dir: string;
  matches_dir: string;
}

export interface SensorRegistrationFailure {
  status: "FAILED";
  failed_stage: string;
  failure_reason: string;
  [key: string]: unknown;
}

export type SensorRegistrationResult = SensorRegistrationSuccess | SensorRegistrationFailure;

export interface FusionLayerMeta {
  role: string;
  interpolation: string;
  dtype: string;
  shape: number[];
  valid_pixel_fraction: number;
}

export interface FusionOutput {
  npz_path: string;
  metadata: {
    reference_sensor: string;
    layers: Record<string, FusionLayerMeta>;
  };
  composite_path?: string | null;
  comparison_paths?: Record<string, string>;
}

export interface RunSummary {
  project: string;
  run_id: string;
  generated_at: string;
  dataset_manifest: DatasetManifest;
  readiness_report: ReadinessReport;
  sensor_results: Record<string, SensorRegistrationResult>;
  fusion_output: FusionOutput;
  run_dir: string;
  cached: boolean;
}

export interface RegisterStartResponse {
  run_id: string;
  status: "STARTED" | "COMPLETE";
  cached: boolean;
  poll_url?: string;
}

export interface RegistrationStatusResponse {
  run_id: string;
  status: "RUNNING" | "COMPLETE" | "ERROR";
  cached: boolean;
}

export interface RunHistoryEntry {
  run_id: string;
  generated_at: string;
  reference_sensor: string;
  sensors_succeeded: string[];
  sensors_failed: string[];
  mean_checkpoint_rmse: number | null;
  mean_inlier_ratio: number | null;
  overall_confidence: ConfidenceLevel | null;
  status: string;
}

export interface RunHistoryResponse {
  runs: RunHistoryEntry[];
}

export interface SensorImageSet {
  reference_analysis_view?: string;
  source_analysis_view?: string;
  reference_phase_congruency?: string;
  source_phase_congruency?: string;
  before_coarse_alignment?: string;
  after_coarse_alignment?: string;
  warped_registered?: string;
  valid_mask?: string;
  checkerboard?: string;
  global_residual_map?: string;
  local_refinement_residual_map?: string;
  candidate_matches?: string;
  inlier_matches?: string;
  multiband_layer_preview?: string;
  comparison_strip?: string;
  original_input?: string;
  composite_registered?: string;
}

export type RegistrationImagesResponse = Record<string, SensorImageSet>;

export interface LunarAIReport {
  scientific_summary: string[];
  detected_features: Record<string, { keypoints_detected: number; accepted_matches: number; inliers: number; classification: string }>;
  regions_of_interest: unknown[];
  sensor_contributions: Record<string, { evidence: string; classification: string }>;
  cross_sensor_observations: { sensor: string; observation: string; confidence: string }[];
  registration_quality: Record<string, unknown>;
  evidence: string;
  confidence_overall: ConfidenceLevel;
  limitations: string[];
  recommended_further_analysis: string[];
}

export interface ExplainRegionResponse {
  roi: { x: number; y: number; radius: number };
  what_is_observed: string;
  sensor_contributions: { sensor: string; evidence: string; registration_confidence?: string; classification: string }[];
  morphological_characteristics: string;
  cross_sensor_evidence: unknown[];
  possible_interpretation: string;
  confidence: string;
  limitations: string;
}

export interface CompareSensorsResponse {
  chain: { sensor: string; role?: string; status?: string; confidence?: string | null; checkpoint_rmse?: number | null }[];
  cross_sensor_interpretation: string;
}

export interface AskLunarAIResponse {
  answer: string;
  engine: string;
  grounded_in?: string;
  engine_error?: string;
}
