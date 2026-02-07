import importlib
import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _fake_video_bytes() -> bytes:
    # Invalid video payload is acceptable because pipeline falls back to synthetic frames.
    return b"not-a-real-video"


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")

    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("PIPELINE_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("PIPELINE_API_KEYS", "admin-test:admin,viewer-test:viewer")
    monkeypatch.setenv("PIPELINE_API_WORKERS", "1")
    monkeypatch.setenv("PIPELINE_MAX_UPLOAD_MB", "50")

    if "src.api.app" in sys.modules:
        module = importlib.reload(sys.modules["src.api.app"])
    else:
        module = importlib.import_module("src.api.app")

    client = testclient.TestClient(module.app)
    try:
        yield client
    finally:
        client.close()


def test_healthcheck_public(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_jobs_endpoint_requires_api_key(api_client):
    response = api_client.get("/api/v1/jobs")
    assert response.status_code == 401


def test_viewer_cannot_create_job(api_client):
    files = {"file": ("sample.mp4", _fake_video_bytes(), "application/octet-stream")}
    data = {
        "max_frames": "15",
        "fps": "20",
        "ocr_interval": "5",
        "clustering_interval": "3",
        "mock_mode": "true",
        "async_mode": "false",
        "zones_json": "[]",
    }

    response = api_client.post("/api/v1/jobs", files=files, data=data, headers={"X-API-Key": "viewer-test"})
    assert response.status_code == 403


def test_admin_can_create_sync_job_and_download_artifacts(api_client):
    files = {"file": ("sample.mp4", _fake_video_bytes(), "application/octet-stream")}
    data = {
        "max_frames": "20",
        "fps": "24",
        "ocr_interval": "5",
        "clustering_interval": "3",
        "mock_mode": "true",
        "async_mode": "false",
        "zones_json": "[{\"name\":\"gate\",\"x1\":10,\"y1\":10,\"x2\":80,\"y2\":80}]",
    }

    created = api_client.post("/api/v1/jobs", files=files, data=data, headers={"X-API-Key": "admin-test"})
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job_id"]

    detail = api_client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": "admin-test"})
    assert detail.status_code == 200
    assert detail.json()["status"] in {"completed", "failed", "running", "queued"}

    # Synchronous mode should complete before response; assert completion for deterministic test.
    assert detail.json()["status"] == "completed"

    events = api_client.get(f"/api/v1/jobs/{job_id}/events", headers={"X-API-Key": "admin-test"})
    assert events.status_code == 200
    assert events.json()["job_id"] == job_id

    video = api_client.get(f"/api/v1/jobs/{job_id}/artifacts/video", headers={"X-API-Key": "admin-test"})
    assert video.status_code == 200
    assert len(video.content) > 0

    analytics = api_client.get(f"/api/v1/jobs/{job_id}/artifacts/analytics", headers={"X-API-Key": "admin-test"})
    assert analytics.status_code == 200
    assert len(analytics.content) > 0
