"""
INVINCIBLES - Dataset Manager
==============================
Robust sensor-mapping layer for the actual supplied lunar dataset.

Responsibilities (Spec Sections 3, 6, 54, 55):
  - Locate the five real sensor images regardless of exact filename spelling.
  - Map each file to a logical sensor role (REFERENCE / SOURCE).
  - Compute real, measured image-characterization statistics (no invented numbers).
  - Produce a machine-readable dataset manifest.
  - Produce a technical readiness report.

OHRC is ALWAYS the fixed reference. This is enforced here and is not configurable.
"""
from __future__ import annotations

import os
import io
import json
import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import cv2

# ---------------------------------------------------------------------------
# Sensor identity table. Matching is done on normalized (lowercased,
# de-hyphenated, de-spaced) filenames so that "OHRC sample.png",
# "ohrc_sample.PNG", "OHRC.png" etc. are all recognised robustly, rather than
# assuming an exact filename.
# ---------------------------------------------------------------------------
SENSOR_TABLE = {
    "OHRC": {
        "role": "REFERENCE",
        "sensor_full_name": "Orbiter High Resolution Camera",
        "aliases": ["ohrc"],
        "kind": "continuous",
    },
    "TMC-Azimuth": {
        "role": "SOURCE",
        "sensor_full_name": "Terrain Mapping Camera (Azimuth product)",
        "aliases": ["tmcazimuth", "tmc-azimuth", "tmc_azimuth"],
        "kind": "derived_terrain",
    },
    "TMC-Slope": {
        "role": "SOURCE",
        "sensor_full_name": "Terrain Mapping Camera (Slope product)",
        "aliases": ["tmcslope", "tmc-slope", "tmc_slope"],
        "kind": "derived_terrain",
    },
    "IIRS": {
        "role": "SOURCE",
        "sensor_full_name": "Imaging Infrared Spectrometer",
        "aliases": ["iirs"],
        "kind": "continuous",
    },
    "SAR": {
        "role": "SOURCE",
        "sensor_full_name": "Synthetic Aperture Radar",
        "aliases": ["sar"],
        "kind": "continuous_speckled",
    },
}


def _normalize(name: str) -> str:
    base = os.path.splitext(name)[0]
    base = base.lower()
    base = re.sub(r"[\s_]*sample[\s_]*", "", base)
    base = re.sub(r"[^a-z0-9]", "", base)
    return base


