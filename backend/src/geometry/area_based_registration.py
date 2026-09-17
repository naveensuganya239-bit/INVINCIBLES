"""
INVINCIBLES - Dense Area-Based Registration (Structural Edge/ECC + NCC)
==========================================================================
A SEPARATE registration algorithm from the sparse RIFT/CFOG keypoint-
descriptor pipeline, used automatically as an escalation path when sparse
feature matching does not produce enough stable correspondences (this is
exactly what happens on TMC-Azimuth/TMC-Slope against OHRC in the actual
supplied dataset: derived terrain products preserve the crater's boundary/
contour geometry extremely well, but do not carry the corner-like texture
that a sparse descriptor needs).

This is a classical AREA-BASED (not feature-based) multi-modal registration
strategy, built in two stages:

  1. GLOBAL INTENSITY-BASED ALIGNMENT
     Gradient-magnitude maps of the reference and source (a photometry-
     independent structural representation - a crater rim is a strong
     gradient edge no matter how the sensor colour-maps it) are aligned
     using OpenCV's ECC (Enhanced Correlation Coefficient) algorithm
     (Evangelidis & Psarakis, 2008), seeded from the SAME FFT log-polar
     phase-congruency coarse-alignment estimate already computed upstream
     (Section 14) so both algorithmic paths are consistent.
     If ECC fails to converge (raises cv2.error, e.g. because the seed is
     too far from the true optimum or the gradient maps are too flat),
     this module automatically falls back to a SECOND, independent
     algorithm: direct maximization of the Mutual Information between the
     two grayscale analysis views over a similarity-transform parameter
     search (Powell's method) - a well-established technique specifically
     designed for cross-modal image pairs whose intensity relationship is
     not linear.

  2. INDEPENDENT DENSE CORRESPONDENCE GENERATION (for honest evaluation)
     The global transform found in step 1 is only a starting hypothesis.
     To produce genuine, independently-measured point correspondences
     (so that the existing FSC / independent-checkpoint / RMSE / confidence
     machinery - identical to the sparse pipeline - can be reused honestly,
     rather than trivially validating the very transform that produced the
     points), a grid of control points is sampled across the reference
     gradient map and each is INDEPENDENTLY re-located in the source
     gradient map via normalized cross-correlation (NCC) template matching
     within a small local search window around the step-1 projection, with
     sub-pixel peak interpolation. Only points whose NCC score clears a
     reliability threshold are kept as accepted correspondences.

This gives an honest, area-based alternative to sparse descriptor matching,
while remaining fully compatible with (and validated by) the same FSC /
model-selection / local-refinement / sub-pixel / confidence pipeline used
for the descriptor-based sensors.
"""
from __future__ import annotations
import numpy as np
import cv2
from scipy.optimize import minimize


def _gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    g = gray.astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag = cv2.GaussianBlur(mag, (3, 3), 0)
    mag_norm = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    return mag_norm.astype(np.float32)


def _ecc_align(ref_edge: np.ndarray, src_edge: np.ndarray, init_matrix_2x3: np.ndarray,
               motion_type=cv2.MOTION_EUCLIDEAN, max_iters=800, eps=1e-7):
    """
    Refines `init_matrix_2x3` (source -> reference) using ECC on gradient-
    magnitude maps. Returns (matrix, correlation_coefficient) or raises.
    A coarse-to-fine (2-level) pyramid is used to widen the basin of
    convergence, which matters because the seed comes from a phase-
    correlation estimate that can be off by several pixels/degrees.
    """
    h, w = ref_edge.shape[:2]
    warp_matrix = init_matrix_2x3.astype(np.float32).copy()

    for scale in (0.5, 1.0):
        sw, sh = max(8, int(w * scale)), max(8, int(h * scale))
        ref_s = cv2.resize(ref_edge, (sw, sh), interpolation=cv2.INTER_AREA)
        src_s = cv2.resize(src_edge, (sw, sh), interpolation=cv2.INTER_AREA)

        wm = warp_matrix.copy()
        wm[0, 2] *= scale
        wm[1, 2] *= scale

        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iters, eps)
        cc, wm_refined = cv2.findTransformECC(ref_s, src_s, wm, motion_type, criteria, None, 5)

        wm_refined[0, 2] /= scale
        wm_refined[1, 2] /= scale
        warp_matrix = wm_refined

    return warp_matrix, float(cc)


