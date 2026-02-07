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
                    analytics_path TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    idempotency_key TEXT
                )
                """
            )
            self._ensure_column(conn, "jobs", "cancel_requested", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "jobs", "idempotency_key", "TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs (status, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_requested_by_created ON jobs (requested_by, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs (idempotency_key, requested_by, created_at DESC)"
            )
            conn.commit()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column_name: str, ddl: str) -> None:
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {row[1] for row in columns}
        if column_name in names:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {ddl}")

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
        idempotency_key: Optional[str] = None,
    ) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, status, requested_by, created_at, updated_at,
                    max_frames, processed_frames, progress,
                    payload_json, zones_json, summary_json, error_message,
                    input_path, output_video_path, analytics_path,
                    cancel_requested, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    0,
                    idempotency_key,
                ),
            )
            conn.commit()

    def find_recent_job_by_idempotency(self, idempotency_key: str, requested_by: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE idempotency_key = ? AND requested_by = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (idempotency_key, requested_by),
            ).fetchone()
        if row is None:
            return None
        return self._serialize_row(row)

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

    def mark_cancel_requested(self, job_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET cancel_requested = 1, updated_at = ?
                WHERE job_id = ? AND status IN (?, ?)
                """,
                (self._now(), job_id, JobStatus.QUEUED.value, JobStatus.RUNNING.value),
            )
            conn.commit()
            return cur.rowcount > 0

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT cancel_requested FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return False
        return bool(int(row["cancel_requested"]))

    def mark_cancelled(self, job_id: str, processed_frames: int, max_frames: int) -> None:
        progress = 0.0
        if max_frames > 0:
            progress = max(0.0, min(100.0, (processed_frames / max_frames) * 100.0))

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, processed_frames = ?, progress = ?, updated_at = ?,
                    error_message = COALESCE(error_message, ?)
                WHERE job_id = ?
                """,
                (
                    JobStatus.CANCELLED.value,
                    int(processed_frames),
                    float(progress),
                    self._now(),
                    "Cancelled by user",
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

    def list_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
        status_filter: Optional[str] = None,
        requested_by_filter: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        where = []
        params: List[object] = []

        if status_filter:
            where.append("status = ?")
            params.append(status_filter)

        if requested_by_filter:
            where.append("requested_by = ?")
            params.append(requested_by_filter)

        where_sql = ""
        if where:
            where_sql = " WHERE " + " AND ".join(where)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs{where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, int(limit), int(offset)),
            ).fetchall()
            count_row = conn.execute(
                f"SELECT COUNT(1) AS c FROM jobs{where_sql}",
                tuple(params),
            ).fetchone()

        total = int(count_row["c"]) if count_row else 0
        return [self._serialize_row(row) for row in rows], total

    def get_metrics(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(1) AS total
                FROM jobs
                GROUP BY status
                """
            ).fetchall()
            fps_row = conn.execute(
                """
                SELECT AVG(CAST(json_extract(summary_json, '$.average_processing_fps') AS REAL)) AS avg_fps
                FROM jobs
                WHERE summary_json IS NOT NULL AND status = ?
                """,
                (JobStatus.COMPLETED.value,),
            ).fetchone()
            total_row = conn.execute("SELECT COUNT(1) AS c FROM jobs").fetchone()

        by_status = {row["status"]: int(row["total"]) for row in rows}
        return {
            "total_jobs": int(total_row["c"]) if total_row else 0,
            "queued": by_status.get(JobStatus.QUEUED.value, 0),
            "running": by_status.get(JobStatus.RUNNING.value, 0),
            "completed": by_status.get(JobStatus.COMPLETED.value, 0),
            "failed": by_status.get(JobStatus.FAILED.value, 0),
            "cancelled": by_status.get(JobStatus.CANCELLED.value, 0),
            "avg_processing_fps": float(fps_row["avg_fps"] or 0.0) if fps_row else 0.0,
        }

    @staticmethod
    def _safe_json_load(raw: Optional[str], default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _serialize_row(row: sqlite3.Row) -> dict:
        summary = JobRepository._safe_json_load(row["summary_json"], None)
        payload = JobRepository._safe_json_load(row["payload_json"], {})
        zones = JobRepository._safe_json_load(row["zones_json"], [])

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
            "cancel_requested": bool(int(row["cancel_requested"] or 0)),
            "idempotency_key": row["idempotency_key"],
        }
