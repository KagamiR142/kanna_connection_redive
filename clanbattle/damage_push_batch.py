"""同 poll 内报刀推送合并：同 Boss 且 create_time 相差 ≤1s 合并为一条消息。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from loguru import logger

from .challenging_count_text import format_challenging_count_line

MERGE_WINDOW_SEC = 1


@dataclass
class DamagePushBlock:
    """单条出刀结算对应的报刀块（不含合并后的完整消息）。"""

    boss_order: int
    create_time: int
    headline: str
    status_line: str
    challenger_count: int
    challenger_lines: List[str]
    boss_enter_signal: int = 0
    merge_line_prefix: str = ""
    merge_line_suffix: str = ""


def merge_window_key(boss_order: int, create_time: int) -> Tuple[int, int]:
    """同 Boss、同一秒级时间窗内的结算可合并。"""
    ts = int(create_time or 0)
    return int(boss_order), ts // MERGE_WINDOW_SEC


def merge_damage_push_blocks(blocks: Sequence[DamagePushBlock]) -> str:
    """多条 headline，状态行与挑战者区各保留最后一刀结算后的内容。"""
    if not blocks:
        return ""
    headlines = [b.headline for b in blocks if b.headline]
    last = blocks[-1]
    prefix = last.merge_line_prefix or ""
    at_tokens: List[str] = []
    threshold_line = ""
    for b in blocks:
        if b.merge_line_prefix:
            prefix = b.merge_line_prefix
        if not b.merge_line_suffix:
            continue
        for line in b.merge_line_suffix.split("\n"):
            if line.startswith("合刀线："):
                threshold_line = line
            elif line.strip():
                for token in line.split():
                    if token.startswith("[CQ:at,") and token not in at_tokens:
                        at_tokens.append(token)
    suffix_parts: List[str] = []
    if at_tokens:
        suffix_parts.append(" ".join(at_tokens))
    if threshold_line:
        suffix_parts.append(threshold_line)
    suffix = "\n".join(suffix_parts)
    body_lines = [
        *headlines,
        last.status_line,
        format_challenging_count_line(
            last.challenger_count, last.boss_enter_signal
        ),
        *last.challenger_lines,
    ]
    lines: List[str] = []
    if prefix:
        lines.append(prefix)
    lines.extend(body_lines)
    if suffix:
        lines.append(suffix)
    return "\n".join(lines)


def group_blocks_for_merge(
    blocks: Sequence[DamagePushBlock],
) -> List[List[DamagePushBlock]]:
    """按 (boss, 1s 窗) 分组，保持输入顺序。"""
    if not blocks:
        return []
    groups: List[List[DamagePushBlock]] = []
    current_key: Tuple[int, int] | None = None
    for block in blocks:
        key = merge_window_key(block.boss_order, block.create_time)
        if current_key is None or key != current_key:
            groups.append([block])
            current_key = key
        else:
            groups[-1].append(block)
    return groups


def flush_damage_push_batch(
    blocks: Sequence[DamagePushBlock],
    *,
    group_id: int,
) -> List[str]:
    """合并后得到待发送的多条消息（不同 Boss / 时间窗各一条）。"""
    messages: List[str] = []
    for group in group_blocks_for_merge(blocks):
        if len(group) == 1:
            messages.append(merge_damage_push_blocks(group))
            continue
        msg = merge_damage_push_blocks(group)
        messages.append(msg)
        logger.info(
            "报刀合并: group={} boss={} count={} window_sec={}",
            group_id,
            group[0].boss_order,
            len(group),
            merge_window_key(group[0].boss_order, group[0].create_time)[1],
        )
    return messages


__all__ = [
    "DamagePushBlock",
    "MERGE_WINDOW_SEC",
    "flush_damage_push_batch",
    "merge_damage_push_blocks",
    "merge_window_key",
]
