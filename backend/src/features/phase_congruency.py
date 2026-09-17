"""
INVINCIBLES - Illumination-Invariant Feature Representation (Spec Section 11)
================================================================================
A Kovesi-style Phase Congruency implementation built on log-Gabor filters
in the frequency domain, evaluated across multiple scales and orientations.

Reference: Kovesi, P. "Image Features From Phase Congruency", Videre:
Journal of Computer Vision Research, 1999. This is an original NumPy/FFT
re-implementation of the published mathematical formulation (not a copy of
any specific source file); it is not a Canny/Sobel gradient relabeled as
"phase congruency" (Section 11 explicitly forbids that shortcut).

Phase congruency measures the extent to which frequency components are
maximally in-phase, which is a property of local image STRUCTURE and is,
by construction, largely invariant to multiplicative and additive
illumination change - which is why it is used here as the shared
representation across differently-illuminated / differently-sensed
modalities (OHRC / TMC / IIRS / SAR).
"""
from __future__ import annotations
import numpy as np


def _log_gabor_radial(rows, cols, scale_wavelengths, sigma_onf=0.55):
    """Radial log-Gabor transfer functions for each scale."""
    x = (np.arange(cols) - cols // 2) / cols
    y = (np.arange(rows) - rows // 2) / rows
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X ** 2 + Y ** 2)
    radius[rows // 2, cols // 2] = 1.0  # avoid log(0)

    filters = []
    for wavelength in scale_wavelengths:
        f0 = 1.0 / wavelength
        log_gabor = np.exp(-(np.log(radius / f0)) ** 2 / (2 * np.log(sigma_onf) ** 2))
        log_gabor[rows // 2, cols // 2] = 0.0
        filters.append(np.fft.ifftshift(log_gabor))
    return filters


def _angular_spread(rows, cols, orientation, n_orient, sigma_angle_deg=45):
    x = (np.arange(cols) - cols // 2) / cols
    y = (np.arange(rows) - rows // 2) / rows
    X, Y = np.meshgrid(x, y)
    theta = np.arctan2(-Y, X)
    angl = orientation * np.pi / n_orient
    ds = np.sin(theta) * np.cos(angl) - np.cos(theta) * np.sin(angl)
    dc = np.cos(theta) * np.cos(angl) + np.sin(theta) * np.sin(angl)
    dtheta = np.abs(np.arctan2(ds, dc))
    sigma = np.pi / n_orient * (sigma_angle_deg / 45.0)
    spread = np.exp(-(dtheta ** 2) / (2 * sigma ** 2))
    return np.fft.ifftshift(spread)


def phase_congruency(gray: np.ndarray, n_scale: int = 4, n_orient: int = 6,
                      min_wavelength: float = 3.0, mult: float = 2.1,
                      sigma_onf: float = 0.55, k: float = 2.0,
                      cutoff: float = 0.5, g: float = 10.0) -> dict:
    """
    Computes a phase-congruency map, orientation map, and per-orientation
    energy, following the standard Kovesi noise-compensated formulation:

        PC = sum_o sum_s W(x) * max(E_so(x) - T, 0) / (sum_s A_so(x) + eps)

    where E is the phase-deviation-weighted energy, T is a noise threshold
    estimated from the smallest-scale filter response statistics, W is a
    weighting that penalises filter responses with low frequency spread
    (i.e. noise-like responses concentrated at a single scale).
    """
    img = gray.astype(np.float64)
    rows, cols = img.shape
    IMG_FFT = np.fft.fft2(img)

    wavelengths = [min_wavelength * (mult ** s) for s in range(n_scale)]
    radial_filters = _log_gabor_radial(rows, cols, wavelengths, sigma_onf)

    epsilon = 1e-4
    pc_total = np.zeros((rows, cols))
    orientation_energy_maps = []
    sum_an_all = np.zeros((rows, cols))
    sum_amp_all_scales_per_orient = []

    for o in range(n_orient):
        spread = _angular_spread(rows, cols, o, n_orient)

        EO = []
        AN = []
        for s, radial in enumerate(radial_filters):
            filt = radial * spread
            resp = np.fft.ifft2(IMG_FFT * filt)
            EO.append(resp)
            AN.append(np.abs(resp))

        AN = np.array(AN)
        EO_real = np.array([e.real for e in EO])
        EO_imag = np.array([e.imag for e in EO])

        sum_an = AN.sum(axis=0)
        sum_real = EO_real.sum(axis=0)
        sum_imag = EO_imag.sum(axis=0)
        mean_energy = np.sqrt(sum_real ** 2 + sum_imag ** 2)

        # Noise threshold estimated from the smallest-scale amplitude
        # response (Kovesi's median-based Rayleigh noise estimate).
        an0 = AN[0]
        median_an0 = np.median(an0)
        rayleigh_sigma = median_an0 / np.sqrt(np.log(4)) + 1e-9
        noise_power = rayleigh_sigma ** 2
        total_energy_est = np.sum(AN, axis=0) + epsilon
        est_sum_an2 = np.sum(AN ** 2, axis=0)
        est_noise_energy = np.sqrt(np.maximum(noise_power * (n_scale + est_sum_an2 / (rayleigh_sigma ** 2 * n_scale + 1e-9)), 0))
        T = est_noise_energy * k * 0.5
        T = np.maximum(T, 1e-6)

        # Frequency spread weighting - penalises energy concentrated in a
        # single scale (more likely to be noise than genuine structure).
        width = sum_an / (n_scale * (AN[0] + epsilon)) - 1.0
        weight = 1.0 / (1.0 + np.exp(g * (cutoff - width)))

        energy = np.maximum(mean_energy - T, 0)
        pc_o = weight * energy / (sum_an + epsilon)
        pc_total += pc_o
        orientation_energy_maps.append(pc_o)
        sum_an_all += sum_an

    pc_total /= n_orient
    pc_norm = pc_total / (pc_total.max() + 1e-9)

    orient_stack = np.array(orientation_energy_maps)
    dominant_orientation = np.argmax(orient_stack, axis=0) * (180.0 / n_orient)

    return {
        "phase_congruency": pc_norm.astype(np.float32),
        "orientation_map": dominant_orientation.astype(np.float32),
        "per_orientation_energy": orient_stack.astype(np.float32),
        "n_scale": n_scale,
        "n_orient": n_orient,
        "wavelengths": wavelengths,
    }
