from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests


@dataclass(slots=True)
class ApiClientConfig:
    base_url: str
    api_key: str
    timeout_seconds: int = 180

    @property
    def headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
        }


class BackendApiClient:
    def __init__(self, config: ApiClientConfig):
        self.config = config

    def create_job(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
        payload: Dict,
        zones: List[dict],
        async_mode: bool = True,
    ) -> dict:
        url = f"{self.config.base_url.rstrip('/')}/api/v1/jobs"
        files = {
            "file": (file_name, file_bytes, "application/octet-stream"),
        }
        data = {
            "max_frames": str(payload["max_frames"]),
            "fps": str(payload["fps"]),
            "ocr_interval": str(payload["ocr_interval"]),
            "clustering_interval": str(payload["clustering_interval"]),
            "mock_mode": str(payload.get("mock_mode", True)).lower(),
            "async_mode": str(async_mode).lower(),
            "zones_json": json.dumps(zones, ensure_ascii=True),
        }

        response = requests.post(
            url,
            headers=self.config.headers,
            files=files,
            data=data,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_job(self, job_id: str) -> dict:
        url = f"{self.config.base_url.rstrip('/')}/api/v1/jobs/{job_id}"
        response = requests.get(url, headers=self.config.headers, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def download_video(self, job_id: str) -> bytes:
        url = f"{self.config.base_url.rstrip('/')}/api/v1/jobs/{job_id}/artifacts/video"
        response = requests.get(url, headers=self.config.headers, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        return response.content

    def download_analytics(self, job_id: str) -> bytes:
        url = f"{self.config.base_url.rstrip('/')}/api/v1/jobs/{job_id}/artifacts/analytics"
        response = requests.get(url, headers=self.config.headers, timeout=self.config.timeout_seconds)
        response.raise_for_status()
        return response.content

    def wait_for_completion(self, job_id: str, poll_interval_seconds: float = 1.2, max_wait_seconds: int = 1800) -> dict:
        started = time.time()
        while True:
            job = self.get_job(job_id)
            if job.get("status") in {"completed", "failed"}:
                return job

            if time.time() - started > max_wait_seconds:
                raise TimeoutError("Job did not finish in configured max_wait_seconds")

            time.sleep(max(0.2, poll_interval_seconds))
