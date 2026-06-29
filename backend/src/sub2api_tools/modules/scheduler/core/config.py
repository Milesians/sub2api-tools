"""Scheduler strategy config.

The merged project reads application configuration from the top-level YAML only.
This module intentionally keeps just the dataclass shape required by the copied
scheduler policy/runner code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    base_url: str = ""
    admin_key: str = ""

    platform: str = "anthropic"
    account_name_pattern: str = ""

    interval_minutes: int = 60
    target_7d_utilization: float = 97.0
    enable_5h_guard: bool = False
    pacing_target_7d_utilization: float = 97.0
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

    db_path: str = "/data/scheduler.db"
    heartbeat_file: str = "/data/last_tick"
    ui_enabled: bool = False
    ui_host: str = "0.0.0.0"
    ui_port: int = 18080
    ui_frame_ancestor_hosts: tuple[str, ...] = ()
    sample_retention_days: int = 14
    decision_retention_days: int = 30
    state_retention_days: int = 30

    window_hours: float = 168.0
    openai_subscription_base_url: str = "https://chatgpt.com/backend-api"
    account_profile_ttl_minutes: int = 720
    account_profile_refresh_enabled: bool = True

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

