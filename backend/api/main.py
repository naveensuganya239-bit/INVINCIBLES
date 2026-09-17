"""
INVINCIBLES Backend API (Spec Section 45)
============================================
FastAPI application exposing the registration engine and Lunar AI
interpretation layer. Registration runs are executed in a background
thread (Section 45: "use asynchronous processing if registration is
computationally expensive") and tracked by run_id, which is a
deterministic hash of the dataset content + pipeline configuration
(Section 46 caching).
"""
from __future__ import annotations
import os
import sys
import json
import glob
import threading
import traceback
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.registration import dataset as ds
from src.registration import pipeline as pl
from src.lunar_ai import interpreter as lunar_ai
from api.schemas import RegisterRequest, ExplainRegionRequest, CompareSensorsRequest, AskLunarAIRequest

RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
METADATA_DIR = os.path.join(PROJECT_ROOT, "data", "metadata")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

app = FastAPI(
    title="INVINCIBLES",
    description="Multi-Modal Lunar Image Registration & Scientific Analysis - Backend API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/static/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/static/data", StaticFiles(directory=RAW_DIR), name="data")

# ---------------------------------------------------------------------------
# In-memory job registry. run_id is deterministic (dataset hash + config
# hash) so re-requesting an already-completed/identical run is instant.
# ---------------------------------------------------------------------------
_JOBS = {}
_JOBS_LOCK = threading.Lock()


def _run_job(run_id: str, config: dict):
    with _JOBS_LOCK:
        _JOBS[run_id] = {"status": "RUNNING", "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        summary = pl.run_full_demo(PROJECT_ROOT, config)
        with _JOBS_LOCK:
            job_record = {"status": "COMPLETE", "summary": summary,
                          "finished_at": datetime.now(timezone.utc).isoformat()}
            _JOBS[summary["run_id"]] = job_record
            _JOBS[run_id] = job_record
    except Exception as e:
        with _JOBS_LOCK:
            _JOBS[run_id] = {"status": "ERROR", "error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/health")
def health():
    return {"project": "INVINCIBLES", "status": "READY"}


def _with_preview_urls(manifest: dict) -> dict:
    """Adds a `preview_url` convenience field per sensor (frontend-only
    concern; does not modify the manifest written to disk by dataset.py)."""
    import copy
    m = copy.deepcopy(manifest)
    for key, entry in m.get("sensors", {}).items():
        fname = os.path.basename(entry["file"])
        entry["preview_url"] = f"/static/data/{fname}"
    return m


@app.get("/api/dataset")
def get_dataset():
    try:
        manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return _with_preview_urls(manifest)


@app.get("/api/dataset/analysis")
def get_dataset_analysis():
    try:
        manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
        readiness = ds.readiness_report(manifest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"manifest": _with_preview_urls(manifest), "readiness_report": readiness}


@app.post("/api/register")
def start_registration(req: RegisterRequest, background_tasks: BackgroundTasks):
    manifest = ds.build_manifest(RAW_DIR, METADATA_DIR)
    config = {
        "force_rerun": req.force_rerun,
        "max_keypoints": req.max_keypoints,
        "ratio_thresh": req.ratio_thresh,
        "min_matches": req.min_matches,
        "reproj_thresh": req.reproj_thresh,
        "sensors": sorted(req.sensors) if req.sensors else None,
    }
    dataset_hash = pl.compute_dataset_hash(manifest)
    import hashlib
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:8]
    run_id = f"{dataset_hash}_{config_hash}"

    cache_marker = os.path.join(OUTPUT_DIR, "cache", f"{run_id}.json")
    if os.path.exists(cache_marker) and not req.force_rerun:
        with open(cache_marker) as fh:
            summary = json.load(fh)
        summary["cached"] = True
        with _JOBS_LOCK:
            _JOBS[run_id] = {"status": "COMPLETE", "summary": summary, "cached": True}
        return {"run_id": run_id, "status": "COMPLETE", "cached": True}

    with _JOBS_LOCK:
        already_running = _JOBS.get(run_id, {}).get("status") == "RUNNING"
    if not already_running:
        background_tasks.add_task(_run_job, run_id, config)
    return {"run_id": run_id, "status": "STARTED", "cached": False,
            "poll_url": f"/api/register/{run_id}/status"}


