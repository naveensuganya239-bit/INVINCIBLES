# INVINCIBLES
### Multi-Modal, Sun-Angle and Scale-Invariant Lunar Image Registration
**Backend prototype - Smart India Hackathon**

This is the real, executable backend for INVINCIBLES: a scientific image-registration
engine that registers multi-sensor Chandrayaan-2-style lunar observations
(TMC-Azimuth, TMC-Slope, IIRS, SAR) into the fixed OHRC reference coordinate frame,
and quantitatively validates the result. Every number in every output was computed
from the actual supplied images in `data/raw/` - nothing is hard-coded, simulated,
or fabricated. Where a stage fails, the system reports the failure honestly instead
of manufacturing a convincing-looking result.

This package contains **backend only** (FastAPI + a standalone CLI). The frontend
is intentionally not included here.

---

## 1. Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Option A: run everything from the command line, no server needed
python run_pipeline.py --report

# Option B: run the API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Optional: set `ANTHROPIC_API_KEY` in your environment to enable the interactive,
Claude-backed Lunar AI Q&A endpoint (`/api/lunar-ai/ask`). Without it, Lunar AI
still works end-to-end using a transparent rule-based fallback grounded in the
same computed data.

Run the test suite:

```bash
pytest tests/ -v
```

---

## 2. Project layout

```
invincibles/
├── data/
│   ├── raw/            # the 5 original, UNMODIFIED sensor images
│   ├── metadata/        # dataset_manifest.json (machine-readable, generated)
│   └── processed/
├── src/
│   ├── registration/     # dataset mapping, pipeline orchestration, report
│   ├── preprocessing/    # sensor-aware preprocessing (CLAHE, Lee/Frost, etc.)
│   ├── features/         # scale-space, phase congruency, keypoints/ANMS, descriptors
│   ├── matching/          # ratio-test + mutual cross-check matcher
│   ├── geometry/          # coarse alignment, FSC consensus, model selection,
│   │                       local refinement, sub-pixel refinement,
│   │                       dense area-based (ECC/MI/NCC) fallback registration
│   ├── evaluation/         # RMSE/confidence metrics, warping, checkerboard
│   ├── fusion/             # multi-band output writer
│   └── lunar_ai/           # epistemically-honest interpretation engine
├── api/                  # FastAPI application + pydantic schemas
├── output/                # diagnostics / matches / registered / metrics / reports / cache
├── tests/                 # pytest unit + integration tests
├── requirements.txt
├── run_pipeline.py        # CLI entry point
└── README.md
```

---

## 3. Pipeline (implemented exactly as specified)

```
RAW MULTI-SENSOR DATA -> INPUT VALIDATION -> IMAGE CHARACTERIZATION ->
SENSOR-AWARE PREPROCESSING -> MULTI-SCALE REPRESENTATION ->
ILLUMINATION-ROBUST FEATURE REPRESENTATION (Phase Congruency) ->
FEATURE DETECTION (Shi-Tomasi on phase congruency, multiscale) -> ANMS ->
COARSE GEOMETRIC ALIGNMENT (FFT log-polar phase correlation) ->
MULTI-MODAL DESCRIPTOR (RIFT / CFOG fallback) -> FEATURE MATCHING (ratio
test + mutual cross-check) -> ROBUST OUTLIER REJECTION (FSC) ->
TRANSFORMATION MODEL SELECTION (similarity -> affine -> homography,
residual-justified) -> LOCAL TERRAIN-RELIEF REFINEMENT (evidence-gated) ->
SUB-PIXEL REFINEMENT (upsampled phase correlation) -> INDEPENDENT
CHECKPOINT VALIDATION -> WARPING (sensor-appropriate interpolation) ->
CHECKERBOARD -> MULTI-SENSOR OUTPUT -> LUNAR AI.
```

OHRC is hard-locked as the reference everywhere in the codebase
(`src/registration/dataset.py::SENSOR_TABLE`) - it cannot be swapped out through
the API.

If any stage cannot produce a valid result, the pipeline stops for that sensor
and returns `{"status": "FAILED", "failed_stage": ..., "failure_reason": ...}`
rather than continuing to build on top of an unreliable result (see
`src/registration/pipeline.py::_fail`).

---

## 4. Documented algorithmic deviations

The spec requires that any deviation from the primary algorithm be investigated,
justified, and documented. Deviations actually taken on this codebase:

### 4.1 RIFT -> CFOG fallback (per-run, automatic)
Primary descriptor is an original NumPy re-implementation of RIFT's core idea
(log-Gabor Convolution Sequence -> Maximum Index Map -> localized histogram
descriptor), following Li, Hu & Ai (2020) "RIFT: Multi-modal Image Matching
Based on Radiation-Invariant Feature Transform" (IEEE TIP). No third-party RIFT
source code was copied - only the published mathematical idea was used as a
reference (see `src/features/descriptors.py` module docstring for full detail).

