from __future__ import annotations

import json
import os
import secrets
from typing import Dict

from fastapi import Depends, Header, HTTPException, status

from src.api.models import PERMISSIONS, Principal, Role


class ApiKeyService:
    """
    API key based authentication for service-to-service and dashboard usage.
    Environment format:
      PIPELINE_API_KEYS=admin-key:admin,ops-key:operator,viewer-key:viewer
    """

    def __init__(self) -> None:
        self._keys = self._load_keys()

    def _load_keys(self) -> Dict[str, str]:
        raw = os.getenv("PIPELINE_API_KEYS", "dev-local-key:admin")
        mapping: Dict[str, str] = {}

        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            if ":" not in token:
                continue
            key, role = token.split(":", maxsplit=1)
            role = role.strip().lower()
            if role not in PERMISSIONS:
                continue
            mapping[key.strip()] = role

        if not mapping:
            mapping["dev-local-key"] = Role.ADMIN

        return mapping

    def authenticate(self, api_key: str) -> Principal:
        role = self._keys.get(api_key)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
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
