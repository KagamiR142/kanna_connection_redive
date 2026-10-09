"""PNG 渲染共用基础设施（字体、后续可扩展配色常量）。"""
from .fonts import load_font, resolve_font_path

__all__ = ["load_font", "resolve_font_path"]
