from __future__ import annotations

from typing import List

from fastapi import HTTPException, status

from src.api.schemas import JobCreatePayload, ZoneIn
from src.api.security import safe_json_load


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_zones(zones_json: str) -> List[dict]:
    zones = safe_json_load(zones_json, [])
    if not isinstance(zones, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="zones_json must be a JSON array")

    validated: List[dict] = []
    for zone in zones:
        model = ZoneIn.model_validate(zone)
        validated.append(model.model_dump())
    return validated


def build_job_payload(
    *,
    max_frames: int,
    fps: int,
    ocr_interval: int,
    clustering_interval: int,
    mock_mode: str | bool,
    async_mode: str | bool,
    zones_json: str,
) -> tuple[JobCreatePayload, List[dict]]:
    zones = parse_zones(zones_json)
    model = JobCreatePayload(
        max_frames=max_frames,
        fps=fps,
        ocr_interval=ocr_interval,
        clustering_interval=clustering_interval,
        mock_mode=parse_bool(mock_mode),
        async_mode=parse_bool(async_mode),
        zones=[ZoneIn.model_validate(zone) for zone in zones],
    )
    return model, zones
