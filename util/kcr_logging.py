"""KCR 三日志 + 控制台心跳（毫秒时间戳）。

- kcr-qq.log：群/私聊入站、机器人出站、指令命中
- hoshino-kcr.log：监控、状态图、Boss 元数据等内部运维
- kcr-web.log：Web API / 运维
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

_CONFIGURED = False
_HOOKS_INSTALLED = False
_LOG_DIR: Optional[Path] = None

_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}"
)

_KCR_MODULE_PREFIX = "hoshino.modules.kanna_connection_redive"


def log_dir() -> Path:
    global _LOG_DIR
    if _LOG_DIR is None:
        # .../HoshinoBot-master/hoshino/modules/kanna_connection_redive/util/kcr_logging.py
        _LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def _is_kcr_module(record) -> bool:
    return str(record["name"]).startswith(_KCR_MODULE_PREFIX)


def _qq_filter(record) -> bool:
    return bool(record["extra"].get("kcr_qq"))


def _web_filter(record) -> bool:
    return bool(record["extra"].get("kcr_web"))


def _ops_filter(record) -> bool:
    if record["extra"].get("kcr_qq") or record["extra"].get("kcr_web"):
        return False
    if record["extra"].get("kcr_ops"):
        return True
    return _is_kcr_module(record)


def _console_filter(record) -> bool:
    return bool(record["extra"].get("kcr_console"))


def qq_log():
    return logger.bind(kcr_qq=True)


def ops_log():
    return logger.bind(kcr_ops=True)


def web_log():
    return logger.bind(kcr_web=True)


def setup_kcr_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    base = log_dir()
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format=_LOG_FORMAT,
        filter=_console_filter,
    )
    logger.add(
        base / "kcr-qq.log",
        level="DEBUG",
        format=_LOG_FORMAT,
        rotation="20 MB",
        encoding="utf-8",
        filter=_qq_filter,
    )
    logger.add(
        base / "hoshino-kcr.log",
        level="DEBUG",
        format=_LOG_FORMAT,
        rotation="20 MB",
        encoding="utf-8",
        filter=_ops_filter,
    )
    logger.add(
        base / "kcr-web.log",
        level="DEBUG",
        format=_LOG_FORMAT,
        rotation="20 MB",
        encoding="utf-8",
        filter=_web_filter,
    )
    for name in ("nonebot", "hoshino", "config", "chara", "半月刊"):
        logging.getLogger(name).setLevel(logging.WARNING)
    ops_log().info("KCR logging ready dir={}", base)


def log_heartbeat(monitor_groups: int) -> None:
    logger.bind(kcr_console=True).info(
        "[heartbeat] monitors={} logs={}", monitor_groups, log_dir()
    )


def install_qq_message_hooks() -> None:
    """入站 preprocessor + 出站 send 包装 + msghandler 命中日志。"""
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    _HOOKS_INSTALLED = True

    from nonebot import get_bot, message_preprocessor

    @message_preprocessor
    async def _kcr_log_inbound(bot, ev, _):
        from .qq_message_log import log_inbound_event

        log_inbound_event(ev)

    bot = get_bot()
    if getattr(bot, "_kcr_send_wrapped", False):
        pass
    else:
        bot._kcr_send_wrapped = True
        _orig_send = bot.send

        async def _send(ev, message, *args, **kwargs):
            from .qq_message_log import log_outbound_event

            log_outbound_event(ev, message)
            return await _orig_send(ev, message, *args, **kwargs)

        bot.send = _send

        if hasattr(bot, "send_private_msg"):
            _orig_pm = bot.send_private_msg

            async def _send_pm(*args, **kwargs):
                from .qq_message_log import log_outbound_private

                log_outbound_private(*args, **kwargs)
                return await _orig_pm(*args, **kwargs)

            bot.send_private_msg = _send_pm

        if hasattr(bot, "send_group_msg"):
            _orig_gm = bot.send_group_msg

            async def _send_gm(*args, **kwargs):
                from .qq_message_log import log_outbound_group

                log_outbound_group(*args, **kwargs)
                return await _orig_gm(*args, **kwargs)

            bot.send_group_msg = _send_gm

    import hoshino.msghandler as mh

    if getattr(mh, "_kcr_hit_wrapped", False):
        return
    mh._kcr_hit_wrapped = True

    async def _handle_message_logged(bot, event, _):
        from hoshino import CanceledException, trigger
        from nonebot.command import SwitchException

        from .qq_message_log import log_handler_hit

        if event.detail_type != "group":
            return

        for t in trigger.chain:
            for service_func in t.find_handler(event):
                if service_func.only_to_me and not event["to_me"]:
                    continue
                if not service_func.sv._check_all(event):
                    continue
                log_handler_hit(
                    int(event.message_id),
                    service_func.__name__,
                    getattr(service_func.sv, "name", ""),
                )
                service_func.sv.logger.info(
                    f"Message {event.message_id} triggered {service_func.__name__}."
                )
                try:
                    await service_func.func(bot, event)
                except SwitchException:
                    continue
                except CanceledException:
                    raise
                except Exception as e:
                    service_func.sv.logger.error(
                        f"{type(e)} occured when {service_func.__name__} "
                        f"handling message {event.message_id}."
                    )
                    service_func.sv.logger.exception(e)
                raise CanceledException("Handled by Hoshino")

    mh.handle_message = _handle_message_logged
