"""record_semantics 映射契约（`python test_record_semantics.py`）。"""
from __future__ import annotations

import unittest


def _map_semantics(display_state: int, record_flag: float, record_is_kill: int) -> dict:
    """与 `semantics_from_settlement` 保持一致的纯函数契约（单测不拉全栈依赖）。"""
    return {
        "knife_state": int(display_state),
        "flag": float(record_flag),
        "is_kill": int(record_is_kill),
    }


class TestRecordSemantics(unittest.TestCase):
    def test_kill_semantics(self) -> None:
        s = _map_semantics(1, 0.0, 1)
        self.assertEqual(s["knife_state"], 1)
        self.assertEqual(s["is_kill"], 1)
        self.assertEqual(s["flag"], 0.0)

    def test_comp_semantics(self) -> None:
        s = _map_semantics(2, 0.5, 0)
        self.assertEqual(s["knife_state"], 2)
        self.assertEqual(s["is_kill"], 0)
        self.assertEqual(s["flag"], 0.5)


if __name__ == "__main__":
    unittest.main()
