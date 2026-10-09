import io
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .basedata import FilePath
from .status_dto import (
    BossStatusDTO,
    ClanStatusDTO,
    CompensationEntry,
    QueueActor,
    StatusSummaryDTO,
)
from .util.boss_assets import boss_icon_path
from .util.image.fonts import load_font, resolve_font_path

# ── 调色板 ──────────────────────────────────────────────────────────
BG_COLOR = (245, 238, 218)
CARD_COLOR = (255, 252, 242)
CARD_BORDER = (220, 208, 175)
SHADOW_COLOR = (210, 198, 165)
ACCENT_LINE = (230, 220, 195)

PILL_GRAY = (210, 208, 202)
PILL_GREEN = (186, 228, 186)
PILL_COMP = (220, 232, 248)
PILL_ALERT = (228, 94, 104)

# 区块间距（在上一轮基础上再缩减 50%）
PADDING = 3
COL_GAP = 2
ROW_GAP = 2
COL_W = 404
SLOT_H = 424
INNER_PAD = 14

BOSS_ICON_SIZE = 56
HP_BAR_H = 28
HP_BAR_TRACK = (225, 220, 210)
HP_BAR_FILL = (230, 65, 75)

FONT_BOSS_TITLE = 19
FONT_PCT = 18
FONT_LAP = 16
FONT_HP = 15
FONT_GUILD = 19
FONT_METRIC_TITLE = 16
FONT_METRIC_VAL = 21
FONT_QUEUE_LABEL = 17
FONT_PILL = 19
FONT_PILL_COMPACT = 17
FONT_COMP = FONT_PILL

QUEUE_LINE_H_COMFORT = 32
QUEUE_LINE_H_COMPACT = 28
PILL_H_COMFORT = 26
PILL_H_COMPACT = 22
PILL_GAP = 9
QUEUE_GAP = 4
QUEUE_PANEL_PAD = 5
QUEUE_LABEL_W = 40
QUEUE_CONTENT_RIGHT_PAD = 12
COMFORT_SUB_ROWS = 3
COMFORT_CH_ROWS = 4
DEFAULT_SUB_ROWS = 4
DEFAULT_CH_ROWS = 6
STOLEN_MIN_SUB_ROWS = 3
STOLEN_MIN_CH_ROWS = 3
MAX_QUEUE_ROWS = 8
TOTAL_QUEUE_LINES = 10
PILL_PAD_X = 5
MAX_COMP_TAGS = 3
COMP_LINE_H = 36

FONT_PATH = resolve_font_path()
PLACEHOLDER_ICON = FilePath.img.value / "clanbattle" / "boss_placeholder.png"


@dataclass
class _QueueVisualRow:
    kind: str  # pair | single | full | message | comp_query
    actors: List[QueueActor]


@dataclass
class _QueueLayout:
    sub_h: int
    ch_h: int
    max_sub_rows: int
    max_ch_rows: int
    pill_font: int
    line_h: int
    pill_h: int
    block_offset_y: int


def _queue_area_top() -> int:
    header_y = INNER_PAD + 2
    hp_bar_y = header_y + 30
    hp_end = hp_bar_y + HP_BAR_H
    icon_bottom = INNER_PAD + BOSS_ICON_SIZE
    return max(icon_bottom, hp_end) + 6


def _queue_inner_h() -> int:
    return SLOT_H - INNER_PAD - _queue_area_top() - QUEUE_GAP


def _panel_h_from_lines(line_count: float, line_h: int) -> int:
    return int(math.ceil(line_count * line_h + QUEUE_PANEL_PAD * 2))