def discover_dataset(raw_dir: str) -> dict:
    """
    Inspect the raw data directory programmatically and build a robust
    sensor -> filepath mapping. Raises with a descriptive error if a
    required sensor cannot be located (fails loudly rather than guessing
    silently, per Section 30 - no silent continuation after a failure).
    """
    if not os.path.isdir(raw_dir):
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")

    files = [f for f in os.listdir(raw_dir)
             if f.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff"))]

    normalized_lookup = {_normalize(f): f for f in files}

    mapping = {}
    unresolved = []
    for sensor_key, meta in SENSOR_TABLE.items():
        found = None
        for alias in meta["aliases"]:
            alias_n = _normalize(alias)
            for norm_name, real_name in normalized_lookup.items():
                if alias_n == norm_name or alias_n in norm_name:
                    found = real_name
                    break
            if found:
                break
        if found:
            mapping[sensor_key] = os.path.join(raw_dir, found)
        else:
            unresolved.append(sensor_key)

    if unresolved:
        raise FileNotFoundError(
            f"Could not robustly locate sensor image(s) for: {unresolved}. "
            f"Files present in {raw_dir}: {files}"
        )

    return mapping


def _read_raw(path: str) -> np.ndarray:
    """Read image preserving original bit depth/channels. No modification."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(f"Failed to read image: {path}")
    return img


def _to_grayscale_analysis_view(img: np.ndarray) -> np.ndarray:
    """A read-only grayscale VIEW used only for statistics, never persisted
    over the original array."""
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img[..., 0]


def _estimate_noise_sigma(gray: np.ndarray) -> float:
    """
    Fast, standard noise-sigma estimator (Immerkaer 1996) using the
    Laplacian-of-a-checkerboard operator. Real measurement, not a guess.
    """
    H, W = gray.shape
    g = gray.astype(np.float64)
    M = [[1, -2, 1], [-2, 4, -2], [1, -2, 1]]
    conv = cv2.filter2D(g, -1, np.array(M, dtype=np.float64))
    sigma = np.sum(np.abs(conv)) * np.sqrt(0.5 * np.pi) / (6 * (W - 2) * (H - 2))
    return float(sigma)


def _estimate_feature_density(gray: np.ndarray) -> float:
    """Fraction of pixels flagged as structurally significant by FAST corner
    detection - a real, computed proxy for feature density."""
    fast = cv2.FastFeatureDetector_create(threshold=20)
    kps = fast.detect(gray, None)
    return float(len(kps)) / float(gray.shape[0] * gray.shape[1]) * 1e4  # per 10k px


def _speckle_index(gray: np.ndarray) -> Optional[float]:
    """Coefficient-of-variation based speckle index (std/mean over a sliding
    local window average) - the standard SAR speckle descriptor."""
    g = gray.astype(np.float64)
    mean = cv2.blur(g, (7, 7))
    mean_sq = cv2.blur(g * g, (7, 7))
    var = np.clip(mean_sq - mean ** 2, 0, None)
    std = np.sqrt(var)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(mean > 1e-6, std / mean, 0)
    return float(np.nanmean(cv))


def characterize_image(sensor_key: str, path: str) -> dict:
    """Compute the full forensic characterization block for one image
    (Section 6). All values are real, measured quantities."""
    raw = _read_raw(path)
    gray = _to_grayscale_analysis_view(raw)
    g = gray.astype(np.float64)

    h, w = gray.shape[:2]
    channels = 1 if raw.ndim == 2 else raw.shape[2]

    hist, _ = np.histogram(gray, bins=32, range=(0, 255) if gray.dtype == np.uint8 else None)
    hist_norm = (hist / hist.sum()).tolist()

    invalid_mask = ~np.isfinite(raw.astype(np.float64)) if np.issubdtype(raw.dtype, np.floating) else np.zeros_like(gray, dtype=bool)

    stats = {
        "sensor": sensor_key,
        "filename": os.path.basename(path),
        "source_path": path,
        "width": int(w),
        "height": int(h),
        "channels": int(channels),
        "dtype": str(raw.dtype),
        "min": float(np.min(g)),
        "max": float(np.max(g)),
        "mean": float(np.mean(g)),
        "std": float(np.std(g)),
        "median": float(np.median(g)),
        "percentile_1": float(np.percentile(g, 1)),
        "percentile_5": float(np.percentile(g, 5)),
        "percentile_95": float(np.percentile(g, 95)),
        "percentile_99": float(np.percentile(g, 99)),
        "dynamic_range": float(np.max(g) - np.min(g)),
        "histogram_32bin": hist_norm,
        "estimated_noise_sigma": _estimate_noise_sigma(gray),
        "approx_feature_density_per_10k_px": _estimate_feature_density(gray),
        "has_nan_or_inf": bool(invalid_mask.any()),
        "orientation": "landscape" if w >= h else "portrait",
        "aspect_ratio": float(w) / float(h),
        "visual_contrast_std_over_mean": float(np.std(g) / (np.mean(g) + 1e-6)),
        "saturated_high_fraction": float(np.mean(gray >= 250)) if gray.dtype == np.uint8 else None,
        "saturated_low_fraction": float(np.mean(gray <= 2)) if gray.dtype == np.uint8 else None,
    }

    if sensor_key == "SAR":
        stats["speckle_index_mean_cv"] = _speckle_index(gray)

    if sensor_key in ("TMC-Azimuth", "TMC-Slope"):
        # Determine continuous vs categorical-like behaviour: count unique
        # quantized levels relative to the theoretical range.
        unique_vals = np.unique(gray)
        stats["unique_value_count"] = int(len(unique_vals))
        stats["behaves_as_categorical"] = bool(len(unique_vals) < 40)

    return stats


@dataclass
class SensorRecord:
    key: str
    role: str
    sensor_full_name: str
    file: str
    stats: dict = field(default_factory=dict)


def build_manifest(raw_dir: str, metadata_dir: str) -> dict:
    """
    PHASE 1 - DATASET FORENSIC ANALYSIS.
    Discovers, characterizes, and records the real dataset. Writes a
    machine-readable manifest to metadata_dir and returns it.
    """
    os.makedirs(metadata_dir, exist_ok=True)
    mapping = discover_dataset(raw_dir)

    records = {}
    for sensor_key, path in mapping.items():
        meta = SENSOR_TABLE[sensor_key]
        stats = characterize_image(sensor_key, path)
        with open(path, "rb") as fh:
            file_hash = hashlib.sha256(fh.read()).hexdigest()
        records[sensor_key] = {
            "role": meta["role"],
            "sensor_full_name": meta["sensor_full_name"],
            "kind": meta["kind"],
            "file": path,
            "sha256": file_hash,
            "stats": stats,
        }

    manifest = {
        "project": "INVINCIBLES",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_sensor": "OHRC",
        "reference_locked": True,
        "region_scope": "single-region (reusable engine)",
        "sensors": records,
    }

    out_path = os.path.join(metadata_dir, "dataset_manifest.json")
    with open(out_path, "w") as fh:
        json.dump(manifest, fh, indent=2)

    return manifest


def readiness_report(manifest: dict) -> dict:
    """Section 55 - technical readiness report derived from the actual
    manifest (not a hard-coded checklist)."""
    sensors_present = {k: True for k in manifest["sensors"].keys()}
    required = ["OHRC", "TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"]
    report = {k: (k in manifest["sensors"]) for k in required}

    # Feasibility flags are computed from real characteristics where possible.
    ohrc_stats = manifest["sensors"].get("OHRC", {}).get("stats", {})
    report["phase_congruency_feasible"] = ohrc_stats.get("width", 0) > 32 and ohrc_stats.get("height", 0) > 32
    report["rift_feasible"] = report["phase_congruency_feasible"]
    report["fsc_gtm_feasible"] = True  # graph/grid consensus has no hard image precondition
    report["subpixel_feasible"] = True
    report["multiband_output_feasible"] = all(report[k] for k in required)
    return report
