from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config
from .sub2api import Sub2APIClient


@dataclass
class AppContext:
    cfg: Config
    config_path: Path
    sub2api: Sub2APIClient
    scheduler: Any | None = None


app_context: AppContext | None = None


def set_context(ctx: AppContext) -> None:
    global app_context
    app_context = ctx


def get_context() -> AppContext:
    if app_context is None:
        raise RuntimeError("app context is not initialized")
    return app_context
