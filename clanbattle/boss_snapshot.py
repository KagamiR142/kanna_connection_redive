"""Boss 快照读取（蓝图 §4.0）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .model import ClanBattle


@dataclass
class BossSnap:
    boss: int
    lap: int
    current_hp: int
    max_hp: int
    fighter_num: int


def get_boss_snap(clan_info: Optional["ClanBattle"], boss: int) -> Optional[BossSnap]:
    if not clan_info or boss < 1 or boss > 5:
        return None
    b = clan_info.boss[boss - 1]
    return BossSnap(
        boss=boss,
        lap=b.lap_num or 0,
        current_hp=b.current_hp or 0,
        max_hp=b.max_hp or 0,
        fighter_num=b.fighter_num or 0,
    )


def format_hp_short(hp: int) -> str:
    """蓝图 hp_short：如 2531w。"""
    if hp > 10000:
        return f"{hp // 10000}w"
    return str(hp)


def format_boss_status_line(snap: BossSnap) -> str:
    from .base import format_bignum, format_precent

    hp_short = format_hp_short(snap.current_hp) if snap.current_hp else "0"
    if snap.current_hp and snap.max_hp:
        pct = format_precent(snap.current_hp / snap.max_hp)
        hp_detail = (
            f"（{format_bignum(snap.current_hp)}/{format_bignum(snap.max_hp)}，{pct}）"
        )
    else:
        hp_detail = "（无法挑战）"
    return f"{snap.lap}周目{hp_short}{hp_detail}"


def format_apply_boss_status_line(snap: BossSnap) -> str:
    """申请成功专用 Boss 行（w 缩写，与结算报刀「万」后缀分离）。"""
    from .base import format_precent

    if not snap.current_hp or not snap.max_hp:
        return f"{snap.lap}周目（无法挑战）"
    hp_w = int(snap.current_hp) // 10000
    max_w = int(snap.max_hp) // 10000
    pct = format_precent(snap.current_hp / snap.max_hp)
    return f"{snap.lap}周目 {hp_w}w/{max_w}w，{pct}"
