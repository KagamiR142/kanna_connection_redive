"""出刀/战报 PNG 通用渲染（与 status_image 共用字体与配色）。"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from ..util.image.fonts import load_font, resolve_font_path

BG = (245, 238, 218)
TITLE_COLOR = (55, 50, 45)
SUBTITLE_COLOR = (120, 110, 95)
BODY_COLOR = (40, 38, 35)
ACCENT = (180, 70, 60)
HEADING_COLOR = (200, 45, 45)
MARGIN = 42
LINE_H = 36
TITLE_H = 44
SUBTITLE_H = 30
PIPE_SEP = " || "
SEP_LINE = "————————————"
REPORT_COL_SEP = "  "
DEFAULT_BODY_WIDTH = 720


@dataclass
class ReportLine:
    kind: str  # body | accent | sep | pipes | heading
    text: str = ""
    items: Tuple[str, ...] = ()


def _font(size: int) -> ImageFont.FreeTypeFont:
    return load_font(size)


def layout_pipe_joined(
    items: Sequence[str],
    max_inner_width: float,
    font: ImageFont.FreeTypeFont,
    draw: ImageDraw.ImageDraw,
) -> List[str]:
    """账号列表换行：仅在 ` || ` 之间断开；行末可带 ` || `。"""
    if not items:
        return []
    lines: List[str] = []
    current = ""
    for item in items:
        if not current:
            current = item
            continue
        trial = current + PIPE_SEP + item
        if draw.textlength(trial, font=font) <= max_inner_width:
            current = trial
        else:
            lines.append(current + PIPE_SEP)
            current = item
    if current:
        lines.append(current)
    return lines


def _expand_report_lines(
    structured: Sequence[ReportLine],
    body_width: float,
) -> List[Tuple[str, str]]:
    """展开为 (text, kind) 列表供绘制。"""
    body_font = _font(18)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    out: List[Tuple[str, str]] = []
    for row in structured:
        if row.kind == "sep":
            out.append((SEP_LINE, "sep"))
        elif row.kind == "accent":
            out.append((row.text, "accent"))
        elif row.kind == "body":
            out.append((row.text, "body"))
        elif row.kind == "pipes":
            for seg in layout_pipe_joined(row.items, body_width, body_font, draw):
                out.append((seg, "body"))
        elif row.kind == "heading":
            out.append((row.text, "heading"))
        else:
            out.append((row.text, "body"))
    return out


def _wrap_plain_line(text: str, max_chars: int = 46) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    parts: List[str] = []
    buf = ""
    width = 0
    for ch in text:
        w = 2 if len(ch.encode("utf-8")) > 1 else 1
        if width + w > max_chars and buf:
            parts.append(buf)
            buf = ch
            width = w
        else:
            buf += ch
            width += w
    if buf:
        parts.append(buf)
    return parts


def _measure_render_lines(
    title: str,
    subtitle: Optional[str],
    lines: Sequence[Union[str, ReportLine]],
) -> Tuple[int, List[Tuple[str, str]]]:
    title_font = _font(22)
    body_font = _font(18)
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    max_w = draw.textlength(title, font=title_font)
    if subtitle:
        max_w = max(max_w, draw.textlength(subtitle, font=_font(15)))

    if lines and isinstance(lines[0], ReportLine):
        canvas_w = max(int(max_w + MARGIN * 2), DEFAULT_BODY_WIDTH + MARGIN * 2)
        body_width = canvas_w - MARGIN * 2
        flat = _expand_report_lines(lines, body_width)
    else:
        flat = []
        for line in lines:
            for seg in _wrap_plain_line(str(line)):
                flat.append((seg, "body"))

    for text, _kind in flat:
        max_w = max(max_w, draw.textlength(text, font=body_font))

    width = int(max(max_w + MARGIN * 2, 520))
    if lines and isinstance(lines[0], ReportLine):
        body_width = width - MARGIN * 2
        flat = _expand_report_lines(lines, body_width)
    return width, flat


def render_report_png(
    title: str,
    lines: Sequence[Union[str, ReportLine]],
    *,
    subtitle: Optional[str] = None,
) -> bytes:
    width, flat = _measure_render_lines(title, subtitle, lines)
    height = MARGIN * 2 + TITLE_H + (SUBTITLE_H if subtitle else 0) + len(flat) * LINE_H
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    y = MARGIN
    draw.text((MARGIN, y), title, fill=TITLE_COLOR, font=_font(22))
    y += TITLE_H
    if subtitle:
        draw.text((MARGIN, y), subtitle, fill=SUBTITLE_COLOR, font=_font(15))
        y += SUBTITLE_H
    body_font = _font(18)
    for text, kind in flat:
        if kind == "accent":
            color = ACCENT
        elif kind == "heading":
            color = HEADING_COLOR
        elif kind == "sep":
            color = BODY_COLOR
        else:
            color = BODY_COLOR
        draw.text((MARGIN, y), text, fill=color, font=body_font)
        y += LINE_H
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
