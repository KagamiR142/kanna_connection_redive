"""会战响应文案（与 docs/developer/commands/会战指令.md 保持同步）。"""
from __future__ import annotations

APPLY_FORMAT_LINES = (
    "申请出刀格式：{进|申请出刀}<boss>[b][账号编号][:留言][@user]",
    "例：进1 / 申请出刀1b / 申请出刀2 2 / 进3b：满补 / 进3b 2@user",
)


def apply_format_error(sender: str) -> str:
    return f"{sender} 指令格式错误\n" + "\n".join(APPLY_FORMAT_LINES)


def unbound_account(sender: str) -> str:
    return f"未绑定游戏账号 {sender}"


def unbound_account_bind_hint(sender: str) -> str:
    return f"未绑定游戏账号，请先私聊绑定账号 {sender}"


TREE_FORMAT_LINES = (
    "挂树格式：挂树[boss][:留言][@user]",
    "例：挂树 / 挂树：失误了 / 挂树1 / 挂树1：留言",
)


def tree_format_error(sender: str) -> str:
    return f"{sender} 指令格式错误\n" + "\n".join(TREE_FORMAT_LINES)
