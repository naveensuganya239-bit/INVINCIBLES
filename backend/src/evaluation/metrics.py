"""
INVINCIBLES - Independent Validation & Confidence (Spec Sections 22, 23, 28)
===============================================================================
Correspondences are split into a fitting set (used to estimate the
transform) and an independent checkpoint set (used only to measure error),
which prevents artificially optimistic RMSE. Confidence is derived
transparently from measured factors, never assigned as an arbitrary label.
"""
from __future__ import annotations
import numpy as np


def split_fit_checkpoint(n_points: int, checkpoint_fraction: float = 0.25, seed: int = 7, min_checkpoints: int = 4):
    rng = np.random.default_rng(seed)
    idx = np.arange(n_points)
    rng.shuffle(idx)
    n_check = max(min_checkpoints, int(round(n_points * checkpoint_fraction)))
    n_check = min(n_check, n_points - 3) if n_points > 3 else 0
    checkpoint_idx = idx[:n_check]
    fit_idx = idx[n_check:]
    return fit_idx, checkpoint_idx


def compute_rmse(errors: np.ndarray):
    if errors is None or len(errors) == 0:
        return None
    return float(np.sqrt(np.mean(np.array(errors) ** 2)))


def classify_confidence(inlier_ratio, n_inliers, checkpoint_rmse, coverage_percentage,
                         rmse_before, rmse_after_local, rmse_after_subpixel):
    """
    Transparent, rule-based confidence classification built from measured
    quantities only (Section 28). Returns level + itemised supporting/
    limiting factors so the reasoning is fully auditable.
    """
    factors = []
    score = 0
    max_score = 5

    if inlier_ratio is not None and inlier_ratio >= 0.35:
        factors.append(("PASS", f"inlier ratio {inlier_ratio:.2%} >= 35%"))
        score += 1
    elif inlier_ratio is not None:
        factors.append(("WEAK", f"inlier ratio {inlier_ratio:.2%} below 35%"))

    if n_inliers is not None and n_inliers >= 20:
        factors.append(("PASS", f"{n_inliers} reliable inliers (>=20)"))
        score += 1
    elif n_inliers is not None:
        factors.append(("WEAK", f"only {n_inliers} reliable inliers"))

    if checkpoint_rmse is not None and checkpoint_rmse <= 2.5:
        factors.append(("PASS", f"independent checkpoint RMSE {checkpoint_rmse:.2f}px <= 2.5px"))
        score += 1
    elif checkpoint_rmse is not None:
        factors.append(("WEAK", f"independent checkpoint RMSE {checkpoint_rmse:.2f}px > 2.5px"))

    if coverage_percentage is not None and coverage_percentage >= 50:
        factors.append(("PASS", f"spatial coverage {coverage_percentage:.1f}% of grid cells >= 50%"))
        score += 1
    elif coverage_percentage is not None:
        factors.append(("WEAK", f"spatial coverage {coverage_percentage:.1f}% of grid cells < 50%"))

    improved = (rmse_before is not None and rmse_after_subpixel is not None and rmse_after_subpixel <= rmse_before)
    if improved:
        factors.append(("PASS", "refinement stages did not increase error (residuals stable or improved)"))
        score += 1
    else:
        factors.append(("WEAK", "refinement stages did not demonstrably improve residual error"))

    if score >= 4:
        level = "HIGH"
    elif score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {"level": level, "score": score, "max_score": max_score, "factors": factors}
