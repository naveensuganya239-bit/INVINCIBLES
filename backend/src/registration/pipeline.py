"""
INVINCIBLES - Core Registration Pipeline (Spec Section 8, 31, 46, 53)
========================================================================
Orchestrates the full stage sequence for one SOURCE sensor against the
fixed OHRC REFERENCE:

RAW -> VALIDATION -> CHARACTERIZATION -> SENSOR-AWARE PREPROCESSING ->
MULTI-SCALE REPRESENTATION -> PHASE CONGRUENCY -> KEYPOINTS -> ANMS ->
COARSE ALIGNMENT -> MULTI-MODAL DESCRIPTOR (RIFT/CFOG) -> MATCHING ->
FSC CONSENSUS -> TRANSFORMATION MODEL SELECTION -> LOCAL REFINEMENT
ANALYSIS -> SUB-PIXEL REFINEMENT -> INDEPENDENT VALIDATION -> WARPING ->
CHECKERBOARD -> METRICS -> CONFIDENCE.

If any stage cannot produce a scientifically valid result, the pipeline
STOPS for that sensor and returns an honest FAILED status with the exact
stage and reason (Section 30, 53) rather than continuing to build on top
of an unreliable result.
"""
from __future__ import annotations
import os
import io
import json
import time
import hashlib
from datetime import datetime, timezone

import numpy as np
import cv2

from src.registration import dataset as ds
from src.preprocessing import sensor_preprocessing as pp
from src.features import scale_space, phase_congruency as pcmod, keypoints as kpmod, descriptors as descmod
from src.geometry import coarse_alignment as coarse, consensus, transformation as tf, local_refinement as lref, subpixel as spx, area_based_registration as abr
from src.geometry.residual_interp import interpolate_local_correction
from src.evaluation import metrics as evalm, warping as warpmod
from src.matching import matcher as matchmod

PROJECT_ROOT = None  # set by api layer / run_pipeline.py


def _sensor_evidence_text(sensor_key: str) -> str:
    table = {
        "TMC-Azimuth": "Terrain-direction (sun-azimuth-relative slope orientation) structural information.",
        "TMC-Slope": "Slope-magnitude derived terrain structural information.",
        "IIRS": "Spectral-band brightness structural information (no compositional interpretation).",
        "SAR": "Radar backscatter structural information, robust to solar illumination.",
    }
    return table.get(sensor_key, "Structural information.")


def _fail(stage: str, reason: str, extra: dict = None) -> dict:
    result = {"status": "FAILED", "failed_stage": stage, "failure_reason": reason}
    if extra:
        result.update(extra)
    return result


