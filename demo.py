from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

import numpy as np

# Ensure src is importable when running directly.
sys.path.append(str(Path(__file__).resolve().parent))

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


def setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_zone_args(raw_zones: List[str]) -> List[dict]:
    zones: List[dict] = []
    for raw in raw_zones:
        # Format: name:x1,y1,x2,y2
        try:
            name, coords = raw.split(":", maxsplit=1)
            x1, y1, x2, y2 = [int(v.strip()) for v in coords.split(",")]
            zones.append({"name": name.strip(), "x1": x1, "y1": y1, "x2": x2, "y2": y2})
        except ValueError:
            logging.getLogger(__name__).warning(
                "Ignoring invalid --zone value '%s'. Expected format name:x1,y1,x2,y2", raw
            )
    return zones


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Modular AI Vision Pipeline")
    parser.add_argument("--video_path", type=str, default=None, help="Path to input video")
    parser.add_argument("--output_path", type=str, default="output.mp4", help="Path to save output video")
    parser.add_argument("--max_frames", type=int, default=180, help="Maximum number of frames to process")
    parser.add_argument("--fps", type=int, default=30, help="Output FPS")
    parser.add_argument("--ocr_interval", type=int, default=30, help="OCR refresh interval in frames")
    parser.add_argument("--cluster_interval", type=int, default=5, help="Clustering refresh interval in frames")
    parser.add_argument("--export_jsonl", type=str, default=None, help="Optional path to export analytics JSONL")
    parser.add_argument(
        "--zone",
        action="append",
        default=[],
        help="Monitoring zone in format name:x1,y1,x2,y2 (can be used multiple times)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Keep components in mock mode (default True)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable verbose logs")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    setup_logging(args.debug)
    logger = logging.getLogger("DemoPipeline")

    zones = parse_zone_args(args.zone)

    logger.info("Initializing modules...")
    detector = ObjectDetector(mock_mode=args.mock)
    segmenter = VideoSegmenter()
    identifier = VisualIdentifier(mock_mode=args.mock)
    reader = SceneTextReader(mock_mode=args.mock)
    transformer = PerspectiveTransformer(
        src_points=np.array([[0, 0], [1280, 0], [1280, 720], [0, 720]], dtype=np.float32),
        dst_points=np.array([[0, 0], [100, 0], [100, 200], [0, 200]], dtype=np.float32),
    )
    analyzer = EventAnalyzer(fps=args.fps, dwell_seconds=3, zones=zones)
    visualizer = PipelineVisualizer()

    config = PipelineConfig(
        output_path=Path(args.output_path),
        export_jsonl_path=Path(args.export_jsonl) if args.export_jsonl else None,
        max_frames=max(1, args.max_frames),
        fps=max(1, args.fps),
        ocr_interval=max(1, args.ocr_interval),
        clustering_interval=max(1, args.cluster_interval),
    )

    pipeline = VisionPipeline(
        detector=detector,
        segmenter=segmenter,
        identifier=identifier,
        reader=reader,
        transformer=transformer,
        analyzer=analyzer,
        visualizer=visualizer,
        config=config,
        logger=logger,
    )

    logger.info("Running pipeline...")
    with JsonlExporter(config.export_jsonl_path) as exporter:
        summary = pipeline.run_video(
            video_path=args.video_path,
            output_path=config.output_path,
            max_frames=config.max_frames,
            exporter=exporter,
        )

    logger.info("Pipeline completed")
    logger.info(
        "Summary | frames=%s events=%s avg_fps=%.2f output=%s",
        int(summary["frames_processed"]),
        int(summary["events_detected"]),
        float(summary["average_processing_fps"]),
        str(config.output_path),
    )


if __name__ == "__main__":
    main()
