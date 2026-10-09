"""周目 Boss 出刀记录图 DTO。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class BossLapKnifeEntryDTO:
    actor_label: str
    time_text: str
    damage: int
    knife_type: str
    hp_before: int
    hp_after: int
    hp_after_percent: str = ""


@dataclass
class BossLapSectionDTO:
    lap: int
    subtitle: str
    entries: List[BossLapKnifeEntryDTO] = field(default_factory=list)


@dataclass
class BossLapRecordsReportDTO:
    title: str
    subtitle: str = ""
    entries: List[BossLapKnifeEntryDTO] = field(default_factory=list)
    sections: List[BossLapSectionDTO] = field(default_factory=list)
    empty_text: str = ""
    max_hp: int = 0
    query_day_ts: int = 0
