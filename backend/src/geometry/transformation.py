"""
INVINCIBLES - Transformation Estimation (Spec Section 19)
============================================================
Selects the least complex geometric model (similarity -> affine ->
homography) that adequately explains the observed correspondences, using
residual analysis rather than automatically jumping to the most complex
model.
"""
from __future__ import annotations
import numpy as np
from src.geometry.consensus import fsc_estimate, _apply_transform


def select_transformation_model(pts_ref, pts_src, match_distances, reproj_thresh=6.0):
    """
    Tries similarity, then affine, then homography (in that order),
    running FSC for each. Selects the simplest model whose independent
    residual RMS is not meaningfully improved (>15% relative reduction)
    by the next-more-complex model, following the principle that
    complexity must be justified by evidence.
    """
    results = {}
    for model in ("similarity", "affine", "homography"):
        results[model] = fsc_estimate(pts_ref, pts_src, match_distances, model=model, reproj_thresh=reproj_thresh)

    def residual_rms(model):
        r = results[model]
        if not r["success"]:
            return np.inf
        inl = r["inlier_mask"]
        proj = _apply_transform(np.array(r["matrix"]), np.array(pts_src)[inl], model)
        err = np.sqrt(np.sum((proj - np.array(pts_ref)[inl]) ** 2, axis=1))
        return float(np.sqrt(np.mean(err ** 2))) if len(err) else np.inf

    rms = {m: residual_rms(m) for m in results}

    chosen = "similarity" if results["similarity"]["success"] else None
    justification = []

    if results["similarity"]["success"]:
        justification.append(f"similarity RMS={rms['similarity']:.3f}px")
        if results["affine"]["success"] and rms["affine"] < rms["similarity"] * 0.85:
            chosen = "affine"
            justification.append(f"affine RMS={rms['affine']:.3f}px improves >15% over similarity -> affine justified")
            if results["homography"]["success"] and rms["homography"] < rms["affine"] * 0.85:
                chosen = "homography"
                justification.append(f"homography RMS={rms['homography']:.3f}px improves >15% over affine -> homography justified")
            else:
                justification.append("homography did not improve residuals enough to justify added complexity")
        else:
            justification.append("affine did not improve residuals enough to justify added complexity over similarity")
    elif results["affine"]["success"]:
        chosen = "affine"
        justification.append(f"similarity failed; affine RMS={rms['affine']:.3f}px used")
    elif results["homography"]["success"]:
        chosen = "homography"
        justification.append(f"similarity/affine failed; homography RMS={rms['homography']:.3f}px used")

    return {
        "chosen_model": chosen,
        "all_results": results,
        "all_rms": rms,
        "justification": "; ".join(justification) if justification else "No model reached the minimum inlier requirement.",
    }
