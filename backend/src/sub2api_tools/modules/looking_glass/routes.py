from __future__ import annotations

import os
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ...shared.config import api_base_path, feature_url_path, lg_probe_paths
from ...shared.context import get_context
from ...shared.deps import require_roles
from ...shared.security import Session


router = APIRouter()
_reports: dict[str, dict[str, Any]] = {}


@router.get("/lg/config")
def config(session: Session = Depends(require_roles("user", "admin"))) -> dict[str, Any]:
    ctx = get_context()
    return {
        "public_path": feature_url_path(ctx.cfg, "looking-glass"),
        "probe": _probe_config(),
        "user": {"id": session.user_id, "role": session.role},
    }


@router.get("/lg/entrypoints")
def entrypoints(session: Session = Depends(require_roles("user", "admin"))) -> dict[str, Any]:
    ctx = get_context()
    settings = _settings()
    raw = []
    default_url = _first(settings, "base_url", "baseUrl", "api_base_url", "apiBaseUrl")
    if default_url:
        raw.append({"source": "admin_default", "name": "默认入口", "base_url": default_url})
    for item in settings.get("custom_endpoints") or settings.get("customEndpoints") or []:
        base_url = _first(item, "base_url", "baseUrl", "endpoint")
        if base_url:
            raw.append({
                "source": "admin_custom",
                "name": item.get("name") or "自定义入口",
                "base_url": base_url,
                "description": item.get("description") or "",
            })
    seen: set[str] = set()
    items = []
    for item in raw:
        base_url = str(item["base_url"]).rstrip("/")
        if not base_url or base_url in seen:
            continue
        seen.add(base_url)
        endpoint_id = hashlib.sha256(base_url.encode("utf-8")).hexdigest()[:12]
        public_path = feature_url_path(ctx.cfg, "looking-glass")
        lg_base_url = urljoin(base_url + "/", public_path.lstrip("/"))
        probe_base_url = urljoin(base_url + "/", api_base_path(ctx.cfg).strip("/") + "/lg")
        items.append({
            "id": endpoint_id,
            "endpoint_public_id": endpoint_id,
            "source": item["source"],
            "name": item["name"],
            "description": item.get("description", ""),
            "base_url": base_url,
            "public_path": public_path,
            "lg_base_url": lg_base_url.rstrip("/"),
            "probe_base_url": probe_base_url.rstrip("/"),
        })
    return {
        "source": "admin_api",
        "public_path": feature_url_path(ctx.cfg, "looking-glass"),
        "entrypoints": items,
        "entrypoint_count": len(items),
        "probe": _probe_config(),
        "user": {"id": session.user_id, "role": session.role},
    }


@router.post("/lg/reports")
async def create_report(request: Request, session: Session = Depends(require_roles("user", "admin"))) -> dict[str, Any]:
    payload = await request.json()
    report_id = "lg_" + secrets.token_urlsafe(12)
    report = {
        "report_id": report_id,
        "user_id": session.user_id,
        "created_at": int(time.time()),
        "payload": payload,
    }
    _reports[report_id] = report
    return {"report_id": report_id, "report": report}


@router.get("/lg/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    report = _reports.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@router.get("/lg/diag/meta")
def diag_meta() -> dict[str, Any]:
    ctx = get_context()
    return {
        "ok": True,
        "public_path": feature_url_path(ctx.cfg, "looking-glass"),
        "probe": _probe_config(),
    }


@router.get("/lg/diag/ping")
def diag_ping(response: Response) -> dict[str, Any]:
    response.headers["X-Request-Id"] = secrets.token_hex(8)
    return {"ok": True, "ts": time.time()}


@router.get("/lg/diag/headers")
def diag_headers(request: Request, response: Response) -> dict[str, Any]:
    response.headers["X-Request-Id"] = secrets.token_hex(8)
    host = request.client.host if request.client else ""
    return {
        "ok": True,
        "origin_peer": {
            "ip": host,
        },
        "headers": {
            "host": request.headers.get("host", ""),
            "user_agent": request.headers.get("user-agent", ""),
        },
    }


@router.get("/lg/diag/blob")
def diag_blob(size: str = "64k") -> Response:
    byte_count = _blob_size(size)
    return Response(
        os.urandom(byte_count),
        media_type="application/octet-stream",
        headers={"X-Request-Id": secrets.token_hex(8)},
    )


@router.post("/lg/diag/upload")
async def diag_upload(request: Request, response: Response) -> dict[str, Any]:
    response.headers["X-Request-Id"] = secrets.token_hex(8)
    body = await request.body()
    return {"ok": True, "bytes": len(body)}


@router.get("/lg/diag/stream")
def diag_stream(events: int = 20, interval_ms: int = 200, bytes: int = 32) -> StreamingResponse:
    async def stream():
        import asyncio

        payload = "x" * max(1, min(bytes, 1024))
        for index in range(max(1, min(events, 200))):
            yield f"event: sample\ndata: {index}:{payload}\n\n".encode("utf-8")
            await asyncio.sleep(max(0, min(interval_ms, 5000)) / 1000)
        yield b"event: done\ndata: ok\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Request-Id": secrets.token_hex(8)},
    )


def _settings() -> dict[str, Any]:
    ctx = get_context()
    resp = ctx.sub2api.admin_get(ctx.cfg.sub2api.settings_path)
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") if isinstance(body, dict) and "data" in body else body
    return data if isinstance(data, dict) else {}


def _probe_config() -> dict[str, Any]:
    cfg = get_context().cfg.looking_glass
    return {
        "browser_repeat": cfg.browser_repeat,
        "browser_timeout_ms": cfg.browser_timeout_ms,
        "paths": lg_probe_paths(),
        "blob_sizes": cfg.blob_sizes,
        "stream": {
            "events": cfg.stream.events,
            "interval_ms": cfg.stream.interval_ms,
            "bytes": cfg.stream.bytes,
        },
    }


def _first(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _blob_size(value: str) -> int:
    value = value.strip().lower()
    units = {"k": 1024, "m": 1024 * 1024}
    if value[-1:] in units:
        return max(1, min(int(float(value[:-1]) * units[value[-1]]), 20 * 1024 * 1024))
    return max(1, min(int(value), 20 * 1024 * 1024))
