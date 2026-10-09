"""合刀线相关 HP 简略格式（亿为单位，一位小数 + e）。"""
from __future__ import annotations


def format_hp_e(hp: int) -> str:
    """如 5.5e（5.5亿）、0.5e（五千万）。"""
    value = round(float(hp) / 1e8, 1)
    return f"{value:.1f}e"
