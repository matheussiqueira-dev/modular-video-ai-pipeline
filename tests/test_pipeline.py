import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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


def _build_pipeline(tmp_path):
    config = PipelineConfig(
        output_path=tmp_path / "test_output.mp4",
        export_jsonl_path=tmp_path / "test_analytics.jsonl",
        max_frames=5,
        fps=24,
        ocr_interval=2,
        clustering_interval=1,
    )

    detector = ObjectDetector(mock_mode=True)
    segmenter = VideoSegmenter()
    identifier = VisualIdentifier(mock_mode=True)
    reader = SceneTextReader(mock_mode=True)
    transformer = PerspectiveTransformer(
        src_points=np.array([[0, 0], [1280, 0], [1280, 720], [0, 720]], dtype=np.float32),
        dst_points=np.array([[0, 0], [100, 0], [100, 200], [0, 200]], dtype=np.float32),
    )
    analyzer = EventAnalyzer(fps=24, dwell_seconds=1)
    visualizer = PipelineVisualizer()

    return VisionPipeline(
        detector=detector,
        segmenter=segmenter,
        identifier=identifier,
        reader=reader,
        transformer=transformer,
        analyzer=analyzer,
        visualizer=visualizer,
        config=config,
    ), config


def test_process_frame_outputs_visual_and_stats(tmp_path):
    pipeline, _ = _build_pipeline(tmp_path)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    out_frame, tracks, events, stats = pipeline.process_frame(frame, frame_idx=0)

    assert out_frame.shape == frame.shape
    assert isinstance(tracks, list)
    assert isinstance(events, list)
    assert "processing_fps" in stats


def test_run_video_generates_output_and_summary(tmp_path):
    pipeline, config = _build_pipeline(tmp_path)
    callback_calls = []

    def _on_progress(done_frames, total_frames, stats):
        callback_calls.append((done_frames, total_frames, stats))

    with JsonlExporter(config.export_jsonl_path) as exporter:
        summary = pipeline.run_video(
            video_path=None,
            output_path=config.output_path,
            max_frames=config.max_frames,
            exporter=exporter,
            progress_callback=_on_progress,
        )

    assert config.output_path.exists()
    assert config.export_jsonl_path.exists()
    assert int(summary["frames_processed"]) == config.max_frames
    assert summary["average_processing_fps"] > 0
    assert len(callback_calls) == config.max_frames
    assert callback_calls[-1][0] == config.max_frames
