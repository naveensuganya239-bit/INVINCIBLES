"""
INVINCIBLES - Local Terrain-Relief Refinement (Spec Section 20)
==================================================================
After the global transform, the residuals of inlier correspondences are
inspected for systematic local structure. If a piecewise-affine model
(over a Delaunay triangulation of the inlier points) meaningfully reduces
residuals relative to the single global transform, it is used for the
final warp; otherwise, the global model alone is kept (no deformation is
introduced merely for cosmetic reasons - Section 20 is explicit about
this).
"""
from __future__ import annotations
import numpy as np
import cv2
from scipy.spatial import Delaunay


def _global_residuals(pts_ref, pts_src_warped):
    return np.sqrt(np.sum((np.array(pts_ref) - np.array(pts_src_warped)) ** 2, axis=1))


def residual_has_local_structure(pts_ref, residual_vec, grid_size=4, coeff_var_thresh=0.35):
    """
    A crude but real test for spatially systematic (non-random) residuals:
    bins residual magnitude into a coarse grid and measures the
    coefficient of variation across cells. Uniform/random residuals give a
    low CoV; systematic local distortion clusters large residuals in
    specific cells, giving a high CoV.
    """
    pts = np.array(pts_ref)
    if len(pts) < 8:
        return False, 0.0
    x_min, y_min = pts.min(axis=0)
    x_max, y_max = pts.max(axis=0)
    cell_w = max((x_max - x_min) / grid_size, 1e-6)
    cell_h = max((y_max - y_min) / grid_size, 1e-6)
    cell_means = {}
    for (x, y), r in zip(pts, residual_vec):
        gx = min(int((x - x_min) / cell_w), grid_size - 1)
        gy = min(int((y - y_min) / cell_h), grid_size - 1)
        cell_means.setdefault((gx, gy), []).append(r)
    means = [np.mean(v) for v in cell_means.values() if len(v) > 0]
    if len(means) < 3:
        return False, 0.0
    cov = float(np.std(means) / (np.mean(means) + 1e-9))
    return cov > coeff_var_thresh, cov


def piecewise_affine_warp(src_gray, pts_ref, pts_src, out_shape, interpolation=cv2.INTER_LINEAR):
    """
    Warps src_gray into the reference frame using a piecewise-affine
    transform defined by a Delaunay triangulation of the (already
    globally-aligned) inlier correspondence points.
    """
    h, w = out_shape[:2]
    output = np.zeros((h, w), dtype=src_gray.dtype)
    mask_out = np.zeros((h, w), dtype=np.uint8)

    pts_ref = np.array(pts_ref, dtype=np.float64)
    pts_src = np.array(pts_src, dtype=np.float64)
    if len(pts_ref) < 4:
        return output, mask_out, {"triangles": 0}

    tri = Delaunay(pts_ref)
    for simplex in tri.simplices:
        dst_tri = pts_ref[simplex].astype(np.float32)
        src_tri = pts_src[simplex].astype(np.float32)

        r = cv2.boundingRect(dst_tri)
        x, y, tw, th = r
        if tw <= 0 or th <= 0:
            continue
        dst_tri_local = dst_tri - [x, y]

        r_src = cv2.boundingRect(src_tri)
        xs, ys, sw, sh = r_src
        if sw <= 0 or sh <= 0:
            continue
        src_tri_local = src_tri - [xs, ys]

        sh_img_h, sh_img_w = src_gray.shape[:2]
        xs_c, ys_c = max(xs, 0), max(ys, 0)
        xe_c, ye_c = min(xs + sw, sh_img_w), min(ys + sh, sh_img_h)
        if xe_c <= xs_c or ye_c <= ys_c:
            continue
        patch = src_gray[ys_c:ye_c, xs_c:xe_c]
        if patch.size == 0:
            continue

        try:
            M = cv2.getAffineTransform(src_tri_local, dst_tri_local)
        except cv2.error:
            continue

        warped = cv2.warpAffine(patch.astype(np.float32), M, (tw, th),
                                 flags=interpolation, borderMode=cv2.BORDER_REFLECT)

        tri_mask = np.zeros((th, tw), dtype=np.uint8)
        cv2.fillConvexPoly(tri_mask, np.int32(dst_tri_local), 1)

        y0, y1 = max(y, 0), min(y + th, h)
        x0, x1 = max(x, 0), min(x + tw, w)
        if y1 <= y0 or x1 <= x0:
            continue
        wy0, wy1 = y0 - y, y1 - y
        wx0, wx1 = x0 - x, x1 - x

        region_mask = tri_mask[wy0:wy1, wx0:wx1].astype(bool)
        output[y0:y1, x0:x1][region_mask] = warped[wy0:wy1, wx0:wx1][region_mask].astype(src_gray.dtype)
        mask_out[y0:y1, x0:x1][region_mask] = 255

    return output, mask_out, {"triangles": int(len(tri.simplices))}
