"""
Interpolates the local (fit-set) residual field measured after the global
transform onto arbitrary query points (typically the independent
checkpoint points), giving an honest estimate of what a local terrain-
relief correction would do to points that were NOT used to build it -
without requiring a full dense re-warp for every metric calculation.
"""
from __future__ import annotations
import numpy as np
from scipy.interpolate import griddata


def interpolate_local_correction(fit_ref_pts, residual_vectors, query_pts):
    fit_ref_pts = np.array(fit_ref_pts, dtype=np.float64)
    residual_vectors = np.array(residual_vectors, dtype=np.float64)
    query_pts = np.array(query_pts, dtype=np.float64)

    if len(fit_ref_pts) < 4 or len(query_pts) == 0:
        return np.zeros_like(query_pts)

    try:
        corr_x = griddata(fit_ref_pts, residual_vectors[:, 0], query_pts, method="linear", fill_value=0.0)
        corr_y = griddata(fit_ref_pts, residual_vectors[:, 1], query_pts, method="linear", fill_value=0.0)
    except Exception:
        return np.zeros_like(query_pts)

    corr_x = np.nan_to_num(corr_x)
    corr_y = np.nan_to_num(corr_y)
    return np.stack([corr_x, corr_y], axis=1)
