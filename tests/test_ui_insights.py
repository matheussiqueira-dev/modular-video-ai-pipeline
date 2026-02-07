import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.insights import compare_summaries, kpi_status


def test_compare_summaries_without_previous():
    current = {"frames_processed": 100, "events_detected": 10, "average_processing_fps": 12.5}

    result = compare_summaries(current, None)

    assert result["has_previous"] is False
    assert result["current"]["frames_processed"] == 100


def test_compare_summaries_with_previous_returns_deltas():
    current = {"frames_processed": 140, "events_detected": 12, "average_processing_fps": 15.0}
    previous = {"frames_processed": 100, "events_detected": 10, "average_processing_fps": 13.0}

    result = compare_summaries(current, previous)

    assert result["has_previous"] is True
    assert result["delta"]["frames_processed"] == 40
    assert result["delta"]["events_detected"] == 2
    assert result["delta"]["average_processing_fps"] == 2.0


def test_kpi_status():
    assert kpi_status(0.0) == "stable"
    assert kpi_status(2.0, higher_is_better=True) == "improved"
    assert kpi_status(-2.0, higher_is_better=True) == "degraded"
    assert kpi_status(-1.0, higher_is_better=False) == "improved"
