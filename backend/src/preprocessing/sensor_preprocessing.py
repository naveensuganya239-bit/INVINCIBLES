"""
INVINCIBLES - Sensor-Aware Preprocessing
==========================================
Implements Spec Section 9. Preprocessing respects the physical meaning of
each modality. The ORIGINAL radiometric/terrain values are never modified;
a separate "analysis view" is produced for feature extraction only.
"""
from __future__ import annotations
import numpy as np
import cv2


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img.copy()
    if img.shape[2] == 4:
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def clahe_enhance(gray: np.ndarray, clip_limit: float = 2.5, tile: int = 8) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return clahe.apply(gray)


def bilateral_denoise(gray: np.ndarray, d: int = 5, sigma_color: float = 40, sigma_space: float = 40) -> np.ndarray:
    return cv2.bilateralFilter(gray, d, sigma_color, sigma_space)


def lee_filter(gray: np.ndarray, win: int = 7) -> np.ndarray:
    """
    Refined-Lee style adaptive speckle filter for SAR.
    Suppresses multiplicative speckle noise while preserving edges by
    weighting the local mean/pixel value with the ratio of local variance
    to (local variance + noise variance), which is the classical Lee (1980)
    adaptive filter formulation.
    """
    img = gray.astype(np.float64)
    mean = cv2.boxFilter(img, -1, (win, win))
    mean_sq = cv2.boxFilter(img * img, -1, (win, win))
    var = np.clip(mean_sq - mean ** 2, 0, None)

    overall_variance = np.var(img)
    noise_variance = max(overall_variance * 0.05, 1e-6)  # measured proxy for speckle variance

    weight = var / (var + noise_variance + 1e-6)
    filtered = mean + weight * (img - mean)
    return np.clip(filtered, 0, 255).astype(np.uint8)


def frost_filter(gray: np.ndarray, win: int = 7, damping: float = 2.0) -> np.ndarray:
    """Frost filter alternative for SAR speckle suppression (exponential
    distance-weighted kernel driven by local coefficient of variation)."""
    img = gray.astype(np.float64)
    pad = win // 2
    padded = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REFLECT)
    out = np.zeros_like(img)
    yy, xx = np.mgrid[-pad:pad + 1, -pad:pad + 1]
    dist = np.sqrt(xx ** 2 + yy ** 2)

    mean = cv2.boxFilter(img, -1, (win, win))
    mean_sq = cv2.boxFilter(img * img, -1, (win, win))
    var = np.clip(mean_sq - mean ** 2, 0, None)
    cv_local = np.sqrt(var) / (mean + 1e-6)

    H, W = img.shape
    for i in range(H):
        for j in range(W):
            patch = padded[i:i + win, j:j + win]
            k = damping * cv_local[i, j]
            kernel = np.exp(-k * dist)
            kernel /= kernel.sum() + 1e-9
            out[i, j] = np.sum(kernel * patch)
    return np.clip(out, 0, 255).astype(np.uint8)


def preprocess_sensor(sensor_key: str, gray: np.ndarray) -> dict:
    """
    Returns a dict:
      original        -> untouched grayscale analysis view
      analysis_view   -> sensor-appropriate enhanced view used for feature
                         extraction ONLY
      method          -> textual description of what was applied and why
    """
    original = gray.copy()

    if sensor_key == "OHRC":
        denoised = bilateral_denoise(original)
        view = clahe_enhance(denoised)
        method = "CLAHE(clip=2.5,tile=8) on bilateral-denoised grayscale (reference sharpening for feature extraction only)"

    elif sensor_key == "IIRS":
        denoised = bilateral_denoise(original, d=5, sigma_color=30, sigma_space=30)
        view = clahe_enhance(denoised, clip_limit=3.0)
        method = "Local-contrast normalization via CLAHE(clip=3.0) on denoised IIRS view; original spectral values preserved separately"

    elif sensor_key == "SAR":
        # Choose based on measured speckle severity (coefficient of variation)
        mean = cv2.blur(original.astype(np.float64), (7, 7))
        std = np.sqrt(np.clip(cv2.blur(original.astype(np.float64) ** 2, (7, 7)) - mean ** 2, 0, None))
        cv_index = float(np.mean(std / (mean + 1e-6)))
        if cv_index > 0.35:
            view = lee_filter(original, win=7)
            method = f"Refined Lee adaptive speckle filter (measured speckle CV={cv_index:.3f} > 0.35 threshold)"
        else:
            view = bilateral_denoise(original, d=5, sigma_color=25, sigma_space=25)
            method = f"Bilateral denoise (measured speckle CV={cv_index:.3f} <= 0.35 threshold; Lee filter unnecessary)"
        view = clahe_enhance(view, clip_limit=2.0)

    elif sensor_key in ("TMC-Azimuth", "TMC-Slope"):
        # Derived terrain product: do NOT apply arbitrary photometric
        # normalization to the semantic values. Build a *separate* visual/
        # feature-extraction representation only.
        view = clahe_enhance(original, clip_limit=1.5)
        method = "No photometric alteration of semantic terrain values; mild CLAHE(clip=1.5) applied ONLY to a separate feature-extraction view"

    else:
        view = clahe_enhance(original)
        method = "Default CLAHE enhancement"

    return {"original": original, "analysis_view": view, "method": method}
