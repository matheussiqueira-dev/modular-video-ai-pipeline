from __future__ import annotations

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from src.api.models import Principal
from src.api.repository import JobRepository
from src.api.schemas import (
    ErrorResponse,
    JobCancelResponse,
    JobEventsResponse,
    JobListResponse,
    JobMetricsResponse,
    JobStatus,
    JobSummary,
)
from src.api.security import generate_job_id, normalize_idempotency_key, require_permission
from src.api.service import PipelineJobService
from src.api.settings import ApiSettings
from src.api.validators import build_job_payload


logger = logging.getLogger("pipeline_api")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuntimeContext:
    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)

        self.runtime_root = settings.runtime_root
        self.uploads_dir = settings.uploads_dir
        self.outputs_dir = settings.outputs_dir
        self.repository = JobRepository(db_path=settings.db_path)
        self.service = PipelineJobService(self.repository)
        self.executor = ThreadPoolExecutor(max_workers=settings.workers)
        self.max_upload_mb = settings.max_upload_mb


context = RuntimeContext(ApiSettings.from_env())

app = FastAPI(
    title="Modular Video AI Pipeline API",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    started = _utc_now()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error for request_id=%s", request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    elapsed_ms = int((_utc_now() - started).total_seconds() * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"

    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )

    return response


@app.get("/api/v1/health")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "service": "modular-video-ai-pipeline-api",
        "version": app.version,
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
        cancel_requested=bool(record.get("cancel_requested", False)),
        idempotency_key=record.get("idempotency_key"),
    )


def _create_job_record(
    *,
    principal: Principal,
    payload_model,
    zones: list,
    input_path: Path,
    idempotency_key: Optional[str],
) -> dict:
    job_id = generate_job_id()
    output_video_path = context.outputs_dir / f"{job_id}.mp4"
    analytics_path = context.outputs_dir / f"{job_id}.jsonl"

    payload = {
        "max_frames": int(payload_model.max_frames),
        "fps": int(payload_model.fps),
        "ocr_interval": int(payload_model.ocr_interval),
        "clustering_interval": int(payload_model.clustering_interval),
        "mock_mode": bool(payload_model.mock_mode),
    }

    context.repository.create_job(
        job_id=job_id,
        requested_by=principal.role,
        payload=payload,
        zones=zones,
        max_frames=int(payload_model.max_frames),
        input_path=str(input_path),
        output_video_path=str(output_video_path),
        analytics_path=str(analytics_path),
        idempotency_key=idempotency_key,
    )

    if bool(payload_model.async_mode):
        context.executor.submit(context.service.process_job, job_id)
    else:
        context.service.process_job(job_id)

    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created job")
    return record


@app.post(
    "/api/v1/jobs",
    response_model=JobSummary,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
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
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    principal: Principal = Depends(require_permission("jobs:write")),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file must have a filename")

    extension = Path(file.filename).suffix.lower()
    if extension not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported video format")

    payload_model, zones = build_job_payload(
        max_frames=max_frames,
        fps=fps,
        ocr_interval=ocr_interval,
        clustering_interval=clustering_interval,
        mock_mode=mock_mode,
        async_mode=async_mode,
        zones_json=zones_json,
    )

    idempotency_key = normalize_idempotency_key(x_idempotency_key)
    if idempotency_key:
        existing = context.repository.find_recent_job_by_idempotency(idempotency_key=idempotency_key, requested_by=principal.role)
        if existing is not None:
            logger.info("Idempotency hit for key=%s request_id=%s", idempotency_key, request.state.request_id)
            return _to_job_summary(existing)

    safe_name = f"{generate_job_id()}{extension}"
    input_path = context.uploads_dir / safe_name
    _save_upload_file(file, input_path, context.max_upload_mb)

    record = _create_job_record(
        principal=principal,
        payload_model=payload_model,
        zones=zones,
        input_path=input_path,
        idempotency_key=idempotency_key,
    )
    return _to_job_summary(record)


@app.post(
    "/api/v1/jobs/{job_id}/retry",
    response_model=JobSummary,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def retry_job(
    job_id: str,
    async_mode: bool = Query(True),
    principal: Principal = Depends(require_permission("jobs:write")),
):
    original = context.repository.get_job(job_id)
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    input_path = Path(original["input_path"])
    if not input_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original input artifact not found")

    payload = dict(original.get("payload", {}))
    payload["async_mode"] = async_mode

    zones = list(original.get("zones", []))
    payload_model, _ = build_job_payload(
        max_frames=int(payload.get("max_frames", 240)),
        fps=int(payload.get("fps", 30)),
        ocr_interval=int(payload.get("ocr_interval", 30)),
        clustering_interval=int(payload.get("clustering_interval", 5)),
        mock_mode=bool(payload.get("mock_mode", True)),
        async_mode=bool(async_mode),
        zones_json=json.dumps(zones, ensure_ascii=True),
    )

    record = _create_job_record(
        principal=principal,
        payload_model=payload_model,
        zones=zones,
        input_path=input_path,
        idempotency_key=None,
    )
    return _to_job_summary(record)


@app.post(
    "/api/v1/jobs/{job_id}/cancel",
    response_model=JobCancelResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def cancel_job(job_id: str, principal: Principal = Depends(require_permission("jobs:write"))):
    _ = principal
    record = context.repository.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if record["status"] in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
        return JobCancelResponse(job_id=job_id, status=JobStatus(record["status"]), cancel_requested=False)

    marked = context.repository.mark_cancel_requested(job_id)
    refreshed = context.repository.get_job(job_id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobCancelResponse(
        job_id=job_id,
        status=JobStatus(refreshed["status"]),
        cancel_requested=bool(marked or refreshed.get("cancel_requested", False)),
    )


@app.get(
    "/api/v1/jobs",
    response_model=JobListResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[JobStatus] = Query(default=None, alias="status"),
    requested_by: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_permission("jobs:read")),
):
    _ = principal
    records, total = context.repository.list_jobs(
        limit=limit,
        offset=offset,
        status_filter=status_filter.value if status_filter else None,
        requested_by_filter=requested_by,
    )
    return JobListResponse(items=[_to_job_summary(record) for record in records], total=total)


@app.get(
    "/api/v1/jobs/metrics",
    response_model=JobMetricsResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def job_metrics(principal: Principal = Depends(require_permission("jobs:read"))):
    _ = principal
    return JobMetricsResponse(**context.repository.get_metrics())


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
            if row.get("record_type") == "event":
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
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
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

    sliced = events[offset : offset + limit]
    return JobEventsResponse(job_id=job_id, count=len(events), items=sliced)


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
