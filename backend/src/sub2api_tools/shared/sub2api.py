from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests

from .config import Sub2APIConfig


USERINFO_PATH = "/api/v1/auth/me"


class Sub2APIClient:
    def __init__(self, cfg: Sub2APIConfig, timeout: float = 8.0):
        self.cfg = cfg
        self.timeout = timeout
        self.session = requests.Session()

    def verify_user(self, credential: str) -> dict[str, Any]:
        if not credential:
            raise ValueError("credential is required")
        resp = self.session.get(
            _join(self.cfg.base_url, USERINFO_PATH),
            headers={"Accept": "application/json", "Authorization": f"Bearer {credential}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        user = _unwrap_user(resp.json())
        if not str(user.get("id") or user.get("user_id") or "").strip():
            raise ValueError("userinfo response missing user id")
        return user

    def admin_get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.session.get(
            _join(self.cfg.base_url, path),
            headers={"Accept": "application/json", "x-api-key": self.cfg.admin_api_key},
            timeout=self.timeout,
            **kwargs,
        )


def _join(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _unwrap_user(body: Any) -> dict[str, Any]:
    data = body.get("data") if isinstance(body, dict) and "data" in body else body
    if isinstance(data, dict) and isinstance(data.get("user"), dict):
        data = data["user"]
    if not isinstance(data, dict):
        raise ValueError("invalid userinfo response")
    user = dict(data)
    if "id" not in user and "user_id" in user:
        user["id"] = user["user_id"]
    return user
