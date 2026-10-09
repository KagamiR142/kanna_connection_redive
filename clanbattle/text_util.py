"""文本清洗与蓝图占位符。"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from ..util.display import (
    display_name_sort_key,
    game_display_name,
    locale_sort_key,
    qq_display_name,
    sender_placeholder,
)

__all__ = [
    "display_name_sort_key",
    "game_display_name",
    "locale_sort_key",
    "qq_display_name",
    "sender_placeholder",
    "strip_trailing_cq_at",
]


def strip_trailing_cq_at(message) -> Tuple[str, Optional[int]]:
    """从消息段末尾提取代发 @，返回 (plain_without_trailing_at, proxy_qq)。"""
    segments = list(message)
    proxy_qq: Optional[int] = None
    while segments:
        seg = segments[-1]
        if seg.type == "at" and seg.data.get("qq") != "all":
            proxy_qq = int(seg.data["qq"])
            segments.pop()
            continue
        if seg.type == "text" and not seg.data.get("text", "").strip():
            segments.pop()
            continue
        break
    plain = "".join(
        s.data.get("text", "") if s.type == "text" else "" for s in segments
    ).strip()
    plain = re.sub(r"\[CQ:at,qq=\d+\]\s*$", "", plain).strip()
    return plain, proxy_qq
