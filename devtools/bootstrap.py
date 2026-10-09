"""预览/测试脚本启动：注册包名并启用 KCR_TOOLING。"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
PKG = "kanna_connection_redive"


def bootstrap() -> Path:
    os.environ.setdefault("KCR_TOOLING", "1")
    root = str(MODULE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)

    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [root]
        sys.modules[PKG] = pkg

    for sub in (
        "util",
        "clanbattle",
        "knife_budget",
        "database",
        "webui",
        "challenge",
        "captcha",
        "client",
        "member",
        "tools",
    ):
        subpath = MODULE_ROOT / sub
        if subpath.is_dir():
            fq = f"{PKG}.{sub}"
            if fq not in sys.modules:
                m = types.ModuleType(fq)
                m.__path__ = [str(subpath)]
                sys.modules[fq] = m

    return MODULE_ROOT