def _save_png(path, img):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if img.dtype != np.uint8:
        img = cv2.normalize(img.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    cv2.imwrite(path, img)


def _draw_matches(ref_gray, src_gray, pts_ref, pts_src, inlier_mask=None, max_lines=150):
    h = max(ref_gray.shape[0], src_gray.shape[0])
    canvas = np.zeros((h, ref_gray.shape[1] + src_gray.shape[1]), dtype=np.uint8)
    canvas[:ref_gray.shape[0], :ref_gray.shape[1]] = ref_gray
    canvas[:src_gray.shape[0], ref_gray.shape[1]:] = src_gray
    canvas_c = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    offset = ref_gray.shape[1]
    n = len(pts_ref)
    step = max(1, n // max_lines)
    for i in range(0, n, step):
        p1 = (int(pts_ref[i][0]), int(pts_ref[i][1]))
        p2 = (int(pts_src[i][0]) + offset, int(pts_src[i][1]))
        color = (0, 255, 0) if (inlier_mask is None or inlier_mask[i]) else (0, 0, 255)
        cv2.line(canvas_c, p1, p2, color, 1)
        cv2.circle(canvas_c, p1, 2, color, -1)
        cv2.circle(canvas_c, p2, 2, color, -1)
    return canvas_c


def _area_based_fallback(ref_gray: np.ndarray, src_gray: np.ndarray, coarse_result: dict):
    """
    Escalation path: SEPARATE dense area-based registration algorithm
    (src/geometry/area_based_registration.py), used automatically when
    sparse RIFT/CFOG keypoint-descriptor matching does not produce enough
    stable correspondences. Operates on the ORIGINAL (unenhanced)
    grayscale views rather than the CLAHE analysis view, because the
    gradient-magnitude representation this algorithm relies on is
    measurably cleaner on the untouched terrain-product values (CLAHE's
    local-contrast boosting can distort the smooth radial gradient around
    a crater rim). Returns a dict with pts_ref/pts_src/match_dist (in each
    image's own native pixel coordinates, exactly like the sparse path)
    plus diagnostic info, or None if this algorithm also fails to produce
    enough correspondences.
    """
    h_ref, w_ref = ref_gray.shape[:2]
    h_src, w_src = src_gray.shape[:2]

    matrix_ab, method_ab, quality_ab, notes_ab = abr.estimate_global_alignment(
        ref_gray, src_gray, coarse_result.get("matrix"), coarse_result, (h_ref, w_ref))

    src_resized = cv2.resize(src_gray, (w_ref, h_ref), interpolation=cv2.INTER_LINEAR)

    # Prefer a STRICTER NCC threshold and a larger, more distinctive patch
    # first (fewer but far more reliable correspondences after the
    # mutual forward/backward consistency check); only relax progressively
    # if too few survive to form a usable fit/checkpoint split.
    pts_ref = pts_src_resized = scores = None
    threshold_used = None
    for patch_half, mutual_tol, ncc_thresh in ((24, 1.5, 0.5), (20, 2.0, 0.45), (16, 2.5, 0.4), (16, 3.0, 0.3)):
        pts_ref, pts_src_resized, scores = abr.dense_ncc_correspondences(
            ref_gray, src_resized, matrix_ab, grid_step=10, patch_half=patch_half,
            search_radius=16, ncc_thresh=ncc_thresh, mutual_tol=mutual_tol)
        threshold_used = ncc_thresh
        if len(pts_ref) >= 15:
            break

    if pts_ref is None or len(pts_ref) == 0:
        return None

    # Convert source points from the (ref-sized) resized coordinate frame
    # used internally by the area-based algorithm back into the source
    # image's OWN native analysis-view pixel coordinates, so downstream
    # FSC/model-selection fits the transform in the same convention used
    # by the sparse descriptor path.
    sx, sy = w_src / w_ref, h_src / h_ref
    pts_src = pts_src_resized * np.array([sx, sy])

    match_dist = 1.0 - scores  # NCC score (higher=better) -> distance-like (lower=better)

    return {
        "pts_ref": pts_ref,
        "pts_src": pts_src,
        "match_dist": match_dist,
        "method": method_ab,
        "quality": quality_ab,
        "notes": notes_ab,
        "ncc_threshold_used": threshold_used,
        "n_correspondences": len(pts_ref),
        "mean_ncc_score": float(np.mean(scores)),
    }


def register_sensor(sensor_key: str, manifest: dict, run_dir: str, config: dict = None) -> dict:
    """Runs the complete pipeline for ONE source sensor against OHRC."""
    config = config or {}
    t0 = time.time()
    diag_dir = os.path.join(run_dir, "diagnostics", sensor_key)
    matches_dir = os.path.join(run_dir, "matches")
    os.makedirs(diag_dir, exist_ok=True)
    os.makedirs(matches_dir, exist_ok=True)

    ref_path = manifest["sensors"]["OHRC"]["file"]
    src_path = manifest["sensors"][sensor_key]["file"]

    # ---- STAGE: INPUT VALIDATION ----
    ref_raw = cv2.imread(ref_path, cv2.IMREAD_UNCHANGED)
    src_raw = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    if ref_raw is None or src_raw is None:
        return _fail("INPUT_VALIDATION", f"Could not read image file(s) for OHRC or {sensor_key}.")

    ref_gray_orig = pp.to_gray(ref_raw)
    src_gray_orig = pp.to_gray(src_raw)
    if ref_gray_orig.std() < 1e-3 or src_gray_orig.std() < 1e-3:
        return _fail("INPUT_VALIDATION", "One of the images is flat / contains no structural information.")

    # ---- STAGE: SENSOR-AWARE PREPROCESSING ----
    ref_pp = pp.preprocess_sensor("OHRC", ref_gray_orig)
    src_pp = pp.preprocess_sensor(sensor_key, src_gray_orig)
    _save_png(os.path.join(diag_dir, "ref_analysis_view.png"), ref_pp["analysis_view"])
    _save_png(os.path.join(diag_dir, "src_analysis_view.png"), src_pp["analysis_view"])

    # ---- STAGE: MULTI-SCALE REPRESENTATION ----
    ref_pyramid = scale_space.build_gaussian_pyramid(ref_pp["analysis_view"])
    src_pyramid = scale_space.build_gaussian_pyramid(src_pp["analysis_view"])

    # ---- STAGE: PHASE CONGRUENCY ----
    try:
        ref_pc = pcmod.phase_congruency(ref_pp["analysis_view"])
        src_pc = pcmod.phase_congruency(src_pp["analysis_view"])
    except Exception as e:
        return _fail("PHASE_CONGRUENCY", f"Phase congruency computation raised an exception: {e}")

    _save_png(os.path.join(diag_dir, "ref_phase_congruency.png"), ref_pc["phase_congruency"])
    _save_png(os.path.join(diag_dir, "src_phase_congruency.png"), src_pc["phase_congruency"])

    if ref_pc["phase_congruency"].max() < 1e-4 or src_pc["phase_congruency"].max() < 1e-4:
        return _fail("PHASE_CONGRUENCY", "Phase congruency response is degenerate (near zero) - insufficient structural content for illumination-invariant matching.")

    # ---- STAGE: KEYPOINT DETECTION + ANMS ----
    ref_kps_raw = kpmod.detect_keypoints_multiscale(ref_pc["phase_congruency"], ref_pyramid)
    src_kps_raw = kpmod.detect_keypoints_multiscale(src_pc["phase_congruency"], src_pyramid)
    ref_kps = kpmod.anms(ref_kps_raw, num_to_keep=config.get("max_keypoints", 600))
    src_kps = kpmod.anms(src_kps_raw, num_to_keep=config.get("max_keypoints", 600))

    if len(ref_kps) < 8 or len(src_kps) < 8:
        return _fail("KEYPOINT_DETECTION", f"Insufficient stable keypoints detected (ref={len(ref_kps)}, src={len(src_kps)}).")

    ref_grid = kpmod.grid_distribution(ref_kps, ref_pp["analysis_view"].shape)
    src_grid = kpmod.grid_distribution(src_kps, src_pp["analysis_view"].shape)

    # ---- STAGE: COARSE GEOMETRIC ALIGNMENT (diagnostic) ----
    try:
        coarse_result = coarse.estimate_coarse_similarity(ref_pc["phase_congruency"], src_pc["phase_congruency"])
        before_img = cv2.resize(src_pp["analysis_view"], (ref_pp["analysis_view"].shape[1], ref_pp["analysis_view"].shape[0]))
        after_img = coarse.apply_coarse_transform(src_pp["analysis_view"], coarse_result["matrix"], ref_pp["analysis_view"].shape)
        _save_png(os.path.join(diag_dir, "before_coarse_alignment.png"), before_img)
        _save_png(os.path.join(diag_dir, "after_coarse_alignment.png"), after_img)
    except Exception as e:
        coarse_result = {"scale": None, "rotation_deg": None, "tx": None, "ty": None, "matrix": None,
                          "phase_correlation_confidence": 0.0, "error": str(e)}

    # ---- STAGE: MULTI-MODAL DESCRIPTOR (RIFT / CFOG fallback) ----
    ref_desc_out = descmod.build_descriptors(ref_pp["analysis_view"], ref_kps)
    src_desc_out = descmod.build_descriptors(src_pp["analysis_view"], src_kps)

    ref_valid = ref_desc_out["valid_mask"]
    src_valid = src_desc_out["valid_mask"]
    ref_kps_v = [kp for kp, v in zip(ref_kps, ref_valid) if v]
    src_kps_v = [kp for kp, v in zip(src_kps, src_valid) if v]
    ref_desc_v = ref_desc_out["descriptors"][ref_valid]
    src_desc_v = src_desc_out["descriptors"][src_valid]

    if len(ref_kps_v) < 8 or len(src_kps_v) < 8:
        return _fail("DESCRIPTOR_EXTRACTION", "Too few keypoints survived descriptor patch-boundary filtering.")

    # ---- STAGE: FEATURE MATCHING ----
    match_result = matchmod.match_descriptors(ref_desc_v, src_desc_v, ratio_thresh=config.get("ratio_thresh", 0.85))
    n_accepted = match_result["n_accepted"]
    min_matches = config.get("min_matches", 8)

    correspondence_method = f"sparse_descriptor_matching ({ref_desc_out['method']})"
    area_based_info = None

    if n_accepted >= min_matches:
        pts_ref = np.array([[ref_kps_v[i]["x"], ref_kps_v[i]["y"]] for i, j, d in match_result["accepted_matches"]])
        pts_src = np.array([[src_kps_v[j]["x"], src_kps_v[j]["y"]] for i, j, d in match_result["accepted_matches"]])
        match_dist = np.array([d for i, j, d in match_result["accepted_matches"]])
    else:
        # ---- ESCALATION: sparse descriptor matching produced too few
        # correspondences. Automatically retry with a SEPARATE, area-based
        # algorithm (ECC/Mutual-Information global alignment + dense NCC
        # template-matching correspondences on gradient-magnitude maps) -
        # a genuinely different registration strategy better suited to
        # derived terrain products (TMC-Azimuth/TMC-Slope) that preserve
        # boundary/contour structure but lack corner-like texture.
        area_based_info = _area_based_fallback(ref_gray_orig, src_gray_orig, coarse_result)

        if area_based_info is None or area_based_info["n_correspondences"] < min_matches:
            return _fail("FEATURE_MATCHING",
                         f"Insufficient stable cross-modal correspondences from sparse descriptor matching "
                         f"({n_accepted} accepted, minimum required = {min_matches}); the area-based fallback "
                         f"(ECC/Mutual-Information + dense NCC correspondences) was attempted and also failed "
                         f"to reach the minimum ({0 if area_based_info is None else area_based_info['n_correspondences']} correspondences found).",
                         extra={"n_keypoints_ref": len(ref_kps), "n_keypoints_src": len(src_kps),
                                "n_candidate_matches": match_result["n_candidate"], "n_accepted_matches": n_accepted,
                                "descriptor_method": ref_desc_out["method"],
                                "area_based_fallback_attempted": True})

        pts_ref = area_based_info["pts_ref"]
        pts_src = area_based_info["pts_src"]
        match_dist = area_based_info["match_dist"]
        correspondence_method = f"dense_area_based_fallback ({area_based_info['method']}, quality={area_based_info['quality']:.3f})"

    match_viz = _draw_matches(ref_pp["analysis_view"], src_pp["analysis_view"], pts_ref, pts_src)
    cv2.imwrite(os.path.join(matches_dir, f"{sensor_key}_candidate_matches.png"), match_viz)

    # ---- STAGE: INDEPENDENT VALIDATION SPLIT ----
    fit_idx, check_idx = evalm.split_fit_checkpoint(len(pts_ref))
    if len(fit_idx) < 4:
        return _fail("INDEPENDENT_VALIDATION_SPLIT", "Not enough correspondences remain to form a fitting set after reserving independent checkpoints.")

    # ---- STAGE: ROBUST OUTLIER REJECTION + TRANSFORMATION MODEL SELECTION (on FIT set) ----
    model_selection = tf.select_transformation_model(pts_ref[fit_idx], pts_src[fit_idx], match_dist[fit_idx],
                                                       reproj_thresh=config.get("reproj_thresh", 6.0))
    chosen_model = model_selection["chosen_model"]
    if chosen_model is None:
        return _fail("ROBUST_OUTLIER_REJECTION", "FSC consensus failed to find a geometrically consistent hypothesis for any transformation model on the fitting set.",
                     extra={"model_attempts": {m: r.get("reason") for m, r in model_selection["all_results"].items() if not r["success"]}})

    chosen_result = model_selection["all_results"][chosen_model]
    matrix = np.array(chosen_result["matrix"])
    fit_inlier_mask = chosen_result["inlier_mask"]

    match_viz_inliers = _draw_matches(ref_pp["analysis_view"], src_pp["analysis_view"],
                                       pts_ref[fit_idx], pts_src[fit_idx], inlier_mask=fit_inlier_mask)
    cv2.imwrite(os.path.join(matches_dir, f"{sensor_key}_inlier_matches.png"), match_viz_inliers)

    # ---- RMSE BEFORE REFINEMENT (checkpoint set, global transform only) ----
    proj_check_global = consensus._apply_transform(matrix, pts_src[check_idx], chosen_model)
    rmse_before = evalm.compute_rmse(np.sqrt(np.sum((proj_check_global - pts_ref[check_idx]) ** 2, axis=1)))

    # ---- STAGE: LOCAL TERRAIN-RELIEF REFINEMENT ----
    fit_ref_inl = pts_ref[fit_idx][fit_inlier_mask]
    fit_src_inl = pts_src[fit_idx][fit_inlier_mask]
    proj_fit_inl = consensus._apply_transform(matrix, fit_src_inl, chosen_model)
    residual_vectors = fit_ref_inl - proj_fit_inl
    residual_mag = np.sqrt(np.sum(residual_vectors ** 2, axis=1))
    has_local_structure, cov = lref.residual_has_local_structure(fit_ref_inl, residual_mag)

    if has_local_structure and len(fit_ref_inl) >= 6:
        correction = interpolate_local_correction(fit_ref_inl, residual_vectors, proj_check_global)
        proj_check_local = proj_check_global + correction
        local_refinement_used = True
    else:
        proj_check_local = proj_check_global
        local_refinement_used = False

    rmse_after_local = evalm.compute_rmse(np.sqrt(np.sum((proj_check_local - pts_ref[check_idx]) ** 2, axis=1)))

    # ---- STAGE: SUB-PIXEL REFINEMENT (on checkpoint correspondences) ----
    ref_gray_view = ref_pp["analysis_view"]
    src_warped_full = warpmod.warp_original(sensor_key, src_pp["analysis_view"], matrix, ref_gray_view.shape)[0] \
        if False else None
    # Warp the analysis view globally so patch sampling around projected
    # checkpoint locations is meaningful in the reference frame.
    h_ref, w_ref = ref_gray_view.shape[:2]
    if matrix.shape == (2, 3):
        src_warped_analysis = cv2.warpAffine(src_pp["analysis_view"], matrix, (w_ref, h_ref))
    else:
        src_warped_analysis = cv2.warpPerspective(src_pp["analysis_view"], matrix, (w_ref, h_ref))

    refined_pts, subpixel_accepted = spx.refine_subpixel(ref_gray_view, src_warped_analysis,
                                                           pts_ref[check_idx], proj_check_local)
    rmse_after_subpixel = evalm.compute_rmse(np.sqrt(np.sum((refined_pts - pts_ref[check_idx]) ** 2, axis=1)))
    if rmse_after_subpixel is None:
        rmse_after_subpixel = rmse_after_local

    # ---- STAGE: WARPING (original, unmodified sensor data) ----
    warped_original, valid_mask = warpmod.warp_original(sensor_key, src_gray_orig, matrix, (h_ref, w_ref))
    checkerboard_img = warpmod.checkerboard(ref_gray_orig, warped_original)
    _save_png(os.path.join(diag_dir, "warped_registered.png"), warped_original)
    _save_png(os.path.join(diag_dir, "valid_mask.png"), valid_mask)
    _save_png(os.path.join(diag_dir, "checkerboard.png"), checkerboard_img)

    # residual maps
    residual_map_global = np.zeros((h_ref, w_ref), dtype=np.float32)
    for (x, y), err in zip(pts_ref[check_idx], np.sqrt(np.sum((proj_check_global - pts_ref[check_idx]) ** 2, axis=1))):
        cv2.circle(residual_map_global, (int(x), int(y)), 6, float(min(err, 20)), -1)
    _save_png(os.path.join(diag_dir, "global_residual_map.png"), residual_map_global)

    residual_map_local = np.zeros((h_ref, w_ref), dtype=np.float32)
    for (x, y), err in zip(pts_ref[check_idx], np.sqrt(np.sum((proj_check_local - pts_ref[check_idx]) ** 2, axis=1))):
        cv2.circle(residual_map_local, (int(x), int(y)), 6, float(min(err, 20)), -1)
    _save_png(os.path.join(diag_dir, "local_refinement_residual_map.png"), residual_map_local)

    # ---- STAGE: SPATIAL MATCH DISTRIBUTION (of inliers) ----
    inlier_kp_dicts = [{"x": p[0], "y": p[1]} for p in fit_ref_inl]
    inlier_grid = kpmod.grid_distribution(inlier_kp_dicts, (h_ref, w_ref))

    # ---- STAGE: CONFIDENCE ----
    confidence = evalm.classify_confidence(
        inlier_ratio=chosen_result["inlier_ratio"],
        n_inliers=chosen_result["n_inliers"],
        checkpoint_rmse=rmse_after_subpixel,
        coverage_percentage=inlier_grid["coverage_percentage"],
        rmse_before=rmse_before,
        rmse_after_local=rmse_after_local,
        rmse_after_subpixel=rmse_after_subpixel,
    )

    elapsed = time.time() - t0

    # area_based_info (when the dense area-based fallback was used) carries
    # raw numpy correspondence arrays needed internally for FSC/refinement;
    # strip those before this becomes part of the API-facing result so the
    # response stays JSON-serializable (and lean).
    area_based_fallback_public = None
    if area_based_info is not None:
        area_based_fallback_public = {
            "method": area_based_info["method"],
            "quality": area_based_info["quality"],
            "notes": area_based_info["notes"],
            "ncc_threshold_used": area_based_info["ncc_threshold_used"],
            "n_correspondences": area_based_info["n_correspondences"],
            "mean_ncc_score": area_based_info["mean_ncc_score"],
        }

    result = {
        "status": "SUCCESS",
        "sensor": sensor_key,
        "processing_time_sec": elapsed,
        "preprocessing_method": src_pp["method"],
        "correspondence_method": correspondence_method,
        "descriptor_method": ref_desc_out["method"],
        "descriptor_deviation_reason": ref_desc_out["deviation_reason"],
        "area_based_fallback": area_based_fallback_public,
        "coarse_alignment": {k: v for k, v in coarse_result.items() if k != "matrix"},
        "sensor_evidence_description": _sensor_evidence_text(sensor_key),
        "keypoint_grid_distribution": {"reference": ref_grid, "source": src_grid, "inliers": inlier_grid},
        "local_refinement": {"used": local_refinement_used, "residual_coefficient_of_variation": cov},
        "metrics": {
            "n_keypoints_reference": len(ref_kps),
            "n_keypoints_source": len(src_kps),
            "n_keypoints": len(ref_kps) + len(src_kps),
            "n_candidate_matches": match_result["n_candidate"] if area_based_info is None else area_based_info["n_correspondences"],
            "n_accepted_matches": n_accepted if area_based_info is None else area_based_info["n_correspondences"],
            "n_fit_points": len(fit_idx),
            "n_checkpoint_points": len(check_idx),
            "n_inliers": chosen_result["n_inliers"],
            "n_total_fit": chosen_result["n_total"],
            "inlier_ratio": chosen_result["inlier_ratio"],
            "transformation_model": chosen_model,
            "transformation_matrix": chosen_result["matrix"],
            "model_selection_justification": model_selection["justification"],
            "checkpoint_rmse_before_refinement": rmse_before,
            "checkpoint_rmse_after_local_refinement": rmse_after_local,
            "checkpoint_rmse_final": rmse_after_subpixel,
            "checkpoint_rmse_improvement_px": (rmse_before - rmse_after_subpixel) if (rmse_before is not None and rmse_after_subpixel is not None) else None,
            "valid_pixel_fraction": float(np.mean(valid_mask > 0)),
        },
        "confidence": confidence,
        "diagnostics_dir": diag_dir,
        "matches_dir": matches_dir,
        "warped_image": warped_original,
        "valid_mask": valid_mask,
    }
    return result


def compute_dataset_hash(manifest: dict) -> str:
    h = hashlib.sha256()
    for key in sorted(manifest["sensors"].keys()):
        h.update(manifest["sensors"][key]["sha256"].encode())
    return h.hexdigest()[:16]


def run_full_demo(project_root: str, config: dict = None) -> dict:
    """
    Section 31 - RUN FULL DEMO. Automatically processes all source sensors
    against the fixed OHRC reference and writes a full output package.
    """
    config = config or {}
    raw_dir = os.path.join(project_root, "data", "raw")
    metadata_dir = os.path.join(project_root, "data", "metadata")
    output_dir = os.path.join(project_root, "output")
    cache_dir = os.path.join(output_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    manifest = ds.build_manifest(raw_dir, metadata_dir)
    readiness = ds.readiness_report(manifest)

    dataset_hash = compute_dataset_hash(manifest)
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:8]
    run_id = f"{dataset_hash}_{config_hash}"
    run_dir = os.path.join(output_dir, "registered", run_id)
    cache_marker = os.path.join(cache_dir, f"{run_id}.json")

    cached = os.path.exists(cache_marker) and not config.get("force_rerun", False)

    if cached:
        with open(cache_marker) as fh:
            cached_summary = json.load(fh)
        cached_summary["cached"] = True
        cached_summary["run_id"] = run_id
        return cached_summary

    ALL_SOURCE_SENSORS = ["TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"]
    requested = config.get("sensors")
    if requested:
        invalid = [s for s in requested if s not in ALL_SOURCE_SENSORS]
        if invalid:
            raise ValueError(f"Unknown source sensor(s) requested: {invalid}. Valid options: {ALL_SOURCE_SENSORS}")
        source_sensors = [s for s in ALL_SOURCE_SENSORS if s in requested]
    else:
        source_sensors = ALL_SOURCE_SENSORS
    sensor_results = {}
    layers_for_fusion = {
        "OHRC": {
            "image": cv2.imread(manifest["sensors"]["OHRC"]["file"], cv2.IMREAD_UNCHANGED),
            "mask": np.ones(pp.to_gray(cv2.imread(manifest["sensors"]["OHRC"]["file"], cv2.IMREAD_UNCHANGED)).shape, dtype=np.uint8) * 255,
            "role": "REFERENCE",
            "interpolation": "n/a (reference)",
        }
    }

    for sensor_key in source_sensors:
        res = register_sensor(sensor_key, manifest, run_dir, config)
        if res["status"] == "SUCCESS":
            layers_for_fusion[sensor_key] = {
                "image": res.pop("warped_image"),
                "mask": res.pop("valid_mask"),
                "role": "SOURCE",
                "interpolation": "nearest" if sensor_key in ("TMC-Azimuth", "TMC-Slope") else "bicubic",
            }
        sensor_results[sensor_key] = res

    from src.fusion import multiband
    fusion_result = multiband.save_multiband_output(run_dir, "OHRC", layers_for_fusion)

    # ---- Generate per-sensor comparison strips (original vs registered) ----
    comparison_paths = {}
    ohrc_raw = layers_for_fusion.get("OHRC", {}).get("image")
    for sensor_key in source_sensors:
        if sensor_results[sensor_key].get("status") == "SUCCESS":
            registered_img = layers_for_fusion.get(sensor_key, {}).get("image")
            original_src_path = manifest["sensors"][sensor_key]["file"]
            if registered_img is not None and ohrc_raw is not None:
                cmp_path = multiband.generate_comparison_strip(
                    run_dir, sensor_key, original_src_path, registered_img, ohrc_raw
                )
                if cmp_path:
                    comparison_paths[sensor_key] = cmp_path

    summary = {
        "project": "INVINCIBLES",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_manifest": manifest,
        "readiness_report": readiness,
        "sensor_results": {k: {kk: vv for kk, vv in v.items() if kk not in ("warped_image", "valid_mask")}
                            for k, v in sensor_results.items()},
        "fusion_output": {
            "npz_path": fusion_result["npz_path"],
            "metadata": fusion_result["metadata"],
            "composite_path": fusion_result.get("composite_path"),
            "comparison_paths": comparison_paths,
        },
        "run_dir": run_dir,
        "cached": False,
    }

    with open(cache_marker, "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    metrics_path = os.path.join(output_dir, "metrics", f"{run_id}.json")
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    return summary