def _max_rows_in_panel(panel_h: int, line_h: int) -> int:
    inner = panel_h - QUEUE_PANEL_PAD * 2
    return max(1, inner // line_h)


def _font(size: int) -> ImageFont.FreeTypeFont:
    return load_font(size)


def _text_size(text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _truncate_to_inner_width(
    text: str, inner_w: int, font: ImageFont.ImageFont
) -> str:
    """按像素宽度截断（灰胶囊账号单次截断，避免 draw_pill 二次裁剪）。"""
    text = text or ""
    if _text_size(text, font)[0] <= inner_w:
        return text
    for n in range(len(text), 0, -1):
        candidate = text[:n] + "…"
        if _text_size(candidate, font)[0] <= inner_w:
            return candidate
    return "…"


def _truncate_width(text: str, max_w: int, font: ImageFont.ImageFont) -> str:
    if _text_size(text, font)[0] <= max_w:
        return text
    for n in range(len(text), 0, -1):
        candidate = text[:n] + "…"
        if _text_size(candidate, font)[0] <= max_w:
            return candidate
    return "…"


def _actor_account_message(actor: QueueActor) -> Tuple[str, Optional[str]]:
    if actor.message:
        return actor.label, actor.message
    if ":" in actor.label and not actor.is_unknown:
        account, msg = actor.label.split(":", 1)
        return account, msg or None
    return actor.label, None


def _round_corner(img: Image.Image, radius: int = 10) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.paste(img, mask=mask)
    return result


def _card_shell(width: int, height: int) -> Image.Image:
    card = Image.new("RGBA", (width, height), CARD_COLOR + (255,))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=14,
        outline=CARD_BORDER + (255,),
        width=1,
    )
    return card


def _drop_shadow(img: Image.Image, offset: Tuple[int, int] = (2, 3)) -> Image.Image:
    border = 8
    full_w = img.width + abs(offset[0]) + border * 2
    full_h = img.height + abs(offset[1]) + border * 2
    shadow = Image.new("RGBA", (full_w, full_h), BG_COLOR + (255,))
    shadow_layer = Image.new("RGBA", img.size, SHADOW_COLOR + (140,))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(3))
    sx = border + max(offset[0], 0)
    sy = border + max(offset[1], 0)
    shadow.paste(shadow_layer, (sx, sy), shadow_layer)
    ix = border - min(offset[0], 0)
    iy = border - min(offset[1], 0)
    shadow.paste(img, (ix, iy), img if img.mode == "RGBA" else None)
    return shadow


