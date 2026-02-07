from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from fastapi import Depends, Header, HTTPException, status

from src.api.models import PERMISSIONS, Principal, Role


@dataclass(slots=True)
class RateBucket:
    window_start: float
    count: int


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._lock = threading.Lock()
        self._buckets: Dict[str, RateBucket] = {}

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now - bucket.window_start >= self.window_seconds:
                self._buckets[key] = RateBucket(window_start=now, count=1)
                return

            if bucket.count >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({self.max_requests}/{self.window_seconds}s)",
                )

            bucket.count += 1


class ApiKeyService:
    """
    API key auth + role permissions.
    Environment format:
      PIPELINE_API_KEYS=admin-key:admin,ops-key:operator,viewer-key:viewer
    """

    def __init__(self) -> None:
        self._keys = self._load_keys()
        self._limiter = FixedWindowRateLimiter(
            max_requests=int(os.getenv("PIPELINE_RATE_LIMIT_REQUESTS", "300")),
            window_seconds=int(os.getenv("PIPELINE_RATE_LIMIT_WINDOW_SECONDS", "60")),
        )

    def _load_keys(self) -> Dict[str, str]:
        raw = os.getenv("PIPELINE_API_KEYS", "dev-local-key:admin")
        mapping: Dict[str, str] = {}

        for token in raw.split(","):
            token = token.strip()
            if not token or ":" not in token:
                continue
            key, role = token.split(":", maxsplit=1)
            key = key.strip()
            role = role.strip().lower()
            if not key or role not in PERMISSIONS:
                continue
            mapping[key] = role

        if not mapping:
            mapping["dev-local-key"] = Role.ADMIN

        return mapping

    def authenticate(self, api_key: str) -> Principal:
        role = None
        for expected_key, expected_role in self._keys.items():
            if secrets.compare_digest(api_key, expected_key):
                role = expected_role
                break

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        self._limiter.check(api_key)
        return Principal(api_key=api_key, role=role)

    def authorize(self, principal: Principal, permission: str) -> None:
        allowed = PERMISSIONS.get(principal.role, set())
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role}' is not allowed to perform '{permission}'",
            )


auth_service = ApiKeyService()


def get_principal(x_api_key: str = Header(default="", alias="X-API-Key")) -> Principal:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    return auth_service.authenticate(x_api_key)


def require_permission(permission: str):
    def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        auth_service.authorize(principal, permission)
        return principal

    return _dependency


def generate_job_id() -> str:
    return secrets.token_hex(8)


def safe_json_load(value: str, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def normalize_idempotency_key(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    key = raw.strip()
    if not key:
        return None
    if len(key) > 120:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="X-Idempotency-Key too long")
    return key
