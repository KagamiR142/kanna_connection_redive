"""pytest 根配置：确保模块根目录在 sys.path 中。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 工具链/测试模式：跳过 setting_clanbattle.json 严格校验（见 clanbattle_setting.py）
os.environ.setdefault("KCR_TOOLING", "1")

ROOT = Path(__file__).resolve().parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
