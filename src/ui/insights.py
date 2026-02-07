from __future__ import annotations

from typing import Dict, Optional


def compare_summaries(current: Dict, previous: Optional[Dict]) -> Dict:
    if not current:
        return {
            "has_previous": False,
            "current": {},
            "delta": {},
        }

    current_metrics = {
        "frames_processed": int(current.get("frames_processed", 0)),
        "events_detected": int(current.get("events_detected", 0)),
        "average_processing_fps": float(current.get("average_processing_fps", 0.0)),
    }

    if not previous:
        return {
            "has_previous": False,
            "current": current_metrics,
            "delta": {},
        }

    previous_metrics = {
        "frames_processed": int(previous.get("frames_processed", 0)),
        "events_detected": int(previous.get("events_detected", 0)),
        "average_processing_fps": float(previous.get("average_processing_fps", 0.0)),
    }

    return {
        "has_previous": True,
        "current": current_metrics,
        "previous": previous_metrics,
        "delta": {
            "frames_processed": current_metrics["frames_processed"] - previous_metrics["frames_processed"],
            "events_detected": current_metrics["events_detected"] - previous_metrics["events_detected"],
            "average_processing_fps": current_metrics["average_processing_fps"] - previous_metrics["average_processing_fps"],
        },
    }


def kpi_status(delta_value: float, higher_is_better: bool = True) -> str:
    if delta_value == 0:
        return "stable"

    improved = delta_value > 0 if higher_is_better else delta_value < 0
    return "improved" if improved else "degraded"
