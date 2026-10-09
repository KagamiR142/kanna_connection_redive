"""击杀刀型：有整刀余量时默认整刀；申请带 b 且有余补偿时走补偿击杀。"""
from __future__ import annotations

import unittest

try:
    from .classifier import TimelineInfo
    from .settlement import apply_settlement_to_budget
except ImportError:
    from classifier import TimelineInfo
    from settlement import apply_settlement_to_budget

from types import SimpleNamespace


def _budget(**kwargs):
    base = {
        "viewer_id": 1,
        "pcr_date": "2026-09-26",
        "used_full": 1,
        "avail_comp": 1,
        "used_points": 1.5,
        "comp_seconds": 90,
        "comp_boss": 1,
        "updated_at": 0,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestKillSettlementPriority(unittest.TestCase):
    def test_kill_prefers_full_when_both_available(self) -> None:
        b = _budget()
        r = apply_settlement_to_budget(
            b, is_kill=True, damage=100, declared_comp_apply=False
        )
        self.assertEqual(r.settled_kind, "full")
        self.assertEqual(b.used_full, 2)
        self.assertEqual(b.avail_comp, 2)

    def test_kill_with_apply_b_uses_comp(self) -> None:
        b = _budget()
        r = apply_settlement_to_budget(
            b, is_kill=True, damage=100, declared_comp_apply=True
        )
        self.assertEqual(r.settled_kind, "comp")
        self.assertEqual(b.used_full, 1)
        self.assertEqual(b.avail_comp, 0)

    def test_timeline_seconds_match_beats_kill_full_heuristic(self) -> None:
        b = _budget(comp_seconds=35)
        r = apply_settlement_to_budget(
            b,
            is_kill=True,
            damage=100,
            declared_comp_apply=False,
            timeline=TimelineInfo(35, 35),
        )
        self.assertEqual(r.settled_kind, "comp")
        self.assertEqual(b.used_full, 1)


if __name__ == "__main__":
    unittest.main()
