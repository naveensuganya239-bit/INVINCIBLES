import os
import sys
import shutil
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.registration import dataset as ds
from src.registration import pipeline as pl
from src.geometry import area_based_registration as abr

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
METADATA_DIR = os.path.join(PROJECT_ROOT, "data", "metadata")
TEST_RUN_DIR = os.path.join(PROJECT_ROOT, "output", "registered", "_pytest_area_based_run")


def teardown_module(module):
    if os.path.isdir(TEST_RUN_DIR):
        shutil.rmtree(TEST_RUN_DIR)


def test_gradient_magnitude_is_nonzero_on_structured_image():
    img = np.zeros((128, 128), dtype=np.uint8)
    cv2.circle(img, (64, 64), 40, 200, 2)
    mag = abr._gradient_magnitude(img)
    assert mag.max() > 0


def test_mutual_information_higher_for_identical_than_shuffled():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 255, size=(64, 64)).astype(np.uint8)
    mi_self = abr._mutual_information(a, a)
    b = a.copy().ravel()
    rng.shuffle(b)
    b = b.reshape(a.shape)
    mi_shuffled = abr._mutual_information(a, b)
    assert mi_self > mi_shuffled


def test_estimate_global_alignment_recovers_near_identity_on_identical_images():
    img = np.zeros((200, 200), dtype=np.uint8)
    cv2.circle(img, (100, 100), 60, 220, -1)
    cv2.circle(img, (100, 100), 20, 80, -1)
    identity = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
    matrix, method, quality, notes = abr.estimate_global_alignment(
        img, img, identity, {"scale": 1.0, "rotation_deg": 0.0, "tx": 0.0, "ty": 0.0}, img.shape)
    assert method in ("ECC_GRADIENT_EUCLIDEAN", "ECC_GRADIENT_AFFINE", "MUTUAL_INFORMATION_POWELL")
    # near-identity: translation should be small for two identical images
    assert abs(matrix[0, 2]) < 5
    assert abs(matrix[1, 2]) < 5


def test_dense_ncc_correspondences_recovers_known_shift():
    img = np.zeros((200, 200), dtype=np.uint8)
    cv2.circle(img, (100, 100), 60, 220, -1)
    cv2.circle(img, (100, 100), 20, 80, -1)
    shifted = np.roll(img, shift=(3, 5), axis=(0, 1))
    identity = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
    pts_ref, pts_src, scores = abr.dense_ncc_correspondences(img, shifted, identity, grid_step=15, patch_half=16, search_radius=10)
    assert len(pts_ref) > 0
    diffs = pts_src - pts_ref
    # shifted = np.roll(img, (dy=3, dx=5)) means src pixel at (x,y) came
    # from ref pixel at (x-5, y-3); matched src location should be ~ (x+5,y+3)
    assert abs(np.median(diffs[:, 0]) - 5) < 2
    assert abs(np.median(diffs[:, 1]) - 3) < 2


def test_tmc_sensors_reach_success_status_on_actual_dataset():
    """
    Regression test for the reported issue: TMC-Azimuth and TMC-Slope must
    both reach SUCCESS (not FAILED) on the actual supplied dataset, via the
    area-based fallback algorithm, since sparse RIFT/CFOG matching alone
    does not find enough correspondences on these derived terrain products.
    """
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    for sensor in ["TMC-Azimuth", "TMC-Slope"]:
        result = pl.register_sensor(sensor, manifest, TEST_RUN_DIR, config={})
        assert result["status"] == "SUCCESS", (
            f"{sensor} failed: {result.get('failed_stage')} - {result.get('failure_reason')}"
        )
        assert "area_based" in result["correspondence_method"] or "descriptor" in result["correspondence_method"]
        assert result["metrics"]["n_inliers"] > 0
        assert result["confidence"]["level"] in ("HIGH", "MEDIUM", "LOW")
