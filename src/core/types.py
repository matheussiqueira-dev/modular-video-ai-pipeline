from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np


Bbox = Tuple[int, int, int, int]
Point = Tuple[int, int]


@dataclass(slots=True)
class Detection:
    bbox: Bbox
    label: str
    score: float
    class_id: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": [int(v) for v in self.bbox],
            "label": self.label,
            "score": float(self.score),
            "class_id": int(self.class_id),
        }


@dataclass(slots=True)
class Track:
    id: int
    bbox: Bbox
    class_id: int
    label: str
    mask: np.ndarray
    cluster_id: Optional[int] = None
    ocr_text: str = ""
    world_position: Optional[Point] = None

    def to_dict(self, include_mask: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": int(self.id),
            "bbox": [int(v) for v in self.bbox],
            "class_id": int(self.class_id),
            "label": self.label,
            "cluster_id": None if self.cluster_id is None else int(self.cluster_id),
            "ocr_text": self.ocr_text,
            "world_position": list(self.world_position) if self.world_position else None,
        }
        if include_mask:
            payload["mask"] = self.mask.astype(np.uint8).tolist()
        return payload


@dataclass(slots=True)
class PipelineEvent:
    frame: int
    event_type: str
    object_id: int
    details: str
    severity: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame": int(self.frame),
            "type": self.event_type,
            "object_id": int(self.object_id),
            "details": self.details,
            "severity": self.severity,
        }


@dataclass(slots=True)
class PipelineStats:
    frame_idx: int
    processing_fps: float
    active_tracks: int
    events_in_frame: int
    class_distribution: Dict[str, int] = field(default_factory=dict)
