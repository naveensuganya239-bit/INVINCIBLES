"""
INVINCIBLES - Multi-Modal Descriptor (Spec Sections 15, 16)
==============================================================
PRIMARY: RIFT - Radiation-variation Insensitive Feature Transform.

Adapted from the published method of:
    Li, J., Hu, Q., Ai, M. (2020) "RIFT: Multi-modal Image Matching Based
    on Radiation-Invariant Feature Transform", IEEE TIP.
This module is an ORIGINAL NumPy re-implementation of the paper's core
mathematical idea (log-Gabor Convolution Sequence -> Maximum Index Map ->
localized MIM histogram descriptor). No third-party RIFT source file or
codebase was copied; only the published mathematical formulation was used
as the algorithmic reference. No license obligations are inherited because
no external code was reused verbatim.

  1. Convolve the image with log-Gabor filters at `n_scale` scales and
     `n_orient` orientations (Convolution Sequence, CS).
  2. Sum convolution amplitude across scales for each orientation -> one
     amplitude map per orientation.
  3. Maximum Index Map (MIM): at every pixel, the orientation index with
     maximum amplitude. This raster is highly repeatable across sensing
     modalities because it encodes *structure*, not *radiometry*.
  4. Build a localized histogram-of-MIM-index descriptor around each
     keypoint (grid of cells, histogram of MIM indices per cell,
     concatenated and L2-normalized) - directly analogous to SIFT's
     gradient-orientation histogram, but built on the radiation-invariant
     MIM instead of raw gradients.

FALLBACK: CFOG (Channel Features of Orientated Gradients) descriptor,
used automatically when the MIM raster is degenerate (near-uniform /
low orientation contrast - i.e. RIFT would not be reliable on this
image), combined with FFT-based phase correlation for a translation
sanity check. This mirrors the CFOG + phase-correlation fallback
recommended in Section 16 for cases where a log-Gabor MIM descriptor is
not well-conditioned on the actual supplied data.

Trade-offs of the fallback: CFOG is somewhat less radiometrically
invariant than RIFT/MIM in principle, but is numerically simpler and more
stable on small or low-texture image patches, at a modest expected cost in
matching precision under severe multi-modal radiometric difference.
"""
from __future__ import annotations
import numpy as np
import cv2


