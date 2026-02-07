from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st


def init_session_state() -> None:
    defaults = {
        "run_result": None,
        "run_history": [],
        "zones_editor": "area_restrita,80,120,390,520\nentrada,900,120,1240,540",
        "selected_preset": "Custom",
        "max_frames": 240,
        "fps": 30,
        "ocr_interval": 30,
        "cluster_interval": 5,
        "high_contrast": False,
        "reduced_motion": False,
        "mock_mode": True,
        "execution_target": "Local Engine",
        "backend_base_url": "http://localhost:8000",
        "backend_api_key": "",
        "backend_poll": 1.2,
        "config_profiles": [],
        "profile_name_input": "",
        "selected_profile_name": "",
        "video_advisor_cache": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def save_run_result(payload: Dict) -> None:
    st.session_state["run_result"] = payload

    history: List[Dict] = list(st.session_state.get("run_history", []))
    history.insert(
        0,
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "preset": payload.get("preset", "Custom"),
            "frames": int(payload.get("summary", {}).get("frames_processed", 0)),
            "events": int(payload.get("summary", {}).get("events_detected", 0)),
            "avg_fps": round(float(payload.get("summary", {}).get("average_processing_fps", 0.0)), 2),
            "summary": dict(payload.get("summary", {})),
            "execution_target": payload.get("execution_target", "Local Engine"),
        },
    )
    st.session_state["run_history"] = history[:10]


def get_run_result() -> Dict | None:
    return st.session_state.get("run_result")


def get_run_history() -> List[Dict]:
    return list(st.session_state.get("run_history", []))


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    if df.empty:
        return b""
    return df.to_csv(index=False).encode("utf-8")
