from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class FrontendControl:
    preset_name: str
    uploaded: Any
    execution_target: str
    max_frames: int
    fps: int
    ocr_interval: int
    cluster_interval: int
    high_contrast: bool
    reduced_motion: bool
    mock_mode: bool
    zones: List[dict] = field(default_factory=list)
    backend_base_url: str = ""
    backend_api_key: str = ""
    backend_poll: float = 1.2
    run_clicked: bool = False


@dataclass(slots=True)
class RunPayload:
    preset: str
    summary: Dict[str, Any]
    video_bytes: bytes
    analytics_bytes: bytes
    frames_df: Any
    events_df: Any
    zones: List[dict]
    execution_target: str
    config: Dict[str, Any]
    job_id: Optional[str] = None
