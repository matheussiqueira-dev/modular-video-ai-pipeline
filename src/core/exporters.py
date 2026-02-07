from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class JsonlExporter:
    """Lightweight append-only exporter for pipeline telemetry."""

    def __init__(self, output_path: Optional[Path]):
        self.output_path = output_path
        self._handle = None

    def open(self) -> None:
        if self.output_path is None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.output_path.open("w", encoding="utf-8")

    def write(self, record_type: str, payload: Dict[str, Any]) -> None:
        if self._handle is None:
            return
        row = {"type": record_type, **payload}
        self._handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    def close(self) -> None:
        if self._handle is None:
            return
        self._handle.flush()
        self._handle.close()
        self._handle = None

    def __enter__(self) -> "JsonlExporter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        self.close()
