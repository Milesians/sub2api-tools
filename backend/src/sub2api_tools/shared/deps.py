from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

from .config import FeatureConfig
from .context import get_context
from .security import Session, verify_token


def current_session(authorization: str = Header(default="")) -> Session:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    ctx = get_context()
    try:
        return verify_token(token, ctx.cfg.security.session_secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_roles(*roles: str) -> Callable[[Session], Session]:
    allowed = set(roles)

    def dependency(session: Session = Depends(current_session)) -> Session:
        if session.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return session

    return dependency


def visible_features(role: str) -> list[FeatureConfig]:
    cfg = get_context().cfg
    return [
        feature for feature in cfg.features
        if feature.enabled and role in set(feature.visibility)
    ]


def feature_by_id(feature_id: str) -> FeatureConfig | None:
    for feature in get_context().cfg.features:
        if feature.id == feature_id and feature.enabled:
            return feature
    return None


def _bearer(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return ""
