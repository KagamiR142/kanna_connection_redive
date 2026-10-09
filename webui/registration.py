"""私聊「注册」与 WebAccount 写入（QQ 与 Web 共用逻辑）。"""
from __future__ import annotations

import random
import string
from typing import Tuple

from loguru import logger

from ..database.dal import pcr_sqla
from ..database.models import WebAccount
from .password_util import hash_password


def _random_initial_password() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=8))


async def handle_web_register(qq_id: int) -> Tuple[str, str]:
    """
    返回 (用户可见文案, 日志摘要)。
    见蓝图：未注册发新密码；已注册且仍为初始密码则重置；已改密则提示自行登录。
    """
    account = str(qq_id)
    existing = await pcr_sqla.web_query_user(account)
    if existing is None:
        plain = _random_initial_password()
        await pcr_sqla.web_upsert_user(
            WebAccount(
                account=account,
                password=hash_password(plain),
                temp=False,
                priority=0,
                is_initial_password=True,
            )
        )
        logger.info("Web 注册: qq={} 新用户已创建", qq_id)
        msg = (
            f"Web 注册成功。\n账号：{account}\n初始密码：{plain}\n"
            "请使用该密码登录 Web，登录后请尽快修改密码。"
        )
        return msg, "new_user"

    if bool(getattr(existing, "is_initial_password", True)):
        plain = _random_initial_password()
        await pcr_sqla.web_upsert_user(
            WebAccount(
                account=account,
                password=hash_password(plain),
                temp=False,
                priority=existing.priority or 0,
                is_initial_password=True,
            )
        )
        logger.info("Web 注册: qq={} 重置初始密码（用户尚未改密）", qq_id)
        msg = (
            f"您尚未修改过初始密码，已为您生成新密码。\n账号：{account}\n"
            f"新密码：{plain}\n登录后请尽快修改密码。"
        )
        return msg, "reset_initial"

    logger.info("Web 注册: qq={} 已改密，拒绝重发密码", qq_id)
    msg = "您已修改过 Web 登录密码，请使用您设置的密码登录。若忘记密码请联系管理员。"
    return msg, "already_changed"
