"""已迁移 → python -m devtools.previews.knife_report"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    print("[KCR] tools/ 已迁移，运行 devtools.previews.knife_report …")
    runpy.run_module("devtools.previews.knife_report", run_name="__main__")
