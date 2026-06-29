from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


Role = str

FEATURE_PATHS = {
    "looking-glass": "/lg",
    "account-scheduler": "/admin/scheduler",
}
FEATURE_NAMES = {
    "looking-glass": "网络诊断",
    "account-scheduler": "账号调度",
}
LG_PROBE_PATHS = {
    "ping": "/diag/ping",
    "blob": "/diag/blob",
    "upload": "/diag/upload",
    "stream": "/diag/stream",
}


@dataclass
class AppConfig:
    listen: str = "0.0.0.0:8080"
    env: str = "production"
    base_path: str = "/tools"
    trust_forwarded_headers: bool = True
    static_dir: str = "frontend/dist"


@dataclass
class SecurityConfig:
    session_secret: str = "change_this_session_secret"
    session_ttl_seconds: int = 1800
    allowed_origins: list[str] = field(default_factory=list)
    sensitive_action_password: str = "change_this_sensitive_password"


@dataclass
class Sub2APIConfig:
    base_url: str = ""
    admin_api_key: str = ""
    endpoint_cache_ttl_seconds: int = 60


@dataclass
class StorageConfig:
    sqlite_dsn: str = "/data/sub2api-tools.db"


@dataclass
class FeatureConfig:
    id: str
    name: str = ""
    visibility: list[Role] = field(default_factory=list)
    enabled: bool = True
    path: str = ""


@dataclass
class StreamConfig:
    events: int = 20
    interval_ms: int = 200
    bytes: int = 32


@dataclass
class LookingGlassConfig:
    browser_repeat: int = 20
    browser_timeout_ms: int = 8000
    blob_sizes: list[str] = field(default_factory=lambda: ["64k", "1m", "5m", "20m"])
    stream: StreamConfig = field(default_factory=StreamConfig)


@dataclass
class SchedulerConfig:
    enabled: bool = True
    auto_start: bool = True
    platform: str = "openai"
    account_name_pattern: str = ""
    interval_minutes: int = 15
    heartbeat_file: str = "/data/scheduler-last-tick"
    pacing_target_7d_utilization: float = 97.0
    target_7d_utilization: float = 97.0
    enable_5h_guard: bool = False
    drain_target_7d_utilization: float = 99.4
    hard_cap_7d_utilization: float = 99.8
    hard_cap_5h_utilization: float = 98.0
    protect_7d_utilization: float = 97.0
    max_boost_ratio: float = 0.15
    mild_boost_ratio: float = 0.35
    max_boost_min: int = 1
    boost_load_factor_multiplier: float = 3.0
    mild_load_factor_multiplier: float = 2.0
    max_load_factor: int = 100
    max_active_probes_per_round: int = 10
    usage_stale_threshold_minutes: int = 90
    cooldown_minutes: int = 60
    safe_tail_hours: float = 2.0
    warmup_hours: float = 24.0
    strong_score_threshold: float = 3.0
    strong_min_required_rate: float = 0.6
    mild_score_threshold: float = 1.0
    ahead_band_pp: float = 3.0
    cooldown_abs_rate_pph: float = 1.2
    cooldown_required_rate_multiplier: float = 2.5
    cooldown_near_target_band_pp: float = 2.0
    will_hit_goal_soon_hours: float = 5.0
    emergency_window_hours: float = 12.0
    emergency_projected_end_threshold: float = 94.0
    emergency_final_gap_pp: float = 5.0
    emergency_rate_gap_pph: float = 0.8
    terminal_drain_enabled: bool = True
    terminal_window_hours: float = 36.0
    terminal_final_margin_hours: float = 0.25
    terminal_min_runway_hours: float = 0.25
    terminal_strong_gap_pp: float = 1.5
    terminal_mild_gap_pp: float = 0.4
    terminal_strong_required_rate_pph: float = 0.35
    terminal_mild_required_rate_pph: float = 0.10
    terminal_strong_pressure: float = 1.8
    terminal_mild_pressure: float = 0.9
    terminal_done_band_pp: float = 0.10
    terminal_min_recent_rate_pph: float = 0.05
    terminal_dynamic_load_factor_enabled: bool = True
    terminal_strong_load_factor_multiplier: float = 4.0
    terminal_mild_load_factor_multiplier: float = 2.5
    terminal_normal_load_factor_multiplier: float = 1.5
    terminal_max_load_factor: int = 100
    terminal_usage_stale_threshold_minutes: int = 20
    terminal_max_active_probes_per_round: int = 50
    terminal_active_probe_ratio: float = 0.50
    terminal_min_active_probes_per_round: int = 20
    terminal_interval_minutes: int = 15
    priority_bands: tuple[int, ...] = (1010, 1030, 1050, 1070, 1099)
    sample_retention_days: int = 14
    decision_retention_days: int = 30
    state_retention_days: int = 30
    window_hours: float = 168.0
    openai_subscription_base_url: str = "https://chatgpt.com/backend-api"
    account_profile_ttl_minutes: int = 720
    account_profile_refresh_enabled: bool = True
    codex_invite_reset_base_url: str = "https://chatgpt.com/backend-api"

    @property
    def band_boost(self) -> int:
        return self.priority_bands[0]

    @property
    def band_mild(self) -> int:
        return self.priority_bands[1]

    @property
    def band_normal(self) -> int:
        return self.priority_bands[2]

    @property
    def band_protect(self) -> int:
        return self.priority_bands[3]

    @property
    def band_floor(self) -> int:
        return self.priority_bands[4]


