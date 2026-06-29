from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .modules.looking_glass.routes import router as lg_router
from .modules.scheduler.routes import router as scheduler_router
from .modules.scheduler.service import SchedulerService
from .shared.auth_routes import router as auth_router
from .shared.config import Config, api_base_path, join_path, load_config
from .shared.context import AppContext, set_context
from .shared.health import router as health_router
from .shared.security import origin_allow_regex
from .shared.sub2api import Sub2APIClient


def create_app(config_path: str | Path = "config.yaml") -> FastAPI:
    cfg = load_config(config_path)
    scheduler = SchedulerService(cfg)
    ctx = AppContext(
        cfg=cfg,
        config_path=Path(config_path),
        sub2api=Sub2APIClient(cfg.sub2api),
        scheduler=scheduler,
    )
    set_context(ctx)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler.start()
        yield
        await scheduler.stop()

    app = FastAPI(title="sub2api tools", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=origin_allow_regex(cfg.security.allowed_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=["X-Request-Id", "Content-Length"],
    )
    api_prefix = api_base_path(cfg)
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(health_router, prefix=api_prefix)
    app.include_router(lg_router, prefix=api_prefix)
    app.include_router(scheduler_router, prefix=api_prefix)
    _mount_frontend(app, cfg)
    return app


def _mount_frontend(app: FastAPI, cfg: Config) -> None:
    static_dir = Path(cfg.app.static_dir)
    if not static_dir.is_absolute():
        static_dir = Path.cwd() / static_dir
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount(join_path(cfg.app.base_path, "/assets"), StaticFiles(directory=assets), name="assets")

    @app.get("{path:path}", include_in_schema=False)
    def frontend(path: str, request: Request):
        request_path = "/" + path.strip("/")
        if request_path == "/" and cfg.app.base_path != "/":
            raise HTTPException(status_code=404)
        if not _under_base_path(request_path, cfg.app.base_path):
            raise HTTPException(status_code=404)
        if _under_base_path(request_path, api_base_path(cfg)):
            raise HTTPException(status_code=404)
        index = static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=503, detail="frontend is not built")
        return FileResponse(index)


def _under_base_path(request_path: str, base_path: str) -> bool:
    return base_path == "/" or request_path == base_path or request_path.startswith(f"{base_path}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="sub2api tools service")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    host, port = _listen(cfg.app.listen)
    uvicorn.run(create_app(args.config), host=host, port=port)


def _listen(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    return host or "0.0.0.0", int(port or "8080")
