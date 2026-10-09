"""本 poll 待结算战报参与 ledger 归零冻结。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from tests._module_loader import PKG, load_module

_mock_dal = ModuleType(f"{PKG}.database.dal")
_mock_dal.pcr_sqla = MagicMock()
sys.modules[f"{PKG}.database.dal"] = _mock_dal

_wh = load_module("clanbattle/damage_history_watermark.py", "kcr_wh_pending")
orders_with_pending_damage_history = _wh.orders_with_pending_damage_history


class PendingHistoryOrdersTests(unittest.IsolatedAsyncioTestCase):
    def test_watermark_module_defines_helper(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "clanbattle"
            / "damage_history_watermark.py"
        )
        src = path.read_text(encoding="utf-8")
        self.assertIn("async def orders_with_pending_damage_history", src)

    async def test_collects_same_second_pending_orders(self) -> None:
        latest_time = 100
        hist = [
            SimpleNamespace(
                history_id=2, create_time=100, order_num=5, viewer_id=1
            ),
            SimpleNamespace(
                history_id=1, create_time=50, order_num=3, viewer_id=2
            ),
        ]
        _mock_dal.pcr_sqla.is_record_settlement_locked = AsyncMock(return_value=False)
        orders = await orders_with_pending_damage_history(1, hist, latest_time)
        self.assertEqual(orders, {5})

    async def test_skips_locked_at_same_second(self) -> None:
        latest_time = 100
        hist = [
            SimpleNamespace(
                history_id=2, create_time=100, order_num=5, viewer_id=1
            ),
        ]

        async def _locked(_gid, log_id):
            return log_id == 2

        _mock_dal.pcr_sqla.is_record_settlement_locked = _locked
        orders = await orders_with_pending_damage_history(1, hist, latest_time)
        self.assertEqual(orders, set())


if __name__ == "__main__":
    unittest.main()