@app.get("/api/register/{run_id}/status")
def registration_status(run_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(run_id)
    if job is None:
        cache_marker = os.path.join(OUTPUT_DIR, "cache", f"{run_id}.json")
        if os.path.exists(cache_marker):
            return {"run_id": run_id, "status": "COMPLETE", "cached": True}
        raise HTTPException(status_code=404, detail="Unknown run_id. Start a registration run via POST /api/register.")
    return {"run_id": run_id, "status": job["status"], "cached": job.get("cached", False)}


def _get_summary_or_404(run_id: str) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(run_id)
    if job and "summary" in job:
        return job["summary"]
    cache_marker = os.path.join(OUTPUT_DIR, "cache", f"{run_id}.json")
    if os.path.exists(cache_marker):
        with open(cache_marker) as fh:
            return json.load(fh)
    raise HTTPException(status_code=404, detail="Results not available yet for this run_id.")


@app.get("/api/register/{run_id}/results")
def registration_results(run_id: str):
    return _get_summary_or_404(run_id)


@app.get("/api/runs")
def list_runs():
    """
    Run History (Spec Section 35). Reads directly from the existing
    output/cache/*.json cache files written by src/registration/pipeline.py
    - no new storage mechanism, no change to the registration algorithm.
    Returns a lightweight summary per run, newest first.
    """
    cache_dir = os.path.join(OUTPUT_DIR, "cache")
    if not os.path.isdir(cache_dir):
        return {"runs": []}

    runs = []
    for fname in sorted(os.listdir(cache_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(cache_dir, fname)
        try:
            with open(fpath) as fh:
                summary = json.load(fh)
        except Exception:
            continue

        sensor_results = summary.get("sensor_results", {})
        successes = [s for s, r in sensor_results.items() if r.get("status") == "SUCCESS"]
        failures = [s for s, r in sensor_results.items() if r.get("status") != "SUCCESS"]
        rmses = [r["metrics"]["checkpoint_rmse_final"] for r in sensor_results.values()
                 if r.get("status") == "SUCCESS" and r.get("metrics", {}).get("checkpoint_rmse_final") is not None]
        ratios = [r["metrics"]["inlier_ratio"] for r in sensor_results.values()
                  if r.get("status") == "SUCCESS" and r.get("metrics", {}).get("inlier_ratio") is not None]
        confidences = [r["confidence"]["level"] for r in sensor_results.values() if r.get("status") == "SUCCESS"]
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        overall_confidence = min(confidences, key=lambda c: rank.get(c, 0)) if confidences else None

        runs.append({
            "run_id": summary.get("run_id"),
            "generated_at": summary.get("generated_at"),
            "reference_sensor": "OHRC",
            "sensors_succeeded": successes,
            "sensors_failed": failures,
            "mean_checkpoint_rmse": (sum(rmses) / len(rmses)) if rmses else None,
            "mean_inlier_ratio": (sum(ratios) / len(ratios)) if ratios else None,
            "overall_confidence": overall_confidence,
            "status": "COMPLETE",
        })

    runs.sort(key=lambda r: r.get("generated_at") or "", reverse=True)
    return {"runs": runs}


@app.get("/api/register/{run_id}/metrics")
def registration_metrics(run_id: str):
    summary = _get_summary_or_404(run_id)
    out = {}
    for sensor, res in summary["sensor_results"].items():
        if res.get("status") == "SUCCESS":
            out[sensor] = {"metrics": res["metrics"], "confidence": res["confidence"]}
        else:
            out[sensor] = {"status": "FAILED", "failed_stage": res.get("failed_stage"), "reason": res.get("failure_reason")}
    return out


def _to_output_url(path: str | None) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    rel = os.path.relpath(path, OUTPUT_DIR).replace("\\", "/")
    return f"/static/output/{rel}"


@app.get("/api/register/{run_id}/matches")
def registration_matches(run_id: str):
    summary = _get_summary_or_404(run_id)
    run_dir = summary["run_dir"]
    files = sorted(glob.glob(os.path.join(run_dir, "matches", "*.png")))
    return {"images": [_to_output_url(f) for f in files if _to_output_url(f)]}


@app.get("/api/register/{run_id}/residuals")
def registration_residuals(run_id: str):
    summary = _get_summary_or_404(run_id)
    run_dir = summary["run_dir"]
    out = {}
    for sensor in summary["sensor_results"].keys():
        diag_dir = os.path.join(run_dir, "diagnostics", sensor)
        if not os.path.isdir(diag_dir):
            continue
        imgs = sorted(glob.glob(os.path.join(diag_dir, "*residual*.png")))
        out[sensor] = [_to_output_url(f) for f in imgs if _to_output_url(f)]
    return out


_DIAGNOSTIC_FILES = {
    "reference_analysis_view": "ref_analysis_view.png",
    "source_analysis_view": "src_analysis_view.png",
    "reference_phase_congruency": "ref_phase_congruency.png",
    "source_phase_congruency": "src_phase_congruency.png",
    "before_coarse_alignment": "before_coarse_alignment.png",
    "after_coarse_alignment": "after_coarse_alignment.png",
    "warped_registered": "warped_registered.png",
    "valid_mask": "valid_mask.png",
    "checkerboard": "checkerboard.png",
    "global_residual_map": "global_residual_map.png",
    "local_refinement_residual_map": "local_refinement_residual_map.png",
}


@app.get("/api/register/{run_id}/images")
def registration_images(run_id: str):
    """
    Convenience endpoint (Sections 20, 21, 25, 27) that resolves every
    diagnostic/registered image the pipeline actually wrote for this run
    into ready-to-use URLs, per sensor, so the frontend never has to guess
    filenames. Only images that actually exist on disk are included.
    """
    summary = _get_summary_or_404(run_id)
    run_dir = summary["run_dir"]

    manifest_sensors = summary.get("dataset_manifest", {}).get("sensors", {})
    out = {}
    for sensor in summary["sensor_results"].keys():
        diag_dir = os.path.join(run_dir, "diagnostics", sensor)
        entry = {key: _to_output_url(os.path.join(diag_dir, fname)) for key, fname in _DIAGNOSTIC_FILES.items()}
        entry["candidate_matches"] = _to_output_url(os.path.join(run_dir, "matches", f"{sensor}_candidate_matches.png"))
        entry["inlier_matches"] = _to_output_url(os.path.join(run_dir, "matches", f"{sensor}_inlier_matches.png"))
        entry["multiband_layer_preview"] = _to_output_url(os.path.join(run_dir, f"layer_{sensor}.png"))
        entry["comparison_strip"] = _to_output_url(os.path.join(run_dir, f"comparison_{sensor}.png"))
        orig_file = manifest_sensors.get(sensor, {}).get("file", "")
        if orig_file:
            entry["original_input"] = f"/static/data/{os.path.basename(orig_file)}"
        out[sensor] = {k: v for k, v in entry.items() if v is not None}

    ohrc_preview = _to_output_url(os.path.join(run_dir, "layer_OHRC.png"))
    ohrc_file = manifest_sensors.get("OHRC", {}).get("file", "")
    ohrc_entry = {}
    if ohrc_preview:
        ohrc_entry["multiband_layer_preview"] = ohrc_preview
    if ohrc_file:
        ohrc_entry["original_input"] = f"/static/data/{os.path.basename(ohrc_file)}"
    if ohrc_entry:
        out["OHRC"] = ohrc_entry

    comp_img = _to_output_url(os.path.join(run_dir, "composite_registered.png"))
    if comp_img:
        out["COMPOSITE"] = {"composite_registered": comp_img}

    return out


@app.get("/api/register/{run_id}/composite")
def get_composite(run_id: str):
    """Returns composite registered false-color image URL and channel mapping."""
    summary = _get_summary_or_404(run_id)
    run_dir = summary["run_dir"]
    comp_path = os.path.join(run_dir, "composite_registered.png")
    url = _to_output_url(comp_path)
    if url:
        return {
            "available": True,
            "url": url,
            "channels": {
                "R": "OHRC (Optical Reference)",
                "G": "IIRS (Infrared Spectral) or TMC-Slope",
                "B": "SAR (Radar Backscatter) or TMC-Azimuth"
            },
            "description": "Multi-sensor false-color registered composite overlay."
        }
    return {
        "available": False,
        "url": None,
        "message": "Composite registered image not yet generated for this run."
    }


@app.get("/api/register/{run_id}/comparison")
def get_comparison(run_id: str):
    """Returns side-by-side comparison strips and raw vs registered URLs for all sensors."""
    summary = _get_summary_or_404(run_id)
    run_dir = summary["run_dir"]
    manifest_sensors = summary.get("dataset_manifest", {}).get("sensors", {})
    out = {}

    ohrc_file = manifest_sensors.get("OHRC", {}).get("file", "")
    out["OHRC"] = {
        "sensor": "OHRC",
        "role": "REFERENCE",
        "raw_input_url": f"/static/data/{os.path.basename(ohrc_file)}" if ohrc_file else None,
        "multiband_preview_url": _to_output_url(os.path.join(run_dir, "layer_OHRC.png")),
    }

    for sensor, res in summary["sensor_results"].items():
        comp_strip_path = os.path.join(run_dir, f"comparison_{sensor}.png")
        orig_file = manifest_sensors.get(sensor, {}).get("file", "")
        raw_name = os.path.basename(orig_file) if orig_file else ""
        diag_dir = os.path.join(run_dir, "diagnostics", sensor)
        warped_path = os.path.join(diag_dir, "warped_registered.png")

        out[sensor] = {
            "sensor": sensor,
            "status": res.get("status"),
            "confidence": res.get("confidence", {}).get("level") if res.get("status") == "SUCCESS" else None,
            "transformation_model": res.get("metrics", {}).get("transformation_model") if res.get("status") == "SUCCESS" else None,
            "checkpoint_rmse_final": res.get("metrics", {}).get("checkpoint_rmse_final") if res.get("status") == "SUCCESS" else None,
            "comparison_strip_url": _to_output_url(comp_strip_path),
            "raw_input_url": f"/static/data/{raw_name}" if raw_name else None,
            "warped_registered_url": _to_output_url(warped_path),
        }
    return out


@app.get("/api/output")
def list_output(run_id: str):
    summary = _get_summary_or_404(run_id)
    return summary.get("fusion_output", {})


@app.get("/api/report", response_class=PlainTextResponse)
def get_report(run_id: str):
    summary = _get_summary_or_404(run_id)
    from src.registration import report as reportmod
    return reportmod.build_markdown_report(summary)


# ---------------------------------------------------------------------------
# LUNAR AI
# ---------------------------------------------------------------------------
def _sensor_results_for_ai(summary: dict) -> dict:
    return summary["sensor_results"]


@app.post("/api/lunar-ai/analyze")
def lunar_ai_analyze(payload: dict):
    run_id = payload.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    summary = _get_summary_or_404(run_id)
    return lunar_ai.build_scientific_report(_sensor_results_for_ai(summary))


@app.post("/api/lunar-ai/explain-region")
def lunar_ai_explain_region(req: ExplainRegionRequest):
    summary = _get_summary_or_404(req.run_id)
    roi = {"x": req.x, "y": req.y, "radius": req.radius}
    return lunar_ai.explain_region(roi, _sensor_results_for_ai(summary))


@app.post("/api/lunar-ai/compare-sensors")
def lunar_ai_compare_sensors(req: CompareSensorsRequest):
    summary = _get_summary_or_404(req.run_id)
    return lunar_ai.compare_sensors(_sensor_results_for_ai(summary))


@app.post("/api/lunar-ai/ask")
def lunar_ai_ask(req: AskLunarAIRequest):
    summary = _get_summary_or_404(req.run_id)
    report = lunar_ai.build_scientific_report(_sensor_results_for_ai(summary))
    context = {
        "sensor_results": _sensor_results_for_ai(summary),
        "lunar_ai_report": report,
        "dataset_manifest_summary": {k: v.get("stats", {}).get("sensor") for k, v in summary["dataset_manifest"]["sensors"].items()},
    }
    return lunar_ai.ask_lunar_ai(req.question, context)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
