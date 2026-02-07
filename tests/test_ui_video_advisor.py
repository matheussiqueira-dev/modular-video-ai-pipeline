import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.video_advisor import VideoMetadata, inspect_uploaded_video, recommend_pipeline_params


def test_recommend_pipeline_params_short_video_quality_bias():
    metadata = VideoMetadata(width=1280, height=720, fps=30.0, frame_count=450, duration_seconds=15.0)

    recommendation = recommend_pipeline_params(metadata)

    assert recommendation["fps"] == 30
    assert recommendation["ocr_interval"] <= 14
    assert recommendation["profile_hint"] == "quality"


def test_recommend_pipeline_params_long_high_res_throughput_bias():
    metadata = VideoMetadata(width=3840, height=2160, fps=30.0, frame_count=7200, duration_seconds=240.0)

    recommendation = recommend_pipeline_params(metadata)

    assert recommendation["fps"] == 20
    assert recommendation["cluster_interval"] >= 8
    assert recommendation["profile_hint"] == "throughput"


def test_inspect_uploaded_video_handles_none():
    assert inspect_uploaded_video(None) is None
