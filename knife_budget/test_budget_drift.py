"""budget_drift / 整刀漂移（`python test_budget_drift.py`）。"""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

try:
    from .budget_drift import sanitize_budget_counters, try_consume_full_slot
except ImportError:
    from budget_drift import sanitize_budget_counters, try_consume_full_slot


def _budget(**kwargs):
    base = {
        "viewer_id": 1,
        "used_full": 3,
        "avail_comp": 0,
        "used_points": 3.0,
        "comp_seconds": 35,
        "comp_boss": 1,
        "comp_pool": json.dumps([{"seconds": 35, "boss": 1}]),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestBudgetDrift(unittest.TestCase):
    def test_sanitize_extreme_counters(self) -> None:
        b = _budget(used_full=99, avail_comp=-2, used_points=9.0)
        sanitize_budget_counters(b, viewer_id=1, context="test")
        self.assertEqual(b.used_full, 3)
        self.assertEqual(b.avail_comp, 0)
        self.assertEqual(b.used_points, 3.0)

    def test_try_consume_full_slot_logs_not_raises(self) -> None:
        b = _budget(used_full=3)
        ok = try_consume_full_slot(
            b, viewer_id=1, boss_order=2, reason="test"
        )
        self.assertFalse(ok)
        self.assertEqual(b.used_full, 3)


if __name__ == "__main__":
    unittest.main()
