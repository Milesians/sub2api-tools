from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from sub2api_tools.app import create_app
from sub2api_tools.shared.context import get_context
from sub2api_tools.shared.security import verify_token


class FakeSub2API:
    def __init__(self, role: str):
        self.role = role

    def verify_user(self, credential: str) -> dict:
        return {
            "id": "42",
            "username": "demo",
            "role": self.role,
            "is_admin": self.role == "admin",
        }


def test_bootstrap_filters_features_for_user(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))
    get_context().sub2api = FakeSub2API("user")

    with TestClient(app) as client:
        res = client.post("/tools/api/auth/bootstrap", json={"user_id": "42", "token": "t"})

    body = res.json()
    assert res.status_code == 200
    assert [item["id"] for item in body["features"]] == ["looking-glass"]
    token = body["session_token"]
    assert verify_token(token, "secret").user_id == "42"


def test_bootstrap_filters_features_for_admin(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))
    get_context().sub2api = FakeSub2API("admin")

    with TestClient(app) as client:
        res = client.post("/tools/api/auth/bootstrap", json={"user_id": "42", "token": "t"})

    body = res.json()
    assert res.status_code == 200
    assert [item["id"] for item in body["features"]] == ["looking-glass", "account-scheduler"]
    assert [item["path"] for item in body["features"]] == ["/lg", "/admin/scheduler"]
    assert body["app"]["basePath"] == "/tools"


def test_auth_me_restores_jwt_without_sub2api_call(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))
    get_context().sub2api = FakeSub2API("admin")

    with TestClient(app) as client:
        boot = client.post("/tools/api/auth/bootstrap", json={"user_id": "42", "token": "t"}).json()
        res = client.get("/tools/api/auth/me", headers={"Authorization": f"Bearer {boot['session_token']}"})

    body = res.json()
    assert res.status_code == 200
    assert "session_token" not in body
    assert body["user"]["id"] == "42"
    assert [item["id"] for item in body["features"]] == ["looking-glass", "account-scheduler"]


def test_scheduler_disabled_does_not_create_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "tools.db"
    app = create_app(_config(tmp_path))

    with TestClient(app) as client:
        res = client.get("/tools/api/health")

    assert res.status_code == 200
    assert not db_path.exists()


def test_scheduler_can_query_without_auto_start(tmp_path: Path) -> None:
    db_path = tmp_path / "tools.db"
    app = create_app(_config(tmp_path, scheduler={"enabled": True, "auto_start": False}))

    get_context().scheduler.start()

    with TestClient(app) as client:
        res = client.get("/tools/api/health")

    assert res.status_code == 200
    assert res.json()["scheduler_enabled"] is True
    assert res.json()["scheduler_auto_start"] is False
    assert db_path.exists()
    assert get_context().scheduler._task is None


def test_bootstrap_rejects_disallowed_origin(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path, allowed_origins=["https://*.sub2api.example.com"]))
    get_context().sub2api = FakeSub2API("user")

    with TestClient(app) as client:
        res = client.post(
            "/tools/api/auth/bootstrap",
            headers={"Origin": "https://badsub2api.example.com"},
            json={"user_id": "42", "token": "t"},
        )

    assert res.status_code == 403
    assert res.json()["detail"] == "origin is not allowed"


def test_bootstrap_allows_wildcard_origin(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path, allowed_origins=["https://*.sub2api.example.com"]))
    get_context().sub2api = FakeSub2API("user")

    with TestClient(app) as client:
        res = client.post(
            "/tools/api/auth/bootstrap",
            headers={"Origin": "https://admin.sub2api.example.com"},
            json={"user_id": "42", "token": "t"},
        )

    assert res.status_code == 200


def test_bootstrap_allows_src_url_when_origin_header_missing(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path, allowed_origins=["https://sub2api.example.com"]))
    get_context().sub2api = FakeSub2API("user")

    with TestClient(app) as client:
        res = client.post(
            "/tools/api/auth/bootstrap",
            json={"user_id": "42", "token": "t", "src_url": "https://sub2api.example.com/admin"},
        )

    assert res.status_code == 200


def test_cors_rejects_disallowed_origin(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path, allowed_origins=["https://*.sub2api.example.com"]))

    with TestClient(app) as client:
        res = client.options(
            "/tools/api/health",
            headers={
                "Origin": "https://badsub2api.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert res.status_code == 400


def test_cors_allows_wildcard_origin(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path, allowed_origins=["https://*.sub2api.example.com"]))

    with TestClient(app) as client:
        res = client.options(
            "/tools/api/health",
            headers={
                "Origin": "https://admin.sub2api.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "https://admin.sub2api.example.com"


def _config(
    tmp_path: Path,
    allowed_origins: list[str] | None = None,
    scheduler: dict | None = None,
) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({
        "app": {
            "listen": "127.0.0.1:8080",
            "basePath": "/tools",
            "static_dir": str(tmp_path / "dist"),
        },
        "security": {
            "session_secret": "secret",
            "allowed_origins": allowed_origins or [],
            "sensitive_action_password": "password",
        },
        "sub2api": {
            "base_url": "https://sub2api.example.com",
            "admin_api_key": "key",
        },
        "storage": {
            "sqlite_dsn": str(tmp_path / "tools.db"),
        },
        "scheduler": scheduler or {"enabled": False},
        "features": [
            {
                "id": "looking-glass",
                "name": "网络诊断",
                "visibility": ["user", "admin"],
                "enabled": True,
            },
            {
                "id": "account-scheduler",
                "name": "账号调度",
                "visibility": ["admin"],
                "enabled": True,
            },
        ],
    }), encoding="utf-8")
    return path
