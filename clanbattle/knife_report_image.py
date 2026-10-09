"""出刀/战报 PNG 渲染（委托 report_image）。"""
from __future__ import annotations

from typing import Union

from .knife_report_builder import (
    guild_dto_to_lines,
    guild_knife_count_dto_to_report_lines,
    user_dto_to_report_lines,
)
from .knife_report_dto import (
    GuildKnifeCountReportDTO,
    GuildPointsReportDTO,
    UserKnifeReportDTO,
)
from .report_image import render_report_png


def render_user_knife_report_png(dto: UserKnifeReportDTO) -> bytes:
    return render_report_png(dto.title, user_dto_to_report_lines(dto))


def render_guild_points_report_png(dto: GuildPointsReportDTO) -> bytes:
    return render_report_png(
        dto.title,
        guild_dto_to_lines(dto),
        subtitle=dto.subtitle,
    )


def render_guild_knife_count_report_png(dto: GuildKnifeCountReportDTO) -> bytes:
    title = "今日出刀 · 公会统计"
    if len(dto.day_sections) == 1:
        title = f"今日出刀 · {dto.day_sections[0].yymmdd}"
    elif dto.day_sections:
        title = f"当期出刀 · {dto.day_sections[0].yymmdd}-{dto.day_sections[-1].yymmdd}"
    return render_report_png(title, guild_knife_count_dto_to_report_lines(dto))


def render_report_from_dto(
    dto: Union[UserKnifeReportDTO, GuildPointsReportDTO, GuildKnifeCountReportDTO],
) -> bytes:
    if isinstance(dto, UserKnifeReportDTO):
        return render_user_knife_report_png(dto)
    if isinstance(dto, GuildKnifeCountReportDTO):
        return render_guild_knife_count_report_png(dto)
    return render_guild_points_report_png(dto)
