from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .core.api import AdminAPI
from .core.codex_invite import CodexInviteReset, InviteResetError
from .core.config import Config as CoreConfig
from .core.runner import _touch_heartbeat, tick
from .core.store import Store
from ...shared.config import Config


class SchedulerService:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.core_cfg = core_config(cfg)
        self.api = AdminAPI(self.core_cfg.base_url, self.core_cfg.admin_key)
        self._task: asyncio.Task[None] | None = None
        if self.cfg.scheduler.enabled:
            Store(self.core_cfg.db_path).close()

    def start(self) -> None:
        if not self.cfg.scheduler.enabled or not self.cfg.scheduler.auto_start or self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def run_once(self) -> dict[str, Any]:
        terminal_active = await asyncio.to_thread(self._tick)
        return {
            "ok": True,
            "terminal_active": terminal_active,
            "triggered_at": _iso(datetime.now(UTC)),
        }

    def snapshot(self, decision_limit: int = 80) -> dict[str, Any]:
        if not self.cfg.scheduler.enabled:
            return {
                "generated_at": _iso(datetime.now(UTC)),
                "config": {
                    "platform": self.core_cfg.platform,
                    "account_name_pattern": self.core_cfg.account_name_pattern,
                    "db_path": self.core_cfg.db_path,
                    "heartbeat_file": self.core_cfg.heartbeat_file,
                },
                "heartbeat": _heartbeat(self.core_cfg.heartbeat_file),
                "summary": _summary([], []),
                "accounts": [],
                "decisions": [],
            }
        return snapshot(
            self.core_cfg.db_path,
            self.core_cfg.heartbeat_file,
            decision_limit,
            self.core_cfg.platform,
            self.core_cfg.account_name_pattern,
        )

    def set_paused(self, account_id: int, paused: bool) -> dict[str, Any]:
        store = Store(self.core_cfg.db_path)
        try:
            control = store.set_account_paused(account_id, paused, datetime.now(UTC))
        finally:
            store.close()
        return {
            "account_id": control.account_id,
            "scheduler_paused": control.paused,
            "scheduler_control_updated_at": _iso(control.updated_at),
        }

    def invite(self) -> CodexInviteReset:
        return CodexInviteReset(self.api, self.cfg.scheduler.codex_invite_reset_base_url)

    async def _loop(self) -> None:
        while True:
            terminal_active = False
            try:
                terminal_active = await asyncio.to_thread(self._tick)
            except Exception:
                import logging

                logging.getLogger(__name__).exception("scheduler tick failed")
            minutes = self.core_cfg.terminal_interval_minutes if terminal_active else self.core_cfg.interval_minutes
            await asyncio.sleep(max(1, minutes) * 60)

    def _tick(self) -> bool:
        store = Store(self.core_cfg.db_path)
        try:
            terminal_active = tick(self.core_cfg, self.api, store)
            _touch_heartbeat(self.core_cfg.heartbeat_file)
            return terminal_active
        finally:
            store.close()


def core_config(cfg: Config) -> CoreConfig:
    scheduler = cfg.scheduler
    core = CoreConfig()
    for name, value in scheduler.__dict__.items():
        if hasattr(core, name):
            setattr(core, name, value)
    core.base_url = cfg.sub2api.base_url
    core.admin_key = cfg.sub2api.admin_api_key
    core.db_path = cfg.storage.sqlite_dsn
    core.heartbeat_file = scheduler.heartbeat_file
    return core


def snapshot(
    db_path: str,
    heartbeat_file: str,
    decision_limit: int,
    platform: str,
    account_name_pattern: str,
) -> dict[str, Any]:
    Store(db_path).close()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        decisions = _rows(
            conn,
            """
            SELECT * FROM decision_log
            ORDER BY decided_at DESC, id DESC
            LIMIT ?
            """,
            (decision_limit,),
        )
        accounts = _rows(
            conn,
            """
            SELECT
              s.account_id,
              COALESCE(d.account_name, '') AS name,
              s.last_priority,
              s.current_priority,
              s.current_load_factor,
              s.last_7d_used,
              s.last_5h_used,
              s.last_7d_reset_at,
              s.last_sampled_at,
              s.hourly_burn_ewma,
              s.cooldown_until,
              COALESCE(c.paused, 0) AS scheduler_paused,
              c.updated_at AS scheduler_control_updated_at,
              p.email,
              p.subscription_plan,
              p.subscription_status,
              p.subscription_expires_at,
              p.updated_at AS profile_updated_at,
              p.subscription_error,
              d.reason AS last_reason,
              d.current_priority AS last_current_priority,
              d.target_priority AS last_target_priority,
              d.current_load_factor AS last_current_load_factor,
              d.target_load_factor AS last_target_load_factor,
              d.target_now AS expected_7d_used,
              CASE
                WHEN d.target_now IS NOT NULL AND s.last_7d_used IS NOT NULL
                THEN d.target_now - s.last_7d_used
                ELSE NULL
              END AS expected_7d_gap,
              d.projected_end AS projected_7d_end,
              d.required_rate,
              d.recent_rate,
              d.remaining_hours,
              d.mode,
              d.drain_gap,
              d.drain_required_rate,
              d.drain_pressure,
              d.drain_level,
              d.deadline_hours,
              d.decided_at AS last_decided_at
            FROM account_state s
            LEFT JOIN account_control c ON c.account_id = s.account_id
            LEFT JOIN account_profile_cache p ON p.account_id = s.account_id
            LEFT JOIN (
              SELECT *
              FROM decision_log
              WHERE id IN (
                SELECT MAX(id)
                FROM decision_log
                GROUP BY account_id
              )
            ) d ON d.account_id = s.account_id
            ORDER BY s.updated_at DESC, s.account_id
            """,
        )
        return {
            "generated_at": _iso(datetime.now(UTC)),
            "config": {
                "platform": platform,
                "account_name_pattern": account_name_pattern,
                "db_path": db_path,
                "heartbeat_file": heartbeat_file,
            },
            "heartbeat": _heartbeat(heartbeat_file),
            "summary": _summary(decisions, accounts),
            "accounts": accounts,
            "decisions": [_with_changed(d) for d in decisions],
        }
    finally:
        conn.close()


def _rows(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def _summary(decisions: list[dict[str, Any]], accounts: list[dict[str, Any]]) -> dict[str, Any]:
    last_run_id = decisions[0]["run_id"] if decisions else None
    last_run = [d for d in decisions if d.get("run_id") == last_run_id]
    return {
        "account_count": len(accounts),
        "last_run_id": last_run_id,
        "last_decided_at": decisions[0]["decided_at"] if decisions else None,
        "last_run_decision_count": len(last_run),
        "last_run_changed_count": sum(1 for d in last_run if _is_changed(d)),
        "changed_account_count": sum(1 for a in accounts if a.get("last_current_priority") != a.get("last_target_priority")),
    }


def _heartbeat(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"exists": False, "path": path, "modified_at": None, "age_seconds": None}
    modified = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    return {
        "exists": True,
        "path": path,
        "modified_at": _iso(modified),
        "age_seconds": round((datetime.now(UTC) - modified).total_seconds()),
    }


def _with_changed(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "changed": _is_changed(row)}


def _is_changed(row: dict[str, Any]) -> bool:
    return (
        row.get("current_priority") != row.get("target_priority")
        or row.get("current_load_factor") != row.get("target_load_factor")
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
