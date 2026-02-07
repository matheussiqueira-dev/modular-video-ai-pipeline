from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ZoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    x1: int = Field(ge=0, le=10000)
    y1: int = Field(ge=0, le=10000)
    x2: int = Field(ge=0, le=10000)
    y2: int = Field(ge=0, le=10000)

    @model_validator(mode="after")
    def normalize_bounds(self):
        if self.x1 == self.x2 or self.y1 == self.y2:
            raise ValueError("Zone area must be greater than zero")

        if self.x1 > self.x2:
            self.x1, self.x2 = self.x2, self.x1

        if self.y1 > self.y2:
            self.y1, self.y2 = self.y2, self.y1

        return self


class JobCreatePayload(BaseModel):
    max_frames: int = Field(default=240, ge=10, le=4000)
    fps: int = Field(default=30, ge=1, le=120)
    ocr_interval: int = Field(default=30, ge=1, le=300)
    clustering_interval: int = Field(default=5, ge=1, le=120)
    mock_mode: bool = True
    async_mode: bool = True
    zones: List[ZoneIn] = Field(default_factory=list)


class JobSummary(BaseModel):
    job_id: str
    status: JobStatus
    requested_by: str
    created_at: datetime
    updated_at: datetime
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    max_frames: int
    processed_frames: int = 0
    summary: Optional[dict] = None
    error_message: Optional[str] = None
    cancel_requested: bool = False
    idempotency_key: Optional[str] = None


class JobListResponse(BaseModel):
    items: List[JobSummary]
    total: int


class JobEventsResponse(BaseModel):
    job_id: str
    count: int
    items: List[dict]


class JobCancelResponse(BaseModel):
    job_id: str
    status: JobStatus
    cancel_requested: bool


class JobMetricsResponse(BaseModel):
    total_jobs: int
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    avg_processing_fps: float


class ErrorResponse(BaseModel):
    detail: str
    request_id: Optional[str] = None
