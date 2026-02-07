import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.analytics import filter_events, load_analytics_jsonl, summarize_events, summarize_frames


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_load_analytics_jsonl_reads_frames_and_events(tmp_path):
    rows = [
        {
            "record_type": "frame",
            "type": "frame",
            "frame": 0,
            "stats": {"processing_fps": 9.5, "active_tracks": 2, "events_in_frame": 0},
        },
        {
            "record_type": "event",
            "type": "ZONE_ENTRY",
            "frame": 4,
            "object_id": 1,
            "severity": "info",
            "details": "Object 1 entered zone",
        },
    ]
    path = tmp_path / "analytics.jsonl"
    _write_jsonl(path, rows)

    frames_df, events_df = load_analytics_jsonl(path)

    assert len(frames_df) == 1
    assert len(events_df) == 1
    assert events_df.iloc[0]["type"] == "ZONE_ENTRY"


def test_summarize_helpers_return_expected_values():
    frames_df = pd.DataFrame(
        [
            {"frame": 0, "processing_fps": 8.0, "active_tracks": 2, "events_in_frame": 1},
            {"frame": 1, "processing_fps": 12.0, "active_tracks": 3, "events_in_frame": 0},
        ]
    )
    events_df = pd.DataFrame(
        [
            {"frame": 1, "type": "ZONE_ENTRY", "object_id": 1, "severity": "info", "details": "in"},
            {"frame": 2, "type": "STATIONARY_WARNING", "object_id": 2, "severity": "warning", "details": "still"},
        ]
    )

    frame_summary = summarize_frames(frames_df)
    event_summary = summarize_events(events_df)

    assert frame_summary["avg_fps"] == 10.0
    assert frame_summary["peak_tracks"] == 3
    assert event_summary["total"] == 2
    assert event_summary["warning"] == 1


def test_filter_events_applies_combined_filters():
    events_df = pd.DataFrame(
        [
            {"frame": 1, "type": "ZONE_ENTRY", "object_id": 1, "severity": "info", "details": "entered gate"},
            {"frame": 2, "type": "ZONE_EXIT", "object_id": 1, "severity": "info", "details": "left gate"},
            {"frame": 3, "type": "STATIONARY_WARNING", "object_id": 2, "severity": "warning", "details": "stationary"},
        ]
    )

    filtered = filter_events(
        events_df,
        selected_types=["STATIONARY_WARNING"],
        selected_severities=["warning"],
        object_id_query="2",
        text_query="stationary",
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["object_id"] == 2
