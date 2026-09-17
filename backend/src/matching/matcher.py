"""
INVINCIBLES - Feature Matching (Spec Section 17)
===================================================
Nearest-neighbor matching of source descriptors against OHRC reference
descriptors, with Lowe's ratio test and mutual (bidirectional) consistency
cross-checking. Every reported match corresponds to an actual computed
correspondence - none are synthesized for display purposes.
"""
from __future__ import annotations
import numpy as np
import cv2


def match_descriptors(desc_ref: np.ndarray, desc_src: np.ndarray, ratio_thresh: float = 0.85):
    """
    Returns dict with:
      candidate_matches: list of (ref_idx, src_idx, distance) passing ratio test ref->src
      accepted_matches:  subset passing mutual cross-check (src->ref agrees)
      counts
    """
    if len(desc_ref) < 2 or len(desc_src) < 2:
        return {"candidate_matches": [], "accepted_matches": [],
                "n_candidate": 0, "n_accepted": 0}

    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

    knn_r2s = bf.knnMatch(desc_ref, desc_src, k=2)
    candidate = []
    for pair in knn_r2s:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio_thresh * n.distance:
            candidate.append((m.queryIdx, m.trainIdx, float(m.distance)))

    knn_s2r = bf.knnMatch(desc_src, desc_ref, k=2)
    best_s2r = {}
    for pair in knn_s2r:
        if len(pair) < 1:
            continue
        m = pair[0]
        best_s2r[m.queryIdx] = m.trainIdx

    accepted = []
    for ref_idx, src_idx, dist in candidate:
        if best_s2r.get(src_idx) == ref_idx:
            accepted.append((ref_idx, src_idx, dist))

    return {
        "candidate_matches": candidate,
        "accepted_matches": accepted,
        "n_candidate": len(candidate),
        "n_accepted": len(accepted),
    }
