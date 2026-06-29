from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class Session:
    user_id: str
    username: str
    email: str
    role: str
    theme: str = ""
    lang: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def issue_token(session: Session, secret: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "sub": session.user_id,
        "username": session.username,
        "email": session.email,
        "role": session.role,
        "theme": session.theme,
        "lang": session.lang,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def verify_token(token: str, secret: str) -> Session:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")
    signing_input = f"{parts[0]}.{parts[1]}"
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    actual = _b64_decode(parts[2])
    if not hmac.compare_digest(expected, actual):
        raise ValueError("invalid token signature")
    payload = json.loads(_b64_decode(parts[1]).decode("utf-8"))
    if int(payload.get("exp") or 0) < int(time.time()):
        raise ValueError("token expired")
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise ValueError("token missing subject")
    role = _role(payload)
    return Session(
        user_id=user_id,
        username=str(payload.get("username") or ""),
        email=str(payload.get("email") or ""),
        role=role,
        theme=str(payload.get("theme") or ""),
        lang=str(payload.get("lang") or ""),
    )


def user_role(user: dict[str, Any]) -> str:
    role = str(user.get("role") or "").strip().lower()
    is_admin = bool(user.get("is_admin"))
    if is_admin or role in {"admin", "root", "owner"}:
        return "admin"
    return "user"


def origin_allowed(origin: str, allowed_origins: Sequence[str]) -> bool:
    if not allowed_origins:
        return True
    parsed_origin = _split_origin(origin)
    if parsed_origin is None:
        return False
    return any(_origin_matches(parsed_origin, allowed) for allowed in allowed_origins)


def host_allowed(host: str, allowed_origins: Sequence[str]) -> bool:
    if not allowed_origins:
        return True
    clean_host = _clean_host(host)
    if not clean_host:
        return False
    return any(_host_matches(clean_host, allowed) for allowed in allowed_origins)


def origin_allow_regex(allowed_origins: Sequence[str]) -> str:
    if not allowed_origins:
        return ".*"
    return "^(?:" + "|".join(_origin_regex(origin) for origin in allowed_origins) + ")$"


def origin_from_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or "*" in host:
        return ""
    port = _port(parsed)
    if port == _default_port(parsed.scheme):
        port = None
    return _format_origin(parsed.scheme, host, port)


def _role(payload: dict[str, Any]) -> str:
    role = str(payload.get("role") or "user").strip().lower()
    return "admin" if role == "admin" else "user"


def _split_origin(value: str) -> tuple[str, str, int | None] | None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return None
    port = _port(parsed)
    if port == _default_port(parsed.scheme):
        port = None
    return parsed.scheme, host, port


def _origin_matches(origin: tuple[str, str, int | None], allowed: str) -> bool:
    allowed_origin = _split_origin(allowed)
    if allowed_origin is None:
        return False
    scheme, host, port = origin
    allowed_scheme, allowed_host, allowed_port = allowed_origin
    if scheme != allowed_scheme or port != allowed_port:
        return False
    if allowed_host.startswith("*."):
        suffix = allowed_host[2:]
        return host != suffix and host.endswith(f".{suffix}")
    return host == allowed_host


def _host_matches(host: str, allowed: str) -> bool:
    allowed_origin = _split_origin(allowed)
    if allowed_origin is None:
        return False
    _, allowed_host, _ = allowed_origin
    if allowed_host.startswith("*."):
        suffix = allowed_host[2:]
        return host != suffix and host.endswith(f".{suffix}")
    return host == allowed_host


def _origin_regex(origin: str) -> str:
    parsed = _split_origin(origin)
    if parsed is None:
        return re.escape(origin)
    scheme, host, port = parsed
    port_part = "" if port is None else f":{port}"
    if host.startswith("*."):
        return f"{re.escape(scheme)}://(?:[^./:]+\\.)+{re.escape(host[2:])}{re.escape(port_part)}"
    return re.escape(_format_origin(scheme, host, port))


def _format_origin(scheme: str, host: str, port: int | None) -> str:
    return f"{scheme}://{host}{'' if port is None else f':{port}'}"


def _port(parsed: Any) -> int | None:
    try:
        return parsed.port
    except ValueError:
        return None


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _clean_host(value: str) -> str:
    parsed = urlparse(f"//{value.strip()}")
    host = (parsed.hostname or "").lower().rstrip(".")
    return "" if "*" in host else host


def _b64_json(value: dict[str, Any]) -> str:
    return _b64(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
