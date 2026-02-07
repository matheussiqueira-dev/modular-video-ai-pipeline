from __future__ import annotations

import logging
import math
from typing import List, Optional

import numpy as np


class ObjectDetector:
    """
    Wrapper for object detection models (RF-DETR style interface).
    Defaults to deterministic mock mode to keep local development lightweight.
    """

    def __init__(
        self,
        model_input: str = "rf-detr-resnet50",
        confidence_threshold: float = 0.5,
        device: str = "cuda",
        mock_mode: bool = True,
    ):
        self.logger = logging.getLogger(__name__)
        self.confidence_threshold = float(confidence_threshold)
        self.device = device
        self.model_name = model_input
        self.model = None
        self.processor = None
        self.mock_mode = bool(mock_mode)
        self._load_model()

    def _load_model(self) -> None:
        self.logger.info("Loading detection model '%s' on %s", self.model_name, self.device)
        if self.mock_mode:
            self.logger.info("Object detector running in deterministic mock mode.")
            return

        try:
            # Real inference scaffold (intentionally disabled by default)
            # from transformers import AutoImageProcessor, AutoModelForObjectDetection
            # self.processor = AutoImageProcessor.from_pretrained(self.model_name)
            # self.model = AutoModelForObjectDetection.from_pretrained(self.model_name).to(self.device)
            self.mock_mode = True
            self.logger.warning("Real model loading disabled. Falling back to mock mode.")
        except Exception as exc:
            self.logger.exception("Failed to load model. Switching to mock mode: %s", exc)
            self.mock_mode = True

    def detect(self, frame: np.ndarray, frame_idx: Optional[int] = None) -> List[dict]:
        if not isinstance(frame, np.ndarray):
            raise TypeError("frame must be a numpy.ndarray")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must have shape (H, W, 3)")

        if self.mock_mode:
            detections = self._mock_inference(frame, frame_idx or 0)
        else:
            detections = []
            # Real inference hook goes here.

        return [d for d in detections if d["score"] >= self.confidence_threshold]

    def _mock_inference(self, frame: np.ndarray, frame_idx: int) -> List[dict]:
        h, w, _ = frame.shape

        person_width = max(20, int(0.18 * w))
        person_height = max(40, int(0.5 * h))
        person_x = int(0.15 * w + (frame_idx % 60) * 1.8)
        person_y = int(0.25 * h)

        person_bbox = self._clamp_bbox(
            person_x,
            person_y,
            person_x + person_width,
            person_y + person_height,
            w,
            h,
        )

        angle = frame_idx / 7.0
        ball_center_x = int(0.62 * w + math.sin(angle) * (0.05 * w))
        ball_center_y = int(0.58 * h + math.cos(angle * 1.4) * (0.06 * h))
        radius = max(8, int(min(w, h) * 0.02))
        ball_bbox = self._clamp_bbox(
            ball_center_x - radius,
            ball_center_y - radius,
            ball_center_x + radius,
            ball_center_y + radius,
            w,
            h,
        )

        return [
            {"bbox": person_bbox, "label": "person", "score": 0.96, "class_id": 0},
            {"bbox": ball_bbox, "label": "sports ball", "score": 0.89, "class_id": 32},
        ]

    @staticmethod
    def _clamp_bbox(x1: int, y1: int, x2: int, y2: int, width: int, height: int) -> List[int]:
        x1 = int(max(0, min(width - 2, x1)))
        y1 = int(max(0, min(height - 2, y1)))
        x2 = int(max(x1 + 1, min(width - 1, x2)))
        y2 = int(max(y1 + 1, min(height - 1, y2)))
        return [x1, y1, x2, y2]
