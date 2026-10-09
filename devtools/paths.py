"""devtools 路径常量。"""
from __future__ import annotations

from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = MODULE_ROOT / "devtools" / "output"
FIXTURES_API_DIR = MODULE_ROOT / "devtools" / "fixtures" / "api"
BOSS_INFO_JSON = MODULE_ROOT / "resource" / "data" / "boss_info.json"
