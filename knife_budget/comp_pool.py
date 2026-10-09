"""未出补偿刀池：多组秒数并存（设计文档 §1.3、timeline 比对）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from loguru import logger


@dataclass(frozen=True)
class CompPoolEntry:
    seconds: int
    boss: int = 0


def _parse_raw(raw: Any) -> List[CompPoolEntry]:
    if not raw:
        return []
    if isinstance(raw, list):
        data = raw
    else:
        text = str(raw).strip()
        if not text or text == "[]":
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("comp_pool JSON 解析失败: {}", text[:120])
            return []
    out: List[CompPoolEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        sec = int(item.get("seconds") or item.get("s") or 0)
        if sec <= 0:
            continue
        out.append(
            CompPoolEntry(seconds=sec, boss=int(item.get("boss") or item.get("b") or 0))
        )
    return out


def read_comp_pool(budget) -> List[CompPoolEntry]:
    return _parse_raw(getattr(budget, "comp_pool", None))


def write_comp_pool(budget, entries: Sequence[CompPoolEntry]) -> None:
    payload = [{"seconds": int(e.seconds), "boss": int(e.boss)} for e in entries]
    budget.comp_pool = json.dumps(payload, ensure_ascii=False)
    _sync_legacy_fields(budget, entries)


def _sync_legacy_fields(budget, entries: Sequence[CompPoolEntry]) -> None:
    if entries:
        budget.comp_seconds = int(entries[0].seconds)
        budget.comp_boss = int(entries[0].boss)
    else:
        budget.comp_seconds = 0
        budget.comp_boss = 0


def ensure_comp_pool_migrated(budget) -> List[CompPoolEntry]:
    """将旧版单条 comp_seconds 迁入 comp_pool（幂等）。"""
    entries = read_comp_pool(budget)
    if entries:
        return entries
    sec = int(getattr(budget, "comp_seconds", 0) or 0)
    if sec > 0:
        entries = [
            CompPoolEntry(
                seconds=sec, boss=int(getattr(budget, "comp_boss", 0) or 0)
            )
        ]
        write_comp_pool(budget, entries)
        logger.debug(
            "comp_pool 迁移旧字段: viewer={} entries={}",
            getattr(budget, "viewer_id", None),
            len(entries),
        )
    return entries


def comp_seconds_candidates(budget) -> List[int]:
    entries = ensure_comp_pool_migrated(budget)
    return sorted({e.seconds for e in entries})


def add_comp_to_pool(
    budget,
    seconds: int,
    *,
    boss_order: int = 0,
    viewer_id: Optional[int] = None,
) -> None:
    sec = int(seconds)
    if sec <= 0:
        return
    entries = list(ensure_comp_pool_migrated(budget))
    entries.append(CompPoolEntry(seconds=sec, boss=int(boss_order or 0)))
    write_comp_pool(budget, entries)
    logger.info(
        "comp_pool 新增: viewer={} boss={} sec={} total={}",
        viewer_id or getattr(budget, "viewer_id", None),
        boss_order,
        sec,
        len(entries),
    )


def list_pending_comp_entries(budget) -> List[CompPoolEntry]:
    """未出补偿池快照（展示/统计共用）。"""
    return list(ensure_comp_pool_migrated(budget))


def consume_comp_from_pool(
    budget,
    *,
    seconds: Optional[int] = None,
    viewer_id: Optional[int] = None,
) -> Optional[int]:
    entries = list(ensure_comp_pool_migrated(budget))
    if not entries:
        _sync_legacy_fields(budget, [])
        return None
    idx = 0
    if seconds is not None:
        target = int(seconds)
        for i, e in enumerate(entries):
            if e.seconds == target:
                idx = i
                break
        else:
            logger.warning(
                "comp_pool 无匹配秒数，跳过池消耗: viewer={} target={} pool={}",
                viewer_id or getattr(budget, "viewer_id", None),
                target,
                [e.seconds for e in entries],
            )
            return None
    removed = entries.pop(idx)
    write_comp_pool(budget, entries)
    logger.info(
        "comp_pool 消耗: viewer={} sec={} remain={}",
        viewer_id or getattr(budget, "viewer_id", None),
        removed.seconds,
        len(entries),
    )
    return removed.seconds


def pool_has_comp_resources(budget) -> bool:
    return bool(comp_seconds_candidates(budget)) or int(
        getattr(budget, "avail_comp", 0) or 0
    ) > 0
