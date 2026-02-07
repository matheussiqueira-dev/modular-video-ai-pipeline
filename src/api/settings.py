from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class ApiSettings:
    runtime_root: Path
    uploads_dir: Path
    outputs_dir: Path
    db_path: Path
    workers: int
    max_upload_mb: int


    @staticmethod
    def from_env() -> "ApiSettings":
        runtime_root = Path(os.getenv("PIPELINE_RUNTIME_DIR", "runtime"))
        uploads_dir = runtime_root / "uploads"
        outputs_dir = runtime_root / "outputs"

        return ApiSettings(
            runtime_root=runtime_root,
            uploads_dir=uploads_dir,
            outputs_dir=outputs_dir,
            db_path=runtime_root / "api_jobs.sqlite3",
            workers=max(1, int(os.getenv("PIPELINE_API_WORKERS", "2"))),
            max_upload_mb=max(1, int(os.getenv("PIPELINE_MAX_UPLOAD_MB", "200"))),
        )
