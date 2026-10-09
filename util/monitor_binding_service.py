"""监控账号绑定文案、邮箱打码、出刀监控状态（QQ/Web 共用）。"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ..clanbattle_setting import get_clanbattle_settings
from ..database.dal import pcr_sqla
from ..database.models import Account
from ..rbac import is_admin_plus

MONITOR_ACCOUNT_SLOTS: tuple[int, ...] = (1, 2, 3)

if TYPE_CHECKING:
    from ..clanbattle.model import ClanBattle


def mask_login_email(value: Optional[str]) -> str:
    """群聊展示用：b***@163.com。"""
    if not value:
        return "未绑定"
    text = str(value).strip()
    if "@" not in text:
        return text[0] + "***" if text else "未绑定"
    local, domain = text.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def monitor_account_email_display(acc: Optional[Account]) -> str:
    if not acc:
        return "未绑定"
    if acc.refresh:
        return mask_login_email(acc.refresh)
    if acc.account and "@" in str(acc.account):
        return mask_login_email(str(acc.account))
    return "（已绑定，非邮箱账号）"


def build_binding_help_text() -> str:
    cfg = get_clanbattle_settings()
    retry = "、".join(cfg.captcha_retry_commands) or "重试过码"
    return (
        "【监控账号绑定说明】（仅管理员及以上可执行绑定）\n"
        "私聊发送（加号为空格）：\n"
        "· 绑定账号1 账号 密码（B 服）\n"
        "· 绑定账号2 / 绑定账号3 账号 密码（备用监控槽位）\n"
        "· 渠绑定账号 login_id token\n"
        "· 台绑定账号 short_udid udid viewer_id\n"
        f"过码失败可发送：{retry}\n"
        "群聊发送【出刀监控状态】可查看监控与槽位（邮箱已打码）。\n"
        "私聊【刷新会战元数据】可一次性更新当期全部 Boss 名称/头像（管理员+）。\n"
        "成员游戏身份绑定请用 Web 会战平台，与监控账号不同。"
    )


async def format_slot_line(slot: int, operator_qq: int) -> str:
    acc = await pcr_sqla.query_monitor_account(operator_qq, slot)
    if not acc:
        return f"槽位{slot}：未绑定"
    name = acc.name or "未命名"
    email = monitor_account_email_display(acc)
    return f"槽位{slot}：{email} / {name}"


async def format_monitor_status_message(
    group_id: int, clan_info: Optional["ClanBattle"], requester_qq: int
) -> str:
    from ..clanbattle.status_cache import is_monitor_active

    lines: List[str] = []
    slot_owner = requester_qq
    if clan_info and is_monitor_active(clan_info):
        slot = int(getattr(clan_info, "monitor_slot", 1) or 1)
        acc_name = getattr(clan_info, "monitor_account_name", "") or "未知"
        slot_owner = int(clan_info.user_id)
        lines.append(
            f"本群出刀监控：已开启（操作者 QQ {clan_info.user_id}，槽位{slot}，账号 {acc_name}）"
        )
    else:
        lines.append("本群出刀监控：未开启")

    for slot in MONITOR_ACCOUNT_SLOTS:
        lines.append(await format_slot_line(slot, slot_owner))
    return "\n".join(lines)


def require_binding_admin(qq_id: int) -> bool:
    return is_admin_plus(int(qq_id))
