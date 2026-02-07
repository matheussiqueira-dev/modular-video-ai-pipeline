from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.api.schemas import JobStatus


class JobRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    max_frames INTEGER NOT NULL,
                    processed_frames INTEGER NOT NULL,
                    progress REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    zones_json TEXT NOT NULL,
                    summary_json TEXT,
                    error_message TEXT,
                    input_path TEXT,
                    output_video_path TEXT,
                    analytics_path TEXT
                )
                """
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(
        self,
        *,
        job_id: str,
        requested_by: str,
        payload: dict,
        zones: list,
        max_frames: int,
        input_path: str,
        output_video_path: str,
        analytics_path: str,
    ) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, status, requested_by, created_at, updated_at,
                    max_frames, processed_frames, progress,
                    payload_json, zones_json, summary_json, error_message,
                    input_path, output_video_path, analytics_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    JobStatus.QUEUED.value,
                    requested_by,
                    now,
                    now,
                    int(max_frames),
                    0,
                    0.0,
                    json.dumps(payload, ensure_ascii=True),
                    json.dumps(zones, ensure_ascii=True),
                    None,
                    None,
                    input_path,
                    output_video_path,
                    analytics_path,
                ),
            )
            conn.commit()

    def update_job_progress(self, job_id: str, processed_frames: int, max_frames: int, status: str = JobStatus.RUNNING.value) -> None:
        progress = 0.0
        if max_frames > 0:
            progress = max(0.0, min(100.0, (processed_frames / max_frames) * 100.0))

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, processed_frames = ?, progress = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, int(processed_frames), float(progress), self._now(), job_id),
            )
            conn.commit()

    def complete_job(self, job_id: str, summary: dict, processed_frames: int, max_frames: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, summary_json = ?, processed_frames = ?, progress = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.COMPLETED.value,
                    json.dumps(summary, ensure_ascii=True),
                    int(processed_frames),
                    100.0 if max_frames > 0 else 0.0,
                    self._now(),
                    job_id,
                ),
            )
            conn.commit()

    def fail_job(self, job_id: str, message: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, error_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (JobStatus.FAILED.value, message[:1000], self._now(), job_id),
            )
            conn.commit()

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._serialize_row(row)

    def list_jobs(self, limit: int = 20, offset: int = 0) -> Tuple[List[dict], int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (int(limit), int(offset)),
            ).fetchall()
            count_row = conn.execute("SELECT COUNT(1) AS c FROM jobs").fetchone()

        total = int(count_row["c"]) if count_row else 0
        return [self._serialize_row(row) for row in rows], total

    @staticmethod
    def _serialize_row(row: sqlite3.Row) -> dict:
        summary = None
        if row["summary_json"]:
            try:
                summary = json.loads(row["summary_json"])
            except json.JSONDecodeError:
                summary = None

        payload = {}
        if row["payload_json"]:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                payload = {}

        zones = []
        if row["zones_json"]:
            try:
                zones = json.loads(row["zones_json"])
            except json.JSONDecodeError:
                zones = []

        return {
            "job_id": row["job_id"],
            "status": row["status"],
            "requested_by": row["requested_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "max_frames": int(row["max_frames"]),
            "processed_frames": int(row["processed_frames"]),
            "progress": float(row["progress"]),
            "payload": payload,
            "zones": zones,
            "summary": summary,
            "error_message": row["error_message"],
            "input_path": row["input_path"],
            "output_video_path": row["output_video_path"],
            "analytics_path": row["analytics_path"],
        }