def _fit_in_slot(content: Image.Image, slot_w: int, slot_h: int) -> Image.Image:
    slot = Image.new("RGBA", (slot_w, slot_h), (0, 0, 0, 0))
    y = max(0, (slot_h - content.height) // 2)
    slot.paste(content, (0, y), content)
    return slot


def _load_boss_icon(unit_id: int) -> Image.Image:
    if unit_id:
        path = boss_icon_path(unit_id)
        if path.is_file():
            return Image.open(path).convert("RGBA")
    if PLACEHOLDER_ICON.is_file():
        return Image.open(PLACEHOLDER_ICON).convert("RGBA")
    img = Image.new("RGBA", (128, 128), (200, 200, 200, 255))
    draw = ImageDraw.Draw(img)
    draw.text((36, 48), "?", fill=(120, 120, 120), font=_font(42))
    return img


def _draw_vertical_label(
    draw: ImageDraw.ImageDraw,
    text: str,
    label_w: int,
    origin_x: int,
    origin_y: int,
    area_h: int,
    font: ImageFont.ImageFont,
    color: Tuple[int, int, int],
    top_aligned: bool = True,
) -> None:
    gap = 2
    sizes = [_text_size(ch, font) for ch in text]
    total_h = sum(h for _, h in sizes) + gap * (len(text) - 1)
    y = origin_y + (QUEUE_PANEL_PAD if top_aligned else max(QUEUE_PANEL_PAD, (area_h - total_h) // 2))
    for ch, (cw, ch_h) in zip(text, sizes):
        draw.text((origin_x + (label_w - cw) // 2, y), ch, fill=color, font=font)
        y += ch_h + gap


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    bg: Tuple[int, int, int],
    font: ImageFont.ImageFont,
    text_color: Tuple[int, int, int] = (50, 48, 44),
    pad_x: int = PILL_PAD_X,
    align: str = "center",
    truncate: bool = True,
) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg + (255,))
    inner_w = w - pad_x * 2
    shown = (
        _truncate_width(text, inner_w, font) if truncate else (text or "")
    )
    bbox = font.getbbox(shown)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x + pad_x if align == "left" else x + (w - tw) // 2
    ty = y + (h - th) // 2 - bbox[1]
    draw.text((tx, ty), shown, fill=text_color, font=font)


def _draw_horizontal_actor_count(
    draw: ImageDraw.ImageDraw,
    label_w: int,
    count: int,
    start_y: int,
) -> None:
    font = _font(FONT_QUEUE_LABEL)
    text = str(count)
    tw, _ = _text_size(text, font)
    draw.text(
        ((label_w - tw) // 2, start_y),
        text,
        fill=(100, 95, 88),
        font=font,
    )


def _actor_prefix(actor: QueueActor) -> str:
    parts: List[str] = []
    if actor.is_board_message:
        parts.append("(留言)")
    if actor.is_comp:
        parts.append("(补)")
    if actor.is_tree:
        parts.append("(挂树)")
    return "".join(parts)


def _plain_actor(actor: QueueActor) -> QueueActor:
    account, _ = _actor_account_message(actor)
    return QueueActor(
        label=account,
        is_unknown=actor.is_unknown,
        is_comp=actor.is_comp,
        comp_seconds=actor.comp_seconds,
        is_tree=actor.is_tree,
        is_board_message=actor.is_board_message,
        full_row=actor.full_row,
    )


def _pill_text(actor: QueueActor, *, query_mode: bool) -> str:
    account, _ = _actor_account_message(actor)
    prefix = _actor_prefix(actor)
    if actor.is_comp:
        sec = int(actor.comp_seconds or 0)
        if sec > 0:
            body = f"{account} {sec}秒" if query_mode else f"{account}-{sec}s"
            return f"{prefix}{body}" if prefix else body
    if prefix:
        return f"{prefix}{account}"
    return account


def _pill_color(actor: QueueActor) -> Tuple[int, int, int]:
    if actor.is_comp or actor.is_tree:
        return PILL_ALERT
    return PILL_GRAY


def _actor_queue_priority(actor: QueueActor) -> int:
    """队列胶囊纵向顺序：挂树 > 补偿 > 留言 > 整行 > 半行。"""
    if actor.is_tree:
        return 0
    if actor.is_comp:
        return 1
    _, message = _actor_account_message(actor)
    if message:
        return 2
    if actor.full_row:
        return 3
    return 4


def _sort_queue_actors(actors: List[QueueActor]) -> List[QueueActor]:
    indexed = list(enumerate(actors))
    indexed.sort(key=lambda item: (_actor_queue_priority(item[1]), item[0]))
    result: List[QueueActor] = []
    for _, actor in indexed:
        _, message = _actor_account_message(actor)
        if message:
            result.append(actor)
        else:
            result.append(_plain_actor(actor))
    return result


def _build_queue_rows(
    actors: List[QueueActor], *, query_mode: bool = False
) -> List[_QueueVisualRow]:
    rows: List[_QueueVisualRow] = []
    plain_buf: List[QueueActor] = []

    def flush_plain() -> None:
        nonlocal plain_buf
        while plain_buf:
            if len(plain_buf) >= 2:
                rows.append(_QueueVisualRow("pair", [plain_buf.pop(0), plain_buf.pop(0)]))
            else:
                rows.append(_QueueVisualRow("single", [plain_buf.pop(0)]))

    for actor in _sort_queue_actors(actors):
        account, message = _actor_account_message(actor)
        if query_mode and actor.is_comp and not message:
            flush_plain()
            rows.append(_QueueVisualRow("comp_query", [_plain_actor(actor)]))
            continue
        if message:
            flush_plain()
            rows.append(_QueueVisualRow("message", [actor]))
        elif actor.full_row:
            flush_plain()
            rows.append(_QueueVisualRow("full", [_plain_actor(actor)]))
        else:
            plain_buf.append(_plain_actor(actor))
            if len(plain_buf) == 2:
                rows.append(_QueueVisualRow("pair", [plain_buf.pop(0), plain_buf.pop(0)]))
    flush_plain()
    return rows


def _count_queue_rows(actors: List[QueueActor], *, query_mode: bool = False) -> int:
    if not actors:
        return 1
    return len(_build_queue_rows(actors, query_mode=query_mode))


def _allocate_compact_line_budget(
    subscribe: List[QueueActor],
    challenge: List[QueueActor],
    sub_need: int,
    ch_need: int,
) -> Tuple[float, float]:
    line_budget = float(TOTAL_QUEUE_LINES)
    sub_steal = bool(subscribe) and sub_need > DEFAULT_SUB_ROWS
    ch_steal = bool(challenge) and ch_need > DEFAULT_CH_ROWS

    if not sub_steal and not ch_steal:
        sub_lines = float(DEFAULT_SUB_ROWS)
        ch_lines = float(DEFAULT_CH_ROWS)
    elif ch_steal and not sub_steal:
        ch_lines = min(
            float(ch_need),
            float(MAX_QUEUE_ROWS),
            line_budget - float(STOLEN_MIN_SUB_ROWS),
        )
        sub_lines = line_budget - ch_lines
    elif sub_steal and not ch_steal:
        sub_lines = min(
            float(sub_need),
            float(MAX_QUEUE_ROWS),
            line_budget - float(STOLEN_MIN_CH_ROWS),
        )
        ch_lines = line_budget - sub_lines
    else:
        ch_lines = min(
            float(ch_need),
            float(MAX_QUEUE_ROWS),
            line_budget - float(STOLEN_MIN_SUB_ROWS),
        )
        sub_lines = line_budget - ch_lines

    return max(1.0, sub_lines), max(1.0, ch_lines)


def _resolve_queue_layout(
    subscribe: List[QueueActor],
    challenge: List[QueueActor],
    *,
    query_mode: bool = False,
) -> _QueueLayout:
    inner_h = _queue_inner_h()
    sub_need = (
        min(_count_queue_rows(subscribe, query_mode=query_mode), MAX_QUEUE_ROWS)
        if subscribe
        else 1
    )
    ch_need = (
        min(_count_queue_rows(challenge, query_mode=query_mode), MAX_QUEUE_ROWS)
        if challenge
        else 1
    )

    if sub_need <= COMFORT_SUB_ROWS and ch_need <= COMFORT_CH_ROWS:
        content_h = inner_h - QUEUE_GAP
        total_lines = COMFORT_SUB_ROWS + COMFORT_CH_ROWS
        sub_h = int(content_h * COMFORT_SUB_ROWS / total_lines)
        ch_h = content_h - sub_h
        min_sub = _panel_h_from_lines(COMFORT_SUB_ROWS, QUEUE_LINE_H_COMFORT)
        min_ch = _panel_h_from_lines(COMFORT_CH_ROWS, QUEUE_LINE_H_COMFORT)
        if sub_h < min_sub:
            sub_h = min_sub
            ch_h = content_h - sub_h
        if ch_h < min_ch:
            ch_h = min_ch
            sub_h = content_h - ch_h
        return _QueueLayout(
            sub_h=sub_h,
            ch_h=ch_h,
            max_sub_rows=COMFORT_SUB_ROWS,
            max_ch_rows=COMFORT_CH_ROWS,
            pill_font=FONT_PILL,
            line_h=QUEUE_LINE_H_COMFORT,
            pill_h=PILL_H_COMFORT,
            block_offset_y=0,
        )

    sub_lines, ch_lines = _allocate_compact_line_budget(
        subscribe, challenge, sub_need, ch_need
    )
    sub_h = _panel_h_from_lines(sub_lines, QUEUE_LINE_H_COMPACT)
    sub_h = min(sub_h, inner_h - _panel_h_from_lines(1, QUEUE_LINE_H_COMPACT))
    ch_h = inner_h - sub_h

    sub_alloc = int(min(sub_lines, MAX_QUEUE_ROWS))
    ch_alloc = int(min(ch_lines, MAX_QUEUE_ROWS))
    rows_sub_comfort = _max_rows_in_panel(sub_h, QUEUE_LINE_H_COMFORT)
    rows_ch_comfort = _max_rows_in_panel(ch_h, QUEUE_LINE_H_COMFORT)
    comfort_fits = (
        rows_sub_comfort >= min(sub_need, sub_alloc)
        and rows_ch_comfort >= min(ch_need, ch_alloc)
    )

    if comfort_fits:
        return _QueueLayout(
            sub_h=sub_h,
            ch_h=ch_h,
            max_sub_rows=min(MAX_QUEUE_ROWS, rows_sub_comfort),
            max_ch_rows=min(MAX_QUEUE_ROWS, rows_ch_comfort),
            pill_font=FONT_PILL,
            line_h=QUEUE_LINE_H_COMFORT,
            pill_h=PILL_H_COMFORT,
            block_offset_y=0,
        )

    rows_sub = _max_rows_in_panel(sub_h, QUEUE_LINE_H_COMPACT)
    rows_ch = _max_rows_in_panel(ch_h, QUEUE_LINE_H_COMPACT)
    return _QueueLayout(
        sub_h=sub_h,
        ch_h=ch_h,
        max_sub_rows=min(MAX_QUEUE_ROWS, rows_sub),
        max_ch_rows=min(MAX_QUEUE_ROWS, rows_ch),
        pill_font=FONT_PILL_COMPACT,
        line_h=QUEUE_LINE_H_COMPACT,
        pill_h=PILL_H_COMPACT,
        block_offset_y=0,
    )


def _queue_panel(
    title: str,
    actors: List[QueueActor],
    bg_color: Tuple[int, int, int],
    panel_h: int,
    max_rows: int,
    pill_font_size: int,
    line_h: int,
    pill_h: int,
    *,
    query_mode: bool = False,
) -> Image.Image:
    content_w = COL_W - INNER_PAD * 2
    panel = Image.new("RGBA", (content_w, panel_h), bg_color + (255,))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((0, 0, content_w - 1, panel_h - 1), radius=8, fill=bg_color + (255,))
    draw.rounded_rectangle((0, 0, 4, panel_h), radius=2, fill=(180, 170, 150, 180))

    label_font = _font(FONT_QUEUE_LABEL)
    _draw_vertical_label(
        draw,
        title,
        QUEUE_LABEL_W,
        0,
        0,
        panel_h,
        label_font,
        (70, 65, 58),
        top_aligned=True,
    )

    if actors and len(actors) > 5:
        title_h = sum(_text_size(c, label_font)[1] for c in title) + 2
        _draw_horizontal_actor_count(
            draw, QUEUE_LABEL_W, len(actors), QUEUE_PANEL_PAD + title_h + 4
        )

    content_x = QUEUE_LABEL_W
    content_max_w = content_w - content_x - QUEUE_CONTENT_RIGHT_PAD
    pill_w = (content_max_w - PILL_GAP) // 2
    actor_font = _font(pill_font_size)
    inner_single = pill_w - PILL_PAD_X * 2

    if not actors:
        draw.text((content_x, QUEUE_PANEL_PAD), "暂无", fill=(150, 145, 135), font=actor_font)
        return _round_corner(panel, 8)

    rows = _build_queue_rows(actors, query_mode=query_mode)[:max_rows]
    y = QUEUE_PANEL_PAD
    for row in rows:
        py = y + (line_h - pill_h) // 2
        if row.kind == "message":
            actor = row.actors[0]
            account, message = _actor_account_message(actor)
            text = f"{account}：{message}"
            _draw_pill(
                draw,
                content_x,
                py,
                content_max_w,
                pill_h,
                text,
                PILL_GREEN,
                actor_font,
                align="left",
            )
        elif row.kind == "comp_query":
            actor = row.actors[0]
            text = _pill_text(actor, query_mode=True)
            _draw_pill(
                draw,
                content_x,
                py,
                content_max_w,
                pill_h,
                text,
                _pill_color(actor),
                actor_font,
                align="left",
            )
        elif row.kind == "full":
            actor = row.actors[0]
            text = _pill_text(actor, query_mode=query_mode)
            _draw_pill(
                draw,
                content_x,
                py,
                content_max_w,
                pill_h,
                text,
                _pill_color(actor),
                actor_font,
                align="left",
            )
        elif row.kind == "pair":
            for i, actor in enumerate(row.actors):
                px = content_x + i * (pill_w + PILL_GAP)
                shown = _truncate_to_inner_width(
                    _pill_text(actor, query_mode=query_mode),
                    inner_single,
                    actor_font,
                )
                _draw_pill(
                    draw,
                    px,
                    py,
                    pill_w,
                    pill_h,
                    shown,
                    _pill_color(actor),
                    actor_font,
                    truncate=False,
                )
        else:
            actor = row.actors[0]
            shown = _truncate_to_inner_width(
                _pill_text(actor, query_mode=query_mode),
                inner_single,
                actor_font,
            )
            _draw_pill(
                draw,
                content_x,
                py,
                pill_w,
                pill_h,
                shown,
                _pill_color(actor),
                actor_font,
                truncate=False,
            )
        y += line_h

    return _round_corner(panel, 8)


def _comp_tags(entry: CompensationEntry) -> List[Tuple[int, int]]:
    tags: List[Tuple[int, int]] = []
    if entry.boss_order or entry.comp_seconds:
        tags.append((int(entry.boss_order or 0), int(entry.comp_seconds or 0)))
    for item in entry.extra_comp or []:
        if len(item) >= 2:
            tags.append((int(item[0]), int(item[1])))
    return tags[:MAX_COMP_TAGS]


def _comp_tag_count(entry: CompensationEntry) -> int:
    return max(int(entry.comp_knives or 0), len(_comp_tags(entry)))


def _comp_sort_key(entry: CompensationEntry) -> Tuple[int, str]:
    return (-_comp_tag_count(entry), entry.label)


def _comp_text(entry: CompensationEntry) -> str:
    parts = []
    for boss, sec in _comp_tags(entry):
        b = boss if boss else "-"
        parts.append(f"({b}-{sec}s)")
    suffix = " ".join(parts)
    return f"{entry.label}  {suffix}".strip() if suffix else entry.label


def _comp_needs_full_row(entry: CompensationEntry) -> bool:
    return _comp_tag_count(entry) > 1


def _layout_comp_lines(entries: List[CompensationEntry]) -> List[List[CompensationEntry]]:
    ordered = sorted(entries, key=_comp_sort_key)
    lines: List[List[CompensationEntry]] = []
    pending: List[CompensationEntry] = []
    for entry in ordered:
        if _comp_needs_full_row(entry):
            if pending:
                lines.append(pending)
                pending = []
            lines.append([entry])
        else:
            pending.append(entry)
            if len(pending) == 2:
                lines.append(pending)
                pending = []
    if pending:
        lines.append(pending)
    return lines


def _metric_chip(title: str, value: str, bg: Tuple[int, int, int]) -> Image.Image:
    w, h = 88, 58
    chip = Image.new("RGBA", (w, h), bg + (255,))
    draw = ImageDraw.Draw(chip)
    title_font = _font(FONT_METRIC_TITLE)
    val_font = _font(FONT_METRIC_VAL)
    tw, _ = _text_size(title, title_font)
    draw.text(((w - tw) // 2, 6), title, fill=(90, 85, 80), font=title_font)
    vw, vh = _text_size(value, val_font)
    draw.text(((w - vw) // 2, h - vh - 14), value, fill=(45, 42, 38), font=val_font)
    return _round_corner(chip, 10)


def _guild_summary_card(summary: StatusSummaryDTO, comp_use_pills: bool) -> Image.Image:
    card = _card_shell(COL_W, SLOT_H)
    draw = ImageDraw.Draw(card)

    chips = [
        _metric_chip("整刀", str(summary.full_knives), (255, 210, 215)),
        _metric_chip("补偿", str(summary.comp_knives), (255, 228, 190)),
        _metric_chip("阶段", summary.phase, (186, 232, 255)),
        _metric_chip(
            "排名",
            str(summary.guild_rank) if summary.guild_rank else "-",
            (205, 235, 205),
        ),
    ]
    x = INNER_PAD
    y_top = INNER_PAD
    for chip in chips:
        card.paste(chip, (x, y_top), chip)
        x += chip.width + 7

    comp_top = y_top + 66
    comp_h = SLOT_H - comp_top - INNER_PAD
    draw.line((INNER_PAD, comp_top - 4, COL_W - INNER_PAD, comp_top - 4), fill=ACCENT_LINE, width=1)

    label_font = _font(FONT_QUEUE_LABEL)
    _draw_vertical_label(
        draw,
        "补偿详情",
        QUEUE_LABEL_W,
        INNER_PAD,
        comp_top,
        comp_h,
        label_font,
        (120, 110, 95),
        top_aligned=True,
    )

    content_x = INNER_PAD + QUEUE_LABEL_W
    content_w = COL_W - content_x - INNER_PAD
    comp_font = _font(FONT_COMP)
    line_h = COMP_LINE_H
    pill_h = PILL_H_COMFORT
    y = comp_top + QUEUE_PANEL_PAD

    if not summary.compensation:
        draw.text((content_x, y), "暂无补偿", fill=(140, 135, 125), font=comp_font)
        return _round_corner(card, 14)

    comp_lines = _layout_comp_lines(summary.compensation)
    max_y = comp_top + comp_h - INNER_PAD
    for line_entries in comp_lines:
        if y + line_h > max_y:
            draw.text((content_x, y), "…", fill=(140, 135, 125), font=comp_font)
            break
        py = y + (line_h - pill_h) // 2
        if len(line_entries) == 1:
            entry = line_entries[0]
            text = _comp_text(entry)
            _draw_pill(
                draw,
                content_x,
                py,
                content_w,
                pill_h,
                text,
                PILL_COMP,
                comp_font,
                align="left",
            )
        else:
            half_w = (content_w - PILL_GAP) // 2
            for i, entry in enumerate(line_entries):
                text = _comp_text(entry)
                px = content_x + i * (half_w + PILL_GAP)
                _draw_pill(
                    draw,
                    px,
                    py,
                    half_w,
                    pill_h,
                    text,
                    PILL_COMP,
                    comp_font,
                    align="left",
                )
        y += line_h

    return _round_corner(card, 14)


def _hp_bar_inline(current: int, maximum: int, bar_width: int) -> Image.Image:
    layer = Image.new("RGBA", (bar_width, HP_BAR_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    ratio = (current / maximum) if maximum else 0.0
    fill_w = max(HP_BAR_H, round(bar_width * ratio)) if current > 0 else 0
    radius = HP_BAR_H // 2
    draw.rounded_rectangle(
        (0, 0, bar_width - 1, HP_BAR_H), radius=radius, fill=HP_BAR_TRACK + (255,)
    )
    if fill_w:
        draw.rounded_rectangle(
            (0, 0, fill_w, HP_BAR_H), radius=radius, fill=HP_BAR_FILL + (255,)
        )
    hp_text = f"{current:,} / {maximum:,}"
    info_font = _font(FONT_HP)
    tw, th = _text_size(hp_text, info_font)
    tx = max(8, (bar_width - tw) // 2)
    ty = (HP_BAR_H - th) // 2 - 1
    draw.text(
        (tx, ty),
        hp_text,
        fill=(255, 255, 255),
        font=info_font,
        stroke_width=2,
        stroke_fill=(70, 35, 35),
    )
    return layer


def _lap_badge(lap: int, is_behind: bool) -> Image.Image:
    text = f"{lap} 周目"
    font = _font(FONT_LAP)
    tw, th = _text_size(text, font)
    h = 26
    w = tw + 14
    color = (228, 94, 104, 255) if is_behind else (106, 152, 243, 255)
    img = Image.new("RGBA", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.text(((w - tw) // 2, (h - th) // 2 - 1), text, fill=(255, 255, 255), font=font)
    return _round_corner(img, h // 2)


def _boss_card(boss: BossStatusDTO, *, query_mode: bool = False) -> Image.Image:
    card = _card_shell(COL_W, SLOT_H)
    draw = ImageDraw.Draw(card)

    icon = _load_boss_icon(boss.unit_id).resize((BOSS_ICON_SIZE, BOSS_ICON_SIZE))
    card.paste(_round_corner(icon, 10), (INNER_PAD, INNER_PAD))

    content_x = INNER_PAD + BOSS_ICON_SIZE + 12
    content_w = COL_W - content_x - INNER_PAD
    header_y = INNER_PAD + 2

    title = f"{boss.order}-{boss.name}"
    title_font = _font(FONT_BOSS_TITLE)
    pct_font = _font(FONT_PCT)
    draw.text((content_x, header_y), title, fill=(45, 42, 38), font=title_font)
    tw, th = _text_size(title, title_font)
    title_center_y = header_y + th // 2

    ratio = (boss.current_hp / boss.max_hp) if boss.max_hp else 0.0
    pct_text = f"{ratio * 100:.1f}%"
    badge = _lap_badge(boss.lap, boss.is_behind)
    badge_x = content_x + tw + 10
    badge_y = int(title_center_y - badge.height / 2)
    card.paste(badge, (badge_x, badge_y), badge)
    _, pct_h = _text_size(pct_text, pct_font)
    pct_y = int(title_center_y - pct_h / 2) - 1
    pct_color = (200, 55, 65) if ratio < 0.3 else (120, 115, 105)
    draw.text(
        (badge_x + badge.width + 8, pct_y),
        pct_text,
        fill=pct_color,
        font=pct_font,
    )

    hp = _hp_bar_inline(boss.current_hp, boss.max_hp, content_w)
    card.paste(hp, (content_x, header_y + 30), hp)

    layout = _resolve_queue_layout(
        boss.subscribe, boss.challenge, query_mode=query_mode
    )
    subscribe_y = _queue_area_top() + layout.block_offset_y
    sub_h = layout.sub_h
    ch_h = layout.ch_h
    sub_max_rows = layout.max_sub_rows
    ch_max_rows = layout.max_ch_rows
    pill_font = layout.pill_font
    line_h = layout.line_h
    pill_h = layout.pill_h
    sub = _queue_panel(
        "预约",
        boss.subscribe,
        (210, 236, 252),
        sub_h,
        sub_max_rows,
        pill_font,
        line_h,
        pill_h,
        query_mode=query_mode,
    )
    card.paste(sub, (INNER_PAD, subscribe_y), sub)
    ch = _queue_panel(
        "挑战",
        boss.challenge,
        (255, 248, 210),
        ch_h,
        ch_max_rows,
        pill_font,
        line_h,
        pill_h,
        query_mode=query_mode,
    )
    card.paste(ch, (INNER_PAD, subscribe_y + sub_h + QUEUE_GAP), ch)
    return _round_corner(card, 14)


def render_boss_query_image(boss: BossStatusDTO) -> Image.Image:
    """查[1-5] 单 Boss 区块 PNG（补偿胶囊独占一行并带秒数）。"""
    card = _boss_card(boss, query_mode=True)
    return _fit_in_slot(_drop_shadow(card), COL_W, SLOT_H).convert("RGB")


def render_status_image(
    status: ClanStatusDTO, *, comp_use_pills: bool = False
) -> Image.Image:
    bosses = status.bosses[:5]
    while len(bosses) < 5:
        bosses.append(
            BossStatusDTO(
                order=len(bosses) + 1,
                name=f"Boss{len(bosses)+1}",
                unit_id=0,
                lap=0,
                current_hp=0,
                max_hp=1,
                is_behind=False,
            )
        )

    left_slots = [
        _guild_summary_card(status.summary, comp_use_pills),
        _boss_card(bosses[0]),
        _boss_card(bosses[1]),
    ]
    right_slots = [
        _boss_card(bosses[2]),
        _boss_card(bosses[3]),
        _boss_card(bosses[4]),
    ]

    canvas_w = PADDING * 2 + COL_W * 2 + COL_GAP
    canvas_h = PADDING * 2 + SLOT_H * 3 + ROW_GAP * 2
    canvas = Image.new("RGBA", (canvas_w, canvas_h), BG_COLOR + (255,))

    for row in range(3):
        y = PADDING + row * (SLOT_H + ROW_GAP)
        left = _fit_in_slot(_drop_shadow(left_slots[row]), COL_W, SLOT_H)
        canvas.paste(left, (PADDING, y), left)
        right = _fit_in_slot(_drop_shadow(right_slots[row]), COL_W, SLOT_H)
        canvas.paste(right, (PADDING + COL_W + COL_GAP, y), right)

    return canvas.convert("RGB")


def status_image_to_bytes(
    status: ClanStatusDTO, *, comp_use_pills: bool = False
) -> bytes:
    img = render_status_image(status, comp_use_pills=comp_use_pills)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
