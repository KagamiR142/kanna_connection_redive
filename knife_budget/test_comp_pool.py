"""comp_pool 多秒数并存（`python test_comp_pool.py`）。"""
from __future__ import annotations

import unittest

try:
    from .comp_pool import (
        add_comp_to_pool,
        comp_seconds_candidates,
        consume_comp_from_pool,
        read_comp_pool,
        write_comp_pool,
        CompPoolEntry,
    )
except ImportError:
    from comp_pool import (
        add_comp_to_pool,
        comp_seconds_candidates,
        consume_comp_from_pool,
        read_comp_pool,
        write_comp_pool,
        CompPoolEntry,
    )


class _Budget:
    viewer_id = 1
    comp_seconds = 0
    comp_boss = 0
    comp_pool = "[]"
    avail_comp = 0


class TestCompPool(unittest.TestCase):
    def test_multi_seconds(self) -> None:
        b = _Budget()
        add_comp_to_pool(b, 35, boss_order=2, viewer_id=1)
        add_comp_to_pool(b, 90, boss_order=3, viewer_id=1)
        self.assertEqual(sorted(comp_seconds_candidates(b)), [35, 90])
        self.assertEqual(len(read_comp_pool(b)), 2)

    def test_consume_matched(self) -> None:
        b = _Budget()
        add_comp_to_pool(b, 35)
        add_comp_to_pool(b, 90)
        sec = consume_comp_from_pool(b, seconds=90, viewer_id=1)
        self.assertEqual(sec, 90)
        self.assertEqual(sorted(comp_seconds_candidates(b)), [35])

    def test_migrate_legacy(self) -> None:
        b = _Budget()
        b.comp_seconds = 42
        b.comp_boss = 1
        self.assertEqual(comp_seconds_candidates(b), [42])

    def test_consume_no_blind_fifo(self) -> None:
        b = _Budget()
        add_comp_to_pool(b, 89)
        add_comp_to_pool(b, 90)
        self.assertIsNone(consume_comp_from_pool(b, seconds=88, viewer_id=1))
        self.assertEqual(sorted(comp_seconds_candidates(b)), [89, 90])
        sec = consume_comp_from_pool(b, seconds=90, viewer_id=1)
        self.assertEqual(sec, 90)
        self.assertEqual(sorted(comp_seconds_candidates(b)), [89])


if __name__ == "__main__":
    unittest.main()
