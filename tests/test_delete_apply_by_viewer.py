"""delete_apply_by_viewer 仅按 viewer_id 删除（同 QQ 多号互不牵连）。"""
from __future__ import annotations

import unittest
from pathlib import Path


class DeleteApplyByViewerContractTests(unittest.TestCase):
    def test_dal_filters_by_viewer_only(self) -> None:
        dal_path = (
            Path(__file__).resolve().parents[1] / "database" / "dal.py"
        )
        src = dal_path.read_text(encoding="utf-8")
        chunk = src.split("async def delete_apply_by_viewer")[1].split(
            "async def count_notice"
        )[0]
        self.assertIn("NoticeCache.viewer_id == viewer_id", chunk)
        self.assertNotIn("user_id.in_", chunk)


if __name__ == "__main__":
    unittest.main()
