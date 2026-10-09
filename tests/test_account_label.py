"""账号展示名 / 时间格式单元测试（无 Hoshino 环境）。"""
from __future__ import annotations

import sys
import time
from datetime import timedelta

import pytest

from tests._module_loader import load_module

_names = load_module("util/display/names.py", "kcr_names")
_dal = load_module("database/dal.py", "kcr_dal")
load_module("database/models.py", "kcr_models")
sys.modules["kanna_connection_redive.database.dal"] = _dal
_ks = load_module("knife_budget/knife_state.py", "kcr_ks")

display_name_sort_key = _names.display_name_sort_key
format_knife_time_text = _ks.format_knife_time_text
pcr_date = _dal.pcr_date


@pytest.fixture(autouse=True)
def _restore_real_dal() -> None:
    """其它测试模块 import 时可能注入 mock dal，运行前恢复本文件加载的真实 dal。"""
    sys.modules["kanna_connection_redive.database.dal"] = _dal


def test_display_name_sort_key_pinyin() -> None:
    assert display_name_sort_key("Alice") < display_name_sort_key("Bob")
    assert display_name_sort_key("阿明") < display_name_sort_key("波爷")


def test_format_knife_time_yesterday_prefix() -> None:
    today5 = pcr_date(int(time.time()))
    yesterday_noon = today5 - timedelta(hours=12)
    ts = int(yesterday_noon.timestamp())
    text = format_knife_time_text(ts, query_day_ts=int(today5.timestamp()))
    assert text.startswith("(昨)")
