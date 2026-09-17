import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.features import phase_congruency as pcmod, keypoints as kpmod, scale_space


def _synthetic_structured_image(size=256):
    img = np.zeros((size, size), dtype=np.uint8)
    for i in range(0, size, 16):
        img[:, i:i + 2] = 200
    for i in range(0, size, 24):
        img[i:i + 2, :] = 150
    return img


def test_phase_congruency_is_bounded_and_nonzero_on_structured_image():
    img = _synthetic_structured_image()
    result = pcmod.phase_congruency(img, n_scale=3, n_orient=4)
    pc = result["phase_congruency"]
    assert pc.shape == img.shape
    assert pc.max() <= 1.0 + 1e-6
    assert pc.max() > 0.01  # structured image must produce a real response


def test_phase_congruency_is_low_on_flat_image():
    flat = np.full((128, 128), 128, dtype=np.uint8)
    result = pcmod.phase_congruency(flat, n_scale=3, n_orient=4)
    assert result["phase_congruency"].max() < 0.05


def test_keypoint_detection_and_anms_reduces_and_spreads_points():
    img = _synthetic_structured_image()
    pyramid = scale_space.build_gaussian_pyramid(img, num_levels=3)
    pc = pcmod.phase_congruency(img, n_scale=3, n_orient=4)["phase_congruency"]
    raw_kps = kpmod.detect_keypoints_multiscale(pc, pyramid)
    assert len(raw_kps) > 0

    reduced = kpmod.anms(raw_kps, num_to_keep=30)
    assert len(reduced) <= 30

    grid = kpmod.grid_distribution(reduced, img.shape, grid_size=4)
    assert grid["coverage_percentage"] >= 0
    assert sum(sum(row) for row in grid["counts"]) == len(reduced)
