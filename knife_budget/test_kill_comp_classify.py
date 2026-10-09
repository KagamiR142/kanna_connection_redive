"""kill_comp 分类：D<R 击杀在 R>0 时按合刀 R_eff=min(R,D)。"""
from __future__ import annotations

import unittest

try:
    from .kill_comp import KillCompKind, classify_kill_comp, resolve_kill_comp_seconds
except ImportError:
    from kill_comp import KillCompKind, classify_kill_comp, resolve_kill_comp_seconds


class KillCompClassifyTests(unittest.TestCase):
    def test_d_less_than_r_is_merge_when_r_positive(self) -> None:
        self.assertEqual(
            classify_kill_comp(749_664_146, 295_718_651, is_kill=True),
            KillCompKind.MERGE,
        )

    def test_resolve_uses_r_eff_for_d_less_than_r(self) -> None:
        res = resolve_kill_comp_seconds(
            749_664_146,
            295_718_651,
            is_kill=True,
            context="test",
        )
        self.assertEqual(res.kind, KillCompKind.MERGE)
        self.assertIsNotNone(res.seconds)
        self.assertGreaterEqual(int(res.seconds or 0), 21)
        self.assertLessEqual(int(res.seconds or 0), 90)


if __name__ == "__main__":
    unittest.main()
