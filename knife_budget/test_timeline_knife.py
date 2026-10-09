"""timeline 秒数匹配单元测试（`python test_timeline_knife.py`）。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

try:
    from .classifier import TimelineInfo
    from .knife_state import KnifeDisplayState
    from .settlement import apply_settlement_to_budget
    from .timeline_knife import resolve_timeline_verdict
except ImportError:
    from classifier import TimelineInfo
    from knife_state import KnifeDisplayState
    from settlement import apply_settlement_to_budget
    from timeline_knife import resolve_timeline_verdict


def _budget(**kwargs):
    base = {
        "viewer_id": 1,
        "used_full": 1,
        "avail_comp": 1,
        "used_points": 1.5,
        "comp_seconds": 35,
        "comp_boss": 1,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestTimelineSecondsMatch(unittest.TestCase):
    def test_match_comp_seconds(self) -> None:
        b = _budget(comp_seconds=35)
        v = resolve_timeline_verdict(
            TimelineInfo(35, 35), b, is_kill=True, viewer_id=1
        )
        self.assertTrue(v.force_comp_settlement)
        self.assertEqual(v.matched_comp_seconds, 35)

    def test_mismatch_with_full_remaining(self) -> None:
        b = _budget(comp_seconds=35)
        v = resolve_timeline_verdict(
            TimelineInfo(88, 90), b, is_kill=True, viewer_id=1
        )
        self.assertTrue(v.force_full_settlement)
        self.assertFalse(v.force_comp_settlement)

    def test_settlement_match_uses_comp_kill(self) -> None:
        b = _budget(comp_seconds=35)
        r = apply_settlement_to_budget(
            b,
            is_kill=True,
            damage=100,
            timeline=TimelineInfo(35, 35),
        )
        self.assertEqual(r.settled_kind, "comp")
        self.assertEqual(b.used_full, 1)

    def test_settlement_mismatch_uses_full_kill(self) -> None:
        b = _budget(comp_seconds=35)
        r = apply_settlement_to_budget(
            b,
            is_kill=True,
            damage=100,
            timeline=TimelineInfo(88, 90),
        )
        self.assertEqual(r.settled_kind, "full")
        self.assertEqual(b.used_full, 2)

    def test_timeline_full_when_used_full_exhausted(self) -> None:
        b = _budget(used_full=3, avail_comp=0, used_points=3.0, comp_seconds=35)
        r = apply_settlement_to_budget(
            b,
            is_kill=False,
            damage=100,
            timeline=TimelineInfo(88, 90),
            viewer_id=1,
        )
        self.assertEqual(r.settled_kind, "full")
        self.assertLessEqual(b.used_points, 3.0)
        self.assertLessEqual(b.used_full, 3)

    def test_dual_pool_match_90(self) -> None:
        import json

        from .comp_pool import comp_seconds_candidates

        b = _budget(comp_seconds=89, avail_comp=2, used_full=3, used_points=3.0)
        b.comp_pool = json.dumps(
            [{"seconds": 89, "boss": 2}, {"seconds": 90, "boss": 1}]
        )
        r = apply_settlement_to_budget(
            b,
            is_kill=True,
            damage=100,
            timeline=TimelineInfo(90, 90),
            viewer_id=1,
        )
        self.assertEqual(r.settled_kind, "comp")
        self.assertEqual(sorted(comp_seconds_candidates(b)), [89])

    def test_kill_srt90_points_remain_prefers_full(self) -> None:
        import json

        b = _budget(used_full=2, used_points=1.5, avail_comp=1, comp_seconds=90)
        b.comp_pool = json.dumps([{"seconds": 90, "boss": 1}])
        v = resolve_timeline_verdict(
            TimelineInfo(90, 90), b, is_kill=True, viewer_id=1
        )
        self.assertTrue(v.force_full_settlement)
        self.assertFalse(v.force_comp_settlement)
        r = apply_settlement_to_budget(
            b,
            is_kill=True,
            damage=100,
            timeline=TimelineInfo(90, 90),
            viewer_id=1,
        )
        self.assertEqual(r.settled_kind, "full")

    def test_kill_srt90_no_full_points_uses_comp(self) -> None:
        import json

        b = _budget(used_full=3, used_points=2.5, avail_comp=1, comp_seconds=90)
        b.comp_pool = json.dumps([{"seconds": 90, "boss": 1}])
        v = resolve_timeline_verdict(
            TimelineInfo(90, 90), b, is_kill=True, viewer_id=1
        )
        self.assertTrue(v.force_comp_settlement)
        self.assertFalse(v.force_full_settlement)


if __name__ == "__main__":
    unittest.main()
