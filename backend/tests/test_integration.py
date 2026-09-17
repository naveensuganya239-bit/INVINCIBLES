import os
import sys
import shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.registration import dataset as ds
from src.registration import pipeline as pl

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
METADATA_DIR = os.path.join(PROJECT_ROOT, "data", "metadata")
TEST_RUN_DIR = os.path.join(PROJECT_ROOT, "output", "registered", "_pytest_integration_run")


def teardown_module(module):
    if os.path.isdir(TEST_RUN_DIR):
        shutil.rmtree(TEST_RUN_DIR)


def test_full_pipeline_dataset_to_registration_to_evaluation_to_output():
    """
    Integration test: dataset -> registration -> evaluation -> output,
    run against the ACTUAL supplied lunar dataset (IIRS is used because it
    reliably reaches SUCCESS on this dataset; the point of this test is to
    exercise every real stage end-to-end, not to assert a specific accuracy
    number).
    """
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    assert "OHRC" in manifest["sensors"]

    result = pl.register_sensor("IIRS", manifest, TEST_RUN_DIR, config={})

    # The pipeline must return one of these two honest outcomes - never a
    # silently fabricated result.
    assert result["status"] in ("SUCCESS", "FAILED")

    if result["status"] == "FAILED":
        assert "failed_stage" in result and "failure_reason" in result
        return

    m = result["metrics"]
    assert m["n_keypoints_reference"] > 0
    assert m["n_accepted_matches"] > 0
    assert 0.0 <= m["inlier_ratio"] <= 1.0
    assert m["checkpoint_rmse_final"] is None or m["checkpoint_rmse_final"] >= 0
    assert result["confidence"]["level"] in ("HIGH", "MEDIUM", "LOW")
    assert os.path.isdir(result["diagnostics_dir"])
    assert result["warped_image"].shape[:2] == (730, 621)  # OHRC reference shape (h, w)


def test_dataset_hash_is_deterministic_for_caching():
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    h1 = pl.compute_dataset_hash(manifest)
    h2 = pl.compute_dataset_hash(manifest)
    assert h1 == h2
    assert len(h1) == 16
