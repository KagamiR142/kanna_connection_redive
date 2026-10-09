"""damage_history 水位线：同秒合刀须能续处理。"""
from __future__ import annotations

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from tests._module_loader import PKG, load_module

_mock_dal = ModuleType(f"{PKG}.database.dal")
_mock_dal.pcr_sqla = MagicMock()
sys.modules[f"{PKG}.database.dal"] = _mock_dal

_wh = load_module("clanbattle/damage_history_watermark.py", "kcr_damage_history_watermark")
collect_damage_histories_to_process = _wh.collect_damage_histories_to_process
has_unsettled_damage_history = _wh.has_unsettled_damage_history
iter_histories_at_or_after_watermark = _wh.iter_histories_at_or_after_watermark
orders_with_pending_damage_history = _wh.orders_with_pending_damage_history

_dpb = load_module("clanbattle/damage_push_batch.py", "kcr_damage_push_batch")
DamagePushBlock = _dpb.DamagePushBlock
flush_damage_push_batch = _dpb.flush_damage_push_batch


def _history(log_id: int, viewer: int, create_time: int, order: int = 5):
    return SimpleNamespace(
        history_id=log_id,
        viewer_id=viewer,
        create_time=create_time,
        order_num=order,
        lap_num=36,
        damage=1,
        kill=False,
        name="test",
    )


class WatermarkCollectTests(unittest.TestCase):
    def test_same_second_included_at_watermark(self):
        """旧逻辑 create_time<=watermark 会漏掉同秒第二条；新逻辑应包含。"""
        t = 1790582387
        hist = [
            _history(592457, 1320614342783, t),
            _history(592456, 1251608339513, t),
            _history(592400, 1, t - 10),
        ]
        batch = collect_damage_histories_to_process(hist, t)
        ids = [int(h.history_id) for h in batch]
        self.assertEqual(ids, [592456, 592457])

    def test_strictly_older_stops_scan(self):
        t = 100
        hist = [
            _history(3, 1, 100),
            _history(2, 1, 50),
            _history(1, 1, 200),
        ]
        collected = list(iter_histories_at_or_after_watermark(hist, t))
        self.assertEqual([h.history_id for h in collected], [3])

    def test_newer_than_watermark_only(self):
        t = 100
        hist = [
            _history(2, 1, 200),
            _history(1, 1, 50),
        ]
        batch = collect_damage_histories_to_process(hist, t)
        self.assertEqual([h.history_id for h in batch], [2])


class WatermarkAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _mock_dal.pcr_sqla.is_record_settlement_locked = AsyncMock(return_value=False)

    async def test_has_unsettled_same_second_second_poll(self):
        """模拟第二人晚到：水位已等于 create_time，仍应判定有待结算。"""
        t = 1790582387
        hist = [_history(592457, 1320614342783, t)]
        locked = AsyncMock(return_value=False)
        _mock_dal.pcr_sqla.is_record_settlement_locked = locked
        pending = await has_unsettled_damage_history(838306960, hist, t)
        self.assertTrue(pending)
        locked.assert_awaited_once_with(838306960, 592457)

    async def test_has_unsettled_false_when_all_locked(self):
        t = 1790582387
        hist = [
            _history(592457, 1320614342783, t),
            _history(592456, 1251608339513, t),
        ]
        _mock_dal.pcr_sqla.is_record_settlement_locked = AsyncMock(return_value=True)
        pending = await has_unsettled_damage_history(1, hist, t)
        self.assertFalse(pending)

    async def test_orders_pending_includes_same_second_unlocked(self):
        t = 100
        hist = [_history(1, 1, 100, order=5)]
        _mock_dal.pcr_sqla.is_record_settlement_locked = AsyncMock(return_value=False)
        orders = await orders_with_pending_damage_history(1, hist, t)
        self.assertEqual(orders, {5})


class SamePollMergeTests(unittest.TestCase):
    def test_two_blocks_same_second_merge(self):
        blocks = [
            DamagePushBlock(5, 1790582387, "a", "s1", 0, []),
            DamagePushBlock(5, 1790582387, "b", "s2", 1, ["c"]),
        ]
        msgs = flush_damage_push_batch(blocks, group_id=1)
        self.assertEqual(len(msgs), 1)
        self.assertIn("a", msgs[0])
        self.assertIn("b", msgs[0])


if __name__ == "__main__":
    unittest.main()