def _mutual_information(a: np.ndarray, b: np.ndarray, bins=32) -> float:
    hist_2d, _, _ = np.histogram2d(a.ravel(), b.ravel(), bins=bins)
    pxy = hist_2d / (hist_2d.sum() + 1e-12)
    px = pxy.sum(axis=1)
    py = pxy.sum(axis=0)
    px_py = px[:, None] * py[None, :]
    nonzero = pxy > 0
    return float(np.sum(pxy[nonzero] * np.log(pxy[nonzero] / (px_py[nonzero] + 1e-12) + 1e-12)))


def _mi_align(ref_gray: np.ndarray, src_gray: np.ndarray, init_params: dict, out_shape):
    """
    Fallback algorithm #2: directly maximizes Mutual Information between
    the reference and a similarity-warped source over (scale, rotation,
    tx, ty), using Powell's derivative-free method. Used only if ECC on
    the gradient maps fails to converge.
    """
    h, w = out_shape[:2]
    x0 = np.array([init_params.get("scale", 1.0), init_params.get("rotation_deg", 0.0),
                    init_params.get("tx", 0.0), init_params.get("ty", 0.0)])

    def neg_mi(params):
        s, rot, tx, ty = params
        if s <= 0.3 or s >= 3.0:
            return 1e6
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, s)
        M[0, 2] += tx
        M[1, 2] += ty
        warped = cv2.warpAffine(src_gray, M, (w, h), flags=cv2.INTER_LINEAR)
        valid = warped > 0
        if valid.sum() < 0.2 * w * h:
            return 1e6
        return -_mutual_information(ref_gray[valid], warped[valid])

    result = minimize(neg_mi, x0, method="Powell",
                       options={"maxiter": 200, "xtol": 1e-3, "ftol": 1e-4})
    s, rot, tx, ty = result.x
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, s)
    M[0, 2] += tx
    M[1, 2] += ty
    return M.astype(np.float32), float(-result.fun)


