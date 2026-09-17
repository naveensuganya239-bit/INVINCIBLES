#!/usr/bin/env python3
"""
INVINCIBLES - Standalone Pipeline Runner
===========================================
Run the complete end-to-end registration pipeline from the command line,
without needing the FastAPI server. Useful for evaluators who want to see
raw computation happen and inspect output/ directly.

Usage:
    python run_pipeline.py                 # run full demo (all 4 source sensors)
    python run_pipeline.py --sensor SAR    # run a single sensor
    python run_pipeline.py --force-rerun   # ignore cache
    python run_pipeline.py --report        # also print the markdown report
"""
import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.registration import dataset as ds
from src.registration import pipeline as pl
from src.registration import report as reportmod


def main():
    parser = argparse.ArgumentParser(description="INVINCIBLES lunar registration pipeline")
    parser.add_argument("--sensor", default=None, help="Run a single source sensor (TMC-Azimuth, TMC-Slope, IIRS, SAR)")
    parser.add_argument("--force-rerun", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--max-keypoints", type=int, default=600)
    parser.add_argument("--ratio-thresh", type=float, default=0.85)
    args = parser.parse_args()

    print("=" * 70)
    print("INVINCIBLES - Multi-Modal Lunar Image Registration")
    print("=" * 70)

    raw_dir = os.path.join(PROJECT_ROOT, "data", "raw")
    metadata_dir = os.path.join(PROJECT_ROOT, "data", "metadata")

    print("\n[PHASE 1] Dataset forensic analysis...")
    manifest = ds.build_manifest(raw_dir, metadata_dir)
    readiness = ds.readiness_report(manifest)
    for k, v in readiness.items():
        print(f"  {k}: {'OK' if v else 'MISSING/BLOCKED'}")

    config = {
        "force_rerun": args.force_rerun,
        "max_keypoints": args.max_keypoints,
        "ratio_thresh": args.ratio_thresh,
    }

    if args.sensor:
        print(f"\n[PHASE 2] Running registration for {args.sensor} -> OHRC ...")
        run_dir = os.path.join(PROJECT_ROOT, "output", "registered", f"single_{args.sensor}")
        result = pl.register_sensor(args.sensor, manifest, run_dir, config)
        print(json.dumps({k: v for k, v in result.items() if k not in ("warped_image", "valid_mask")},
                          indent=2, default=str))
        return

    print("\n[PHASE 2] Running FULL DEMO (all source sensors vs OHRC reference)...")
    summary = pl.run_full_demo(PROJECT_ROOT, config)
    print(f"\nRun ID: {summary['run_id']}  (cached={summary.get('cached', False)})")
    for sensor, res in summary["sensor_results"].items():
        status = res.get("status")
        if status == "SUCCESS":
            print(f"  {sensor}: SUCCESS | model={res['metrics']['transformation_model']} | "
                  f"inliers={res['metrics']['n_inliers']} | RMSE={res['metrics']['checkpoint_rmse_final']:.2f}px | "
                  f"confidence={res['confidence']['level']}")
        else:
            print(f"  {sensor}: FAILED at {res.get('failed_stage')} - {res.get('failure_reason')}")

    print(f"\nMulti-band output: {summary['fusion_output']['npz_path']}")

    if args.report:
        print("\n" + "=" * 70)
        print(reportmod.build_markdown_report(summary))


if __name__ == "__main__":
    main()
