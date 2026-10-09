"""战报去重（`python test_record_report.py`）。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

try:
    from .knife_state import KnifeDisplayState
    from .record_report import prepare_records_for_knife_report
except ImportError:
    from knife_state import KnifeDisplayState
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
        "knife_settled_at": 0,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestRecordReport(unittest.TestCase):
    def test_drop_full_when_kill_same_knife(self) -> None:
        full = _rec(
            battle_log_id=10,
            knife_state=int(KnifeDisplayState.FULL),
            time=1000,
        )
        kill = _rec(
            battle_log_id=11,
            knife_state=int(KnifeDisplayState.KILL),
            is_kill=1,
            time=1005,
            kill_comp_seconds=21,
        )
        out = prepare_records_for_knife_report([full, kill])
        self.assertEqual(len(out), 1)
        self.assertEqual(int(out[0].knife_state), int(KnifeDisplayState.KILL))

    def test_same_moment_full_and_comp_keeps_comp(self) -> None:
        full = _rec(
            battle_log_id=10,
            time=2000,
            lap=30,
            boss=4,
            damage=319468688,
            knife_state=int(KnifeDisplayState.FULL),
            knife_settled_at=0,
        )
        comp = _rec(
            battle_log_id=11,
            time=2000,
            lap=30,
            boss=4,
            damage=319468688,
            knife_state=int(KnifeDisplayState.COMP),
            flag=0.5,
            knife_settled_at=2000,
        )
        out = prepare_records_for_knife_report([full, comp])
        self.assertEqual(len(out), 1)
        self.assertEqual(int(out[0].knife_state), int(KnifeDisplayState.COMP))

    def test_drop_full_when_kill_different_damage(self) -> None:
        full = _rec(
            battle_log_id=10,
            damage=305849712,
            knife_state=int(KnifeDisplayState.FULL),
            time=1000,
        )
        kill = _rec(
            battle_log_id=11,
            damage=320531942,
            knife_state=int(KnifeDisplayState.KILL),
            is_kill=1,
            time=1008,
        )
        out = prepare_records_for_knife_report([full, kill])
        self.assertEqual(len(out), 1)
        self.assertEqual(int(out[0].knife_state), int(KnifeDisplayState.KILL))

    def test_same_log_id_prefers_kill(self) -> None:
        full = _rec(
            battle_log_id=99,
            knife_state=int(KnifeDisplayState.FULL),
            knife_settled_at=0,
        )
        kill = _rec(
            battle_log_id=99,
            knife_state=int(KnifeDisplayState.KILL),
            is_kill=1,
            knife_settled_at=100,
        )
        out = prepare_records_for_knife_report([full, kill])
        self.assertEqual(len(out), 1)
        self.assertEqual(int(out[0].knife_state), int(KnifeDisplayState.KILL))


if __name__ == "__main__":
    unittest.main()