def estimate_global_alignment(ref_gray, src_gray, coarse_matrix, coarse_params, out_shape):
    """
    Stage 1: returns (matrix 2x3, method_used, quality_metric, notes).

    Runs a MULTI-START search: both the upstream FFT/phase-congruency
    coarse-alignment hypothesis AND a plain identity hypothesis are tried
    as seeds (identity is a legitimate, standard second start for
    near-nadir same-framing sensor crops, and guards against cases where
    the phase-correlation coarse stage itself converges poorly on a
    heavily re-shaded derived product). For each seed, ECC on gradient-
    magnitude maps is attempted first (Euclidean, then affine motion);
    if ECC does not reach a minimally-acceptable correlation coefficient,
    the Mutual-Information Powell-search fallback is used instead. The
    candidate with the best resulting quality score across all seeds is
    returned, together with a full audit trail of every attempt.
    """
    h, w = out_shape[:2]
    src_resized = cv2.resize(src_gray, (w, h), interpolation=cv2.INTER_LINEAR) \
        if src_gray.shape[:2] != (h, w) else src_gray

    ref_edge = _gradient_magnitude(ref_gray)
    src_edge = _gradient_magnitude(src_resized)

    def _sanitize_matrix(m):
        m = np.array(m, dtype=np.float32) if m is not None else None
        if m is None or not np.all(np.isfinite(m)):
            return np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
        return m

    def _sanitize_params(p):
        p = dict(p or {})
        for key, default in (("scale", 1.0), ("rotation_deg", 0.0), ("tx", 0.0), ("ty", 0.0)):
            v = p.get(key, default)
            p[key] = default if (v is None or not np.isfinite(v)) else v
        return p

    seeds = [
        ("coarse_phase_congruency", _sanitize_matrix(coarse_matrix), _sanitize_params(coarse_params)),
        ("identity", np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32),
         {"scale": 1.0, "rotation_deg": 0.0, "tx": 0.0, "ty": 0.0}),
    ]

    attempts = []
    ecc_candidates = []  # (matrix, method, cc, seed_name)
    mi_candidates = []   # (matrix, method, mi, seed_name)

    for seed_name, init, params in seeds:
        try:
            matrix, cc = _ecc_align(ref_edge, src_edge, init, motion_type=cv2.MOTION_EUCLIDEAN)
            attempts.append({"seed": seed_name, "method": "ECC_GRADIENT_EUCLIDEAN", "quality": cc})
            ecc_candidates.append((matrix, "ECC_GRADIENT_EUCLIDEAN", cc, seed_name))
        except cv2.error:
            attempts.append({"seed": seed_name, "method": "ECC_GRADIENT_EUCLIDEAN", "quality": None, "error": "did not converge"})

        try:
            matrix, cc = _ecc_align(ref_edge, src_edge, init, motion_type=cv2.MOTION_AFFINE)
            attempts.append({"seed": seed_name, "method": "ECC_GRADIENT_AFFINE", "quality": cc})
            ecc_candidates.append((matrix, "ECC_GRADIENT_AFFINE", cc, seed_name))
        except cv2.error:
            attempts.append({"seed": seed_name, "method": "ECC_GRADIENT_AFFINE", "quality": None, "error": "did not converge"})

        matrix, mi = _mi_align(ref_gray, src_resized, params, out_shape)
        attempts.append({"seed": seed_name, "method": "MUTUAL_INFORMATION_POWELL", "quality": mi})
        mi_candidates.append((matrix, "MUTUAL_INFORMATION_POWELL", mi, seed_name))

    # ECC's correlation-coefficient is a directly meaningful convergence
    # signal; it is NOT numerically comparable to the Mutual-Information
    # score (different scale/units), so we do not just take a global max
    # across both. Prefer ANY ECC result that cleared a minimal-confidence
    # threshold over ALL Mutual-Information results; only fall back to the
    # best Mutual-Information candidate when no ECC attempt (from any seed
    # or motion model) reached that threshold.
    ecc_threshold = 0.15
    good_ecc = [c for c in ecc_candidates if c[2] is not None and c[2] >= ecc_threshold]

    if good_ecc:
        matrix, method, cc, seed_name = max(good_ecc, key=lambda c: c[2])
        best = (matrix, method, cc,
                f"ECC on gradient-magnitude maps converged from the '{seed_name}' seed "
                f"(correlation coefficient={cc:.3f}, best of {len(good_ecc)} qualifying ECC attempts "
                f"across {len(seeds)} seeds)")
    else:
        matrix, method, mi, seed_name = max(mi_candidates, key=lambda c: c[2])
        best = (matrix, method, mi,
                f"No ECC attempt reached the {ecc_threshold} correlation-coefficient threshold; "
                f"used the best Mutual-Information Powell search result, from the '{seed_name}' seed "
                f"(final MI={mi:.3f})")

    matrix, method, quality, notes = best
    notes += f" | multi-start audit trail: {attempts}"
    return matrix, method, quality, notes


