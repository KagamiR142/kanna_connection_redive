"""Web 端出刀监控开关（复用 QQ 监控初始化逻辑，不发群消息）。"""
from __future__ import annotations

from typing import Any, Dict

import nonebot
from loguru import logger

from ...clanbattle.monitor_runtime_service import start_clan_monitor
from ...database.dal import pcr_sqla
from ..ops_log import append_ops_log
from ..util import call_in_main_loop


async def start_monitor_web(
    group_id: int, operator_qq: int, account_id: int
) -> Dict[str, Any]:
    accounts = await pcr_sqla.query_account(operator_qq) or []
    account = next((a for a in accounts if a.id == account_id), None)
    if account is None:
        raise ValueError("请选择您已绑定的监控用游戏账号")

    bot = nonebot.get_bot()
    self_id = int(bot.self_id)
    slot = int(getattr(account, "monitor_slot", None) or 1)

    async def _run():
        return await start_clan_monitor(
            group_id=group_id,
            operator_qq=operator_qq,
            bot_id=self_id,
            account=account,
            monitor_slot=slot,
            notify=None,
            ev=None,
        )

    ok, msg, errors = await call_in_main_loop(_run())
    if not ok:
        logger.error(
            "Web 开启监控失败 group={} operator={} errors={}",
            group_id,
            operator_qq,
            errors,
        )
        raise ValueError(msg)
    append_ops_log(
        "monitor",
        f"开启出刀监控（账号 {account.name or account.viewer_id} 槽位{slot}）",
        group_id=group_id,
        user_id=operator_qq,
    )
    from ...util.kcr_logging import web_log

    web_log().info(
        "Web 开启监控: group={} operator={} account_id={} slot={}",
        group_id,
        operator_qq,
        account_id,
        slot,
    )
    return {
        "ok": True,
        "state": "开启",
        "monitor_user_id": operator_qq,
        "account_name": account.name,
    }


async def stop_monitor_web(group_id: int, operator_qq: int) -> Dict[str, Any]:
    from ...clanbattle import clanbattle_info

    clan_info = clanbattle_info.get(group_id)
    if not clan_info:
        return {"ok": True, "state": "关闭"}
    if clan_info.loop_check:
        clan_info.loop_num += 1
        append_ops_log(
            "monitor",
            "关闭出刀监控",
            group_id=group_id,
            user_id=operator_qq,
        )
        logger.info("Web 关闭监控: group={} operator={}", group_id, operator_qq)
    return {"ok": True, "state": "关闭"}
