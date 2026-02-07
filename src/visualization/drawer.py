from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np


class PipelineVisualizer:
    """
    Draws a modern HUD over frames with clear hierarchy and readable contrast.
    """

    PALETTE = [
        (18, 139, 255),
        (52, 211, 153),
        (245, 158, 11),
        (239, 68, 68),
        (99, 102, 241),
        (14, 165, 233),
    ]

    def __init__(self, title: str = "Modular Vision Pipeline"):
        self.title = title
        self._zones: List[dict] = []

    def set_zones(self, zones: List[dict]) -> None:
        self._zones = zones or []

    def draw(
        self,
        frame: np.ndarray,
        tracks: List[dict],
        events: List[dict],
        stats: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        canvas = frame.copy()
        self._draw_background_panels(canvas)
        self._draw_zones(canvas)
        self._draw_tracks(canvas, tracks)
        self._draw_header(canvas, stats or {}, len(tracks), len(events))
        self._draw_object_panel(canvas, tracks)
        self._draw_event_feed(canvas, events)
        return canvas

    def _draw_background_panels(self, canvas: np.ndarray) -> None:
        overlay = canvas.copy()
        h, w = canvas.shape[:2]

        cv2.rectangle(overlay, (0, 0), (w, 70), (8, 19, 34), -1)
        cv2.rectangle(overlay, (w - 280, 70), (w, h), (10, 25, 44), -1)
        cv2.rectangle(overlay, (0, h - 110), (w - 280, h), (12, 30, 50), -1)

        cv2.addWeighted(overlay, 0.68, canvas, 0.32, 0, canvas)

    def _draw_header(self, canvas: np.ndarray, stats: Dict[str, float], track_count: int, event_count: int) -> None:
        cv2.putText(canvas, self.title, (16, 28), cv2.FONT_HERSHEY_DUPLEX, 0.75, (242, 248, 255), 2)

        frame_idx = int(stats.get("frame_idx", 0))
        fps = float(stats.get("processing_fps", 0.0))
        metrics_text = f"Frame {frame_idx:05d}   FPS {fps:05.1f}   Tracks {track_count:02d}   Events {event_count:02d}"
        cv2.putText(canvas, metrics_text, (16, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (174, 209, 255), 2)

    def _draw_tracks(self, canvas: np.ndarray, tracks: List[dict]) -> None:
        for track in tracks:
            x1, y1, x2, y2 = [int(v) for v in track["bbox"]]
            cluster = int(track.get("cluster_id", track["id"]))
            color = self.PALETTE[cluster % len(self.PALETTE)]

            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

            label_parts = [f"#{track['id']}", track.get("label", "object")]
            if track.get("cluster_id") is not None:
                label_parts.append(f"G{track['cluster_id']}")
            if track.get("ocr_text"):
                label_parts.append(track["ocr_text"])
            label = " | ".join(label_parts)

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_y = max(th + 6, y1 - 8)
            cv2.rectangle(canvas, (x1, label_y - th - 6), (x1 + tw + 8, label_y + 4), color, -1)
            cv2.putText(canvas, label, (x1 + 4, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (12, 15, 20), 1)

            mask = track.get("mask")
            if mask is not None and isinstance(mask, np.ndarray) and mask.size > 0:
                self._blend_mask(canvas, mask, color)

    def _draw_zones(self, canvas: np.ndarray) -> None:
        for zone in self._zones:
            x1 = int(zone["x1"])
            y1 = int(zone["y1"])
            x2 = int(zone["x2"])
            y2 = int(zone["y2"])
            name = str(zone["name"])
            color = (255, 180, 0)

            overlay = canvas.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.addWeighted(overlay, 0.08, canvas, 0.92, 0, canvas)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(canvas, name, (x1 + 6, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    def _draw_object_panel(self, canvas: np.ndarray, tracks: List[dict]) -> None:
        h, w = canvas.shape[:2]
        panel_x = w - 270

        cv2.putText(canvas, "Objects", (panel_x + 12, 100), cv2.FONT_HERSHEY_DUPLEX, 0.7, (235, 245, 255), 2)

        y = 128
        max_items = max(3, min(14, (h - 170) // 36))
        for track in tracks[:max_items]:
            cluster = int(track.get("cluster_id", track["id"]))
            color = self.PALETTE[cluster % len(self.PALETTE)]
            cv2.circle(canvas, (panel_x + 16, y - 4), 6, color, -1)

            line = f"#{track['id']} {track.get('label', 'object')}"
            cv2.putText(canvas, line, (panel_x + 30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 233, 248), 1)

            if track.get("ocr_text"):
                cv2.putText(
                    canvas,
                    f"OCR {track['ocr_text']}",
                    (panel_x + 30, y + 16),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (147, 197, 253),
                    1,
                )
            y += 34

    def _draw_event_feed(self, canvas: np.ndarray, events: List[dict]) -> None:
        h, _ = canvas.shape[:2]
        cv2.putText(canvas, "Event Feed", (16, h - 80), cv2.FONT_HERSHEY_DUPLEX, 0.65, (236, 246, 255), 2)

        y = h - 54
        for event in events[-3:]:
            severity = event.get("severity", "info")
            color = (100, 210, 255)
            if severity == "warning":
                color = (80, 190, 255)
            elif severity == "critical":
                color = (70, 70, 255)

            text = f"[{event.get('type', 'EVENT')}] {event.get('details', '')}"
            cv2.putText(canvas, text[:95], (16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y += 24

    @staticmethod
    def _blend_mask(canvas: np.ndarray, mask: np.ndarray, color: tuple) -> None:
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)

        if mask.shape != canvas.shape[:2]:
            return

        colored = np.zeros_like(canvas, dtype=np.uint8)
        colored[:, :] = color
        alpha = (mask > 0).astype(np.uint8) * 38

        for c in range(3):
            canvas[:, :, c] = np.where(
                alpha > 0,
                ((canvas[:, :, c].astype(np.uint16) * (255 - alpha) + colored[:, :, c].astype(np.uint16) * alpha) // 255).astype(np.uint8),
                canvas[:, :, c],
            )
