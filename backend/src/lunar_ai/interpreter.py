"""
INVINCIBLES - Lunar AI (Spec Sections 36-41)
===============================================
Lunar AI is NOT the registration engine. It never performs geometry - it
only interprets outputs that the registration engine has already
computed. Every statement is tagged OBSERVED / DERIVED / UNCERTAIN, and
phrasing strength is explicitly gated by measured registration confidence
(Section 38). No mineral composition, elevation, latitude/longitude, or
crater-age claims are ever made, because the supplied dataset does not
carry the calibration/geolocation metadata that would support them.

An optional interactive layer lets a scientist ask free-form questions.
When an ANTHROPIC_API_KEY is configured, the question is answered by
Claude - but Claude is given ONLY the actual structured, computed
registration/analysis data as context and is explicitly instructed to
stay within it and to flag anything it cannot support from that data as
uncertain. If no API key is configured, a comprehensive rule-based answer
engine (natural-language pattern matching over the same structured data)
is used instead, covering 25+ question categories, so the feature
degrades gracefully rather than fabricating a response.
"""
from __future__ import annotations
import os
import re
import json
import numpy as np

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except Exception:
    _ANTHROPIC_AVAILABLE = False


SYSTEM_PROMPT = """You are "Lunar AI", the scientific interpretation layer of the INVINCIBLES
lunar multi-sensor image registration prototype. You are speaking to a scientist/evaluator.

STRICT RULES:
1. You may only make claims that are directly supported by the structured registration
   and image-analysis data provided to you in the user message as JSON. Treat that JSON
   as your only source of truth about this dataset and this registration run.
2. Classify every substantive claim as one of: OBSERVED (directly read from the data),
   DERIVED (a reasonable inference/computation from the data), or UNCERTAIN (plausible but
   not supported strongly enough by the data to be confident).
3. NEVER state a mineral composition, geological age, absolute latitude/longitude, or
   elevation value unless such information is explicitly present in the provided JSON -
   it is not, in this dataset, so do not invent it.
4. Explicitly reflect registration confidence in how strongly you phrase cross-sensor
   comparisons: if confidence is LOW, say so plainly and hedge; if HIGH, you may speak
   with more confidence about spatial correspondence claims (but never about semantic/
   compositional claims that the sensors here cannot support).
5. Be concise, technical, and honest. If asked something the data cannot answer, say so
   directly rather than guessing.
6. You may hold a natural conversation about the project, the algorithms used, and the
   results - answer like a knowledgeable colleague, not a canned template - but never
   drift from rules 1-4.
"""


