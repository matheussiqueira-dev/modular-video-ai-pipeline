import importlib
import os
import sys
import time

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
    monkeypatch.setenv("PIPELINE_RATE_LIMIT_REQUESTS", "500")

    if "src.api.app" in sys.modules:
        module = importlib.reload(sys.modules["src.api.app"])
    else:
        module = importlib.import_module("src.api.app")

    client = testclient.TestClient(module.app)
    try:
        yield client
    finally:
        client.close()


def _create_job(client, *, async_mode: bool = False, idempotency_key: str | None = None, max_frames: int = 20):
    files = {"file": ("sample.mp4", _fake_video_bytes(), "application/octet-stream")}
    data = {
        "max_frames": str(max_frames),
        "fps": "24",
        "ocr_interval": "5",
        "clustering_interval": "3",
        "mock_mode": "true",
        "async_mode": "true" if async_mode else "false",
        "zones_json": "[{\"name\":\"gate\",\"x1\":10,\"y1\":10,\"x2\":80,\"y2\":80}]",
    }
    headers = {"X-API-Key": "admin-test"}
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key

    return client.post("/api/v1/jobs", files=files, data=data, headers=headers)


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
    created = _create_job(api_client, async_mode=False)
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job_id"]

    detail = api_client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": "admin-test"})
    assert detail.status_code == 200
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


def test_idempotency_key_reuses_existing_job(api_client):
    first = _create_job(api_client, async_mode=False, idempotency_key="idem-001")
    second = _create_job(api_client, async_mode=False, idempotency_key="idem-001")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]


def test_list_jobs_supports_filters(api_client):
    created = _create_job(api_client, async_mode=False)
    job_id = created.json()["job_id"]

    by_status = api_client.get("/api/v1/jobs", params={"status": "completed"}, headers={"X-API-Key": "admin-test"})
    assert by_status.status_code == 200
    assert by_status.json()["total"] >= 1

    by_role = api_client.get(
        "/api/v1/jobs", params={"requested_by": "admin"}, headers={"X-API-Key": "admin-test"}
    )
    assert by_role.status_code == 200
    ids = [item["job_id"] for item in by_role.json()["items"]]
    assert job_id in ids


def test_metrics_endpoint(api_client):
    _create_job(api_client, async_mode=False)
    response = api_client.get("/api/v1/jobs/metrics", headers={"X-API-Key": "admin-test"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] >= 1
    assert "avg_processing_fps" in body


def test_retry_job_creates_new_job(api_client):
    created = _create_job(api_client, async_mode=False)
    original_job_id = created.json()["job_id"]

    retried = api_client.post(
        f"/api/v1/jobs/{original_job_id}/retry", params={"async_mode": "false"}, headers={"X-API-Key": "admin-test"}
    )
    assert retried.status_code == 200

    retry_job_id = retried.json()["job_id"]
    assert retry_job_id != original_job_id


def test_cancel_job_flow(api_client):
    created = _create_job(api_client, async_mode=True, max_frames=300)
    assert created.status_code == 200
    job_id = created.json()["job_id"]

    cancelled = api_client.post(f"/api/v1/jobs/{job_id}/cancel", headers={"X-API-Key": "admin-test"})
    assert cancelled.status_code == 200
    assert cancelled.json()["cancel_requested"] is True

    deadline = time.time() + 15
    last_status = None
    while time.time() < deadline:
        detail = api_client.get(f"/api/v1/jobs/{job_id}", headers={"X-API-Key": "admin-test"})
        assert detail.status_code == 200
        last_status = detail.json()["status"]
        if last_status in {"cancelled", "completed", "failed"}:
            break
        time.sleep(0.2)

    assert last_status in {"cancelled", "completed", "failed"}
