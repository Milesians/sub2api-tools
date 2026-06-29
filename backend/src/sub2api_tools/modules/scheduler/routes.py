from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...shared.context import get_context
from ...shared.deps import require_roles
from ...shared.security import Session
from .core.codex_invite import InviteResetError


router = APIRouter()


class SchedulerControlRequest(BaseModel):
    paused: bool
    sensitive_password: str


class SensitiveRequest(BaseModel):
    sensitive_password: str


class InviteRequest(BaseModel):
    emails: list[str]
    sensitive_password: str


class ConsumeRequest(BaseModel):
    credit_id: str
    sensitive_password: str


@router.get("/scheduler/snapshot")
def scheduler_snapshot(session: Session = Depends(require_roles("admin"))) -> dict[str, Any]:
    return get_context().scheduler.snapshot()


@router.post("/scheduler/refresh")
async def scheduler_refresh(req: SensitiveRequest, session: Session = Depends(require_roles("admin"))) -> dict[str, Any]:
    _verify_sensitive(req.sensitive_password)
    return await get_context().scheduler.run_once()


@router.post("/scheduler/accounts/{account_id}/control")
def scheduler_control(
    account_id: int,
    req: SchedulerControlRequest,
    session: Session = Depends(require_roles("admin")),
) -> dict[str, Any]:
    _verify_sensitive(req.sensitive_password)
    return get_context().scheduler.set_paused(account_id, req.paused)


@router.get("/scheduler/accounts/{account_id}/codex/invite-reset/status")
def invite_status(account_id: int, session: Session = Depends(require_roles("admin"))) -> dict[str, Any]:
    try:
        return get_context().scheduler.invite().status(account_id)
    except InviteResetError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/scheduler/accounts/{account_id}/codex/invite-reset/invite")
def invite_send(
    account_id: int,
    req: InviteRequest,
    session: Session = Depends(require_roles("admin")),
) -> dict[str, Any]:
    _verify_sensitive(req.sensitive_password)
    try:
        return get_context().scheduler.invite().send_invite(account_id, req.emails)
    except InviteResetError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/scheduler/accounts/{account_id}/codex/invite-reset/consume")
def invite_consume(
    account_id: int,
    req: ConsumeRequest,
    session: Session = Depends(require_roles("admin")),
) -> dict[str, Any]:
    _verify_sensitive(req.sensitive_password)
    try:
        return get_context().scheduler.invite().consume(account_id, req.credit_id)
    except InviteResetError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


def _verify_sensitive(value: str) -> None:
    expected = get_context().cfg.security.sensitive_action_password
    if not expected or value != expected:
        raise HTTPException(status_code=403, detail="invalid sensitive action password")
