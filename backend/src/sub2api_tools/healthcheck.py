from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import yaml


def main() -> None:
    cfg_path = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/config.yaml")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    app = data.get("app") or {}
    listen = str(app.get("listen") or "0.0.0.0:8080")
    base_path = str(app.get("basePath") or app.get("base_path") or "/tools").strip("/")
    port = listen.rsplit(":", 1)[-1]
    api_base_path = f"/{base_path}/api" if base_path else "/api"
    url = f"http://127.0.0.1:{port}{api_base_path}/health"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
