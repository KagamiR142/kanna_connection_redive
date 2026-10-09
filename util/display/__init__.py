"""用户可见名称格式化（QQ / 游戏角色 / @sender 占位）。"""
from .names import (
    display_name_sort_key,
    game_display_name,
    locale_sort_key,
    qq_display_name,
    sanitize_display_name,
    sender_placeholder,
)

__all__ = [
    "display_name_sort_key",
    "game_display_name",
    "locale_sort_key",
    "qq_display_name",
    "sanitize_display_name",
    "sender_placeholder",
]
