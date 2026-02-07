from __future__ import annotations

from typing import Dict, List, Tuple


def snapshot_config_from_control(control) -> dict:
    return {
        "execution_target": control.execution_target,
        "max_frames": int(control.max_frames),
        "fps": int(control.fps),
        "ocr_interval": int(control.ocr_interval),
        "cluster_interval": int(control.cluster_interval),
        "mock_mode": bool(control.mock_mode),
        "zones": list(control.zones),
        "backend_base_url": str(control.backend_base_url),
        "backend_poll": float(control.backend_poll),
    }


def add_profile(profiles: List[dict], name: str, config_snapshot: dict, max_items: int = 15) -> Tuple[List[dict], bool, str]:
    cleaned = name.strip()
    if not cleaned:
        return profiles, False, "Nome do perfil vazio"

    updated = [p for p in profiles if p.get("name") != cleaned]
    updated.insert(0, {"name": cleaned, "config": config_snapshot})
    return updated[:max_items], True, "Perfil salvo"


def get_profile_names(profiles: List[dict]) -> List[str]:
    return [p.get("name", "") for p in profiles if p.get("name")]


def find_profile(profiles: List[dict], name: str) -> dict | None:
    for profile in profiles:
        if profile.get("name") == name:
            return profile
    return None


def apply_profile_to_state(config: Dict, state: Dict) -> None:
    state["execution_target"] = config.get("execution_target", state.get("execution_target", "Local Engine"))
    state["max_frames"] = int(config.get("max_frames", state.get("max_frames", 240)))
    state["fps"] = int(config.get("fps", state.get("fps", 30)))
    state["ocr_interval"] = int(config.get("ocr_interval", state.get("ocr_interval", 30)))
    state["cluster_interval"] = int(config.get("cluster_interval", state.get("cluster_interval", 5)))
    state["mock_mode"] = bool(config.get("mock_mode", state.get("mock_mode", True)))
    state["zones_editor"] = _zones_to_text(config.get("zones", []))
    state["backend_base_url"] = str(config.get("backend_base_url", state.get("backend_base_url", "http://localhost:8000")))
    state["backend_poll"] = float(config.get("backend_poll", state.get("backend_poll", 1.2)))


def _zones_to_text(zones: List[dict]) -> str:
    rows = []
    for zone in zones:
        rows.append(f"{zone['name']},{zone['x1']},{zone['y1']},{zone['x2']},{zone['y2']}")
    return "\n".join(rows)
