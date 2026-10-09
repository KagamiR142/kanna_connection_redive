"""会战模块统一配置：所有敏感项集中在 setting_clanbattle.json。"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .basedata import FilePath

_SETTING_PATH = FilePath.data.value / "setting_clanbattle.json"
_EXAMPLE_PATH = FilePath.data.value / "setting_clanbattle.example.json"

_PLACEHOLDER_VALUES = {
    "",
    "CHANGE_ME",
    "REQUIRED",
    "请填写",
    "kcr-admin-change-me",
    "your-password-here",
    "your-admin-key-here",
}


class ConfigValidationError(Exception):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class ClanBattleSettings:
    admin_qq: int = 0
    admin_qqs: List[int] = field(default_factory=list)
    captcha_retry_commands: List[str] = field(
        default_factory=lambda: ["重试过码", "重新登录"]
    )
    captcha_wait_sec: int = 90
    captcha_fallback_bdval: bool = True
    lulu_token: str = ""
    ellye_token: str = ""
    yobot_base_url: str = "http://127.0.0.1:8070"
    yobot_enabled: bool = True
    monitor_max_concurrent_groups: int = 66
    monitor_poll_min_sec: int = 1
    monitor_poll_max_sec: int = 1
    api_host: str = "0.0.0.0"
    api_port: int = 8138
    api_base_path: str = "/kanna_dependency"
    api_admin_key: str = ""
    web_admin_username: str = ""
    web_admin_password: str = ""
    web_public_host: str = "127.0.0.1"
    web_cookie_httponly: bool = False
    web_cookie_secure: bool = False

    @property
    def kcr_api_base(self) -> str:
        return f"http://{self.web_public_host}:{self.api_port}{self.api_base_path}"


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in _PLACEHOLDER_VALUES
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def _load_raw_config() -> Optional[Dict[str, Any]]:
    if not _SETTING_PATH.is_file():
        return None
    import json

    # utf-8-sig：兼容 Windows 记事本保存的 UTF-8 BOM，避免 json.load 直接报错
    with open(_SETTING_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def _normalize_raw(raw: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧版扁平字段。"""
    captcha = dict(raw.get("captcha") or {})
    if raw.get("captcha_retry_commands") and not captcha.get("retry_commands"):
        captcha["retry_commands"] = raw["captcha_retry_commands"]
    if raw.get("captcha_wait_sec") is not None and "wait_sec" not in captcha:
        captcha["wait_sec"] = raw["captcha_wait_sec"]
    if raw.get("captcha_fallback_bdval") is not None and "fallback_bdval" not in captcha:
        captcha["fallback_bdval"] = raw["captcha_fallback_bdval"]
    raw["captcha"] = captcha

    api = dict(raw.get("api") or {})
    if api.get("base_url") and not api.get("port"):
        # 旧版只写了 base_url 时保留默认端口
        pass
    raw["api"] = api
    return raw