@dataclass
class Config:
    app: AppConfig = field(default_factory=AppConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    sub2api: Sub2APIConfig = field(default_factory=Sub2APIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    features: list[FeatureConfig] = field(default_factory=list)
    looking_glass: LookingGlassConfig = field(default_factory=LookingGlassConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)


def load_config(path: str | Path = "config.yaml") -> Config:
    data = _read_yaml(path)
    cfg = Config(
        app=_app_config(data.get("app", {})),
        security=_security_config(data.get("security", {})),
        sub2api=_sub2api_config(data.get("sub2api", {})),
        storage=_build(StorageConfig, data.get("storage", {})),
        features=[_feature(item) for item in data.get("features", [])],
        looking_glass=_looking_glass(data.get("looking_glass", {})),
        scheduler=_scheduler(data.get("scheduler", {})),
    )
    _normalize(cfg)
    return cfg


def api_base_path(cfg: Config) -> str:
    return join_path(cfg.app.base_path, "/api")


def feature_url_path(cfg: Config, feature_id: str) -> str:
    return join_path(cfg.app.base_path, feature_path(feature_id))


def feature_path(feature_id: str) -> str:
    try:
        return FEATURE_PATHS[feature_id]
    except KeyError as exc:
        raise ValueError(f"unsupported feature id: {feature_id}") from exc


def lg_probe_paths() -> dict[str, str]:
    return dict(LG_PROBE_PATHS)


def join_path(base: str, path: str) -> str:
    clean_base = "" if base == "/" else base.rstrip("/")
    clean_path = "/" + path.strip("/")
    return clean_path if not clean_base else f"{clean_base}{clean_path}"


def _read_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"config file not found: {p}")
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("config root must be a mapping")
    return data


def _build(cls: type[Any], data: dict[str, Any]) -> Any:
    if not isinstance(data, dict):
        raise ValueError(f"{cls.__name__} must be a mapping")
    allowed = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in allowed})


def _app_config(data: dict[str, Any]) -> AppConfig:
    if not isinstance(data, dict):
        raise ValueError("AppConfig must be a mapping")
    clean = dict(data)
    if "basePath" in clean and "base_path" not in clean:
        clean["base_path"] = clean["basePath"]
    clean.pop("basePath", None)
    return _build(AppConfig, clean)


