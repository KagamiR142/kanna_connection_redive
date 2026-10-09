"""PIL 字体加载（status_image / report_image 共用）。"""
from __future__ import annotations

from pathlib import Path

from PIL import ImageFont

from ...basedata import FontPath


def resolve_font_path() -> str:
    primary = FontPath.pcr_font.value
    if primary.is_file():
        return str(primary)
    for candidate in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ):
        if candidate.is_file():
            return str(candidate)
    return ""


def load_font(size: int) -> ImageFont.FreeTypeFont:
    path = resolve_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()
