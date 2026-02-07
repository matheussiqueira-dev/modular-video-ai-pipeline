from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Optional

import cv2


@dataclass(slots=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    frame_count: int
    duration_seconds: float


def inspect_uploaded_video(uploaded_file) -> Optional[VideoMetadata]:
    if uploaded_file is None:
        return None

    suffix = Path(uploaded_file.name).suffix if getattr(uploaded_file, "name", "") else ".mp4"
    raw = uploaded_file.getvalue()
    if not raw:
        return None

    with NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(raw)
        tmp.flush()

        capture = cv2.VideoCapture(tmp.name)
        if not capture.isOpened():
            capture.release()
            return None

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.release()

    fps = fps if fps > 0 else 30.0
    duration = (frame_count / fps) if frame_count > 0 else 0.0
    if width <= 0 or height <= 0:
        return None

    return VideoMetadata(
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_seconds=duration,
    )


def recommend_pipeline_params(metadata: VideoMetadata) -> Dict[str, Any]:
    pixels = int(metadata.width * metadata.height)
    is_high_resolution = pixels >= (1920 * 1080)
    is_long_video = metadata.duration_seconds >= 90.0 or metadata.frame_count >= 3000
    is_short_video = metadata.duration_seconds <= 30.0 and metadata.frame_count > 0

    if is_long_video and is_high_resolution:
        params = {
            "max_frames": min(max(180, metadata.frame_count // 10), 360),
            "fps": 20,
            "ocr_interval": 36,
            "cluster_interval": 8,
            "profile_hint": "throughput",
            "reason": "Video longo e alta resolucao: priorizar estabilidade e tempo de resposta.",
        }
    elif is_long_video:
        params = {
            "max_frames": min(max(240, metadata.frame_count // 8), 480),
            "fps": 24,
            "ocr_interval": 28,
            "cluster_interval": 6,
            "profile_hint": "balanced",
            "reason": "Video longo: balancear custo computacional e detalhamento de eventos.",
        }
    elif is_short_video:
        params = {
            "max_frames": min(max(180, metadata.frame_count), 720),
            "fps": 30,
            "ocr_interval": 14,
            "cluster_interval": 4,
            "profile_hint": "quality",
            "reason": "Video curto: aumentar granularidade para analise mais precisa.",
        }
    else:
        params = {
            "max_frames": min(max(240, metadata.frame_count // 2), 600),
            "fps": 28,
            "ocr_interval": 20,
            "cluster_interval": 5,
            "profile_hint": "balanced",
            "reason": "Configuracao intermediaria para cenarios gerais.",
        }

    return {
        **params,
        "metadata": {
            "width": metadata.width,
            "height": metadata.height,
            "fps": round(metadata.fps, 2),
            "frame_count": metadata.frame_count,
            "duration_seconds": round(metadata.duration_seconds, 2),
        },
    }