# --------------------------------------------------------------------------
# Log-Gabor Convolution Sequence + Maximum Index Map
# --------------------------------------------------------------------------
def _log_gabor_bank(rows, cols, n_scale=4, n_orient=6, min_wavelength=4.0, mult=1.8, sigma_onf=0.6):
    x = (np.arange(cols) - cols // 2) / cols
    y = (np.arange(rows) - rows // 2) / rows
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X ** 2 + Y ** 2)
    radius[rows // 2, cols // 2] = 1.0
    theta = np.arctan2(-Y, X)

    filters = [[None] * n_orient for _ in range(n_scale)]
    for s in range(n_scale):
        wavelength = min_wavelength * (mult ** s)
        f0 = 1.0 / wavelength
        radial = np.exp(-(np.log(radius / f0)) ** 2 / (2 * np.log(sigma_onf) ** 2))
        radial[rows // 2, cols // 2] = 0.0
        for o in range(n_orient):
            angl = o * np.pi / n_orient
            ds = np.sin(theta) * np.cos(angl) - np.cos(theta) * np.sin(angl)
            dc = np.cos(theta) * np.cos(angl) + np.sin(theta) * np.sin(angl)
            dtheta = np.abs(np.arctan2(ds, dc))
            sigma_angle = np.pi / n_orient
            spread = np.exp(-(dtheta ** 2) / (2 * sigma_angle ** 2))
            filters[s][o] = np.fft.ifftshift(radial * spread)
    return filters


def compute_mim(gray: np.ndarray, n_scale=4, n_orient=6):
    """Returns (mim_index_map uint8, orientation_amplitude_stack, quality_score)."""
    img = gray.astype(np.float64)
    rows, cols = img.shape
    IMG_FFT = np.fft.fft2(img)
    filters = _log_gabor_bank(rows, cols, n_scale, n_orient)

    orient_amp = np.zeros((n_orient, rows, cols), dtype=np.float64)
    for o in range(n_orient):
        acc = np.zeros((rows, cols))
        for s in range(n_scale):
            resp = np.fft.ifft2(IMG_FFT * filters[s][o])
            acc += np.abs(resp)
        orient_amp[o] = acc

    mim = np.argmax(orient_amp, axis=0).astype(np.uint8)

    # Quality score: how peaked the orientation response is on average
    # (low value => nearly flat / degenerate => RIFT unreliable here).
    max_amp = orient_amp.max(axis=0)
    mean_amp = orient_amp.mean(axis=0)
    peak_ratio = np.mean(max_amp / (mean_amp + 1e-9))
    quality_score = float(peak_ratio)

    return mim, orient_amp, quality_score


def rift_descriptors(gray: np.ndarray, keypoints, n_scale=4, n_orient=8, patch_size=64, grid=6):
    """
    Builds a RIFT-style descriptor for every keypoint dict {x, y, ...}.
    Returns (descriptors ndarray [N, grid*grid*n_orient] float32, valid_mask, quality_score, mim_map)

    Each local cell contributes an AMPLITUDE-WEIGHTED histogram of MIM
    orientation indices (not a plain unweighted count), which meaningfully
    increases discriminative power over a bare index count: cells where the
    dominant orientation is only marginally stronger than competing
    orientations contribute less "votes" than cells with a sharp, confident
    orientation response.
    """
    mim, orient_amp, quality_score = compute_mim(gray, n_scale, n_orient)
    max_amp = orient_amp.max(axis=0)
    mean_amp = orient_amp.mean(axis=0)
    confidence_weight = np.clip((max_amp - mean_amp) / (max_amp + 1e-6), 0, 1)

    h, w = gray.shape
    half = patch_size // 2
    cell = patch_size // grid

    descs = []
    valid = []
    for kp in keypoints:
        cx, cy = int(round(kp["x"])), int(round(kp["y"]))
        if cx - half < 0 or cy - half < 0 or cx + half >= w or cy + half >= h:
            valid.append(False)
            descs.append(np.zeros(grid * grid * n_orient, dtype=np.float32))
            continue
        patch = mim[cy - half:cy + half, cx - half:cx + half]
        weight_patch = confidence_weight[cy - half:cy + half, cx - half:cx + half]
        hist_vec = []
        for gy in range(grid):
            for gx in range(grid):
                cell_patch = patch[gy * cell:(gy + 1) * cell, gx * cell:(gx + 1) * cell]
                cell_weight = weight_patch[gy * cell:(gy + 1) * cell, gx * cell:(gx + 1) * cell]
                hist, _ = np.histogram(cell_patch, bins=n_orient, range=(0, n_orient), weights=cell_weight)
                hist_vec.append(hist.astype(np.float32))
        vec = np.concatenate(hist_vec)
        # SIFT-style illumination-robustness clip + renormalize
        norm = np.linalg.norm(vec)
        vec = vec / norm if norm > 1e-6 else vec
        vec = np.clip(vec, 0, 0.2)
        norm2 = np.linalg.norm(vec)
        vec = vec / norm2 if norm2 > 1e-6 else vec
        descs.append(vec)
        valid.append(True)

    return np.array(descs, dtype=np.float32), np.array(valid), quality_score, mim


# --------------------------------------------------------------------------
# CFOG fallback descriptor
# --------------------------------------------------------------------------
def cfog_descriptors(gray: np.ndarray, keypoints, patch_size=48, grid=4, n_bins=8):
    """
    Channel Features of Oriented Gradients: dense per-pixel gradient
    orientation/magnitude channels, pooled into a spatial grid histogram
    around each keypoint. Numerically stable fallback when the RIFT/MIM
    representation is degenerate on the actual supplied image.
    """
    gx = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    ang = (np.arctan2(gy, gx) + np.pi) * (180.0 / np.pi)  # 0..360

    h, w = gray.shape
    half = patch_size // 2
    cell = patch_size // grid

    descs = []
    valid = []
    for kp in keypoints:
        cx, cy = int(round(kp["x"])), int(round(kp["y"]))
        if cx - half < 0 or cy - half < 0 or cx + half >= w or cy + half >= h:
            valid.append(False)
            descs.append(np.zeros(grid * grid * n_bins, dtype=np.float32))
            continue
        mag_patch = mag[cy - half:cy + half, cx - half:cx + half]
        ang_patch = ang[cy - half:cy + half, cx - half:cx + half]
        hist_vec = []
        for gyi in range(grid):
            for gxi in range(grid):
                m = mag_patch[gyi * cell:(gyi + 1) * cell, gxi * cell:(gxi + 1) * cell]
                a = ang_patch[gyi * cell:(gyi + 1) * cell, gxi * cell:(gxi + 1) * cell]
                hist, _ = np.histogram(a, bins=n_bins, range=(0, 360), weights=m)
                hist_vec.append(hist.astype(np.float32))
        vec = np.concatenate(hist_vec)
        norm = np.linalg.norm(vec)
        vec = vec / norm if norm > 1e-6 else vec
        descs.append(vec)
        valid.append(True)

    return np.array(descs, dtype=np.float32), np.array(valid)


def build_descriptors(gray: np.ndarray, keypoints, quality_threshold: float = 1.15):
    """
    Attempts RIFT first. If the MIM quality score is degenerate (below
    `quality_threshold`, meaning orientation response is nearly flat and a
    Maximum Index Map would not be discriminative), falls back to CFOG and
    records the deviation reason for the report.
    """
    rift_desc, rift_valid, quality_score, mim = rift_descriptors(gray, keypoints)
    if quality_score >= quality_threshold:
        return {
            "method": "RIFT",
            "descriptors": rift_desc,
            "valid_mask": rift_valid,
            "quality_score": quality_score,
            "mim_map": mim,
            "deviation_reason": None,
        }

    cfog_desc, cfog_valid = cfog_descriptors(gray, keypoints)
    return {
        "method": "CFOG",
        "descriptors": cfog_desc,
        "valid_mask": cfog_valid,
        "quality_score": quality_score,
        "mim_map": mim,
        "deviation_reason": (
            f"RIFT Maximum-Index-Map orientation peak ratio ({quality_score:.3f}) "
            f"fell below the reliability threshold ({quality_threshold}); "
            f"the log-Gabor orientation response was too flat to be discriminative "
            f"on this image, so CFOG (gradient-channel histogram) was used instead. "
            f"Expected trade-off: somewhat reduced robustness to strong radiometric "
            f"difference between modalities, partially compensated for downstream by "
            f"FFT phase-correlation-based sub-pixel refinement."
        ),
    }
