from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd


def _frames_events_from_lines(lines: Iterable[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    frame_rows: List[dict] = []
    event_rows: List[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        row_type = row.get("record_type", row.get("type"))
        if row_type == "frame":
            stats = row.get("stats", {})
            frame_rows.append(
                {
                    "frame": int(row.get("frame", 0)),
                    "processing_fps": float(stats.get("processing_fps", 0.0)),
                    "active_tracks": int(stats.get("active_tracks", 0)),
                    "events_in_frame": int(stats.get("events_in_frame", 0)),
                }
            )
        elif row_type == "event":
            event_type = str(row.get("type", "EVENT"))
            event_rows.append(
                {
                    "frame": int(row.get("frame", 0)),
                    "type": event_type,
                    "object_id": int(row.get("object_id", -1)),
                    "severity": str(row.get("severity", "info")),
                    "details": str(row.get("details", "")),
                }
            )

    frames_df = pd.DataFrame(frame_rows)
    events_df = pd.DataFrame(event_rows)

    if not frames_df.empty:
        frames_df = frames_df.sort_values("frame").reset_index(drop=True)

    if not events_df.empty:
        events_df = events_df.sort_values("frame").reset_index(drop=True)

    return frames_df, events_df


def load_analytics_jsonl(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not path.exists():
        return pd.DataFrame(), pd.DataFrame()

    with path.open("r", encoding="utf-8") as handle:
        return _frames_events_from_lines(handle)


def load_analytics_jsonl_bytes(content: bytes) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not content:
        return pd.DataFrame(), pd.DataFrame()
    text = content.decode("utf-8", errors="ignore")
    return _frames_events_from_lines(text.splitlines())


def summarize_frames(frames_df: pd.DataFrame) -> Dict[str, float]:
    if frames_df.empty:
        return {
            "avg_fps": 0.0,
            "peak_tracks": 0,
            "peak_events": 0,
            "frames": 0,
        }

    return {
        "avg_fps": float(frames_df["processing_fps"].mean()),
        "peak_tracks": int(frames_df["active_tracks"].max()),
        "peak_events": int(frames_df["events_in_frame"].max()),
        "frames": int(frames_df["frame"].nunique()),
    }


def summarize_events(events_df: pd.DataFrame) -> Dict[str, int]:
    if events_df.empty:
        return {"total": 0, "warning": 0, "critical": 0, "info": 0}

    severities = events_df["severity"].value_counts().to_dict()
    return {
        "total": int(len(events_df)),
        "warning": int(severities.get("warning", 0)),
        "critical": int(severities.get("critical", 0)),
        "info": int(severities.get("info", 0)),
    }


def filter_events(
    events_df: pd.DataFrame,
    selected_types: List[str],
    selected_severities: List[str],
    object_id_query: str,
    text_query: str,
) -> pd.DataFrame:
    if events_df.empty:
        return events_df

    filtered = events_df.copy()

    if selected_types:
        filtered = filtered[filtered["type"].isin(selected_types)]

    if selected_severities:
        filtered = filtered[filtered["severity"].isin(selected_severities)]

    object_id_query = object_id_query.strip()
    if object_id_query:
        ids = []
        for token in object_id_query.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                ids.append(int(token))
            except ValueError:
                continue
        if ids:
            filtered = filtered[filtered["object_id"].isin(ids)]

    text_query = text_query.strip().lower()
    if text_query:
        filtered = filtered[filtered["details"].str.lower().str.contains(text_query, na=False)]

    return filtered.reset_index(drop=True)
