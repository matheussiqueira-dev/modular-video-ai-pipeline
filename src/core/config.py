from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class PipelineConfig:
    output_path: Path = Path("output.mp4")
    export_jsonl_path: Optional[Path] = None
    max_frames: int = 300
    fps: int = 30
    ocr_interval: int = 30
    clustering_interval: int = 5
    dwell_seconds: int = 3
    zone_entry_threshold: int = 5

    @property
    def dwell_frames(self) -> int:
        return max(1, int(self.dwell_seconds * self.fps))
