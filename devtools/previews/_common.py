"""预览脚本公共：输出目录、样例常量。"""
from __future__ import annotations

from pathlib import Path

from devtools.paths import OUTPUT_DIR
from devtools.previews._boss_meta import boss_max_hp, fetch_boss_phases, load_boss_tables

# 旧预览常量；新示例图请用 _readme_sample
SAMPLE_LAP = 2
HP_RATIO = (0.72, 0.38, 0.91, 0.22, 0.06)


def output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def save_png(img, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + "._tmp.png")
    img.save(tmp, format="PNG")
    if path.exists():
        path.unlink()
    tmp.rename(path)
