"""QQ / 游戏角色显示名（与会战 handler 文案一致）。"""
from __future__ import annotations

from ..message_sanitize import sanitize_remark

_DISPLAY_MAX_LEN = 10


def sanitize_display_name(raw: str, *, fallback: str) -> str:
    text = sanitize_remark(raw or "")
    if not text:
        return fallback
    if len(text) > _DISPLAY_MAX_LEN:
        return text[:_DISPLAY_MAX_LEN]
    return text


def sender_placeholder(user_id: int, card: str = "", nickname: str = "") -> str:
    """蓝图 @sender：文案占位，非 CQ @。"""
    name = card or nickname or ""
    display = sanitize_display_name(name, fallback=f"QQ{user_id}")
    return f"@{display}"


def qq_display_name(user_id: int, card: str = "", nickname: str = "") -> str:
    return sanitize_display_name(card or nickname or "", fallback=f"QQ{user_id}")


def game_display_name(name: str, viewer_id: int) -> str:
    return sanitize_display_name(name or "", fallback=f"UID{viewer_id}")


def locale_sort_key(name: str) -> str:
    """列表按昵称/名称排序（中英混排友好）。"""
    return (name or "").casefold()


def display_name_sort_key(name: str) -> str:
    """用户名排序：英文按字母；中文按拼音首字母。"""
    text = name or ""
    try:
        from pypinyin import lazy_pinyin

        initials = "".join(p[0] for p in lazy_pinyin(text) if p)
        if initials:
            return initials.casefold()
    except ImportError:
        pass
    return locale_sort_key(text)
