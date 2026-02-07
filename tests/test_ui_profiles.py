import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.profiles import add_profile, apply_profile_to_state, find_profile, get_profile_names, snapshot_config_from_control
from src.ui.contracts import FrontendControl


def _control() -> FrontendControl:
    return FrontendControl(
        preset_name="Custom",
        uploaded=None,
        execution_target="Local Engine",
        max_frames=300,
        fps=25,
        ocr_interval=10,
        cluster_interval=4,
        high_contrast=False,
        reduced_motion=False,
        mock_mode=True,
        zones=[{"name": "gate", "x1": 10, "y1": 20, "x2": 100, "y2": 200}],
        backend_base_url="http://localhost:8000",
        backend_api_key="",
        backend_poll=1.5,
        run_clicked=False,
    )


def test_snapshot_profile_from_control():
    config = snapshot_config_from_control(_control())
    assert config["max_frames"] == 300
    assert len(config["zones"]) == 1


def test_add_profile_and_lookup():
    profiles = []
    config = snapshot_config_from_control(_control())

    updated, ok, _ = add_profile(profiles, "ops", config)
    assert ok is True
    assert get_profile_names(updated) == ["ops"]

    found = find_profile(updated, "ops")
    assert found is not None
    assert found["config"]["fps"] == 25


def test_apply_profile_to_state():
    state = {
        "execution_target": "Local Engine",
        "max_frames": 100,
        "fps": 20,
        "ocr_interval": 10,
        "cluster_interval": 5,
        "mock_mode": True,
        "zones_editor": "",
        "backend_base_url": "http://localhost:8000",
        "backend_poll": 1.2,
    }
    config = {
        "execution_target": "Backend API",
        "max_frames": 360,
        "fps": 30,
        "ocr_interval": 12,
        "cluster_interval": 3,
        "mock_mode": False,
        "zones": [{"name": "safe", "x1": 1, "y1": 2, "x2": 3, "y2": 4}],
        "backend_base_url": "http://api.local",
        "backend_poll": 2.0,
    }

    apply_profile_to_state(config, state)

    assert state["execution_target"] == "Backend API"
    assert state["max_frames"] == 360
    assert state["mock_mode"] is False
    assert "safe,1,2,3,4" in state["zones_editor"]
