"""8080 管理 API，供 Yobot 面板调用。"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..clanbattle import clanbattle_info
from ..clanbattle_setting import get_clanbattle_settings, reload_clanbattle_settings
from ..database.dal import pcr_date, pcr_sqla
from ..database.models import Account, ClanBattleMember, UserAccount
from ..knife_budget.service import knife_budget_service
from ..util.tools import load_config, write_config
from ..basedata import FilePath, NoticeType

router = APIRouter(prefix="/api")


def _pcr_date_str() -> str:
    return pcr_date(int(__import__("time").time())).strftime("%Y-%m-%d")


def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> None:
    settings = get_clanbattle_settings()
    if not x_admin_key or x_admin_key != settings.api_admin_key:
        raise HTTPException(status_code=403, detail="invalid admin key")


class ConfigPayload(BaseModel):
    admin_qq: Optional[int] = None
    captcha_retry_commands: Optional[List[str]] = None
    captcha_wait_sec: Optional[int] = None
    captcha_fallback_bdval: Optional[bool] = None
    yobot_base_url: Optional[str] = None
    yobot_enabled: Optional[bool] = None
    monitor_max_concurrent_groups: Optional[int] = None
    monitor_poll_min_sec: Optional[int] = None
    monitor_poll_max_sec: Optional[int] = None
    api_admin_key: Optional[str] = None


class AccountPayload(BaseModel):
    user_id: int
    platform: int = 0
    viewer_id: Optional[int] = None
    allow_others: int = 0
    account: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    refresh: Optional[str] = None


class BindingPayload(BaseModel):
    user_id: int
    account_id: int
    viewer_id: int
    alias: str = ""
    sort_order: int = 0
    is_active: bool = True


class ImportUsersPayload(BaseModel):
    group_id: int
    group_name: str = "公会"
    users: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/admin/config", dependencies=[Depends(verify_admin_key)])
async def get_config():
    s = get_clanbattle_settings()
    return {
        "admin_qq": s.admin_qq,
        "captcha_retry_commands": s.captcha_retry_commands,
        "captcha_wait_sec": s.captcha_wait_sec,
        "captcha_fallback_bdval": s.captcha_fallback_bdval,
        "yobot_base_url": s.yobot_base_url,
        "yobot_enabled": s.yobot_enabled,
        "monitor_max_concurrent_groups": s.monitor_max_concurrent_groups,
        "monitor_poll_min_sec": s.monitor_poll_min_sec,
        "monitor_poll_max_sec": s.monitor_poll_max_sec,
        "api_admin_key": s.api_admin_key,
        "api_port": s.api_port,
        "kcr_api_base": s.kcr_api_base,
        "web_public_host": s.web_public_host,
        "web_admin_username": s.web_admin_username,
    }


@router.put("/admin/config", dependencies=[Depends(verify_admin_key)])
async def put_config(payload: ConfigPayload):
    path = FilePath.clanbattle_setting.value
    raw = load_config(str(path)) or {}
    if payload.admin_qq is not None:
        raw["admin_qq"] = payload.admin_qq
    captcha = raw.setdefault("captcha", {})
    if payload.captcha_retry_commands is not None:
        captcha["retry_commands"] = payload.captcha_retry_commands
    if payload.captcha_wait_sec is not None:
        captcha["wait_sec"] = payload.captcha_wait_sec
    if payload.captcha_fallback_bdval is not None:
        captcha["fallback_bdval"] = payload.captcha_fallback_bdval
    yobot = raw.setdefault("yobot", {})
    if payload.yobot_base_url is not None:
        yobot["base_url"] = payload.yobot_base_url
    if payload.yobot_enabled is not None:
        yobot["enabled"] = payload.yobot_enabled
    monitor = raw.setdefault("monitor", {})
    if payload.monitor_max_concurrent_groups is not None:
        monitor["max_concurrent_groups"] = payload.monitor_max_concurrent_groups
    if payload.monitor_poll_min_sec is not None:
        monitor["poll_min_sec"] = payload.monitor_poll_min_sec
    if payload.monitor_poll_max_sec is not None:
        monitor["poll_max_sec"] = payload.monitor_poll_max_sec
    api = raw.setdefault("api", {})
    if payload.api_admin_key is not None:
        api["admin_key"] = payload.api_admin_key
    write_config(path, raw)
    reload_clanbattle_settings()
    return {"ok": True}


@router.get("/admin/accounts", dependencies=[Depends(verify_admin_key)])
async def list_accounts():
    accounts = await pcr_sqla.list_accounts()
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "platform": a.platform,
            "viewer_id": a.viewer_id,
            "allow_others": a.allow_others,
            "account": a.account,
            "password": a.password,
            "name": a.name,
            "refresh": a.refresh,
        }
        for a in accounts
    ]


@router.post("/admin/accounts", dependencies=[Depends(verify_admin_key)])
async def upsert_account(payload: AccountPayload):
    data = payload.dict(exclude_none=True)
    user_id = data.pop("user_id")
    await pcr_sqla.add_account(user_id, data)
    accounts = await pcr_sqla.query_account(user_id)
    return {"ok": True, "account": accounts[0].dict() if accounts else {}}


@router.delete("/admin/accounts/{user_id}", dependencies=[Depends(verify_admin_key)])
async def remove_account(user_id: int):
    await pcr_sqla.delete_account(user_id)
    return {"ok": True}


@router.get("/admin/bindings", dependencies=[Depends(verify_admin_key)])
async def list_bindings(user_id: Optional[int] = None):
    rows = await pcr_sqla.list_user_account_bindings(user_id)
    return [r.dict() for r in rows]


@router.post("/admin/bindings", dependencies=[Depends(verify_admin_key)])
async def add_binding(payload: BindingPayload):
    row = UserAccount(**payload.dict())
    await pcr_sqla.add_user_account(row)
    return {"ok": True}


@router.delete("/admin/bindings/{binding_id}", dependencies=[Depends(verify_admin_key)])
async def remove_binding(binding_id: int):
    await pcr_sqla.delete_user_account_binding(binding_id)
    return {"ok": True}


@router.post("/admin/users/import", dependencies=[Depends(verify_admin_key)])
async def import_users(payload: ImportUsersPayload):
    imported = 0
    for item in payload.users:
        qq = int(item.get("user_id") or item.get("qq") or 0)
        if not qq:
            continue
        await pcr_sqla.add_member(
            ClanBattleMember(
                group_id=payload.group_id,
                user_id=qq,
                group_name=item.get("group_name") or payload.group_name,
                priority=int(item.get("priority") or 0),
            )
        )
        if item.get("account"):
            await pcr_sqla.add_account(
                qq,
                {
                    "platform": int(item.get("platform") or 0),
                    "viewer_id": item.get("viewer_id"),
                    "account": item.get("account"),
                    "password": item.get("password"),
                    "name": item.get("name") or item.get("game_name"),
                    "allow_others": int(item.get("allow_others") or 0),
                },
            )
        if item.get("viewer_id") and item.get("account_id"):
            await pcr_sqla.add_user_account(
                UserAccount(
                    user_id=qq,
                    account_id=int(item["account_id"]),
                    viewer_id=int(item["viewer_id"]),
                    alias=str(item.get("alias") or ""),
                    sort_order=int(item.get("sort_order") or 0),
                )
            )
        imported += 1
    return {"ok": True, "imported": imported}


@router.get("/admin/monitor", dependencies=[Depends(verify_admin_key)])
async def monitor_status():
    result = []
    for gid, info in clanbattle_info.items():
        result.append(
            {
                "group_id": gid,
                "clan_name": info.clan_name,
                "monitor_user_id": info.user_id,
                "loop_num": info.loop_num,
                "active": bool(info.loop_check),
                "lap_num": info.lap_num,
                "period": info.period,
                "rank": info.rank,
            }
        )
    return result


@router.get("/admin/knife_budget", dependencies=[Depends(verify_admin_key)])
async def knife_budget_list():
    rows = await pcr_sqla.list_knife_budgets(_pcr_date_str())
    return [r.dict() for r in rows]


@router.post("/admin/knife_budget/{viewer_id}/reset", dependencies=[Depends(verify_admin_key)])
async def reset_knife_budget(viewer_id: int):
    await knife_budget_service.reset_budget(viewer_id)
    return {"ok": True}


@router.get("/guild/{group_id}/status", dependencies=[Depends(verify_admin_key)])
async def guild_status(group_id: int):
    clan_info = clanbattle_info.get(group_id)
    if not clan_info:
        raise HTTPException(404, "group not monitored")
    return {
        "group_id": group_id,
        "clan_name": clan_info.clan_name,
        "period": clan_info.period,
        "lap_num": clan_info.lap_num,
        "rank": clan_info.rank,
        "active": bool(clan_info.loop_check),
        "bosses": [
            {
                "order": b.order,
                "lap": b.lap_num,
                "current_hp": b.current_hp,
                "max_hp": b.max_hp,
                "fighter_num": b.fighter_num,
            }
            for b in clan_info.boss
        ],
    }


@router.get("/guild/{group_id}/queues", dependencies=[Depends(verify_admin_key)])
async def guild_queues(group_id: int):
    queues = {}
    from ..clanbattle.reserve_service import list_reserve_for_boss

    for boss in range(1, 6):
        sub = await list_reserve_for_boss(group_id, boss)
        app = await pcr_sqla.get_notice(NoticeType.apply.value, group_id, boss)
        queues[str(boss)] = {
            "subscribe": [n.dict() for n in sub],
            "apply": [n.dict() for n in app],
        }
    return queues