If the log-Gabor orientation response on the actual image is too flat to be
discriminative (measured via a peak-to-mean amplitude ratio), the pipeline
automatically switches to **CFOG** (gradient-orientation channel histograms),
and records the measured quality score and reason in
`result["descriptor_deviation_reason"]`. This is decided per-run from the real
image content, not hard-coded per sensor.

### 4.1b Dense area-based registration fallback (TMC-Azimuth / TMC-Slope)
On the actual supplied dataset, sparse RIFT/CFOG keypoint-descriptor matching
does not find enough stable correspondences for the two DERIVED TERRAIN
products (TMC-Azimuth, TMC-Slope): they preserve the crater's boundary/contour
geometry very well but carry little of the corner-like local texture that a
sparse descriptor needs. Rather than reporting these as permanently FAILED,
`src/registration/pipeline.py::register_sensor` automatically escalates to a
**second, genuinely different, area-based (not feature-based) algorithm**
implemented in `src/geometry/area_based_registration.py`, whenever the sparse
path does not clear the minimum-match threshold:

1. **Global intensity-based alignment.** Gradient-magnitude maps of OHRC and
   the terrain layer (a photometry-independent structural representation - a
   crater rim is a strong edge no matter how a sensor colour-maps it) are
   aligned using OpenCV's **ECC** (Enhanced Correlation Coefficient,
   Evangelidis & Psarakis 2008), tried from two seeds (the upstream phase-
   congruency coarse-alignment estimate, and identity) in a coarse-to-fine
   pyramid. If no ECC attempt reaches a minimally-acceptable correlation
   coefficient, the module falls back to a **third, independent algorithm**:
   direct maximization of **Mutual Information** between the grayscale views
   over a similarity-transform search (Powell's method) - the classical
   technique for cross-modal pairs whose intensity relationship is nonlinear.
2. **Independent dense correspondence generation.** The stage-1 transform is
   only a starting hypothesis. Genuine, independently-measured point
   correspondences are then produced by locating **Shi-Tomasi corners** on
   the reference gradient map (deliberately NOT a uniform grid - a uniform
   grid samples points along the smooth crater rim where NCC template
   matching suffers the classical "aperture problem": a patch can slide
   tangentially along the boundary with almost no score penalty, giving a
   confidently-scored but wrong position) and re-locating each one in the
   source gradient map via normalized cross-correlation (NCC) template
   matching, with sub-pixel parabolic peak interpolation and a
   forward/backward mutual-consistency check.

These independently-measured correspondences then flow into the **same** FSC
consensus, transformation-model-selection, local-refinement, sub-pixel-
refinement, independent-checkpoint-RMSE, and confidence-scoring code used for
the descriptor-based sensors - the fallback only replaces how correspondences
are found, not how the result is evaluated or reported. The chosen
`correspondence_method` (`sparse_descriptor_matching` vs
`dense_area_based_fallback`) and the full multi-start audit trail are recorded
in every result and surfaced in the Markdown report.

With this escalation path, all four source sensors (TMC-Azimuth, TMC-Slope,
IIRS, SAR) reach `SUCCESS` on the actual supplied sample dataset. TMC-Azimuth
and TMC-Slope currently land at MEDIUM confidence (checkpoint RMSE in the
~8-12px range) because the dense NCC correspondences on this particular
sample imagery carry more inherent localization noise than the sparse
descriptor matches found for IIRS/SAR - this is reported honestly rather than
smoothed over, and is the expected trade-off of an area-based method on
lower-texture derived products.

### 4.2 FSC, not vanilla RANSAC
`src/geometry/consensus.py` implements FSC (Fast Sample Consensus) with (a)
match-quality-guided minimal-sample selection and (b) a coarse spatial-grid
fast-consensus pre-check, which is structurally different from uniform-random
RANSAC and converges faster on the low-inlier-ratio correspondence sets typical
of cross-sensor matching. If FSC cannot find a valid hypothesis, this is
reported as an honest `ROBUST_OUTLIER_REJECTION` failure - it is never silently
relabeled as a degenerate RANSAC success.

### 4.3 Coarse alignment
Uses Fourier-Mellin / log-polar FFT phase correlation on the phase-congruency
maps (structural, not raw-intensity) to estimate an initial
scale/rotation/translation hypothesis, rather than explicit crater-ellipse
detection - because reliable crater-boundary detection cannot be guaranteed to
generalize across all four source modalities on the actual supplied imagery.
Both BEFORE/AFTER coarse-alignment diagnostics are saved per sensor.

### 4.4 Keypoint detector
Shi-Tomasi ("good features to track") corner scoring on the phase-congruency
map was used instead of a bare `cornerHarris` threshold sweep, because it
measurably produced far better cross-image repeatability on the actual
supplied dataset during development (empirically verified, not assumed).

All deviations above are surfaced in both the JSON API results and the
Markdown scientific report (`/api/report`), never hidden.

---

## 5. Honesty guarantees actually enforced in code

- `src/registration/pipeline.py` never fills in a metric it didn't compute;
  every `metrics.*` value is a real number derived from the actual FSC/RMSE/
  sub-pixel computation for that run.
- Preprocessing never overwrites `data/raw/*` or the in-memory "original"
  arrays used for final warping (`tests/test_preprocessing.py` asserts this).
- Confidence (`src/evaluation/metrics.py::classify_confidence`) is a rule-based
  aggregation over measured inlier ratio / RMSE / spatial coverage - never an
  arbitrary label.
- Lunar AI (`src/lunar_ai/interpreter.py`) never claims mineral composition,
  elevation, latitude/longitude, or crater age, because this dataset carries no
  calibration or geolocation metadata to support such claims. Every statement
  is tagged OBSERVED / DERIVED / UNCERTAIN.
- Registration failures are structured and explicit
  (`status="FAILED"`, `failed_stage`, `failure_reason`) and Lunar AI explicitly
  refuses to interpret a sensor whose registration failed.

---

## 6. API surface

```
GET  /api/health
GET  /api/dataset                          (includes preview_url per sensor)
GET  /api/dataset/analysis
POST /api/register                       {sensors?, force_rerun?, max_keypoints?, ratio_thresh?, min_matches?, reproj_thresh?}
GET  /api/register/{run_id}/status
GET  /api/register/{run_id}/results
GET  /api/register/{run_id}/metrics
GET  /api/register/{run_id}/matches
GET  /api/register/{run_id}/residuals
GET  /api/register/{run_id}/images         (resolves every diagnostic/registered image URL per sensor)
GET  /api/output?run_id=...
GET  /api/report?run_id=...              (Markdown)
GET  /api/runs                             (run history, read from output/cache/*.json)
POST /api/lunar-ai/analyze               {run_id}
POST /api/lunar-ai/explain-region        {run_id, x, y, radius?}
POST /api/lunar-ai/compare-sensors       {run_id}
POST /api/lunar-ai/ask                   {run_id, question}   <- interactive, Claude-backed when ANTHROPIC_API_KEY is set
```

Diagnostic/registered images are served statically under `/static/output/...`;
original raw sensor images are served under `/static/data/...`. A CORS
policy of `allow_origins=["*"]` is enabled so a separately-hosted frontend
(see `../frontend/`) can call this API directly.

Runs are cached by `run_id = sha256(sorted sensor file hashes)[:16] + "_" + sha256(config)[:8]`;
re-registering the same dataset with the same config returns instantly from
`output/cache/{run_id}.json` unless `force_rerun: true` is passed. `POST
/api/register` accepts an optional `sensors` array (e.g. `["SAR", "IIRS"]`)
to run only a subset of source sensors against OHRC; omitting it runs all
four.

---

## 7. Frontend

A complete frontend lives in the sibling `../frontend/` directory (React +
TypeScript + Vite). Run this backend first (`uvicorn api.main:app
--reload`), then see `../frontend/README.md` to run it. It talks to every
endpoint listed above and nothing else.

## 8. Known limitations (stated, not hidden)

- All four source sensors reach `SUCCESS` on the actual supplied
  `SIH IMAGE.zip` sample set, but at differing confidence: IIRS/SAR (sparse
  RIFT descriptor matching) reach MEDIUM confidence around 4-5px checkpoint
  RMSE; TMC-Azimuth/TMC-Slope (dense area-based fallback) also reach MEDIUM
  confidence but with higher checkpoint RMSE (~8-12px), reflecting genuinely
  higher correspondence-localization noise on those derived terrain products.
  None of these numbers are floors or targets baked into the code - a
  different sample set could legitimately produce FAILED for any sensor, and
  the pipeline will report that honestly rather than forcing a success.
- No geolocation/calibration metadata accompanies the sample imagery, so no
  absolute coordinate, mineral-composition, or age claim is ever produced.
- RIFT is a from-scratch NumPy re-implementation, not a certified reference
  implementation; expect it to be slower and somewhat less optimized than a
  production C++/CUDA RIFT.
- The area-based fallback (Section 4.1b) trades some precision for
  reliability on low-texture derived products; if higher accuracy is needed
  on TMC-Azimuth/TMC-Slope, increasing `patch_half`/tightening `mutual_tol`
  in `src/registration/pipeline.py::_area_based_fallback` trades correspondence
  count for precision (see the parameter sweep documented in that function).
