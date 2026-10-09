"""公会今日刀数聚合与战报去重一致性（`python test_guild_today_counts.py`）。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

try:
    from .knife_state import KnifeDisplayState, aggregate_day_knife_counts
    from .record_report import prepare_records_for_knife_report
except ImportError:
    from knife_state import KnifeDisplayState, aggregate_day_knife_counts
    from record_report import prepare_records_for_knife_report


def _rec(**kwargs):
    base = {
        "group_id": 1,
        "battle_log_id": 0,
        "pcrid": 1,
        "lap": 15,
        "boss": 1,
        "damage": 100,
        "time": 1000,
        "knife_state": int(KnifeDisplayState.FULL),
        "is_kill": 0,
        "flag": 0.0,
        "knife_settled_at": 0,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestGuildTodayCounts(unittest.TestCase):
    def test_prepare_before_aggregate_dedupes_full_kill(self) -> None:
        full = _rec(
            battle_log_id=10,
            knife_state=int(KnifeDisplayState.FULL),
        )
        kill = _rec(
            battle_log_id=11,
            knife_state=int(KnifeDisplayState.KILL),
            is_kill=1,
            time=1005,
        )
        prepared = prepare_records_for_knife_report([full, kill])
        used, full_n, comp_n = aggregate_day_knife_counts(prepared)
        self.assertEqual(full_n, 1)
        self.assertEqual(comp_n, 0)
        self.assertEqual(used, 1.0)

    def test_raw_double_count_without_prepare(self) -> None:
        full = _rec(
            battle_log_id=10,
            knife_state=int(KnifeDisplayState.FULL),
        )
        kill = _rec(
            battle_log_id=11,
            knife_state=int(KnifeDisplayState.KILL),
            is_kill=1,
            time=1005,
        )
        used, full_n, _ = aggregate_day_knife_counts([full, kill])
        self.assertEqual(full_n, 2)
        self.assertEqual(used, 2.0)

    def test_knife_triplet_equation_after_prepare(self) -> None:
        rows = [
            _rec(battle_log_id=1, knife_state=int(KnifeDisplayState.FULL)),
            _rec(
                battle_log_id=2,
                pcrid=2,
                knife_state=int(KnifeDisplayState.COMP),
                flag=0.5,
            ),
            _rec(
                battle_log_id=3,
                pcrid=3,
                knife_state=int(KnifeDisplayState.COMP_KILL),
                is_kill=1,
                flag=0.5,
            ),
        ]
        prepared = prepare_records_for_knife_report(rows)
        used, full_n, comp_n = aggregate_day_knife_counts(prepared)
        weight = round((full_n + 0.5 * comp_n) * 2) / 2
        self.assertEqual(used, weight)
        self.assertEqual(full_n, 1)
        self.assertEqual(comp_n, 2)
        self.assertEqual(used, 2.0)


if __name__ == "__main__":
    unittest.main()
