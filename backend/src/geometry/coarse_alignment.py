"""
INVINCIBLES - Coarse Geometric Alignment (Spec Section 14)
=============================================================
Estimates a coarse similarity transform (scale, rotation, translation)
between a source phase-congruency map and the OHRC reference
phase-congruency map, using the Fourier-Mellin / log-polar phase
correlation technique. This uses structural (phase-congruency edge)
information rather than raw intensity, and does not require detecting an
explicit crater ellipse (which is not reliably present in every modality);
this is the "strongest technically justified fallback" flagged as
acceptable in Section 14 when explicit crater-boundary detection cannot be
guaranteed to generalize across sensors.
"""
from __future__ import annotations
import numpy as np
import cv2


def _highpass_emphasis(shape):
    rows, cols = shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    cy, cx = rows / 2.0, cols / 2.0
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    radius /= radius.max() + 1e-9
    hp = np.cos(np.pi / 2 * radius) ** 2
    return np.fft.ifftshift(hp)


def _log_polar_fft_magnitude(img: np.ndarray):
    rows, cols = img.shape
    F = np.fft.fft2(img)
    Fshift = np.fft.fftshift(F)
    magnitude = np.abs(Fshift)
    magnitude *= np.fft.fftshift(_highpass_emphasis((rows, cols)))
    magnitude = np.nan_to_num(magnitude, nan=0.0, posinf=0.0, neginf=0.0)

    center = (cols / 2.0, rows / 2.0)
    max_radius = min(rows, cols) / 2.0
    log_base = np.exp(np.log(max_radius) / max_radius)
    lp = cv2.logPolar(magnitude.astype(np.float32), center, max_radius / np.log(max_radius + 1e-9),
                       flags=cv2.INTER_LINEAR)
    lp = np.nan_to_num(lp, nan=0.0, posinf=0.0, neginf=0.0)
    return lp


def estimate_coarse_similarity(ref_map: np.ndarray, src_map: np.ndarray) -> dict:
    """
    Returns a dict with keys: scale, rotation_deg, tx, ty, matrix (2x3),
    confidence (phase-correlation response peak value).
    Resizes src to ref's shape first purely for the FFT correlation stage
    (this does not replace true scale-space feature matching later - it
    only estimates an initial coarse hypothesis).
    """
    h, w = ref_map.shape[:2]
    src_resized_for_fft = cv2.resize(src_map, (w, h), interpolation=cv2.INTER_LINEAR)

    ref_f = ref_map.astype(np.float32)
    src_f = src_resized_for_fft.astype(np.float32)

    ref_lp = _log_polar_fft_magnitude(ref_f)
    src_lp = _log_polar_fft_magnitude(src_f)

    (dx_lp, dy_lp), response_rs = cv2.phaseCorrelate(ref_lp, src_lp)
    if not (np.isfinite(dx_lp) and np.isfinite(dy_lp)):
        dx_lp, dy_lp, response_rs = 0.0, 0.0, 0.0

    max_radius = min(h, w) / 2.0
    log_base = np.exp(np.log(max_radius) / max_radius)
    rotation_deg = -(dy_lp * 180.0 / ref_lp.shape[0])
    scale_est_true_res = float(log_base ** dx_lp)
    if not np.isfinite(rotation_deg):
        rotation_deg = 0.0
    if not np.isfinite(scale_est_true_res) or scale_est_true_res <= 0:
        scale_est_true_res = 1.0
    # this scale is relative to the FFT-sized comparison; combine with the
    # true resize ratio actually applied so it reflects real source/ref scale
    true_scale_ratio = (src_map.shape[1] / w)
    scale = scale_est_true_res * true_scale_ratio if np.isfinite(scale_est_true_res) and scale_est_true_res > 0 else true_scale_ratio

    # Now recover translation using standard phase correlation directly on
    # rotation/scale corrected images.
    M_rs = cv2.getRotationMatrix2D((w / 2, h / 2), rotation_deg, 1.0 / scale_est_true_res if scale_est_true_res > 0 else 1.0)
    src_corrected = cv2.warpAffine(src_resized_for_fft, M_rs, (w, h))

    (tx, ty), response_t = cv2.phaseCorrelate(ref_f, src_corrected.astype(np.float32))
    if not (np.isfinite(tx) and np.isfinite(ty)):
        tx, ty, response_t = 0.0, 0.0, 0.0

    # Compose full transform: src(original res) -> resize to ref res -> rotate/scale -> translate
    resize_scale_x = w / src_map.shape[1]
    resize_scale_y = h / src_map.shape[0]

    cos_a = np.cos(np.deg2rad(rotation_deg))
    sin_a = np.sin(np.deg2rad(rotation_deg))
    s = 1.0 / scale_est_true_res if scale_est_true_res > 0 else 1.0

    # Full affine mapping source(original pixel coords) -> ref pixel coords
    Sx = resize_scale_x
    Sy = resize_scale_y
    A = s * np.array([[cos_a, -sin_a], [sin_a, cos_a]]) @ np.array([[Sx, 0], [0, Sy]])
    t = np.array([tx + w / 2 - (A[0, 0] * w / 2 + A[0, 1] * h / 2),
                  ty + h / 2 - (A[1, 0] * w / 2 + A[1, 1] * h / 2)])

    matrix = np.array([[A[0, 0], A[0, 1], t[0]],
                        [A[1, 0], A[1, 1], t[1]]], dtype=np.float64)

    confidence = float(max(0.0, min(1.0, response_t)))

    return {
        "scale": float(1.0 / scale_est_true_res) if scale_est_true_res > 0 else 1.0,
        "rotation_deg": float(rotation_deg),
        "tx": float(t[0]),
        "ty": float(t[1]),
        "matrix": matrix.tolist(),
        "phase_correlation_confidence": confidence,
    }


def apply_coarse_transform(src_gray: np.ndarray, matrix, out_shape) -> np.ndarray:
    M = np.array(matrix, dtype=np.float64)
    h, w = out_shape[:2]
    return cv2.warpAffine(src_gray, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
