"""生成 README 用到的 docs/assets/readme/*.png（统一样例数据）。

用法（模块根目录）:
    python -m devtools.previews.readme_assets
"""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    scripts = (
        "devtools.previews.status",
        "devtools.previews.guild_stats",
        "devtools.previews.knife_report",
        "devtools.previews.boss_query",
        "devtools.previews.boss_lap_records",
    )
    for mod in scripts:
        print(f">>> python -m {mod}")
        proc = subprocess.run([sys.executable, "-m", mod])
        if proc.returncode != 0:
            return proc.returncode
    print("README 示例图已写入 docs/assets/readme/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
