"""出刀/战报图 DTO。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PendingCompDTO:
    """未出补偿；entries 为 (boss_order, seconds) 列表，支持多秒数并存。"""

    entries: List[tuple[int, int]] = field(default_factory=list)

    @property
    def seconds(self) -> int:
        return self.entries[0][1] if self.entries else 0

    @property
    def boss_order(self) -> int:
        return self.entries[0][0] if self.entries else 0


@dataclass
class AccountKnifeSectionDTO:
    slot: int
    game_name: str
    lines: List[str] = field(default_factory=list)
    pending_comp: Optional[PendingCompDTO] = None
    empty_text: Optional[str] = None
    heading: str = ""


@dataclass
class UserKnifeReportDTO:
    title: str
    subtitle: str
    sections: List[AccountKnifeSectionDTO]


@dataclass
class DayPointsBucketDTO:
    day_label: str
    buckets: Dict[str, List[str]]


@dataclass
class GuildPointsReportDTO:
    title: str
    subtitle: str
    footnote: str
    day_sections: List[DayPointsBucketDTO]


@dataclass
class GuildKnifeCountDayDTO:
    yymmdd: str
    total_used_points: float
    full_knife_count: int
    comp_knife_count: int
    buckets: Dict[str, List[str]]
    pending_comp_parts: List[str]


@dataclass
class GuildKnifeCountReportDTO:
    day_sections: List[GuildKnifeCountDayDTO]