def validate_config(raw: Optional[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    if raw is None:
        errors.append(f"配置文件不存在：{_SETTING_PATH}")
        errors.append(f"请复制示例文件并填写：{_EXAMPLE_PATH}")
        return errors, {}

    raw = _normalize_raw(raw)
    captcha = raw.get("captcha") or {}
    api = raw.get("api") or {}
    web_admin = raw.get("web_admin") or {}
    monitor = raw.get("monitor") or {}
    yobot = raw.get("yobot") or {}

    admin_qq = raw.get("admin_qq")
    if _is_blank(admin_qq) or int(admin_qq or 0) <= 0:
        errors.append("admin_qq：须填写有效的管理员 QQ 号")

    retry_cmds = captcha.get("retry_commands") or raw.get("captcha_retry_commands")
    if _is_blank(retry_cmds):
        errors.append("captcha.retry_commands：过码重试指令列表不能为空")

    if _is_blank(api.get("admin_key")):
        errors.append("api.admin_key：管理 API 密钥不能为空（勿使用示例占位符）")

    port = api.get("port", 8138)
    try:
        port = int(port)
        if port <= 0 or port > 65535:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("api.port：须为 1–65535 的有效端口号（推荐 8138）")

    if _is_blank(web_admin.get("username")):
        errors.append("web_admin.username：Web 管理登录用户名不能为空")
    if _is_blank(web_admin.get("password")):
        errors.append("web_admin.password：Web 管理登录密码不能为空")

    if _is_blank(monitor.get("max_concurrent_groups")):
        errors.append("monitor.max_concurrent_groups：不能为空")
    if _is_blank(monitor.get("poll_min_sec")):
        errors.append("monitor.poll_min_sec：不能为空")
    if _is_blank(monitor.get("poll_max_sec")):
        errors.append("monitor.poll_max_sec：不能为空")

    if bool(yobot.get("enabled", False)) and _is_blank(yobot.get("base_url")):
        errors.append("yobot.base_url：Yobot 启用时面板地址不能为空")

    return errors, raw


def _parse_settings(raw: Dict[str, Any]) -> ClanBattleSettings:
    captcha = raw.get("captcha") or {}
    api = raw.get("api") or {}
    web_admin = raw.get("web_admin") or {}
    web_panel = raw.get("web_panel") or {}
    monitor = raw.get("monitor") or {}
    yobot = raw.get("yobot") or {}
    return ClanBattleSettings(
        admin_qq=int(raw.get("admin_qq", 0)),
        admin_qqs=[int(x) for x in (raw.get("admin_qqs") or []) if x],
        captcha_retry_commands=list(
            captcha.get("retry_commands") or raw.get("captcha_retry_commands") or []
        ),
        captcha_wait_sec=int(captcha.get("wait_sec", raw.get("captcha_wait_sec", 90))),
        captcha_fallback_bdval=bool(
            captcha.get("fallback_bdval", raw.get("captcha_fallback_bdval", True))
        ),
        lulu_token=str(captcha.get("lulu_token", "")),
        ellye_token=str(captcha.get("ellye_token", "")),
        yobot_base_url=str(yobot.get("base_url", "http://127.0.0.1:8070")),
        yobot_enabled=bool(yobot.get("enabled", True)),
        monitor_max_concurrent_groups=int(monitor.get("max_concurrent_groups", 66)),
        monitor_poll_min_sec=int(monitor.get("poll_min_sec", 1)),
        monitor_poll_max_sec=int(monitor.get("poll_max_sec", 1)),
        api_host=str(api.get("host", "0.0.0.0")),
        api_port=int(api.get("port", 8138)),
        api_base_path=str(api.get("base_path", "/kanna_dependency")),
        api_admin_key=str(api.get("admin_key", "")),
        web_admin_username=str(web_admin.get("username", "")),
        web_admin_password=str(web_admin.get("password", "")),
        web_public_host=str(web_panel.get("public_host", "127.0.0.1")),
        web_cookie_httponly=bool(api.get("cookie_httponly", False)),
        web_cookie_secure=bool(api.get("cookie_secure", False)),
    )


def ensure_config_or_exit() -> ClanBattleSettings:
    import os

    if os.environ.get("KCR_TOOLING") == "1":
        raw = _load_raw_config() or {}
        return _parse_settings(_normalize_raw(raw))

    raw = _load_raw_config()
    errors, normalized = validate_config(raw)
    if errors:
        banner = [
            "",
            "=" * 60,
            "KCR 模块配置校验失败，机器人拒绝启动。",
            f"配置文件路径：{_SETTING_PATH}",
            "",
            "请逐项填写以下缺失/无效字段后重启：",
        ]
        for err in errors:
            banner.append(f"  - {err}")
        banner.append("")
        banner.append(f"可参考示例：{_EXAMPLE_PATH}")
        banner.append("=" * 60)
        print("\n".join(banner), file=sys.stderr)
        raise SystemExit(1)
    return _parse_settings(normalized)


@lru_cache(maxsize=1)
def get_clanbattle_settings() -> ClanBattleSettings:
    return ensure_config_or_exit()


def reload_clanbattle_settings() -> ClanBattleSettings:
    get_clanbattle_settings.cache_clear()
    return get_clanbattle_settings()


def get_captcha_tokens() -> Tuple[str, str]:
    s = get_clanbattle_settings()
    return s.lulu_token, s.ellye_token


async def sync_web_admin_account() -> None:
    from .database.dal import pcr_sqla
    from .database.models import WebAccount

    s = get_clanbattle_settings()
    await pcr_sqla.web_add_user(
        WebAccount(
            account=s.web_admin_username,
            password=s.web_admin_password,
            temp=False,
            priority=0,
        )
    )
