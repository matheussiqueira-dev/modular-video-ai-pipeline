from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True, slots=True)
class FrontendPreset:
    name: str
    description: str
    max_frames: int
    fps: int
    ocr_interval: int
    cluster_interval: int
    zones_text: str


PRESETS: Dict[str, FrontendPreset] = {
    "Sports Analytics": FrontendPreset(
        name="Sports Analytics",
        description="Balanceado para partidas com foco em tracking e OCR de camisa.",
        max_frames=360,
        fps=30,
        ocr_interval=15,
        cluster_interval=4,
        zones_text="ataque,640,140,1220,620\ndefesa,60,140,620,620",
    ),
    "Retail Monitoring": FrontendPreset(
        name="Retail Monitoring",
        description="Ajustado para detecao de permanencia e fluxo de entrada.",
        max_frames=420,
        fps=24,
        ocr_interval=28,
        cluster_interval=6,
        zones_text="caixa,860,180,1240,620\nentrada,30,130,360,620",
    ),
    "Security Patrol": FrontendPreset(
        name="Security Patrol",
        description="Priorizacao de alertas de zona e deteccao de anomalias.",
        max_frames=480,
        fps=20,
        ocr_interval=40,
        cluster_interval=8,
        zones_text="area_restrita,740,110,1240,640\nportaria,20,120,340,640",
    ),
}


def list_preset_names() -> List[str]:
    return ["Custom"] + list(PRESETS.keys())
