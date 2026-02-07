from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import numpy as np

from src.api.repository import JobRepository
from src.clustering.identifier import VisualIdentifier
from src.core.config import PipelineConfig
from src.core.exporters import JsonlExporter
from src.core.pipeline import VisionPipeline
from src.detection.detector import ObjectDetector
from src.events.analyzer import EventAnalyzer
from src.homography.transformer import PerspectiveTransformer
from src.ocr.reader import SceneTextReader
from src.segmentation.segmenter import VideoSegmenter
from src.visualization.drawer import PipelineVisualizer


class PipelineJobService:
    def __init__(self, repository: JobRepository):
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    def process_job(self, job_id: str) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            self.logger.error("Job %s not found during processing", job_id)
            return

        payload = dict(job.get("payload", {}))
        zones = list(job.get("zones", []))

        config = PipelineConfig(
            output_path=Path(job["output_video_path"]),
            export_jsonl_path=Path(job["analytics_path"]),
            max_frames=int(payload.get("max_frames", 240)),
            fps=int(payload.get("fps", 30)),
            ocr_interval=int(payload.get("ocr_interval", 30)),
            clustering_interval=int(payload.get("clustering_interval", 5)),
        )

        detector = ObjectDetector(mock_mode=bool(payload.get("mock_mode", True)))
        segmenter = VideoSegmenter()
        identifier = VisualIdentifier(mock_mode=bool(payload.get("mock_mode", True)))
        reader = SceneTextReader(mock_mode=bool(payload.get("mock_mode", True)))
        transformer = PerspectiveTransformer(
            src_points=np.array([[0, 0], [1280, 0], [1280, 720], [0, 720]], dtype=np.float32),
            dst_points=np.array([[0, 0], [100, 0], [100, 200], [0, 200]], dtype=np.float32),
        )
        analyzer = EventAnalyzer(fps=config.fps, dwell_seconds=3, zones=zones)
        visualizer = PipelineVisualizer(title="API Session")

        pipeline = VisionPipeline(
            detector=detector,
            segmenter=segmenter,
            identifier=identifier,
            reader=reader,
            transformer=transformer,
            analyzer=analyzer,
            visualizer=visualizer,
            config=config,
        )

        def _progress(done_frames: int, total_frames: int, _stats: dict) -> None:
            self.repository.update_job_progress(
                job_id=job_id,
                processed_frames=done_frames,
                max_frames=total_frames,
            )

        try:
            with JsonlExporter(config.export_jsonl_path) as exporter:
                summary = pipeline.run_video(
                    video_path=job["input_path"],
                    output_path=config.output_path,
                    max_frames=config.max_frames,
                    exporter=exporter,
                    progress_callback=_progress,
                )
            self.repository.complete_job(
                job_id=job_id,
                summary=summary,
                processed_frames=int(summary.get("frames_processed", 0)),
                max_frames=config.max_frames,
            )
        except Exception as exc:
            self.logger.exception("Failed to process job %s", job_id)
            self.repository.fail_job(job_id, str(exc))