def _safe_get(d, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def build_scientific_report(sensor_results: dict) -> dict:
    """
    sensor_results: { sensor_key: { registration metrics dict } } for all
    SOURCE sensors that were processed in this run, as produced by the
    pipeline (real computed values only).
    Produces the structured Lunar AI output required by Section 37.
    """
    summary_lines = []
    detected_features = {}
    sensor_contributions = {}
    cross_sensor = []
    quality_section = {}
    confidence_overall = []
    limitations = [
        "No geolocation (latitude/longitude) metadata accompanies the supplied imagery; "
        "no absolute coordinates are claimed anywhere in this report.",
        "No calibrated reflectance/mineral spectral library was supplied for IIRS; "
        "no mineral composition claims are made.",
        "No independently dated reference is available; no crater-age claims are made.",
    ]

    for sensor, res in sensor_results.items():
        if res.get("status") != "SUCCESS":
            quality_section[sensor] = {
                "status": "FAILED",
                "stage": res.get("failed_stage"),
                "reason": res.get("failure_reason"),
            }
            summary_lines.append(
                f"{sensor}: registration to OHRC FAILED at stage '{res.get('failed_stage')}' "
                f"({res.get('failure_reason')}). No cross-sensor interpretation attempted for {sensor}."
            )
            continue

        conf = res["confidence"]["level"]
        rmse_final = res["metrics"]["checkpoint_rmse_final"]
        inlier_ratio = res["metrics"]["inlier_ratio"]
        n_inliers = res["metrics"]["n_inliers"]

        detected_features[sensor] = {
            "keypoints_detected": res["metrics"]["n_keypoints"],
            "accepted_matches": res["metrics"]["n_accepted_matches"],
            "inliers": n_inliers,
            "classification": "OBSERVED",
        }

        sensor_contributions[sensor] = {
            "evidence": res.get("sensor_evidence_description", "Spatial structural correspondence with OHRC."),
            "classification": "OBSERVED" if inlier_ratio and inlier_ratio > 0 else "UNCERTAIN",
        }

        if conf == "HIGH":
            phrasing = (f"Registration of {sensor} to the OHRC reference achieved HIGH confidence "
                        f"(checkpoint RMSE {rmse_final:.2f}px, inlier ratio {inlier_ratio:.1%}). "
                        f"The available registration metrics provide stronger support for cross-sensor "
                        f"spatial comparison in this region. [DERIVED]")
        elif conf == "MEDIUM":
            phrasing = (f"Registration of {sensor} to OHRC reached MEDIUM confidence "
                        f"(checkpoint RMSE {rmse_final:.2f}px, inlier ratio {inlier_ratio:.1%}). "
                        f"Cross-sensor spatial comparisons should be treated as indicative rather than "
                        f"precise. [DERIVED]")
        else:
            phrasing = (f"Registration of {sensor} to OHRC reached only LOW confidence "
                        f"(checkpoint RMSE {rmse_final:.2f}px, inlier ratio {inlier_ratio:.1%}). "
                        f"Spatial registration uncertainty limits reliable cross-sensor interpretation "
                        f"for {sensor}; findings below should be treated as UNCERTAIN. [UNCERTAIN]")

        summary_lines.append(phrasing)
        cross_sensor.append({
            "sensor": sensor,
            "observation": phrasing,
            "confidence": conf,
        })
        quality_section[sensor] = {
            "status": "SUCCESS",
            "transformation_model": res["metrics"]["transformation_model"],
            "inlier_ratio": inlier_ratio,
            "checkpoint_rmse_final": rmse_final,
            "confidence": conf,
        }
        confidence_overall.append(conf)

    if confidence_overall:
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        overall = min(confidence_overall, key=lambda c: rank[c])
    else:
        overall = "LOW"

    return {
        "scientific_summary": summary_lines,
        "detected_features": detected_features,
        "regions_of_interest": [],  # populated interactively via explain_region
        "sensor_contributions": sensor_contributions,
        "cross_sensor_observations": cross_sensor,
        "registration_quality": quality_section,
        "evidence": "All figures above are taken directly from the registration engine's computed metrics for this run; none are estimated or hard-coded.",
        "confidence_overall": overall,
        "limitations": limitations,
        "recommended_further_analysis": [
            "Acquire or attach real Chandrayaan-2 OHRC/TMC/IIRS/SAR geolocated products for this "
            "region to enable absolute coordinate reporting.",
            "If IIRS spectral calibration data becomes available, extend Lunar AI with a spectral "
            "unmixing module before attempting any compositional statements.",
            "Increase keypoint budget / relax ratio-test threshold for any sensor that reached only "
            "LOW confidence, then re-run.",
        ],
    }


def explain_region(roi: dict, sensor_results: dict) -> dict:
    """Section 40 - EXPLAIN THIS REGION. roi: {x, y, radius} in OHRC pixel coords."""
    observations = []
    for sensor, res in sensor_results.items():
        if res.get("status") != "SUCCESS":
            observations.append({"sensor": sensor, "evidence": "Not available - registration failed for this sensor.", "classification": "UNCERTAIN"})
            continue
        conf = res["confidence"]["level"]
        observations.append({
            "sensor": sensor,
            "evidence": res.get("sensor_evidence_description", "Structural correspondence present at measured confidence."),
            "registration_confidence": conf,
            "classification": "OBSERVED" if conf in ("HIGH", "MEDIUM") else "UNCERTAIN",
        })
    return {
        "roi": roi,
        "what_is_observed": "A local image neighbourhood centred at the requested pixel location, as rendered by each successfully registered sensor layer. [OBSERVED]",
        "sensor_contributions": observations,
        "morphological_characteristics": "Not automatically classified in this prototype; requires a trained morphological classifier that was out of scope for this run. [UNCERTAIN]",
        "cross_sensor_evidence": [o for o in observations if o.get("classification") == "OBSERVED"],
        "possible_interpretation": "Structural feature consistent across the sensors marked OBSERVED above; no semantic (compositional/geological) interpretation is offered without calibrated spectral/geological reference data. [UNCERTAIN beyond structural correspondence]",
        "confidence": min((o.get("registration_confidence", "LOW") for o in observations), key=lambda c: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(c, 0), default="LOW"),
        "limitations": "No geolocation, spectral calibration, or independent ground truth is available for this ROI.",
    }


def compare_sensors(sensor_results: dict) -> dict:
    """Section 41 - COMPARE SENSORS, ordered pipeline of registered layers."""
    chain = []
    for sensor in ["OHRC", "TMC-Azimuth", "TMC-Slope", "IIRS", "SAR"]:
        res = sensor_results.get(sensor)
        if sensor == "OHRC":
            chain.append({"sensor": "OHRC", "role": "REFERENCE", "status": "LOCKED"})
            continue
        if res is None:
            chain.append({"sensor": sensor, "status": "NOT RUN"})
            continue
        chain.append({
            "sensor": sensor,
            "status": res.get("status"),
            "confidence": res.get("confidence", {}).get("level") if res.get("status") == "SUCCESS" else None,
            "checkpoint_rmse": res.get("metrics", {}).get("checkpoint_rmse_final") if res.get("status") == "SUCCESS" else None,
        })
    interpretation = "Cross-sensor spatial comparison is only meaningful for sensors marked SUCCESS above, weighted by their listed confidence."
    return {"chain": chain, "cross_sensor_interpretation": interpretation}


def ask_lunar_ai(question: str, context: dict) -> dict:
    """
    Interactive free-form Q&A grounded strictly in `context` (the real
    computed dataset/registration/report data for the current run).
    """
    context_json = json.dumps(context, indent=2, default=str)
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if _ANTHROPIC_AVAILABLE and api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"CURRENT RUN DATA (JSON):\n{context_json}\n\nQUESTION: {question}"
                }],
            )
            text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
            return {"answer": text, "engine": "claude-sonnet-4-6", "grounded_in": "actual computed run data"}
        except Exception as e:
            fallback = _rule_based_answer(question, context)
            fallback["engine_error"] = f"Claude API call failed ({e}); used rule-based fallback."
            return fallback

    return _rule_based_answer(question, context)


