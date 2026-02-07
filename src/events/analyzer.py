from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Tuple

import numpy as np


@dataclass(slots=True)
class Zone:
    name: str
    x1: int
    y1: int
    x2: int
    y2: int

    def contains(self, point: Tuple[int, int]) -> bool:
        x, y = point
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


class EventAnalyzer:
    """
    Detects temporal events from tracked objects.
    Supported events:
    - STATIONARY_WARNING: object remains almost still for a configured duration
    - ZONE_ENTRY / ZONE_EXIT: object enters/leaves configured zones
    """

    def __init__(
        self,
        fps: int = 30,
        dwell_seconds: int = 3,
        stationary_distance_px: float = 40.0,
        event_cooldown_frames: int = 60,
        zone_entry_threshold: int = 5,
        zones: List[dict] | None = None,
        history_limit: int = 600,
    ):
        self.logger = logging.getLogger(__name__)
        self.fps = max(1, int(fps))
        self.min_dwell_frames = max(1, int(dwell_seconds * self.fps))
        self.stationary_distance_px = float(stationary_distance_px)
        self.event_cooldown_frames = max(1, int(event_cooldown_frames))
        self.zone_entry_threshold = max(1, int(zone_entry_threshold))
        self.history_limit = max(self.min_dwell_frames + 10, int(history_limit))

        self.track_history: Dict[int, Deque[Tuple[int, int, int]]] = defaultdict(
            lambda: deque(maxlen=self.history_limit)
        )
        self.event_log: List[dict] = []
        self._last_event_frame: Dict[tuple, int] = {}

        self.zones: List[Zone] = []
        if zones:
            for raw in zones:
                self.zones.append(
                    Zone(
                        name=str(raw["name"]),
                        x1=int(raw["x1"]),
                        y1=int(raw["y1"]),
                        x2=int(raw["x2"]),
                        y2=int(raw["y2"]),
                    )
                )

        self._zone_frames: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._zone_active: Dict[int, Dict[str, bool]] = defaultdict(lambda: defaultdict(bool))

    def update(self, tracks: List[dict], frame_idx: int) -> List[dict]:
        current_events: List[dict] = []
        current_ids = set()

        for track in tracks:
            obj_id = int(track["id"])
            current_ids.add(obj_id)

            point = self._resolve_point(track)
            self.track_history[obj_id].append((point[0], point[1], frame_idx))

            dwell_event = self._check_dwell_event(obj_id, frame_idx)
            if dwell_event is not None:
                current_events.append(dwell_event)

            current_events.extend(self._check_zone_events(obj_id, point, frame_idx))

        stale_ids = [obj_id for obj_id in self.track_history if obj_id not in current_ids]
        for obj_id in stale_ids:
            self._zone_frames.pop(obj_id, None)
            self._zone_active.pop(obj_id, None)

        self.event_log.extend(current_events)
        return current_events

    def _resolve_point(self, track: dict) -> Tuple[int, int]:
        world_pos = track.get("world_position")
        if world_pos is not None:
            return int(world_pos[0]), int(world_pos[1])

        x1, y1, x2, y2 = [int(v) for v in track["bbox"]]
        return (x1 + x2) // 2, (y1 + y2) // 2

    def _check_dwell_event(self, obj_id: int, frame_idx: int) -> dict | None:
        history = self.track_history[obj_id]
        if len(history) < self.min_dwell_frames:
            return None

        recent = list(history)[-self.min_dwell_frames :]
        start = np.array(recent[0][:2], dtype=np.float32)
        end = np.array(recent[-1][:2], dtype=np.float32)
        distance = float(np.linalg.norm(end - start))

        if distance > self.stationary_distance_px:
            return None

        event_key = (obj_id, "STATIONARY_WARNING")
        if not self._can_emit(event_key, frame_idx):
            return None

        return self._emit_event(
            frame=frame_idx,
            event_type="STATIONARY_WARNING",
            object_id=obj_id,
            details=f"Object {obj_id} stationary for ~{self.min_dwell_frames / self.fps:.1f}s",
            severity="warning",
            event_key=event_key,
        )

    def _check_zone_events(self, obj_id: int, point: Tuple[int, int], frame_idx: int) -> List[dict]:
        if not self.zones:
            return []

        events: List[dict] = []
        for zone in self.zones:
            in_zone = zone.contains(point)
            was_active = self._zone_active[obj_id][zone.name]

            if in_zone:
                self._zone_frames[obj_id][zone.name] += 1
                if not was_active and self._zone_frames[obj_id][zone.name] >= self.zone_entry_threshold:
                    event_key = (obj_id, "ZONE_ENTRY", zone.name)
                    if self._can_emit(event_key, frame_idx):
                        events.append(
                            self._emit_event(
                                frame=frame_idx,
                                event_type="ZONE_ENTRY",
                                object_id=obj_id,
                                details=f"Object {obj_id} entered zone '{zone.name}'",
                                severity="info",
                                event_key=event_key,
                            )
                        )
                    self._zone_active[obj_id][zone.name] = True
            else:
                self._zone_frames[obj_id][zone.name] = 0
                if was_active:
                    event_key = (obj_id, "ZONE_EXIT", zone.name)
                    if self._can_emit(event_key, frame_idx):
                        events.append(
                            self._emit_event(
                                frame=frame_idx,
                                event_type="ZONE_EXIT",
                                object_id=obj_id,
                                details=f"Object {obj_id} left zone '{zone.name}'",
                                severity="info",
                                event_key=event_key,
                            )
                        )
                    self._zone_active[obj_id][zone.name] = False

        return events

    def _emit_event(
        self,
        frame: int,
        event_type: str,
        object_id: int,
        details: str,
        severity: str,
        event_key: tuple,
    ) -> dict:
        self._last_event_frame[event_key] = frame
        return {
            "frame": int(frame),
            "type": event_type,
            "object_id": int(object_id),
            "details": details,
            "severity": severity,
        }

    def _can_emit(self, event_key: tuple, frame_idx: int) -> bool:
        last = self._last_event_frame.get(event_key)
        if last is None:
            return True
        return (frame_idx - last) >= self.event_cooldown_frames
