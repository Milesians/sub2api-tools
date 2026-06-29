from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from .context import get_context
from .deps import current_session, visible_features
from .security import Session, host_allowed, issue_token, origin_allowed, origin_from_url, user_role


class BootstrapRequest(BaseModel):
    user_id: str = ""
    ticket: str = ""
    token: str = ""
    legacy_token: str = ""
    theme: str = ""
    lang: str = ""
    ui_mode: str = ""
    src_host: str = ""
    src_url: str = ""


router = APIRouter()


@router.post("/auth/bootstrap")
def bootstrap(req: BootstrapRequest, origin: str = Header(default="")) -> dict[str, Any]:
    ctx = get_context()
    _check_allowed_origin(req, origin)
    credential = req.ticket or req.token or req.legacy_token
    if not credential:
        raise HTTPException(status_code=401, detail="credential is required")
    try:
        user = ctx.sub2api.verify_user(credential)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="token verification failed") from exc

    actual_id = str(user.get("id") or user.get("user_id") or "").strip()
    expected_id = req.user_id.strip()
    if expected_id and actual_id != expected_id:
        raise HTTPException(status_code=403, detail="user_id does not match token")

    session = Session(
        user_id=actual_id,
        username=str(user.get("username") or user.get("name") or ""),
        email=str(user.get("email") or ""),
        role=user_role(user),
        theme=req.theme,
        lang=req.lang,
    )
    token = issue_token(session, ctx.cfg.security.session_secret, ctx.cfg.security.session_ttl_seconds)
    return _session_payload(session, token)


def _check_allowed_origin(req: BootstrapRequest, origin: str) -> None:
    allowed_origins = get_context().cfg.security.allowed_origins
    if not allowed_origins:
        return
    candidates = [origin.strip(), origin_from_url(req.src_url)]
    if any(candidate and origin_allowed(candidate, allowed_origins) for candidate in candidates):
        return
    if req.src_host and host_allowed(req.src_host, allowed_origins):
        return
    raise HTTPException(status_code=403, detail="origin is not allowed")


@router.get("/auth/me")
def me(session: Session = Depends(current_session)) -> dict[str, Any]:
    return _session_payload(session)


def _session_payload(session: Session, token: str | None = None) -> dict[str, Any]:
    ctx = get_context()
    features = [_feature_payload(feature) for feature in visible_features(session.role)]
    payload = {
        "session_token": token,
        "session_type": session.role,
        "user": {
            "id": session.user_id,
            "username": session.username,
            "email": session.email,
            "role": session.role,
        },
        "app": {
            "basePath": ctx.cfg.app.base_path,
            "theme": session.theme,
            "lang": session.lang,
        },
        "features": features,
    }
    if token is None:
        payload.pop("session_token")
    return payload


def _feature_payload(feature: Any) -> dict[str, Any]:
    return {
        "id": feature.id,
        "name": feature.name,
        "path": feature.path,
        "visibility": feature.visibility,
    }
