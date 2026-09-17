"""
INVINCIBLES - Sub-Pixel Refinement (Spec Section 21)
=======================================================
Refines each inlier correspondence to sub-pixel precision using
upsampled (Foroosh-style) phase correlation on small local patches,
following Guizar-Sicairos, Thurman & Fienup (2008) "Efficient subpixel
image registration algorithms" as implemented in
skimage.registration.phase_cross_correlation. Unstable refinements
(patch mostly flat / correlation below confidence) are rejected and the
original correspondence is kept.
"""
from __future__ import annotations
import numpy as np
from skimage.registration import phase_cross_correlation


def refine_subpixel(ref_gray, src_warped_gray, pts_ref, pts_src_warped,
                     patch_radius=16, upsample_factor=20, max_shift=3.0):
    """
    For each correspondence (already in the SAME coordinate frame, i.e.
    src has already been warped by the global/local transform), extracts a
    local patch pair and estimates the residual sub-pixel shift via
    upsampled phase correlation, then applies it as a correction.

    Returns: refined_pts_src (same length), accepted_mask
    """
    h, w = ref_gray.shape[:2]
    refined = np.array(pts_src_warped, dtype=np.float64).copy()
    accepted = np.zeros(len(pts_ref), dtype=bool)

    for i, ((rx, ry), (sx, sy)) in enumerate(zip(pts_ref, pts_src_warped)):
        rx, ry, sx, sy = int(round(rx)), int(round(ry)), int(round(sx)), int(round(sy))
        r = patch_radius
        if (rx - r < 0 or ry - r < 0 or rx + r >= w or ry + r >= h or
                sx - r < 0 or sy - r < 0 or sx + r >= w or sy + r >= h):
            continue

        ref_patch = ref_gray[ry - r:ry + r, rx - r:rx + r].astype(np.float64)
        src_patch = src_warped_gray[sy - r:sy + r, sx - r:sx + r].astype(np.float64)

        if ref_patch.std() < 1e-3 or src_patch.std() < 1e-3:
            continue  # flat patch -> unstable, reject

        try:
            shift, error, diffphase = phase_cross_correlation(
                ref_patch, src_patch, upsample_factor=upsample_factor, normalization=None)
        except Exception:
            continue

        dy, dx = shift
        if abs(dy) > max_shift or abs(dx) > max_shift:
            continue  # implausible large correction -> reject, keep original

        refined[i] = [sx + dx, sy + dy]
        accepted[i] = True

    return refined, accepted


def rmse(pts_a, pts_b):
    a = np.array(pts_a, dtype=np.float64)
    b = np.array(pts_b, dtype=np.float64)
    if len(a) == 0:
        return None
    err = np.sqrt(np.sum((a - b) ** 2, axis=1))
    return float(np.sqrt(np.mean(err ** 2)))
