from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sub2api_tools.shared.config import Sub2APIConfig, load_config
from sub2api_tools.shared.security import Session, host_allowed, issue_token, origin_allowed, verify_token
from sub2api_tools.shared.sub2api import Sub2APIClient


def test_load_config_requires_visibility_list(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    data = _base_config(tmp_path)
    data["features"][0]["visibility"] = "admin"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="visibility must be a non-empty list"):
        load_config(path)


def test_load_config_accepts_single_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(_base_config(tmp_path)), encoding="utf-8")

    cfg = load_config(path)

    assert cfg.app.base_path == "/tools"
    assert cfg.features[0].path == "/lg"
    assert cfg.features[0].visibility == ["user", "admin"]
    assert cfg.security.allowed_origins == []
    assert cfg.storage.sqlite_dsn == str(tmp_path / "tools.db")


def test_load_config_rejects_old_origin_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    data = _base_config(tmp_path)
    data["security"]["allowed_parent_origins"] = ["https://sub2api.example.com"]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="security.allowed_parent_origins was replaced by security.allowed_origins"):
        load_config(path)


def test_load_config_rejects_sub2api_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    data = _base_config(tmp_path)
    data["sub2api"]["userinfo_path"] = "/api/v1/auth/me"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="sub2api.userinfo_path is fixed by the application"):
        load_config(path)


def test_origin_matcher_supports_wildcards() -> None:
    allowed = ["https://sub2api.example.com", "https://*.sub2api.example.com"]

    assert origin_allowed("https://sub2api.example.com", allowed)
    assert origin_allowed("https://admin.sub2api.example.com", allowed)
    assert origin_allowed("https://a.b.sub2api.example.com", allowed)
    assert host_allowed("admin.sub2api.example.com", allowed)
    assert not origin_allowed("https://badsub2api.example.com", allowed)
    assert not origin_allowed("http://admin.sub2api.example.com", allowed)


def test_jwt_session_round_trip() -> None:
    session = Session(user_id="42", username="alice", email="", role="admin")
    token = issue_token(session, "secret", 60)

    parsed = verify_token(token, "secret")

    assert parsed.user_id == "42"
    assert parsed.role == "admin"
    with pytest.raises(ValueError):
        verify_token(token, "wrong")


def test_sub2api_verify_user_uses_fixed_auth_me_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    client = Sub2APIClient(Sub2APIConfig(base_url="https://sub2api.example.com", admin_api_key="key"))

    class Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": {"id": "42", "role": "user"}}

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        return Resp()

    monkeypatch.setattr(client.session, "get", fake_get)

    user = client.verify_user("token")

    assert user["id"] == "42"
    assert calls[0][0] == "https://sub2api.example.com/api/v1/auth/me"


def _base_config(tmp_path: Path) -> dict:
    return {
        "app": {
            "listen": "127.0.0.1:8080",
            "basePath": "/tools",
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
            }
        ],
    }
