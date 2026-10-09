"""会战状态图 DTO（status_builder / status_image / 预览脚本共用）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueueActor:
    """预约/挑战队列项（展示游戏账号，非 QQ）。message 为预约/出刀留言。"""

    label: str
    message: Optional[str] = None
    is_unknown: bool = False
    qq_id: Optional[int] = None  # 仅兼容旧数据，状态图不展示
    is_comp: bool = False
    comp_seconds: int = 0
    is_tree: bool = False
    is_board_message: bool = False
    full_row: bool = False  # 多绑账号标签较长，状态图/查x 占满一行


@dataclass
class CompDetail:
    """单条补偿记录（boss 序号 + 秒数）。"""

    boss_order: int = 0
    comp_seconds: int = 0


@dataclass
class CompensationEntry:
    """公会成员补偿信息（下半区列表）。"""

    label: str
    comp_knives: int = 0
    comp_seconds: int = 0
    boss_order: int = 0
    # 同一账号的额外补偿段 (boss序号, 秒数)
    extra_comp: List[tuple] = field(default_factory=list)


def compensation_entry_fingerprint_dict(entry: CompensationEntry) -> Dict[str, Any]:
    """状态指纹 JSON 用（与 build_clan_status 展示字段对齐）。"""
    return asdict(entry)


@dataclass
class BossStatusDTO:
    order: int
    name: str
    unit_id: int
    lap: int
    current_hp: int
    max_hp: int
    is_behind: bool
    subscribe: List[QueueActor] = field(default_factory=list)
    challenge: List[QueueActor] = field(default_factory=list)


@dataclass
class StatusSummaryDTO:
    full_knives: int = 0
    comp_knives: int = 0
    phase: str = "A"
    guild_rank: int = 0
    compensation: List[CompensationEntry] = field(default_factory=list)


@dataclass
class ClanStatusDTO:
    summary: StatusSummaryDTO
    bosses: List[BossStatusDTO] = field(default_factory=list)
