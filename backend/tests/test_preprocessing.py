import os
import sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessing import sensor_preprocessing as pp

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")


def _load_gray(name):
    img = cv2.imread(os.path.join(RAW_DIR, name), cv2.IMREAD_UNCHANGED)
    return pp.to_gray(img)


def test_original_data_never_modified_in_place():
    gray = _load_gray("SAR.png")
    original_copy = gray.copy()
    result = pp.preprocess_sensor("SAR", gray)
    assert np.array_equal(gray, original_copy), "Input array must not be mutated"
    assert np.array_equal(result["original"], original_copy)


def test_analysis_view_differs_from_original_when_enhancement_applied():
    gray = _load_gray("OHRC.png")
    result = pp.preprocess_sensor("OHRC", gray)
    assert result["analysis_view"].shape == gray.shape
    assert not np.array_equal(result["analysis_view"], result["original"])


def test_terrain_layers_preserve_semantic_values_separately():
    gray = _load_gray("TMC-Slope.png")
    result = pp.preprocess_sensor("TMC-Slope", gray)
    assert np.array_equal(result["original"], gray)
    assert "No photometric alteration" in result["method"]


def test_sar_speckle_method_selected_based_on_measured_cv():
    gray = _load_gray("SAR.png")
    result = pp.preprocess_sensor("SAR", gray)
    assert "speckle CV=" in result["method"]
