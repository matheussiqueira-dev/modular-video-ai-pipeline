from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import numpy as np


class VideoSegmenter:
    """
    Lightweight segmentation+tracking facade.
    In mock mode, masks are box-based and IDs are kept stable via IoU matching.
    """

    def __init__(
        self,
        model_cfg: str = "sam2_hiera_l.yaml",
        checkpoint: str = "sam2_hiera_large.pt",
        device: str = "cuda",
        iou_threshold: float = 0.35,
        max_missing_frames: int = 10,
    ):
        self.logger = logging.getLogger(__name__)
        self.device = device
        self.predictor = None
        self.inference_state = None
        self.mock_mode = True

        self.iou_threshold = float(iou_threshold)
        self.max_missing_frames = int(max_missing_frames)
        self._next_track_id = 1
        self._active_tracks: Dict[int, dict] = {}

        self._load_model(model_cfg, checkpoint)

    def _load_model(self, cfg: str, checkpoint: str) -> None:
        self.logger.info("Initializing SAM2 with config '%s'", cfg)
        # Real loading scaffold intentionally disabled.
        self.mock_mode = True
        self.logger.info("Video segmenter running in mock mode.")

    def init_state(self, video_path: str) -> None:
        self.logger.info("Preparing inference state for video: %s", video_path)
        self.inference_state = {"video_path": video_path, "mock": self.mock_mode}

    def track_objects(self, frame_idx: int, frame: np.ndarray, detections: list) -> List[dict]:
        if not isinstance(frame, np.ndarray):
            raise TypeError("frame must be a numpy.ndarray")
        if frame.ndim != 3:
            raise ValueError("frame must have shape (H, W, 3)")

        for track in self._active_tracks.values():
            track["missing"] += 1

        assigned_track_ids = set()
        results: List[dict] = []

        for det in detections:
            bbox = self._sanitize_bbox(det.get("bbox", [0, 0, 1, 1]), frame.shape[1], frame.shape[0])
            class_id = int(det.get("class_id", -1))
            label = str(det.get("label", "object"))

            track_id = self._match_existing_track(bbox, class_id, assigned_track_ids)
            if track_id is None:
                track_id = self._next_track_id
                self._next_track_id += 1

            assigned_track_ids.add(track_id)
            self._active_tracks[track_id] = {
                "bbox": bbox,
                "class_id": class_id,
                "label": label,
                "last_seen": frame_idx,
                "missing": 0,
            }

            mask = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.uint8)
            x1, y1, x2, y2 = bbox
            mask[y1:y2, x1:x2] = 1

            results.append(
                {
                    "id": track_id,
                    "mask": mask,
                    "bbox": bbox,
                    "class_id": class_id,
                    "label": label,
                }
            )

        stale_ids = [
            track_id
            for track_id, data in self._active_tracks.items()
            if data["missing"] > self.max_missing_frames
        ]
        for track_id in stale_ids:
            self._active_tracks.pop(track_id, None)

        results.sort(key=lambda item: item["id"])
        return results

    def reset(self) -> None:
        self.inference_state = None
        self._active_tracks.clear()
        self._next_track_id = 1

    def _match_existing_track(self, bbox: List[int], class_id: int, reserved: set[int]) -> int | None:
        best_id = None
        best_iou = 0.0

        for track_id, data in self._active_tracks.items():
            if track_id in reserved:
                continue
            if data["class_id"] != class_id:
                continue
            if data["missing"] > self.max_missing_frames:
                continue

            current_iou = self._iou(bbox, data["bbox"])
            if current_iou > best_iou:
                best_iou = current_iou
                best_id = track_id

        if best_iou >= self.iou_threshold:
            return best_id
        return None

    @staticmethod
    def _sanitize_bbox(raw_bbox: List[int], width: int, height: int) -> List[int]:
        x1, y1, x2, y2 = [int(v) for v in raw_bbox]
        x1 = max(0, min(width - 2, x1))
        y1 = max(0, min(height - 2, y1))
        x2 = max(x1 + 1, min(width - 1, x2))
        y2 = max(y1 + 1, min(height - 1, y2))
        return [x1, y1, x2, y2]

    @staticmethod
    def _iou(a: List[int], b: List[int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0

        inter_area = float((inter_x2 - inter_x1) * (inter_y2 - inter_y1))
        area_a = float((ax2 - ax1) * (ay2 - ay1))
        area_b = float((bx2 - bx1) * (by2 - by1))
        union = area_a + area_b - inter_area
        if union <= 0:
            return 0.0
        return inter_area / union
