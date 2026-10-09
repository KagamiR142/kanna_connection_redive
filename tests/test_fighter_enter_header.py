"""进本上升沿标题：Boss 内人数 + 申请队列行数。"""
from __future__ import annotations

import unittest
from pathlib import Path


class FighterEnterHeaderTests(unittest.TestCase):
    def test_build_fighter_enter_message_header_format(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "clanbattle"
            / "queue_display_service.py"
        )
        src = path.read_text(encoding="utf-8")
        chunk = src.split("async def build_fighter_enter_message")[1].split(
            "def queue_actor_fingerprint"
        )[0]
        self.assertIn("enter_signal", chunk)
        self.assertIn("申请队列中有{z}人：", chunk)
        self.assertIn("z = len(lines)", chunk)


if __name__ == "__main__":
    unittest.main()