def dense_ncc_correspondences(ref_gray, src_gray_full_res_resized, matrix, grid_step=40,
                               patch_half=12, search_radius=10, ncc_thresh=0.35, border=30,
                               require_mutual_consistency=True, mutual_tol=2.5, max_points=2000):
    """
    Stage 2: locates well-localized 2D structural points on the reference
    gradient map (via Shi-Tomasi cornerness) and independently re-locates
    each one in the source gradient map via normalized cross-correlation
    (NCC) template matching within a local search window around the
    Stage-1 projection, with sub-pixel parabolic peak interpolation.
    Returns (pts_ref, pts_src, ncc_scores) - genuine, independently
    measured correspondences, not merely samples of the fitted transform.

    IMPORTANT - why corners, not a uniform grid: an earlier version of
    this function sampled a uniform grid of points and NCC-matched a patch
    around each one. On a smooth, gently-curving boundary (a crater rim is
    exactly this), a patch centred ANYWHERE along the boundary looks
    almost identical to its neighbours a few pixels further along the
    curve - the classical "aperture problem". NCC (and its forward-
    backward mutual check) is then satisfied by a match that has slid
    TANGENTIALLY along the rim, which is nearly invisible on a checkerboard
    visualization (the rim still looks continuous) but produces a large,
    systematic point-position error that inflates RMSE. Restricting
    candidate points to locations with strong 2D (Shi-Tomasi) cornerness -
    where local structure constrains position in BOTH directions, such as
    the small central mound or rim-curvature extrema - removes this
    ambiguity at the source instead of trying to filter it out afterwards.

    If `require_mutual_consistency` is set, each forward match
    (ref -> src) is independently re-verified by searching BACKWARD
    (src -> ref) around the matched source location; a correspondence is
    kept only if the round trip lands back within `mutual_tol` pixels of
    the original reference point.
    """
    ref_edge = _gradient_magnitude(ref_gray)
    src_edge = _gradient_magnitude(src_gray_full_res_resized)
    h, w = ref_edge.shape[:2]

    M = np.array(matrix, dtype=np.float64)

    mask = np.zeros((h, w), dtype=np.uint8)
    mask[border:h - border, border:w - border] = 255
    corners = cv2.goodFeaturesToTrack(
        ref_edge.astype(np.uint8), maxCorners=max_points, qualityLevel=0.01,
        minDistance=max(4, grid_step // 2), blockSize=7, mask=mask, useHarrisDetector=False)

    candidate_points = [] if corners is None else [(int(round(c[0][0])), int(round(c[0][1]))) for c in corners]

    pts_ref, pts_src, scores = [], [], []

    for x, y in candidate_points:
        if x - patch_half < 0 or y - patch_half < 0 or x + patch_half >= w or y + patch_half >= h:
            continue
        ref_patch = ref_edge[y - patch_half:y + patch_half, x - patch_half:x + patch_half]
        if ref_patch.std() < 3.0:
            continue  # skip near-featureless patches (e.g. flat sky/mare)

        proj = M @ np.array([x, y, 1.0])
        px, py = proj[0], proj[1]
        sx0, sy0 = int(round(px - search_radius - patch_half)), int(round(py - search_radius - patch_half))
        sx1, sy1 = int(round(px + search_radius + patch_half)), int(round(py + search_radius + patch_half))
        if sx0 < 0 or sy0 < 0 or sx1 >= w or sy1 >= h:
            continue

        search_region = src_edge[sy0:sy1, sx0:sx1]
        if search_region.shape[0] <= ref_patch.shape[0] or search_region.shape[1] <= ref_patch.shape[1]:
            continue

        result = cv2.matchTemplate(search_region, ref_patch, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < ncc_thresh:
            continue

        mx, my = max_loc
        # sub-pixel parabolic interpolation on the NCC response surface
        if 0 < mx < result.shape[1] - 1 and 0 < my < result.shape[0] - 1:
            dx = 0.5 * (result[my, mx - 1] - result[my, mx + 1]) / \
                 (result[my, mx - 1] - 2 * result[my, mx] + result[my, mx + 1] + 1e-9)
            dy = 0.5 * (result[my - 1, mx] - result[my + 1, mx]) / \
                 (result[my - 1, mx] - 2 * result[my, mx] + result[my + 1, mx] + 1e-9)
            dx = np.clip(dx, -1, 1)
            dy = np.clip(dy, -1, 1)
        else:
            dx = dy = 0.0

        match_x = sx0 + mx + patch_half + dx
        match_y = sy0 + my + patch_half + dy

        if require_mutual_consistency:
            mxi, myi = int(round(match_x)), int(round(match_y))
            if (mxi - patch_half < 0 or myi - patch_half < 0 or
                    mxi + patch_half >= w or myi + patch_half >= h):
                continue
            src_patch_back = src_edge[myi - patch_half:myi + patch_half, mxi - patch_half:mxi + patch_half]
            bx0 = max(0, int(round(x - search_radius - patch_half)))
            by0 = max(0, int(round(y - search_radius - patch_half)))
            bx1 = min(w, int(round(x + search_radius + patch_half)))
            by1 = min(h, int(round(y + search_radius + patch_half)))
            back_region = ref_edge[by0:by1, bx0:bx1]
            if back_region.shape[0] <= src_patch_back.shape[0] or back_region.shape[1] <= src_patch_back.shape[1]:
                continue
            back_result = cv2.matchTemplate(back_region, src_patch_back, cv2.TM_CCOEFF_NORMED)
            _, back_val, _, back_loc = cv2.minMaxLoc(back_result)
            bmx, bmy = back_loc
            back_x = bx0 + bmx + patch_half
            back_y = by0 + bmy + patch_half
            round_trip_error = np.hypot(back_x - x, back_y - y)
            if round_trip_error > mutual_tol:
                continue

        pts_ref.append([x, y])
        pts_src.append([match_x, match_y])
        scores.append(float(max_val))

    return np.array(pts_ref, dtype=np.float64), np.array(pts_src, dtype=np.float64), np.array(scores, dtype=np.float64)
