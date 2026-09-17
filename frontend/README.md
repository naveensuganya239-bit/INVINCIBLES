# INVINCIBLES — Frontend

World-class mission-control frontend for the INVINCIBLES multi-modal lunar
image registration backend. React + TypeScript + Vite, no UI kit — a
custom dark, restrained, instrument-panel design system built specifically
for this project (see `src/index.css`).

This frontend **adapts to the real backend** — every page reads its data
from an actual FastAPI endpoint (see `src/api/`); nothing is hard-coded or
fabricated. If a value isn't available from the backend, the UI shows
`N/A` or an explicit empty/error state rather than inventing one.

## Quick start

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL if your backend isn't on localhost:8000
npm run dev
```

The backend (see `../invincibles/README.md`) must be running for anything
beyond the initial shell to work:

```bash
cd ../invincibles
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Then open http://localhost:5173.

## Build

```bash
npm run build   # type-checks with tsc -b, then builds via Vite into dist/
npm run preview # serve the production build locally
```

## Project structure

```
src/
  api/            Centralized API client (client.ts) + one module per
                   backend resource (dataset, registration, lunarAI,
                   reports, runs) — no scattered fetch() calls.
  types/           TypeScript interfaces mirroring actual backend response
                   shapes (api/main.py, src/registration/pipeline.py).
  context/         RunContext — tracks the active run_id across pages,
                   polls /api/register/{run_id}/status while a job runs.
  components/
    layout/         Sidebar, TopBar
    common/          MetricCard, StatusPill, Tabs, ImageFrame,
                      CompareSlider, PipelineTimeline, SensorCard, Icons
  pages/            One file per navigation section (Mission Control,
                     Dataset, Registration, Feature Analysis, Correspondence,
                     Results, Multi-Sensor, Lunar AI, Reports, Run History)
```

## Environment

`VITE_API_BASE_URL` — base URL of the FastAPI backend. Defaults to
`http://localhost:8000` if unset. Set this to your deployed backend URL
when building for production; the frontend and backend can be deployed
independently.

## Notes on backend-adapted design decisions

- **Sensor selection** actually filters which sensors the backend
  processes (`POST /api/register` with a `sensors` array) — this required
  a small, safe backend addition to honor a field that was already
  declared in the request schema but previously unused; no registration
  algorithm code was touched.
- **Run History** reads directly from the backend's `output/cache/*.json`
  files via a new `GET /api/runs` endpoint — no separate database, no
  frontend-only mock data.
- **Feature Analysis** shows Original / Preprocessed / Phase Congruency /
  Coarse Alignment because those are the diagnostic images the backend
  actually writes per run. There is no fabricated "keypoints overlay" tab
  — the closest real artifact (candidate/inlier match visualization) lives
  on the Correspondence page instead, where it belongs.
- **Correspondence** ALL/INLIERS/OUTLIERS distinction is implemented as a
  toggle between the two real backend-rendered images (candidate matches,
  inlier/outlier classification) rather than redrawing lines client-side
  from raw coordinates the backend doesn't currently expose per-point.
