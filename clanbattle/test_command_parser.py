"""指令解析单元测试（遗留入口：`cd clanbattle && python test_command_parser.py`）。

pytest CI 使用 `tests/test_command_parser.py`（无需 Hoshino）。
"""
from __future__ import annotations

import unittest

try:
    from .command_parser import (
        parse_board_message,
        parse_boss_lap_records,
        parse_cancel_board_message,
    )
except ImportError:
    from command_parser import (
        parse_board_message,
        parse_boss_lap_records,
        parse_cancel_board_message,
    )


class TestBoardMessageParser(unittest.TestCase):
    def test_colon_variants(self) -> None:
        for sep in (":", "：", "﹕", "︰"):
            p = parse_board_message(f"留言3{sep}今晚别动")
            self.assertIsNotNone(p)
            self.assertEqual(p.boss, 3)
            self.assertEqual(p.remark, "今晚别动")

    def test_cancel_board_message(self) -> None:
        boss, ok = parse_cancel_board_message("取消留言2")
        self.assertTrue(ok)
        self.assertEqual(boss, 2)

    def test_boss_lap_records(self) -> None:
        p = parse_boss_lap_records("出刀记录3")
        self.assertIsNotNone(p)
        self.assertEqual(p.boss, 3)
        self.assertIsNone(p.lap)
        p2 = parse_boss_lap_records("出刀记录1周目15")
        self.assertEqual(p2.lap, 15)
        p3 = parse_boss_lap_records("出刀记录2 29")
        self.assertEqual(p3.boss, 2)
        self.assertEqual(p3.lap, 29)
        p4 = parse_boss_lap_records("出刀记录229")
        self.assertEqual(p4.boss, 2)
        self.assertEqual(p4.lap, 29)


if __name__ == "__main__":
    unittest.main()