# ---------------------------------------------------------------------------
# COMPREHENSIVE RULE-BASED Q&A ENGINE
# Handles 25+ question categories with natural, paragraph-style answers.
# All answers are grounded in the actual computed context dict.
# ---------------------------------------------------------------------------

_SENSOR_DESCRIPTIONS = {
    "OHRC": (
        "OHRC stands for Orbiter High Resolution Camera — it is Chandrayaan-2's primary optical "
        "camera, and it serves as the fixed REFERENCE image in this pipeline. All other sensors are "
        "geometrically registered (aligned) to the OHRC frame. OHRC captures fine surface detail "
        "at sub-metre resolution under visible-light illumination. Because it is the reference, its "
        "position is never altered by the registration algorithm."
    ),
    "TMC": (
        "TMC stands for Terrain Mapping Camera. This pipeline uses two derived TMC products: "
        "TMC-Azimuth encodes the sun-azimuth-relative slope orientation of each terrain pixel, "
        "and TMC-Slope encodes the slope magnitude. Both are computed from the stereo DEM (Digital "
        "Elevation Model) rather than directly captured as optical images. This makes them "
        "structurally very different from the OHRC, and registration must rely on shared edge/contour "
        "structure rather than pixel intensity similarity."
    ),
    "IIRS": (
        "IIRS stands for Imaging Infrared Spectrometer — Chandrayaan-2's hyperspectral instrument "
        "sensitive to near-infrared wavelengths. In this pipeline we use a single representative "
        "spectral band as a grayscale image. IIRS captures material reflectance in the infrared, "
        "which can differ significantly from optical appearance. Note: this prototype does NOT "
        "perform any mineralogical interpretation, since no calibrated spectral library is provided."
    ),
    "SAR": (
        "SAR stands for Synthetic Aperture Radar. Unlike optical cameras, SAR actively illuminates "
        "the surface with microwave pulses and records the backscattered signal. This makes it "
        "insensitive to solar illumination and capable of imaging permanently shadowed polar regions. "
        "SAR images are inherently speckled (granular noise) and have very different texture from "
        "optical images, making cross-modal registration challenging — the pipeline uses "
        "phase-congruency features which are illumination-invariant to handle this."
    ),
}

_PIPELINE_STAGES = [
    "INPUT VALIDATION — verifies image files can be loaded and are not degenerate flat images.",
    "SENSOR-AWARE PREPROCESSING — applies sensor-specific normalization (CLAHE for optical, "
    "gradient-enhancing filters for terrain products, speckle suppression for SAR).",
    "MULTI-SCALE REPRESENTATION — builds a Gaussian image pyramid for coarse-to-fine processing.",
    "PHASE CONGRUENCY — computes illumination-invariant structural feature maps using log-Gabor "
    "filter banks; this is key for cross-modal registration where pixel values differ across sensors.",
    "KEYPOINT DETECTION + ANMS — detects stable feature points at multiple scales and applies "
    "Adaptive Non-Maximum Suppression to ensure spatial coverage across the image.",
    "COARSE GEOMETRIC ALIGNMENT — uses phase correlation on the phase-congruency maps to estimate "
    "an initial global similarity transform (rotation, scale, translation).",
    "MULTI-MODAL DESCRIPTOR EXTRACTION (RIFT/CFOG) — builds rotation-invariant feature descriptors "
    "on the phase-congruency maps rather than raw pixel intensities.",
    "FEATURE MATCHING — matches descriptors using ratio-test + mutual cross-check. If sparse "
    "matching yields too few correspondences, an area-based NCC fallback is triggered automatically.",
    "INDEPENDENT VALIDATION SPLIT — reserves a separate checkpoint set (never used in fitting) "
    "for unbiased accuracy measurement.",
    "ROBUST OUTLIER REJECTION + MODEL SELECTION (FSC) — Forward Selection Consensus tests "
    "multiple transformation models (similarity, affine, homography) and picks the simplest "
    "model that explains the inlier correspondences.",
    "LOCAL TERRAIN-RELIEF REFINEMENT — if inlier residuals show spatially structured patterns "
    "(residual CoV > threshold), a scattered-data interpolation corrects local terrain distortions.",
    "SUB-PIXEL REFINEMENT — patch-based NCC locally nudges each checkpoint correspondence to "
    "sub-pixel precision.",
    "WARPING — applies the final transformation to the original (un-preprocessed) sensor image.",
    "CHECKERBOARD GENERATION — interleaves OHRC and warped tiles for visual alignment verification.",
    "METRICS + CONFIDENCE — computes checkpoint RMSE and classifies registration confidence as "
    "HIGH / MEDIUM / LOW based on inlier ratio, RMSE, and spatial coverage.",
]


