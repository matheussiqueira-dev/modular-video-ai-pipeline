from __future__ import annotations

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from src.api.models import Principal
from src.api.repository import JobRepository
from src.api.schemas import ErrorResponse, JobEventsResponse, JobListResponse, JobStatus, JobSummary, ZoneIn
from src.api.security import generate_job_id, require_permission, safe_json_load
from src.api.service import PipelineJobService


logger = logging.getLogger("pipeline_api")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_zones(raw: str) -> List[dict]:
    zones = safe_json_load(raw, [])
    if not isinstance(zones, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="zones_json must be a JSON array")

    validated: List[dict] = []
    for zone in zones:
        model = ZoneIn.model_validate(zone)
        validated.append(model.model_dump())
    return validated


class RuntimeContext:
    def __init__(self) -> None:
        runtime_root = Path(os.getenv("PIPELINE_RUNTIME_DIR", "runtime"))
        uploads_dir = runtime_root / "uploads"
        outputs_dir = runtime_root / "outputs"
        db_path = runtime_root / "api_jobs.sqlite3"

        uploads_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        self.runtime_root = runtime_root
        self.uploads_dir = uploads_dir
        self.outputs_dir = outputs_dir
        self.repository = JobRepository(db_path=db_path)
        self.service = PipelineJobService(self.repository)
        self.executor = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("PIPELINE_API_WORKERS", "2"))))
        self.max_upload_mb = max(1, int(os.getenv("PIPELINE_MAX_UPLOAD_MB", "200")))


context = RuntimeContext()

app = FastAPI(
    title="Modular Video AI Pipeline API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    started = _utc_now()
    response = None
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled error for request_id=%s", request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    elapsed_ms = int((_utc_now() - started).total_seconds() * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response


@app.get("/api/v1/health")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "service": "modular-video-ai-pipeline-api",
        "timestamp": _utc_now().isoformat(),
        "runtime_dir": str(context.runtime_root),
    }


def _save_upload_file(upload: UploadFile, target_path: Path, max_upload_mb: int) -> int:
    max_bytes = max_upload_mb * 1024 * 1024
    size = 0

    with target_path.open("wb") as handle:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                handle.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size is {max_upload_mb}MB",
                )
            handle.write(chunk)

    return size


def _to_job_summary(record: dict) -> JobSummary:
    return JobSummary(
        job_id=record["job_id"],
        status=JobStatus(record["status"]),
        requested_by=record["requested_by"],
        created_at=datetime.fromisoformat(record["created_at"]),
        updated_at=datetime.fromisoformat(record["updated_at"]),
        progress=float(record["progress"]),
        max_frames=int(record["max_frames"]),
        processed_frames=int(record["processed_frames"]),
        summary=record.get("summary"),
        error_message=record.get("error_message"),
    )


@app.post(
    "/api/v1/jobs",
    response_model=JobSummary,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_job(
    request: Request,
    file: UploadFile = File(...),
    max_frames: int = Form(240),
    fps: int = Form(30),
    ocr_interval: int = Form(30),
    clustering_interval: int = Form(5),
    mock_mode: str = Form("true"),
    async_mode: str = Form("true"),
    zones_json: str = Form("[]"),
    principal: Principal = Depends(require_permission("jobs:write")),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file must have a filename")

    extension = Path(file.filename).suffix.lower()
    if extension not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported video format")

    if max_frames < 10 or max_frames > 4000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="max_frames must be in [10, 4000]")
    if fps < 1 or fps > 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="fps must be in [1, 120]")
    if ocr_interval < 1 or ocr_interval > 300:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ocr_interval must be in [1, 300]")
    if clustering_interval < 1 or clustering_interval > 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="clustering_interval must be in [1, 120]")

    zones = _load_zones(zones_json)

    job_id = generate_job_id()
    safe_name = f"{job_id}{extension}"
    input_path = context.uploads_dir / safe_name
    output_video_path = context.outputs_dir / f"{job_id}.mp4"
    analytics_path = context.outputs_dir / f"{job_id}.jsonl"

    _save_upload_file(file, input_path, context.max_upload_mb)

    payload = {
        "max_frames": int(max_frames),
        "fps": int(fps),
        "ocr_interval": int(ocr_interval),
        "clustering_interval": int(clustering_interval),
        "mock_mode": _parse_bool(mock_mode),
        "request_id": request.state.request_id,
    }

    context.repository.create_job(
        job_id=job_id,
        requested_by=principal.role,
        payload=payload,
        zones=zones,
        max_frames=int(max_frames),
        input_path=str(input_path),
        output_video_path=str(output_video_path),
        analytics_path=str(analytics_path),
    )

    run_async = _parse_bool(async_mode)
    if run_async:
        context.executor.submit(context.service.process_job, job_id)
    else:
        context.service.process_job(job_id)

    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created job")
    return _to_job_summary(record)


@app.get(
    "/api/v1/jobs",
    response_model=JobListResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("jobs:read")),
):
    records, total = context.repository.list_jobs(limit=limit, offset=offset)
    _ = principal
    return JobListResponse(items=[_to_job_summary(record) for record in records], total=total)


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobSummary,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_job(job_id: str, principal: Principal = Depends(require_permission("jobs:read"))):
    _ = principal
    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _to_job_summary(record)


def _load_job_events(analytics_path: Path) -> List[dict]:
    items: List[dict] = []
    if not analytics_path.exists():
        return items

    with analytics_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("record_type") == "event" or row.get("type") in {"ZONE_ENTRY", "ZONE_EXIT", "STATIONARY_WARNING"}:
                items.append(row)
    return items


@app.get(
    "/api/v1/jobs/{job_id}/events",
    response_model=JobEventsResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_job_events(
    job_id: str,
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_permission("jobs:read")),
):
    _ = principal
    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    events = _load_job_events(Path(record["analytics_path"]))
    if event_type:
        events = [event for event in events if str(event.get("type", "")).lower() == event_type.lower()]
    if severity:
        events = [event for event in events if str(event.get("severity", "")).lower() == severity.lower()]

    return JobEventsResponse(job_id=job_id, count=len(events), items=events)


@app.get(
    "/api/v1/jobs/{job_id}/artifacts/video",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def download_video(job_id: str, principal: Principal = Depends(require_permission("artifacts:read"))):
    _ = principal
    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    path = Path(record["output_video_path"])
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video artifact not found")

    return FileResponse(path=path, filename=f"{job_id}.mp4", media_type="video/mp4")


@app.get(
    "/api/v1/jobs/{job_id}/artifacts/analytics",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def download_analytics(job_id: str, principal: Principal = Depends(require_permission("artifacts:read"))):
    _ = principal
    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    path = Path(record["analytics_path"])
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analytics artifact not found")

    return FileResponse(path=path, filename=f"{job_id}.jsonl", media_type="application/json")
