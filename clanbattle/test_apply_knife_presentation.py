"""阶段 L：`infer_queue_knife_presentation` 单元测试（遗留入口）。

pytest CI 使用 `tests/test_apply_knife_presentation.py`。
"""
from __future__ import annotations

import unittest

try:
    from .apply_knife_presentation import infer_queue_knife_presentation
except ImportError:
    from apply_knife_presentation import infer_queue_knife_presentation


def _s(full: int, comp: int, comp_seconds: int = 0) -> dict:
    return {"full": full, "comp": comp, "comp_seconds": comp_seconds}


class TestInferQueueKnifePresentation(unittest.TestCase):
    def test_kill_then_apply_infer_comp(self) -> None:
        pres = infer_queue_knife_presentation(_s(2, 1, 90), declared_comp=False)
        self.assertEqual(pres.kind, "infer_comp")
        self.assertTrue(pres.mark_comp_in_queue)
        self.assertIn("推断为补偿", pres.type_suffix)

    def test_only_full(self) -> None:
        pres = infer_queue_knife_presentation(_s(2, 0, 0), declared_comp=False)
        self.assertEqual(pres.kind, "full")
        self.assertFalse(pres.mark_comp_in_queue)

    def test_declared_comp(self) -> None:
        pres = infer_queue_knife_presentation(_s(2, 1, 90), declared_comp=True)
        self.assertEqual(pres.kind, "comp")
        self.assertTrue(pres.mark_comp_in_queue)

    def test_no_full_only_comp(self) -> None:
        pres = infer_queue_knife_presentation(_s(0, 1, 0), declared_comp=False)
        self.assertEqual(pres.kind, "comp")
        self.assertTrue(pres.mark_comp_in_queue)

    def test_dual_no_comp_seconds_infer_comp(self) -> None:
        pres = infer_queue_knife_presentation(_s(2, 1, 0), declared_comp=False)
        self.assertEqual(pres.kind, "infer_comp")
        self.assertTrue(pres.mark_comp_in_queue)


if __name__ == "__main__":
    unittest.main()
