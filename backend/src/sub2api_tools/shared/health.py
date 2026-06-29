from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from .context import get_context


router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    cfg = get_context().cfg
    heartbeat = Path(cfg.scheduler.heartbeat_file)
    return {
        "ok": True,
        "scheduler_enabled": cfg.scheduler.enabled,
        "scheduler_auto_start": cfg.scheduler.auto_start,
        "scheduler_heartbeat_exists": heartbeat.is_file(),
    }
