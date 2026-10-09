"""出刀监控启停（QQ / Web 共用）。"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ..database.models import Account
from ..util.kcr_logging import ops_log
from ..login import login_monitor_account, release_cached_client
from ..util.boss_metadata_service import refresh_clan_boss_metadata
from .registry import clanbattle_info, clanbattle_pool
from .model import ClanBattle, ClanbattleItem, PrioritizedQueryItem
from .status_cache import is_monitor_active

if TYPE_CHECKING:
    from hoshino.typing import CQEvent, HoshinoBot


def _monitor_switching(clan_info: ClanBattle, account: Account, monitor_slot: int) -> bool:
    if not is_monitor_active(clan_info):
        return False
    if getattr(clan_info, "client", None) is None:
        return False
    if clan_info.monitor_account_id == account.id and int(
        clan_info.monitor_slot
    ) == int(monitor_slot):
        return False
    return True


async def start_clan_monitor(
    *,
    group_id: int,
    operator_qq: int,
    bot_id: int,
    account: Account,
    monitor_slot: int = 1,
    notify: Optional["HoshinoBot"] = None,
    ev: Optional["CQEvent"] = None,
) -> tuple[bool, str, List[str]]:
    """
    登录并启动监控轮询。返回 (成功, 用户可见摘要, 错误列表)。
    notify+ev 非空时在群内发送进度/结果。
    """
    errors: List[str] = []
    boss_summary = await refresh_clan_boss_metadata(source=f"monitor_start:g{group_id}")
    if not boss_summary.get("ok"):
        ops_log().warning(
            "监控启动时 Boss 元数据刷新未成功 group={} reason={}",
            group_id,
            boss_summary.get("reason"),
        )

    if group_id not in clanbattle_info:
        clanbattle_info[group_id] = ClanBattle(group_id)
    clan_info = clanbattle_info[group_id]

    if (
        getattr(clan_info, "client", None) is not None
        and clan_info.monitor_account_id == account.id
        and int(clan_info.monitor_slot) == int(monitor_slot)
        and is_monitor_active(clan_info)
    ):
        ok_msg = (
            f"出刀监控已在运行中（幂等跳过重复启动）。\n"
            f"当前监控账号：{clan_info.monitor_account_name or account.name}，"
            f"槽位{monitor_slot}，#监控编号HN000{clan_info.loop_num}"
        )
        ops_log().info(
            "出刀监控幂等跳过 group={} slot={} account_id={} loop={}",
            group_id,
            monitor_slot,
            account.id,
            clan_info.loop_num,
        )
        return True, ok_msg, []

    switching = _monitor_switching(clan_info, account, monitor_slot)
    old_client = clan_info.client if switching else None
    from_slot = int(clan_info.monitor_slot) if switching else None

    if notify and ev:
        if switching:
            await notify.send(
                ev,
                f"正在登录槽位{monitor_slot}账号（{account.name or account.viewer_id}），"
                f"当前槽位{from_slot}监控将保持至切换完成。",
            )
        else:
            await notify.send(
                ev,
                f"正在登录账号，请耐心等待。当前监控账号：{account.name or account.viewer_id}",
            )

    snap: Optional[dict] = None
    if switching:
        snap = {
            "loop_num": clan_info.loop_num,
            "client": old_client,
            "monitor_slot": clan_info.monitor_slot,
            "monitor_account_id": clan_info.monitor_account_id,
            "monitor_account_name": clan_info.monitor_account_name,
            "user_id": clan_info.user_id,
            "bot_id": clan_info.bot_id,
        }

    try:
        new_client = await login_monitor_account(account)
    except Exception as e1:
        errors.append(str(e1))
        if switching:
            msg = (
                f"槽位{monitor_slot}账号登录/初始化失败，已恢复槽位{from_slot}监控。\n"
                f"错误信息：{'；'.join(errors)}"
            )
        else:
            msg = (
                "出刀监控失败次数过多，请重绑账号或手动检查账号登录状态\n"
                f"错误信息：{'；'.join(errors)}"
            )
        if notify and ev:
            await notify.send(ev, msg)
        ops_log().error(
            "出刀监控登录失败: group={} slot={} switching={} err={}",
            group_id,
            monitor_slot,
            switching,
            errors,
        )
        return False, msg, errors

    if switching:
        clan_info._hot_switch_quiet = True
    try:
        await clan_info.init(new_client, operator_qq, bot_id)
    except Exception as e2:
        errors.append(str(e2))
        if switching and snap is not None:
            clan_info.loop_num = snap["loop_num"]
            clan_info.client = snap["client"]
            clan_info.monitor_slot = snap["monitor_slot"]
            clan_info.monitor_account_id = snap["monitor_account_id"]
            clan_info.monitor_account_name = snap["monitor_account_name"]
            clan_info.user_id = snap["user_id"]
            clan_info.bot_id = snap["bot_id"]
            await clanbattle_pool.add_task(
                PrioritizedQueryItem(
                    data=ClanbattleItem(clan_info, clan_info.loop_num)
                )
            )
            msg = (
                f"槽位{monitor_slot}账号登录/初始化失败，已恢复槽位{from_slot}监控。\n"
                f"错误信息：{'；'.join(errors)}"
            )
            release_cached_client(new_client)
            clan_info._hot_switch_quiet = False
        else:
            msg = (
                "出刀监控失败次数过多，请重绑账号或手动检查账号登录状态\n"
                f"错误信息：{'；'.join(errors)}"
            )
            if switching:
                clan_info._hot_switch_quiet = False
        if notify and ev:
            await notify.send(ev, msg)
        ops_log().error(
            "出刀监控初始化失败: group={} slot={} switching={} err={}",
            group_id,
            monitor_slot,
            switching,
            errors,
        )
        return False, msg, errors

    clan_info.monitor_slot = monitor_slot
    clan_info.monitor_account_id = account.id
    clan_info.monitor_account_name = account.name or str(account.viewer_id or "")

    loop_num = clan_info.loop_num
    await clanbattle_pool.add_task(
        PrioritizedQueryItem(data=ClanbattleItem(clan_info, loop_num))
    )
    if switching:
        clan_info._hot_switch_quiet = False

    if switching and old_client is not None and old_client is not new_client:
        release_cached_client(old_client)
        ops_log().info(
            "出刀监控已热切换 group={} from_slot={} to_slot={} loop={}",
            group_id,
            from_slot,
            monitor_slot,
            loop_num,
        )

    switch_hint = (
        f"（已由槽位{from_slot}切换至槽位{monitor_slot}）\n" if switching else ""
    )
    ok_msg = (
        f"{switch_hint}"
        f"出刀监控已开启，发送【取消出刀监控】或直接顶号会退出监控\n"
        f"当前监控账号：{account.name}，槽位{monitor_slot}，#监控编号HN000{loop_num}"
    )
    ops_log().info(
        "出刀监控已开启 group={} operator={} slot={} account_id={} loop={} switch={}",
        group_id,
        operator_qq,
        monitor_slot,
        account.id,
        loop_num,
        switching,
    )
    return True, ok_msg, errors
