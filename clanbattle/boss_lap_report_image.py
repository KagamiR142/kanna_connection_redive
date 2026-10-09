"""周目 Boss 出刀记录 PNG。"""
from __future__ import annotations

from .boss_lap_report_dto import BossLapKnifeEntryDTO, BossLapRecordsReportDTO
from .report_image import REPORT_COL_SEP, ReportLine, render_report_png


def _entry_head_line(ent: BossLapKnifeEntryDTO) -> str:
    return (
        f"{ent.actor_label}{REPORT_COL_SEP}{ent.time_text}{REPORT_COL_SEP}"
        f"{ent.damage}{REPORT_COL_SEP}{ent.knife_type}"
    )


def _append_entry_lines(
    lines: list[ReportLine],
    ent: BossLapKnifeEntryDTO,
    *,
    first: bool,
) -> None:
    if not first:
        lines.append(ReportLine(kind="sep"))
    lines.append(ReportLine(kind="body", text=_entry_head_line(ent)))
    hp_line = f"    {ent.hp_before} --> {ent.hp_after}"
    if ent.hp_after_percent:
        hp_line = f"{hp_line} {ent.hp_after_percent}"
    lines.append(ReportLine(kind="body", text=hp_line))


def boss_lap_dto_to_report_lines(dto: BossLapRecordsReportDTO) -> list[ReportLine]:
    lines: list[ReportLine] = []
    if dto.subtitle:
        lines.append(ReportLine(kind="body", text=dto.subtitle))
    if dto.empty_text:
        lines.append(ReportLine(kind="body", text=dto.empty_text))
        return lines

    if dto.sections:
        for si, sec in enumerate(dto.sections):
            if si > 0:
                lines.append(ReportLine(kind="sep"))
            lines.append(
                ReportLine(kind="heading", text=f"── {sec.lap}周目 ──")
            )
            if sec.subtitle:
                lines.append(ReportLine(kind="body", text=sec.subtitle))
            for i, ent in enumerate(sec.entries):
                _append_entry_lines(lines, ent, first=(i == 0))
        return lines

    for i, ent in enumerate(dto.entries):
        _append_entry_lines(lines, ent, first=(i == 0))
    return lines


def render_boss_lap_records_png(dto: BossLapRecordsReportDTO) -> bytes:
    return render_report_png(dto.title, boss_lap_dto_to_report_lines(dto))
