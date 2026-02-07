from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True, frozen=True)
class Principal:
    api_key: str
    role: str


class Role:
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


PERMISSIONS: Dict[str, set[str]] = {
    Role.ADMIN: {"jobs:read", "jobs:write", "artifacts:read"},
    Role.OPERATOR: {"jobs:read", "jobs:write", "artifacts:read"},
    Role.VIEWER: {"jobs:read", "artifacts:read"},
}
