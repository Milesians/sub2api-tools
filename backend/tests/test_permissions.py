from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from sub2api_tools.app import create_app
from sub2api_tools.shared.security import Session, issue_token


def test_scheduler_requires_admin(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))
    user_token = issue_token(Session(user_id="u1", username="", email="", role="user"), "secret", 60)
    admin_token = issue_token(Session(user_id="a1", username="", email="", role="admin"), "secret", 60)

    with TestClient(app) as client:
        user_res = client.get("/tools/api/scheduler/snapshot", headers={"Authorization": f"Bearer {user_token}"})
        admin_res = client.get("/tools/api/scheduler/snapshot", headers={"Authorization": f"Bearer {admin_token}"})

    assert user_res.status_code == 403
    assert admin_res.status_code == 200


def test_lg_diag_is_public_for_cross_origin_probe(tmp_path: Path) -> None:
    app = create_app(_config(tmp_path))

    with TestClient(app) as client:
        res = client.get("/tools/api/lg/diag/ping")

    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.headers["x-request-id"]


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({
        "app": {
            "listen": "127.0.0.1:8080",
            "basePath": "/tools",
            "static_dir": str(tmp_path / "dist"),
        },
        "security": {
            "session_secret": "secret",
            "sensitive_action_password": "password",
        },
        "sub2api": {
            "base_url": "https://sub2api.example.com",
            "admin_api_key": "key",
        },
        "storage": {
            "sqlite_dsn": str(tmp_path / "tools.db"),
        },
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
