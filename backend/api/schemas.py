from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    sensors: Optional[List[str]] = None  # None -> all four source sensors
    force_rerun: bool = False
    max_keypoints: int = 600
    ratio_thresh: float = 0.85
    min_matches: int = 8
    reproj_thresh: float = 6.0


class ExplainRegionRequest(BaseModel):
    run_id: str
    x: float
    y: float
    radius: float = 24.0


class CompareSensorsRequest(BaseModel):
    run_id: str


class AskLunarAIRequest(BaseModel):
    run_id: str
    question: str
