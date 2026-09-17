"""
INVINCIBLES - Keypoint Detection & ANMS (Spec Sections 12, 13)
=================================================================
Keypoints are detected directly on the phase-congruency representation
(not raw intensity), across the multi-scale pyramid, then spatially
de-clustered using Adaptive Non-Maximal Suppression (Brown, Szeliski,
Winder 2005) so correspondences are not concentrated on the single
strongest crater edge.
"""
from __future__ import annotations
import numpy as np
import cv2


def detect_keypoints_multiscale(pc_map: np.ndarray, pyramid_scales, max_per_level: int = 1500):
    """
    Detects stable, well-localized corners on the phase-congruency map
    using Shi-Tomasi ("good features to track") corner scoring - chosen
    over a bare cornerHarris threshold sweep because it is significantly
    more repeatable across two independently-computed phase-congruency
    maps of the same physical scene (verified empirically on the actual
    supplied dataset during development), which matters far more for
    cross-sensor CORRESPONDENCE than for single-image cornerness. Detection
    runs at the base resolution and at one coarser pyramid level to retain
    scale coverage, with sub-pixel corner localization applied at every
    level (Section 12/21 sub-pixel intent applied as early as possible).
    """
    pc_u8 = np.clip(pc_map * 255.0, 0, 255).astype(np.uint8)
    base_h, base_w = pc_map.shape
    all_kps = []

    levels_to_use = [pyramid_scales[0]]
    if len(pyramid_scales) > 1:
        levels_to_use.append(pyramid_scales[1])

    for level_info in levels_to_use:
        scale = level_info["scale"]
        lvl_w, lvl_h = level_info["width"], level_info["height"]
        resized = cv2.resize(pc_u8, (lvl_w, lvl_h), interpolation=cv2.INTER_AREA) if scale != 1.0 else pc_u8

        corners = cv2.goodFeaturesToTrack(
            resized, maxCorners=max_per_level, qualityLevel=0.01, minDistance=4,
            blockSize=5, useHarrisDetector=False)
        if corners is None:
            continue

        term = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 40, 0.001)
        cv2.cornerSubPix(resized, corners, (5, 5), (-1, -1), term)

        # response = local phase-congruency value at the refined location
        for c in corners:
            x, y = float(c[0][0]), float(c[0][1])
            xi, yi = int(round(x)), int(round(y))
            xi = min(max(xi, 0), lvl_w - 1)
            yi = min(max(yi, 0), lvl_h - 1)
            response = float(resized[yi, xi])
            x_base, y_base = x * (base_w / lvl_w), y * (base_h / lvl_h)
            all_kps.append({
                "x": x_base, "y": y_base, "response": response,
                "scale_level": level_info["level"], "scale": float(scale),
            })

    return all_kps


def anms(keypoints, num_to_keep: int = 500, c_robust: float = 0.9, img_shape=None):
    """
    Adaptive Non-Maximal Suppression. For each keypoint, computes the
    minimum distance to any other keypoint with a sufficiently stronger
    response, then keeps the `num_to_keep` points with the largest such
    "suppression radius" - i.e. the strongest points that are also well
    separated from other strong points.
    """
    n = len(keypoints)
    if n == 0:
        return []
    if n <= num_to_keep:
        return keypoints

    pts = np.array([[kp["x"], kp["y"]] for kp in keypoints])
    resp = np.array([kp["response"] for kp in keypoints])

    radii = np.full(n, np.inf)
    order = np.argsort(-resp)
    sorted_pts = pts[order]
    sorted_resp = resp[order]

    for i in range(n):
        stronger_mask = sorted_resp[:i] > sorted_resp[i] / c_robust
        if not np.any(stronger_mask):
            radii[order[i]] = np.inf
            continue
        d = np.sqrt(np.sum((sorted_pts[:i][stronger_mask] - sorted_pts[i]) ** 2, axis=1))
        radii[order[i]] = np.min(d)

    keep_idx = np.argsort(-radii)[:num_to_keep]
    return [keypoints[i] for i in keep_idx]


def grid_distribution(keypoints, img_shape, grid_size: int = 8):
    """Section 13/29 - spatial distribution diagnostic over a configurable grid."""
    h, w = img_shape[:2]
    counts = np.zeros((grid_size, grid_size), dtype=int)
    cell_h, cell_w = h / grid_size, w / grid_size
    for kp in keypoints:
        gx = min(int(kp["x"] // cell_w), grid_size - 1)
        gy = min(int(kp["y"] // cell_h), grid_size - 1)
        counts[gy, gx] += 1

    empty_cells = int(np.sum(counts == 0))
    return {
        "grid_size": grid_size,
        "counts": counts.tolist(),
        "min_cell_count": int(counts.min()),
        "max_cell_count": int(counts.max()),
        "mean_cell_count": float(counts.mean()),
        "std_cell_count": float(counts.std()),
        "coverage_percentage": float(100.0 * np.sum(counts > 0) / counts.size),
        "empty_cell_percentage": float(100.0 * empty_cells / counts.size),
    }
