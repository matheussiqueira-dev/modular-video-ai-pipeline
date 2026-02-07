from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from src.core.config import PipelineConfig
from src.core.exporters import JsonlExporter


class VisionPipeline:
    """Coordinates all pipeline stages and owns frame-level orchestration."""

    def __init__(
        self,
        detector,
        segmenter,
        identifier,
        reader,
        transformer,
        analyzer,
        visualizer,
        config: Optional[PipelineConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.detector = detector
        self.segmenter = segmenter
        self.identifier = identifier
        self.reader = reader
        self.transformer = transformer
        self.analyzer = analyzer
        self.visualizer = visualizer
        self.config = config or PipelineConfig()

        self._cluster_cache: Dict[int, int] = {}
        self._ocr_cache: Dict[int, str] = {}
        self._frame_times: List[float] = []

        if hasattr(self.visualizer, "set_zones"):
            zone_payload = [
                {
                    "name": z.name,
                    "x1": z.x1,
                    "y1": z.y1,
                    "x2": z.x2,
                    "y2": z.y2,
                }
                for z in getattr(self.analyzer, "zones", [])
            ]
            self.visualizer.set_zones(zone_payload)

    def process_frame(self, frame: np.ndarray, frame_idx: int) -> Tuple[np.ndarray, List[dict], List[dict], Dict[str, float]]:
        tic = time.perf_counter()

        try:
            detections = self.detector.detect(frame, frame_idx=frame_idx)
        except TypeError:
            detections = self.detector.detect(frame)

        tracks = self.segmenter.track_objects(frame_idx, frame, detections)
        self._attach_world_positions(tracks)

        if frame_idx % max(1, self.config.clustering_interval) == 0:
            self._refresh_clusters(frame, tracks)
        for track in tracks:
            track["cluster_id"] = self._cluster_cache.get(track["id"], 0)

        if frame_idx % max(1, self.config.ocr_interval) == 0:
            self._refresh_ocr(frame, tracks)
        for track in tracks:
            track["ocr_text"] = self._ocr_cache.get(track["id"], "")

        events = self.analyzer.update(tracks, frame_idx)

        frame_time = max(1e-6, time.perf_counter() - tic)
        self._frame_times.append(frame_time)
        if len(self._frame_times) > 120:
            self._frame_times.pop(0)

        stats = {
            "frame_idx": frame_idx,
            "processing_fps": 1.0 / float(np.mean(self._frame_times)),
            "active_tracks": len(tracks),
            "events_in_frame": len(events),
        }

        annotated = self.visualizer.draw(frame, tracks, events, stats=stats)
        return annotated, tracks, events, stats

    def run_video(
        self,
        video_path: Optional[str],
        output_path: Path,
        max_frames: int,
        exporter: Optional[JsonlExporter] = None,
        progress_callback: Optional[Callable[[int, int, Dict[str, float]], None]] = None,
        stop_callback: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, float]:
        cap = None
        if video_path and Path(video_path).exists():
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                cap = None

        if cap is None:
            self.logger.warning("Video path not provided/found. Running with synthetic frames.")

        writer = None
        frame_idx = 0
        total_events = 0
        stopped_early = False

        try:
            while frame_idx < max_frames:
                if stop_callback is not None and stop_callback():
                    stopped_early = True
                    break

                if cap is not None:
                    ok, frame = cap.read()
                    if not ok:
                        break
                else:
                    frame = self._synthetic_frame(frame_idx)

                if writer is None:
                    h, w = frame.shape[:2]
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    writer = cv2.VideoWriter(
                        str(output_path),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        self.config.fps,
                        (w, h),
                    )

                out_frame, tracks, events, stats = self.process_frame(frame, frame_idx)
                total_events += len(events)

                if writer is not None:
                    writer.write(out_frame)

                if exporter is not None:
                    exporter.write(
                        "frame",
                        {
                            "frame": frame_idx,
                            "stats": stats,
                            "tracks": [
                                {
                                    "id": int(t["id"]),
                                    "label": t.get("label", "object"),
                                    "bbox": [int(v) for v in t["bbox"]],
                                    "cluster_id": int(t.get("cluster_id", 0)),
                                    "ocr_text": t.get("ocr_text", ""),
                                    "world_position": list(t.get("world_position") or []),
                                }
                                for t in tracks
                            ],
                        },
                    )
                    for event in events:
                        exporter.write("event", event)

                if progress_callback is not None:
                    progress_callback(frame_idx + 1, max_frames, stats)

                frame_idx += 1

        finally:
            if cap is not None:
                cap.release()
            if writer is not None:
                writer.release()

        avg_fps = 1.0 / float(np.mean(self._frame_times)) if self._frame_times else 0.0
        return {
            "frames_processed": frame_idx,
            "events_detected": total_events,
            "average_processing_fps": avg_fps,
            "stopped_early": stopped_early,
        }

    def _attach_world_positions(self, tracks: List[dict]) -> None:
        for track in tracks:
            x1, y1, x2, y2 = [int(v) for v in track["bbox"]]
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            track["world_position"] = self.transformer.transform_point(center)

    def _refresh_clusters(self, frame: np.ndarray, tracks: List[dict]) -> None:
        crops, track_ids = self._extract_crops(frame, tracks)
        if not crops:
            return

        embeddings = self.identifier.extract_embeddings(crops)
        n_clusters = min(3, max(1, len(crops)))
        labels = self.identifier.cluster_embeddings(embeddings, n_clusters=n_clusters)
        for idx, track_id in enumerate(track_ids):
            if idx < len(labels):
                self._cluster_cache[track_id] = int(labels[idx])

    def _refresh_ocr(self, frame: np.ndarray, tracks: List[dict]) -> None:
        for track in tracks:
            crop = self._crop_track(frame, track["bbox"])
            if crop is None:
                continue
            text = self.reader.read_text(crop, track_id=track["id"])
            if text:
                self._ocr_cache[track["id"]] = text

    def _extract_crops(self, frame: np.ndarray, tracks: List[dict]) -> Tuple[List[np.ndarray], List[int]]:
        crops: List[np.ndarray] = []
        ids: List[int] = []

        for track in tracks:
            crop = self._crop_track(frame, track["bbox"])
            if crop is None:
                continue
            crops.append(crop)
            ids.append(int(track["id"]))

        return crops, ids

    @staticmethod
    def _crop_track(frame: np.ndarray, bbox: List[int]) -> np.ndarray | None:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(x1 + 1, min(w, x2))
        y2 = max(y1 + 1, min(h, y2))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return crop

    @staticmethod
    def _synthetic_frame(frame_idx: int, height: int = 720, width: int = 1280) -> np.ndarray:
        base = np.zeros((height, width, 3), dtype=np.uint8)
        gradient = np.linspace(10, 45, width, dtype=np.uint8)
        base[:, :, 0] = gradient
        base[:, :, 1] = gradient[::-1]
        base[:, :, 2] = 28

        rng = np.random.default_rng(seed=frame_idx)
        noise = rng.integers(0, 22, size=(height, width, 3), dtype=np.uint8)
        return cv2.add(base, noise)
