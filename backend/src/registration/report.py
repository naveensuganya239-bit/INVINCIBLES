"""
INVINCIBLES - Scientific Report Generator (Spec Section 42)
==============================================================
Builds a downloadable Markdown scientific report from an actual run
summary. Every figure comes directly from the computed summary dict -
nothing here is invented.
"""
from __future__ import annotations
from src.lunar_ai import interpreter as lunar_ai


def build_markdown_report(summary: dict) -> str:
    lines = []
    lines.append("# INVINCIBLES - Lunar Multi-Sensor Registration Report")
    lines.append(f"\nRun ID: `{summary['run_id']}`  ")
    lines.append(f"Generated: {summary.get('generated_at', 'n/a')}  ")
    lines.append(f"Cached: {summary.get('cached', False)}\n")

    lines.append("## 1. Dataset\n")
    for key, entry in summary["dataset_manifest"]["sensors"].items():
        s = entry["stats"]
        lines.append(f"- **{key}** ({entry['sensor_full_name']}, role={entry['role']}): "
                      f"`{s['filename']}`, {s['width']}x{s['height']}, {s['channels']} ch, dtype={s['dtype']}, "
                      f"mean={s['mean']:.2f}, std={s['std']:.2f}, noise_sigma={s['estimated_noise_sigma']:.3f}")
    lines.append("")

    lines.append("## 2. Registration Results\n")
    for sensor, res in summary["sensor_results"].items():
        lines.append(f"### {sensor} -> OHRC\n")
        if res.get("status") != "SUCCESS":
            lines.append(f"**STATUS: FAILED** at stage `{res.get('failed_stage')}`\n")
            lines.append(f"Reason: {res.get('failure_reason')}\n")
            continue
        m = res["metrics"]
        lines.append(f"- Preprocessing: {res['preprocessing_method']}")
        lines.append(f"- Correspondence method: **{res.get('correspondence_method', 'sparse_descriptor_matching')}**")
        if res.get("area_based_fallback"):
            ab = res["area_based_fallback"]
            lines.append(f"  - Area-based fallback triggered (sparse descriptor matching produced too few "
                          f"correspondences): global alignment method=`{ab['method']}` (quality={ab['quality']:.3f}), "
                          f"NCC threshold used={ab.get('ncc_threshold_used')}, "
                          f"dense correspondences found={ab['n_correspondences']}, mean NCC score={ab['mean_ncc_score']:.3f}")
        lines.append(f"- Descriptor method used: **{res['descriptor_method']}**" +
                      (f" (deviation: {res['descriptor_deviation_reason']})" if res.get("descriptor_deviation_reason") else ""))
        lines.append(f"- Keypoints (ref/src): {m['n_keypoints_reference']} / {m['n_keypoints_source']}")
        lines.append(f"- Candidate matches: {m['n_candidate_matches']}; Accepted matches: {m['n_accepted_matches']}")
        lines.append(f"- Fitting points: {m['n_fit_points']}; Independent checkpoints: {m['n_checkpoint_points']}")
        lines.append(f"- Transformation model: **{m['transformation_model']}** ({res['metrics']['model_selection_justification']})")
        lines.append(f"- Inliers: {m['n_inliers']} / {m['n_total_fit']} (inlier ratio {m['inlier_ratio']:.1%})")
        lines.append(f"- Checkpoint RMSE: before={m['checkpoint_rmse_before_refinement']:.3f}px, "
                      f"after local refinement={m['checkpoint_rmse_after_local_refinement']:.3f}px, "
                      f"final (sub-pixel)={m['checkpoint_rmse_final']:.3f}px")
        lines.append(f"- Local terrain-relief refinement applied: {res['local_refinement']['used']}")
        lines.append(f"- Confidence: **{res['confidence']['level']}**")
        for status, reason in res["confidence"]["factors"]:
            lines.append(f"  - [{status}] {reason}")
        lines.append("")

    lines.append("## 3. Lunar AI Scientific Interpretation\n")
    ai_report = lunar_ai.build_scientific_report(summary["sensor_results"])
    for line in ai_report["scientific_summary"]:
        lines.append(f"- {line}")
    lines.append(f"\n**Overall confidence:** {ai_report['confidence_overall']}\n")
    lines.append("### Limitations\n")
    for lim in ai_report["limitations"]:
        lines.append(f"- {lim}")
    lines.append("\n### Recommended Further Analysis\n")
    for rec in ai_report["recommended_further_analysis"]:
        lines.append(f"- {rec}")

    lines.append("\n## 4. Multi-Sensor Output\n")
    fusion = summary.get("fusion_output", {})
    lines.append(f"- Multi-band archive: `{fusion.get('npz_path')}`")
    for layer, meta in fusion.get("metadata", {}).get("layers", {}).items():
        lines.append(f"  - {layer}: role={meta['role']}, interpolation={meta['interpolation']}, "
                      f"dtype={meta['dtype']}, valid_pixel_fraction={meta['valid_pixel_fraction']:.3f}")

    return "\n".join(lines)
