import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.geometry import consensus, transformation as tf
from src.evaluation import metrics as evalm


def _make_synthetic_correspondences(n_inliers=40, n_outliers=15, seed=0):
    rng = np.random.default_rng(seed)
    ref_pts = rng.uniform(0, 500, size=(n_inliers, 2))
    true_matrix = np.array([[1.02, -0.03, 5.0], [0.03, 1.02, -3.0]])
    A = true_matrix[:, :2]
    t = true_matrix[:, 2]
    A_inv = np.linalg.inv(A)
    src_pts = (ref_pts - t) @ A_inv.T
    src_pts += rng.normal(0, 0.4, src_pts.shape)  # small measurement noise

    outlier_ref = rng.uniform(0, 500, size=(n_outliers, 2))
    outlier_src = rng.uniform(0, 500, size=(n_outliers, 2))

    all_ref = np.vstack([ref_pts, outlier_ref])
    all_src = np.vstack([src_pts, outlier_src])
    distances = np.concatenate([rng.uniform(0.1, 0.3, n_inliers), rng.uniform(0.6, 0.9, n_outliers)])
    return all_ref, all_src, distances, true_matrix


def test_fsc_recovers_inliers_and_rejects_outliers():
    ref, src, dist, true_matrix = _make_synthetic_correspondences()
    result = consensus.fsc_estimate(ref, src, dist, model="affine", reproj_thresh=3.0, max_iters=1500)
    assert result["success"] is True
    assert result["inlier_ratio"] > 0.6
    assert result["n_inliers"] >= 30


def test_fsc_fails_honestly_with_too_few_points():
    ref = np.array([[0, 0], [1, 1]])
    src = np.array([[0, 0], [1, 1]])
    dist = np.array([0.1, 0.1])
    result = consensus.fsc_estimate(ref, src, dist, model="affine")
    assert result["success"] is False
    assert "reason" in result


def test_transformation_model_selection_picks_reasonable_model():
    ref, src, dist, _ = _make_synthetic_correspondences()
    selection = tf.select_transformation_model(ref, src, dist, reproj_thresh=3.0)
    assert selection["chosen_model"] in ("similarity", "affine", "homography")
    assert selection["all_results"][selection["chosen_model"]]["success"]


def test_rmse_and_confidence_are_computed_not_hardcoded():
    errors = np.array([1.0, 2.0, 3.0, 4.0])
    rmse = evalm.compute_rmse(errors)
    expected = float(np.sqrt(np.mean(errors ** 2)))
    assert abs(rmse - expected) < 1e-9

    conf_high = evalm.classify_confidence(0.8, 50, 1.0, 80, 5.0, 3.0, 1.0)
    conf_low = evalm.classify_confidence(0.1, 3, 10.0, 10, 5.0, 8.0, 12.0)
    assert conf_high["level"] in ("HIGH", "MEDIUM")
    assert conf_low["level"] == "LOW"
    assert conf_high["score"] > conf_low["score"]