def _security_config(data: dict[str, Any]) -> SecurityConfig:
    if not isinstance(data, dict):
        raise ValueError("SecurityConfig must be a mapping")
    old_keys = sorted(set(data) & {"allowed_parent_origins", "allowed_src_hosts"})
    if old_keys:
        raise ValueError(f"security.{old_keys[0]} was replaced by security.allowed_origins")
    return _build(SecurityConfig, data)


def _sub2api_config(data: dict[str, Any]) -> Sub2APIConfig:
    if not isinstance(data, dict):
        raise ValueError("Sub2APIConfig must be a mapping")
    old_keys = sorted(set(data) & {"settings_path", "userinfo_path"})
    if old_keys:
        raise ValueError(f"sub2api.{old_keys[0]} is fixed by the application")
    return _build(Sub2APIConfig, data)


def _feature(data: dict[str, Any]) -> FeatureConfig:
    feature = _build(FeatureConfig, data)
    feature.path = feature_path(feature.id)
    if not feature.name:
        feature.name = FEATURE_NAMES.get(feature.id, feature.id)
    if not feature.visibility or not isinstance(feature.visibility, list):
        raise ValueError(f"feature {feature.id} visibility must be a non-empty list")
    invalid = sorted(set(feature.visibility) - {"user", "admin"})
    if invalid:
        raise ValueError(f"feature {feature.id} has invalid visibility: {', '.join(invalid)}")
    return feature


def _looking_glass(data: dict[str, Any]) -> LookingGlassConfig:
    if not isinstance(data, dict):
        raise ValueError("looking_glass must be a mapping")
    stream = _build(StreamConfig, data.get("stream", {}))
    clean = {k: v for k, v in data.items() if k != "stream"}
    cfg = _build(LookingGlassConfig, clean)
    cfg.stream = stream
    return cfg


def _scheduler(data: dict[str, Any]) -> SchedulerConfig:
    cfg = _build(SchedulerConfig, data)
    if isinstance(cfg.priority_bands, list):
        cfg.priority_bands = tuple(int(v) for v in cfg.priority_bands)
    return cfg


def _normalize(cfg: Config) -> None:
    cfg.app.base_path = _path(cfg.app.base_path, "app.basePath")
    if len(cfg.scheduler.priority_bands) != 5 or list(cfg.scheduler.priority_bands) != sorted(cfg.scheduler.priority_bands):
        raise ValueError("scheduler.priority_bands must contain 5 ascending values")
    if cfg.scheduler.platform not in {"openai", "anthropic"}:
        raise ValueError("scheduler.platform must be openai or anthropic")
    if not cfg.features:
        raise ValueError("features must not be empty")
    if cfg.security.session_ttl_seconds <= 0:
        raise ValueError("security.session_ttl_seconds must be positive")
    if not isinstance(cfg.security.allowed_origins, list):
        raise ValueError("security.allowed_origins must be a list")
    cfg.security.allowed_origins = [
        _origin(origin, f"security.allowed_origins[{index}]")
        for index, origin in enumerate(cfg.security.allowed_origins)
    ]
    if not cfg.sub2api.base_url:
        raise ValueError("sub2api.base_url is required")
    if not cfg.sub2api.admin_api_key:
        raise ValueError("sub2api.admin_api_key is required")
    cfg.sub2api.base_url = cfg.sub2api.base_url.rstrip("/")


def _path(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise ValueError(f"{name} must start with /")
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(f"{name} must be a path only")
    parts = [part for part in parsed.path.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValueError(f"{name} must not contain path traversal")
    normalized = "/" + "/".join(parts)
    return "/" if normalized == "/" else normalized.rstrip("/")


def _origin(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an http(s) origin")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not include path, query, or fragment")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"{name} must include host")
    wildcard = host.startswith("*.")
    if "*" in host[2 if wildcard else 0:]:
        raise ValueError(f"{name} wildcard is only allowed as a leading *.")
    netloc = host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return f"{parsed.scheme}://{'*.' if wildcard else ''}{netloc[2:] if wildcard else netloc}"