def _build_metrics_summary(metrics: dict) -> dict:
    """Return a cleaned scalar-only metrics dict for safe string interpolation."""
    safe = {}
    for k, v in metrics.items():
        if isinstance(v, (int, float)) and v is not None:
            safe[k] = v
        elif isinstance(v, str):
            safe[k] = v
        elif isinstance(v, list) and all(isinstance(r, (int, float)) for r in v[:4]):
            safe[k] = v  # e.g. transformation matrix rows
    return safe


def _rule_based_answer(question: str, context: dict) -> dict:
    q = question.lower().strip()
    report = context.get("lunar_ai_report", {})
    sensor_results = context.get("sensor_results", {})

    # ---- Helpers ----
    successful = {s: r for s, r in sensor_results.items() if r.get("status") == "SUCCESS"}
    failed = {s: r for s, r in sensor_results.items() if r.get("status") != "SUCCESS"}

    def _overall_confidence():
        confs = [r["confidence"]["level"] for r in successful.values()]
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        return min(confs, key=lambda c: rank.get(c, 0)) if confs else "N/A"

    def _best_sensor():
        """Return sensor with highest confidence then lowest RMSE."""
        rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        best = max(successful.items(),
                   key=lambda kv: (rank.get(kv[1]["confidence"]["level"], 0),
                                   -kv[1]["metrics"]["checkpoint_rmse_final"]),
                   default=(None, None))
        return best[0]

    def _worst_sensor():
        rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        worst = min(successful.items(),
                    key=lambda kv: (rank.get(kv[1]["confidence"]["level"], 0),
                                    -kv[1]["metrics"]["checkpoint_rmse_final"]),
                    default=(None, None))
        return worst[0]

    # ---- CATEGORY MATCHING ----
    # Each block checks keywords and returns a complete answer if matched.

    # --- What is OHRC / TMC / IIRS / SAR ---
    for key, desc in _SENSOR_DESCRIPTIONS.items():
        if key.lower() in q and any(w in q for w in ("what", "explain", "describe", "tell", "is", "means", "stand")):
            return {
                "answer": desc + "\n\n[OBSERVED — sensor description is a documented fact about the Chandrayaan-2 mission instruments.]",
                "engine": "rule-based",
                "category": "sensor_description",
            }

    # --- Overall confidence ---
    if any(w in q for w in ("overall confidence", "overall registration", "how confident", "confidence level", "what is the confidence")):
        oc = _overall_confidence()
        sensor_lines = []
        for s, r in successful.items():
            m = r["metrics"]
            sensor_lines.append(
                f"  • {s}: {r['confidence']['level']} confidence "
                f"(RMSE={m['checkpoint_rmse_final']:.2f}px, inlier ratio={m['inlier_ratio']:.1%})"
            )
        fail_lines = [f"  • {s}: FAILED at stage '{r.get('failed_stage')}'" for s, r in failed.items()]
        all_lines = "\n".join(sensor_lines + fail_lines)
        return {
            "answer": (
                f"The overall registration confidence for this run is {oc}. "
                f"It is determined by the weakest-performing sensor, since multi-sensor fusion "
                f"reliability is bounded by its least accurate component.\n\n"
                f"Per-sensor breakdown:\n{all_lines}\n\n"
                f"[OBSERVED — all figures come directly from the pipeline's computed metrics.]"
            ),
            "engine": "rule-based",
            "category": "overall_confidence",
        }

    # --- RMSE / accuracy / error ---
    if any(w in q for w in ("rmse", "accuracy", "error", "precision", "pixel error", "how accurate")):
        lines = []
        for s, r in successful.items():
            m = r["metrics"]
            improv = m.get("checkpoint_rmse_improvement_px")
            improv_str = f", improved by {improv:.2f}px after refinement" if improv else ""
            lines.append(
                f"  • {s}: final RMSE = {m['checkpoint_rmse_final']:.2f}px "
                f"(before refinement: {m.get('checkpoint_rmse_before_refinement', 'N/A')}px{improv_str}) "
                f"— {r['confidence']['level']} confidence"
            )
        for s, r in failed.items():
            lines.append(f"  • {s}: FAILED — no RMSE available ({r.get('failure_reason', 'unknown reason')})")
        return {
            "answer": (
                "Checkpoint RMSE (Root Mean Square Error) measures spatial alignment accuracy on "
                "an independent set of correspondence points that were never used to fit the "
                "transformation — making it an unbiased accuracy estimate.\n\n"
                "Results per sensor:\n" + "\n".join(lines) + "\n\n"
                "[OBSERVED — RMSE computed on held-out checkpoint correspondences by the pipeline.]"
            ),
            "engine": "rule-based",
            "category": "rmse",
        }

    # --- Inlier ratio ---
    if any(w in q for w in ("inlier", "inlier ratio", "outlier", "consensus")):
        lines = []
        for s, r in successful.items():
            m = r["metrics"]
            lines.append(
                f"  • {s}: {m['n_inliers']} inliers / {m['n_total_fit']} fit points "
                f"= {m['inlier_ratio']:.1%} inlier ratio"
            )
        return {
            "answer": (
                "The inlier ratio is the fraction of feature correspondences that are geometrically "
                "consistent with the estimated transformation model (after RANSAC/FSC outlier rejection). "
                "A higher inlier ratio means the matched features agree well on a single consistent "
                "geometric transformation, indicating reliable registration.\n\n"
                "Per-sensor inlier statistics:\n" + "\n".join(lines) + "\n\n"
                "[OBSERVED — inlier counts produced by the FSC outlier-rejection stage.]"
            ),
            "engine": "rule-based",
            "category": "inlier_ratio",
        }

    # --- Transformation model ---
    if any(w in q for w in ("transformation", "transform model", "affine", "homography", "similarity", "model")):
        lines = []
        for s, r in successful.items():
            m = r["metrics"]
            justif = m.get("model_selection_justification", "")
            lines.append(
                f"  • {s}: {m['transformation_model'].upper()} — {justif[:120]}"
            )
        return {
            "answer": (
                "The pipeline automatically selects the simplest transformation model that "
                "adequately explains the inlier correspondences:\n"
                "  - SIMILARITY: rotation + uniform scale + translation (4 DOF) — most constrained\n"
                "  - AFFINE: full linear mapping + translation (6 DOF) — allows shear/non-uniform scale\n"
                "  - HOMOGRAPHY: full projective warp (8 DOF) — most flexible, used for large viewpoint differences\n\n"
                "Model selected per sensor:\n" + "\n".join(lines) + "\n\n"
                "[DERIVED — model selection is the FSC algorithm's conclusion from the inlier geometry.]"
            ),
            "engine": "rule-based",
            "category": "transformation_model",
        }

    # --- Best / worst sensor ---
    if any(w in q for w in ("best sensor", "which sensor", "most accurate", "highest confidence", "top sensor")):
        b = _best_sensor()
        if b:
            m = successful[b]["metrics"]
            return {
                "answer": (
                    f"The best-registering sensor in this run is {b}, which achieved "
                    f"{successful[b]['confidence']['level']} confidence with a final checkpoint RMSE of "
                    f"{m['checkpoint_rmse_final']:.2f}px and an inlier ratio of {m['inlier_ratio']:.1%}. "
                    f"This means {b}'s spatial correspondence to the OHRC reference is the most reliable "
                    f"among the sensors processed in this run.\n\n"
                    f"[DERIVED — ranked by confidence level then by RMSE from the pipeline's computed metrics.]"
                ),
                "engine": "rule-based",
                "category": "best_sensor",
            }

    if any(w in q for w in ("worst sensor", "lowest confidence", "failed", "least accurate", "problem")):
        if failed:
            names = ", ".join(failed.keys())
            reasons = "; ".join(f"{s}: {r.get('failure_reason','')}" for s, r in failed.items())
            return {
                "answer": (
                    f"The following sensors failed registration entirely: {names}.\n"
                    f"Failure reasons: {reasons}\n\n"
                    f"When a sensor fails, the pipeline stops rather than continuing on an unreliable "
                    f"result — this is by design (Section 30 of the spec: honest failure over silent degradation).\n\n"
                    f"[OBSERVED — failure stage and reason reported directly by the pipeline.]"
                ),
                "engine": "rule-based",
                "category": "worst_sensor",
            }
        w = _worst_sensor()
        if w:
            m = successful[w]["metrics"]
            return {
                "answer": (
                    f"Among successful registrations, {w} had the lowest confidence: "
                    f"{successful[w]['confidence']['level']} with RMSE={m['checkpoint_rmse_final']:.2f}px "
                    f"and inlier ratio={m['inlier_ratio']:.1%}. "
                    f"This is likely due to the large appearance difference between {w} and the optical OHRC image.\n\n"
                    f"[DERIVED — ranked by confidence and RMSE from the pipeline's computed metrics.]"
                ),
                "engine": "rule-based",
                "category": "worst_sensor",
            }

    # --- Pipeline / how it works ---
    if any(w in q for w in ("pipeline", "how does it work", "how does registration work", "stages", "algorithm", "process", "workflow", "explain the")):
        stages_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(_PIPELINE_STAGES))
        return {
            "answer": (
                "The INVINCIBLES registration pipeline processes each source sensor independently "
                "against the fixed OHRC reference through the following stages:\n\n"
                + stages_str +
                "\n\nIf any stage fails to produce a scientifically valid result, the pipeline stops "
                "for that sensor and reports an honest FAILED status — it never silently continues "
                "on top of an unreliable intermediate result.\n\n"
                "[OBSERVED — pipeline stage descriptions are factual documentation of the implemented algorithm.]"
            ),
            "engine": "rule-based",
            "category": "pipeline",
        }

    # --- Phase congruency ---
    if any(w in q for w in ("phase congruency", "phase correlation", "illumination invariant", "log gabor", "gabor")):
        return {
            "answer": (
                "Phase congruency is a feature detection technique that identifies structurally "
                "significant points (edges, corners, ridges) by measuring the agreement in phase "
                "across multiple frequency bands — rather than using raw pixel intensity gradients.\n\n"
                "This is the key to cross-modal registration in INVINCIBLES: because OHRC (optical), "
                "IIRS (infrared), TMC (terrain-derived), and SAR (radar) images have completely "
                "different pixel value distributions, traditional gradient-based descriptors (like SIFT) "
                "fail. Phase congruency responds to the same structural edges regardless of "
                "illumination, sensor type, or intensity scale — making cross-modal matching possible.\n\n"
                "Implementation: log-Gabor filter bank at 4 scales × 6 orientations.\n\n"
                "[OBSERVED — documented algorithm choice in the INVINCIBLES pipeline.]"
            ),
            "engine": "rule-based",
            "category": "phase_congruency",
        }

    # --- RIFT / CFOG descriptor ---
    if any(w in q for w in ("rift", "cfog", "descriptor", "feature descriptor", "matching descriptor")):
        return {
            "answer": (
                "INVINCIBLES uses RIFT (Rotation-Invariant Feature Transform) as its primary "
                "multi-modal descriptor, with CFOG (Circular Feature-map Orientation Gradient) "
                "as a fallback.\n\n"
                "RIFT builds descriptors on the phase-congruency map rather than the raw image, "
                "making it sensitive to structural boundaries while being insensitive to intensity "
                "differences between sensors. It achieves rotation invariance through circular "
                "histograms of local maximum-index orientation.\n\n"
                "CFOG is used when RIFT does not yield enough valid descriptors — it uses "
                "gradient magnitude statistics on the phase-congruency map and is more robust "
                "to low-texture regions.\n\n"
                "[OBSERVED — documented algorithm choices in the pipeline's descriptor module.]"
            ),
            "engine": "rule-based",
            "category": "descriptor",
        }

    # --- Checkerboard ---
    if any(w in q for w in ("checkerboard", "visual validation", "alignment check", "tile")):
        return {
            "answer": (
                "The checkerboard image is the primary VISUAL validation of registration quality. "
                "The OHRC reference and the warped (registered) sensor image are interleaved in an "
                "alternating tile pattern.\n\n"
                "What to look for:\n"
                "  ✓ GOOD alignment: edges and structures appear continuous and unbroken across tile boundaries\n"
                "  ✗ POOR alignment: ghosting, step discontinuities, or misaligned edges at tile boundaries\n\n"
                "The checkerboard is generated from the original (un-preprocessed) sensor data "
                "after applying the final registration transformation, so it reflects true registration quality.\n\n"
                "[OBSERVED — visual output of the warping + checkerboard generation stage.]"
            ),
            "engine": "rule-based",
            "category": "checkerboard",
        }

    # --- Keypoints / features detected ---
    if any(w in q for w in ("keypoint", "feature point", "features detected", "how many features", "detection")):
        lines = []
        for s, r in successful.items():
            m = r["metrics"]
            lines.append(
                f"  • {s}: {m['n_keypoints_reference']} keypoints on OHRC + "
                f"{m['n_keypoints_source']} on {s} → "
                f"{m['n_accepted_matches']} accepted matches → "
                f"{m['n_inliers']} inliers"
            )
        return {
            "answer": (
                "Keypoints are detected using a phase-congruency based multi-scale detector with "
                "Adaptive Non-Maximum Suppression (ANMS) to ensure even spatial coverage.\n\n"
                "Keypoint → match → inlier funnel per sensor:\n" + "\n".join(lines) + "\n\n"
                "[OBSERVED — keypoint counts measured by the detection stage; match/inlier counts "
                "measured by the matching and FSC stages.]"
            ),
            "engine": "rule-based",
            "category": "keypoints",
        }

    # --- Composite image ---
    if any(w in q for w in ("composite", "overlay", "false color", "rgb", "false-color", "combined image", "multi-sensor image")):
        return {
            "answer": (
                "The composite registered image is a false-color RGB visualization created after "
                "all sensors have been registered to the OHRC reference frame:\n\n"
                "  R (Red channel)   = OHRC — optical reference, fine surface texture\n"
                "  G (Green channel) = IIRS — infrared spectral brightness (or TMC-Slope if IIRS absent)\n"
                "  B (Blue channel)  = SAR  — radar backscatter, surface roughness (or TMC-Azimuth if SAR absent)\n\n"
                "In this visualization, areas that appear yellow/orange have strong OHRC+IIRS response; "
                "cyan areas have strong OHRC+SAR response; white areas are bright across all three sensors. "
                "This is a DERIVED product — its scientific interpretation requires per-sensor calibration "
                "data that is not available in this prototype dataset.\n\n"
                "[DERIVED — composite created from the registered sensor layers by the fusion module.]"
            ),
            "engine": "rule-based",
            "category": "composite",
        }

    # --- Comparison / before-after ---
    if any(w in q for w in ("comparison", "before", "after", "unregistered", "original image", "side by side", "difference")):
        lines = []
        for s, r in successful.items():
            m = r["metrics"]
            lines.append(
                f"  • {s}: warped to OHRC frame using a {m['transformation_model'].upper()} transform "
                f"with {m['valid_pixel_fraction']:.1%} valid pixel coverage after warping"
            )
        return {
            "answer": (
                "Each source sensor's comparison strip shows three panels side-by-side:\n"
                "  LEFT:   Original unregistered sensor image (raw input, native sensor frame)\n"
                "  MIDDLE: OHRC reference image\n"
                "  RIGHT:  Registered sensor image (warped to match the OHRC frame)\n\n"
                "The registration was performed per sensor:\n" + "\n".join(lines) + "\n\n"
                "Valid pixel fraction indicates how much of the OHRC frame is covered by the warped "
                "sensor image — lower values mean the sensor's field of view partially misses the "
                "OHRC area, or that the transformation causes significant extrapolation.\n\n"
                "[OBSERVED — transformation applied; DERIVED — valid coverage fraction computed from the warp mask.]"
            ),
            "engine": "rule-based",
            "category": "comparison",
        }

    # --- Local refinement ---
    if any(w in q for w in ("local refinement", "terrain relief", "residual correction", "residual")):
        lines = []
        for s, r in successful.items():
            lr = r.get("local_refinement", {})
            used = lr.get("used", False)
            cov = lr.get("residual_coefficient_of_variation", 0)
            lines.append(f"  • {s}: local refinement {'APPLIED' if used else 'not applied'} (residual CoV = {cov:.3f})")
        return {
            "answer": (
                "After the global transformation is estimated, the pipeline checks whether the "
                "remaining residual errors have spatially structured patterns — which would indicate "
                "local terrain-relief distortions that the global model cannot capture.\n\n"
                "If the residual coefficient of variation (CoV) exceeds a threshold, a scattered-data "
                "interpolation (RBF) correction field is estimated from the inlier residual vectors "
                "and applied to the checkpoint predictions before sub-pixel refinement.\n\n"
                "Local refinement status:\n" + "\n".join(lines) + "\n\n"
                "[DERIVED — the decision to apply local refinement is based on the measured residual CoV.]"
            ),
            "engine": "rule-based",
            "category": "local_refinement",
        }

    # --- Area-based fallback ---
    if any(w in q for w in ("area based", "ncc", "fallback", "dense matching", "ecc")):
        lines = []
        for s, r in successful.items():
            abf = r.get("area_based_fallback")
            if abf:
                lines.append(f"  • {s}: TRIGGERED — method={abf['method']}, quality={abf['quality']:.3f}, "
                             f"NCC threshold={abf['ncc_threshold_used']:.2f}, "
                             f"correspondences={abf['n_correspondences']}")
            else:
                lines.append(f"  • {s}: not needed (sparse descriptor matching succeeded)")
        return {
            "answer": (
                "When sparse RIFT/CFOG descriptor matching produces too few correspondences "
                "(below the minimum threshold), the pipeline automatically escalates to an "
                "area-based dense registration fallback:\n\n"
                "  1. ECC (Enhanced Correlation Coefficient) or Mutual Information global alignment\n"
                "  2. Dense NCC (Normalized Cross-Correlation) template matching on gradient-magnitude maps\n"
                "  3. Mutual forward/backward consistency check to reject unreliable correspondences\n\n"
                "Area-based fallback status:\n" + "\n".join(lines) + "\n\n"
                "[OBSERVED — fallback triggered/not triggered is a direct pipeline decision.]"
            ),
            "engine": "rule-based",
            "category": "area_based_fallback",
        }

    # --- What sensors were processed ---
    if any(w in q for w in ("which sensors", "what sensors", "sensors processed", "sensors used", "sensors registered")):
        success_list = ", ".join(successful.keys()) if successful else "none"
        fail_list = ", ".join(failed.keys()) if failed else "none"
        return {
            "answer": (
                f"This run processed {len(sensor_results)} source sensors against the OHRC reference:\n\n"
                f"  ✓ Successfully registered: {success_list}\n"
                f"  ✗ Failed: {fail_list}\n\n"
                f"The OHRC is always the fixed reference and is not registered — all other sensors "
                f"are geometrically aligned to it.\n\n"
                f"[OBSERVED — registration status reported directly by the pipeline for each sensor.]"
            ),
            "engine": "rule-based",
            "category": "sensors_processed",
        }

    # --- Valid pixel coverage ---
    if any(w in q for w in ("coverage", "valid pixel", "pixel coverage", "warp coverage", "field of view")):
        lines = []
        for s, r in successful.items():
            vf = r["metrics"].get("valid_pixel_fraction", None)
            if vf is not None:
                lines.append(f"  • {s}: {vf:.1%} of the OHRC frame has valid warped pixels")
        return {
            "answer": (
                "Valid pixel fraction indicates what proportion of the OHRC reference frame is "
                "covered by the warped sensor image after registration. Values below 100% mean "
                "parts of the OHRC area are outside the sensor's field of view, or that the "
                "registration transformation causes extrapolation outside the original sensor bounds.\n\n"
                + "\n".join(lines) + "\n\n"
                "[OBSERVED — computed from the binary valid-pixel mask output by the warping stage.]"
            ),
            "engine": "rule-based",
            "category": "coverage",
        }

    # --- Chandrayaan-2 / mission context ---
    if any(w in q for w in ("chandrayaan", "isro", "mission", "spacecraft", "india", "lunar")):
        return {
            "answer": (
                "INVINCIBLES is a prototype multi-sensor image registration system for data from "
                "Chandrayaan-2, India's second lunar exploration mission launched by ISRO in 2019.\n\n"
                "Chandrayaan-2 carries multiple instruments:\n"
                "  • OHRC (Orbiter High Resolution Camera) — 0.25m resolution optical imager\n"
                "  • TMC-2 (Terrain Mapping Camera-2) — stereo DEM generation\n"
                "  • IIRS (Imaging Infrared Spectrometer) — 0.8–5.0 μm spectral imager\n"
                "  • DFSAR (Dual-Frequency Synthetic Aperture Radar) — L-band + S-band SAR\n\n"
                "The prototype aligns all sensor data to a common OHRC spatial reference frame, "
                "enabling multi-modal scientific analysis of the lunar surface.\n\n"
                "[OBSERVED — factual mission documentation.]"
            ),
            "engine": "rule-based",
            "category": "mission_context",
        }

    # --- Why registration / why important ---
    if any(w in q for w in ("why register", "why important", "purpose", "goal", "objective", "what is the point", "significance")):
        return {
            "answer": (
                "Multi-sensor image registration solves a fundamental problem in planetary science: "
                "each instrument on Chandrayaan-2 images the lunar surface from a slightly different "
                "orbit, viewing angle, and time — so the same terrain feature appears at different "
                "pixel locations in each image.\n\n"
                "Without registration:\n"
                "  • You cannot reliably compare, e.g., OHRC optical detail with IIRS spectral data "
                "at the same terrain location\n"
                "  • SAR and optical images of the same crater cannot be overlaid correctly\n"
                "  • Multi-sensor scientific analysis is impossible\n\n"
                "INVINCIBLES registers all sensors to a common OHRC reference frame, so that pixel "
                "(x, y) in every registered image corresponds to the same lunar surface point. "
                "This enables cross-modal analysis, fusion products, and multi-temporal comparison.\n\n"
                "[OBSERVED — registration motivation documented in the pipeline specification.]"
            ),
            "engine": "rule-based",
            "category": "why_registration",
        }

    # --- Confidence classification criteria ---
    if any(w in q for w in ("high confidence", "medium confidence", "low confidence", "confidence criteria", "how confidence is determined", "confidence threshold")):
        return {
            "answer": (
                "Registration confidence is classified into three levels based on a set of measured "
                "thresholds applied to the pipeline's computed metrics:\n\n"
                "  HIGH:   inlier ratio ≥ 0.5 AND final RMSE ≤ 3.0px AND ≥ 10 inliers AND "
                "spatial coverage ≥ 30%\n"
                "  MEDIUM: inlier ratio ≥ 0.25 AND final RMSE ≤ 8.0px AND ≥ 6 inliers\n"
                "  LOW:    anything below the MEDIUM thresholds\n\n"
                "The overall run confidence is the minimum across all processed sensors — "
                "the weakest link in multi-sensor fusion.\n\n"
                "Current run confidence: " + _overall_confidence() + "\n\n"
                "[DERIVED — confidence classification is a rule-based interpretation of the computed metrics.]"
            ),
            "engine": "rule-based",
            "category": "confidence_criteria",
        }

    # --- Sub-pixel refinement ---
    if any(w in q for w in ("sub-pixel", "subpixel", "sub pixel refinement", "fine alignment")):
        return {
            "answer": (
                "After the global transformation and optional local refinement, the pipeline applies "
                "sub-pixel refinement on each checkpoint correspondence:\n\n"
                "A small NCC (Normalized Cross-Correlation) patch search is performed in the "
                "warped source image around the projected checkpoint location, and the peak of the "
                "NCC surface is localized to sub-pixel precision using parabolic interpolation.\n\n"
                "This stage only improves accuracy if the global alignment is already within ~2px; "
                "if not, the sub-pixel search window is too small and the stage gracefully skips "
                "without degrading the result.\n\n"
                "[OBSERVED — documented pipeline stage; sub-pixel is applied when feasible.]"
            ),
            "engine": "rule-based",
            "category": "subpixel",
        }

    # --- Default: comprehensive helpful fallback ---
    topic_list = (
        "• confidence levels (overall or per-sensor)\n"
        "• RMSE / accuracy / pixel error\n"
        "• inlier ratio / outlier rejection\n"
        "• transformation model (affine, homography, similarity)\n"
        "• specific sensor explanations (OHRC, TMC, IIRS, SAR)\n"
        "• how the pipeline / algorithm works\n"
        "• phase congruency / feature detection\n"
        "• RIFT / CFOG descriptors\n"
        "• checkerboard visual validation\n"
        "• composite registered image / false-color overlay\n"
        "• before/after comparison\n"
        "• local terrain-relief refinement\n"
        "• area-based NCC fallback\n"
        "• valid pixel coverage / warp quality\n"
        "• which sensor registered best or worst\n"
        "• Chandrayaan-2 mission context\n"
        "• why image registration is needed"
    )
    return {
        "answer": (
            f"I can answer questions grounded in the actual computed results of this registration run. "
            f"I could not confidently match your question to one of the topics I cover.\n\n"
            f"Try asking about:\n{topic_list}\n\n"
            f"Example: \"What is the overall confidence and why?\" or "
            f"\"Which sensor registered best?\" or \"Explain what phase congruency is.\""
        ),
        "engine": "rule-based",
        "category": "fallback",
    }
