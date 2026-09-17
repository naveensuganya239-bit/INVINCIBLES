import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.registration import dataset as ds

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
METADATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metadata")


def test_discover_dataset_finds_all_five_sensors():
    mapping = ds.discover_dataset(RAW_DIR)
    assert set(mapping.keys()) == {"OHRC", "TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"}
    for path in mapping.values():
        assert os.path.isfile(path)


def test_ohrc_is_locked_reference():
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    assert manifest["reference_sensor"] == "OHRC"
    assert manifest["reference_locked"] is True
    assert manifest["sensors"]["OHRC"]["role"] == "REFERENCE"
    for source in ["TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"]:
        assert manifest["sensors"][source]["role"] == "SOURCE"


def test_characterization_produces_real_measured_values():
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    stats = manifest["sensors"]["OHRC"]["stats"]
    assert stats["width"] > 0 and stats["height"] > 0
    assert stats["min"] <= stats["mean"] <= stats["max"]
    assert stats["std"] >= 0
    assert isinstance(stats["has_nan_or_inf"], bool)


def test_readiness_report_all_true_for_valid_dataset():
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    report = ds.readiness_report(manifest)
    for key in ["OHRC", "TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"]:
        assert report[key] is True
    assert report["multiband_output_feasible"] is True
