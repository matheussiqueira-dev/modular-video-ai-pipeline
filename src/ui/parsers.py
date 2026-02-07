from __future__ import annotations

from typing import List, Tuple


def parse_zones_text(raw: str) -> Tuple[List[dict], List[str]]:
    """
    Parse zones from lines in format: name,x1,y1,x2,y2
    Returns parsed zones and a list of validation warnings.
    """
    zones: List[dict] = []
    warnings: List[str] = []

    for line_number, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text:
            continue

        parts = [item.strip() for item in text.split(",")]
        if len(parts) != 5:
            warnings.append(f"Linha {line_number}: formato invalido. Use nome,x1,y1,x2,y2")
            continue

        name, x1_raw, y1_raw, x2_raw, y2_raw = parts
        if not name:
            warnings.append(f"Linha {line_number}: nome da zona vazio")
            continue

        try:
            x1 = int(x1_raw)
            y1 = int(y1_raw)
            x2 = int(x2_raw)
            y2 = int(y2_raw)
        except ValueError:
            warnings.append(f"Linha {line_number}: coordenadas devem ser inteiras")
            continue

        if x1 == x2 or y1 == y2:
            warnings.append(f"Linha {line_number}: zona com area nula")
            continue

        if x1 > x2:
            x1, x2 = x2, x1
            warnings.append(f"Linha {line_number}: x1/x2 invertidos automaticamente")

        if y1 > y2:
            y1, y2 = y2, y1
            warnings.append(f"Linha {line_number}: y1/y2 invertidos automaticamente")

        zones.append({"name": name, "x1": x1, "y1": y1, "x2": x2, "y2": y2})

    return zones, warnings


def zones_to_text(zones: List[dict]) -> str:
    rows = []
    for zone in zones:
        rows.append(f"{zone['name']},{zone['x1']},{zone['y1']},{zone['x2']},{zone['y2']}")
    return "\n".join(rows)


def estimated_runtime_seconds(frame_count: int, expected_fps: float) -> float:
    if expected_fps <= 0:
        return 0.0
    return max(0.0, float(frame_count) / float(expected_fps))
