import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.events.analyzer import EventAnalyzer


def test_stationary_warning_event_is_emitted():
    analyzer = EventAnalyzer(fps=10, dwell_seconds=1, stationary_distance_px=3.0, event_cooldown_frames=100)

    events = []
    for frame_idx in range(15):
        tracks = [{"id": 1, "bbox": [100, 100, 140, 180]}]
        events.extend(analyzer.update(tracks, frame_idx))

    assert any(event["type"] == "STATIONARY_WARNING" for event in events)


def test_zone_entry_and_exit_events_are_emitted():
    zones = [{"name": "gate", "x1": 10, "y1": 10, "x2": 60, "y2": 60}]
    analyzer = EventAnalyzer(
        fps=30,
        dwell_seconds=5,
        zone_entry_threshold=2,
        event_cooldown_frames=1,
        zones=zones,
    )

    entry_events = []
    exit_events = []

    for frame_idx in range(6):
        if frame_idx < 3:
            bbox = [20, 20, 40, 40]  # inside zone
        else:
            bbox = [100, 100, 130, 130]  # outside zone

        frame_events = analyzer.update([{"id": 2, "bbox": bbox}], frame_idx)
        entry_events.extend([e for e in frame_events if e["type"] == "ZONE_ENTRY"])
        exit_events.extend([e for e in frame_events if e["type"] == "ZONE_EXIT"])

    assert len(entry_events) >= 1
    assert len(exit_events) >= 1
