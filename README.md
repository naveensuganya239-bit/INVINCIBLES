# INVINCIBLES

### Multi-Modal, Sun-Angle and Scale-Invariant Lunar Image Registration
**Full-stack prototype — Smart India Hackathon**

Real, executable, scientifically traceable registration of multi-sensor
Chandrayaan-2-style lunar observations (TMC-Azimuth, TMC-Slope, IIRS, SAR)
into a common OHRC reference frame, with a scientific-workstation frontend
on top. Every number shown anywhere in the UI is computed by the backend
from the actual images in `backend/data/raw/` — nothing is fabricated.

```
INVINCIBLES/
├── backend/    FastAPI + the full registration engine (see backend/README.md)
└── frontend/   React + TypeScript mission-control UI (see frontend/README.md)
```

## Run the whole stack

**1. Backend** (do this first — the frontend has nothing to show without it):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

This starts the API at `http://localhost:8000`. Optionally set
`ANTHROPIC_API_KEY` in your environment first to enable the interactive
Lunar AI chat (it works without it too, via a rule-based fallback).

**2. Frontend**, in a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`. Click **RUN FULL ANALYSIS** on Mission
Control to kick off a real registration run against the real dataset —
first run takes roughly 30–90 seconds for all four source sensors; repeat
runs with identical settings return instantly from the backend's cache.

## What's already been verified end-to-end

- `cd backend && pytest tests/ -v` — 22/22 passing, including a regression
  test that all four source sensors (TMC-Azimuth, TMC-Slope, IIRS, SAR)
  reach `SUCCESS` against OHRC on the real supplied dataset.
- `cd frontend && npm run build` — clean TypeScript build, no errors.
- A full run was triggered through the live UI against the live backend
  and every page (Mission Control, Dataset, Registration, Feature
  Analysis, Correspondence, Results, Multi-Sensor, Lunar AI incl. region
  click + chat, Reports, Run History) was screenshotted and inspected
  against the real API responses.

## Design note

The frontend was built strictly backend-first: the backend's actual
endpoints, response shapes, and behavior were read directly from source
before any UI code was written (see `frontend/README.md` for the mapping
and the handful of small, additive, non-algorithmic backend endpoints that
were added purely to expose data the frontend needed — e.g. run history,
resolved diagnostic-image URLs — documented in `backend/README.md` §6-7).
No registration algorithm code was changed to build the frontend.
