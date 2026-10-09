"""QQ 入站/出站/指令命中 → kcr-qq.log。"""
from __future__ import annotations

from typing import Any

from .kcr_logging import qq_log


def _plain_summary(message: Any, limit: int = 240) -> str:
    try:
        text = message.extract_plain_text().strip()
    except Exception:
        text = str(message)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text or "(empty)"


def _msg_kind(ev) -> str:
    if getattr(ev, "group_id", None):
        return "group"
    return "private"


def log_inbound_event(ev) -> None:
    qq_log().info(
        "IN {} gid={} uid={} msg_id={} to_me={} plain={}",
        _msg_kind(ev),
        getattr(ev, "group_id", None),
        getattr(ev, "user_id", None),
        getattr(ev, "message_id", None),
        bool(ev.get("to_me")),
        _plain_summary(ev.message),
    )


def log_outbound_event(ev, message) -> None:
    qq_log().info(
        "OUT {} gid={} uid={} plain={}",
        _msg_kind(ev),
        getattr(ev, "group_id", None),
        getattr(ev, "user_id", None),
        _plain_summary(message),
    )


def log_outbound_private(*args, **kwargs) -> None:
    qq_log().info(
        "OUT private uid={} plain={}",
        kwargs.get("user_id"),
        _plain_summary(kwargs.get("message", "")),
    )


def log_outbound_group(*args, **kwargs) -> None:
    qq_log().info(
        "OUT group gid={} plain={}",
        kwargs.get("group_id"),
        _plain_summary(kwargs.get("message", "")),
    )


def log_handler_hit(message_id: int, handler: str, service: str) -> None:
    qq_log().info(
        "HIT msg_id={} handler={} service={}",
        message_id,
        handler,
        service,
    )
