"""入站群消息纯文本清洗（不影响 CQ 消息段代发 @ 解析）。"""
from __future__ import annotations

import re

_CQ_LITERAL = re.compile(r"\[CQ:[^\]]+\]", re.IGNORECASE)
_ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")


def safe_plain(text: str) -> str:
    """用于指令匹配与参数解析的纯文本（代发 @ 仍由 message 段解析）。"""
    if not text:
        return ""
    for zw in _ZERO_WIDTH:
        text = text.replace(zw, "")
    text = _CQ_LITERAL.sub("", text)
    cleaned = []
    for ch in text:
        if ch in ("\t", "\n", "\r") or ord(ch) >= 32:
            cleaned.append(ch)
    return "".join(cleaned).strip()


def sanitize_remark(raw: str) -> str:
    """预约/留言/显示名等场景的备注清洗（与会战 command_parser 原逻辑一致）。"""
    if not raw:
        return ""
    text = re.sub(r"\[CQ:[^\]]+\]", "", raw)
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    for ch in ('"', "'", "`", "\u201c", "\u201d", "\u2018", "\u2019", "\\"):
        text = text.replace(ch, "")
    return text.strip()[:200]
