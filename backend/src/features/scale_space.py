"""
INVINCIBLES - Multi-Scale Representation (Spec Section 10)
============================================================
Explicit Gaussian scale-space pyramid so that scale differences between
sensors (resolution, sampling, apparent feature size) are handled directly
by the feature-detection/matching stages rather than by a single resize.
"""
from __future__ import annotations
import numpy as np
import cv2


def build_gaussian_pyramid(gray: np.ndarray, num_levels: int = 4, scale_factor: float = 1.6, base_sigma: float = 1.0):
    """
    Returns a list of dicts: {level, scale, sigma, image}
    scale=1.0 is the original resolution; each subsequent level is
    progressively blurred at a matching sigma AND resampled, giving a true
    multi-resolution scale-space (not merely a resize).
    """
    levels = []
    current = gray.astype(np.float32)
    sigma = base_sigma
    scale = 1.0
    h0, w0 = gray.shape[:2]

    for lvl in range(num_levels):
        blurred = cv2.GaussianBlur(current, (0, 0), sigmaX=sigma)
        levels.append({
            "level": lvl,
            "scale": float(scale),
            "sigma": float(sigma),
            "width": int(blurred.shape[1]),
            "height": int(blurred.shape[0]),
            "image": np.clip(blurred, 0, 255).astype(np.uint8) if gray.dtype == np.uint8 else blurred,
        })
        new_w = max(8, int(round(w0 / (scale * scale_factor))))
        new_h = max(8, int(round(h0 / (scale * scale_factor))))
        current = cv2.resize(blurred, (new_w, new_h), interpolation=cv2.INTER_AREA)
        scale *= scale_factor
        sigma = base_sigma  # re-applied at each new (smaller) resolution

    return levels
