"""出刀/战报图数据组装（QQ + Web 共用）。"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Union

from loguru import logger

from ..database.dal import pcr_date, pcr_sqla
from ..knife_budget.comp_pool import list_pending_comp_entries
from ..knife_budget.knife_state import (
    aggregate_day_knife_counts,
    format_record_line,
)
from ..knife_budget.record_report import prepare_records_for_knife_report
from ..knife_budget.service import knife_budget_service
from .account_label import (
    build_viewer_binding_cache,
    format_user_report_section_heading,
    format_viewer_account_label,
)
from .member_identity import viewer_to_member_qq
from .report_image import PIPE_SEP, ReportLine, SEP_LINE
from .knife_report_dto import (
    AccountKnifeSectionDTO,
    DayPointsBucketDTO,
    GuildKnifeCountDayDTO,
    GuildKnifeCountReportDTO,
    GuildPointsReportDTO,
    PendingCompDTO,
    UserKnifeReportDTO,
)
from .text_util import game_display_name

USED_POINTS_FOOTNOTE = (
    "统计口径：已用出刀点数（0～3，步长 0.5），非剩余点数"
)
_BUCKET_ORDER = [3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0]


@dataclass(frozen=True)
class GuildTodayKnifeAggregate:
    """公会单日已出刀统计（状态图、今日出刀图、指纹等统一入口）。

    used_points / full_knife_count / comp_knife_count 为「刀型三件套」展示口径，
    均来自结算记录聚合（prepare_records + aggregate_day_knife_counts）。
    budget_used_sum 仅作点数账本校验（含掉刀等），不参与刀型展示。
    """

    used_points: float
    full_knife_count: int
    comp_knife_count: int
    prepared_record_count: int
    record_used_points: float
    budget_used_sum: float


async def guild_today_knife_aggregate(
    group_id: int,
    day_ts: int,
    *,
    clan_info=None,
) -> GuildTodayKnifeAggregate:
    """公会刀型三件套：整刀/补偿/总计均来自当日结算记录聚合。

    Σ knife_budget.used_points 仅校验用；与记录侧不一致时打 WARNING。
    """
    raw = await pcr_sqla.get_day_rcords(day_ts, group_id)
    records = prepare_records_for_knife_report(raw)
    record_used, full_n, comp_n = aggregate_day_knife_counts(records)

    names = await collect_guild_viewer_names(group_id, day_ts, clan_info=clan_info)
    budget_used_sum = 0.0
    for vid in names:
        budget_used_sum += await knife_budget_service.get_used_points(vid, day_ts)
    budget_used_sum = round(budget_used_sum * 2) / 2
    record_used_r = round(float(record_used) * 2) / 2
    knife_weight = round((int(full_n) + 0.5 * int(comp_n)) * 2) / 2
    day_label = _yymmdd(day_ts)

    if abs(knife_weight - record_used_r) > 0.01:
        logger.warning(
            "公会记录刀型合计偏差: group={} day={} full={} comp={} "
            "weight={} record_pts={}",
            group_id,
            day_label,
            full_n,
            comp_n,
            knife_weight,
            record_used_r,
        )
    if abs(budget_used_sum - record_used_r) > 0.01:
        logger.warning(
            "公会今日点数口径偏差: group={} day={} budget_sum={} record_sum={} "
            "full={} comp={} raw_records={} prepared={}",
            group_id,
            day_label,
            budget_used_sum,
            record_used_r,
            full_n,
            comp_n,
            len(raw),
            len(records),
        )
    if abs(knife_weight - budget_used_sum) > 0.01:
        logger.warning(
            "公会预算与刀型合计偏差(可能含掉刀): group={} day={} budget_sum={} "
            "record_pts={} full={} comp={}",
            group_id,
            day_label,
            budget_used_sum,
            record_used_r,
            full_n,
            comp_n,
        )
    logger.info(
        "公会今日刀数: group={} day={} full={} comp={} used_pts={} "
        "budget_pts={} viewers={} prepared_records={}",
        group_id,
        day_label,
        full_n,
        comp_n,
        record_used_r,
        budget_used_sum,
        len(names),
        len(records),
    )
    return GuildTodayKnifeAggregate(
        used_points=record_used_r,
        full_knife_count=int(full_n),
        comp_knife_count=int(comp_n),
        prepared_record_count=len(records),
        record_used_points=record_used_r,
        budget_used_sum=budget_used_sum,
    )


def _group_records_by_pcrid(records: Sequence) -> Dict[int, list]:
    grouped: Dict[int, list] = defaultdict(list)
    for r in records:
        grouped[r.pcrid].append(r)
    for rows in grouped.values():
        rows.sort(key=lambda x: x.time)
    return grouped


def _format_used_bucket_key(used: float) -> str:
    v = round(float(used) * 2) / 2
    if abs(v - round(v)) < 0.01:
        return str(int(round(v)))
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _bucket_sort_key(label: str) -> float:
    try:
        return float(label)
    except ValueError:
        return 999.0


def _yymmdd(ts: int) -> str:
    return time.strftime("%y%m%d", time.localtime(ts))


async def _collect_qq_ids_for_viewers(
    viewer_ids: Iterable[int],
) -> Set[int]:
    qq_ids: Set[int] = set()
    for vid in viewer_ids:
        qq = await viewer_to_member_qq(vid)
        if qq:
            qq_ids.add(qq)
    return qq_ids


async def collect_guild_viewer_names(
    group_id: int, day_ts: int, *, clan_info=None
) -> Dict[int, str]:
    names: Dict[int, str] = {}
    for r in await pcr_sqla.get_day_rcords(day_ts, group_id):
        names[int(r.pcrid)] = r.name or str(r.pcrid)
    date_key = pcr_date(day_ts).strftime("%Y-%m-%d")
    for b in await pcr_sqla.list_knife_budgets(date_key):
        names.setdefault(int(b.viewer_id), str(b.viewer_id))
    if clan_info is not None:
        try:
            members = await clan_info.all_member()
            names.update({int(k): v for k, v in members.items()})
        except Exception as e:
            logger.debug("公会成员列表跳过 group={} err={}", group_id, e)
    return names


async def _pending_comp_for_viewer(
    viewer_id: int, *, day_ts: Optional[int] = None
) -> Optional[PendingCompDTO]:
    budget = await knife_budget_service.get_budget(viewer_id, day_ts)
    if int(budget.avail_comp or 0) <= 0:
        return None
    pool_entries = list_pending_comp_entries(budget)
    if pool_entries:
        entries = [(int(e.boss), int(e.seconds)) for e in pool_entries]
    else:
        sec = int(budget.comp_seconds or 0)
        if sec <= 0:
            return None
        entries = [(int(getattr(budget, "comp_boss", 0) or 0), sec)]
    return PendingCompDTO(entries=entries)


def _format_pending_comp_text(pending: PendingCompDTO) -> str:
    parts = [f"{boss}-{sec}s" for boss, sec in pending.entries]
    return "，".join(parts)


async def build_user_knife_report_dto(
    group_id: int,
    user_id: int,
    *,
    mode: str,
    slot_filter: Optional[int] = None,
    bot=None,
) -> Union[UserKnifeReportDTO, str]:
    from .account_service import list_bound_accounts

    accounts = await list_bound_accounts(user_id, group_id=group_id)
    if not accounts:
        return "未绑定游戏账号，请先私聊绑定账号"
    if slot_filter:
        accounts = [a for a in accounts if a.slot == slot_filter] or accounts

    pcrids = [a.viewer_id for a in accounts]
    binding_cache = await build_viewer_binding_cache(bot, group_id, pcrids)

    if mode == "today":
        title = f"今日战报 · 名下账号 · {time.strftime('%m-%d')}"
        day_ts = int(time.time())
        sections: List[AccountKnifeSectionDTO] = []
        records = prepare_records_for_knife_report(
            await pcr_sqla.get_day_records_for_pcrids(day_ts, group_id, pcrids)
        )
        grouped = _group_records_by_pcrid(records)
        for acc in accounts:
            rows = grouped.get(acc.viewer_id, [])
            gname = game_display_name(acc.name, acc.viewer_id)
            heading = await format_user_report_section_heading(
                bot,
                group_id,
                acc.viewer_id,
                gname,
                binding_cache=binding_cache,
            )
            sec = AccountKnifeSectionDTO(
                slot=acc.slot,
                game_name=gname,
                heading=heading,
            )
            if rows:
                sec.lines = [
                    format_record_line(r, query_day_ts=day_ts) for r in rows
                ]
                sec.pending_comp = await _pending_comp_for_viewer(
                    acc.viewer_id, day_ts=day_ts
                )
            else:
                sec.empty_text = "今日暂无出刀记录"
            sections.append(sec)
        return UserKnifeReportDTO(
            title=title,
            subtitle="",
            sections=sections,
        )

    days = await pcr_sqla.get_season_day_timestamps(group_id)
    if not days:
        return "本期会战目前暂无出刀数据"
    title = "当期战报 · 名下账号"
    sections = []
    for day_ts in days:
        day_label = time.strftime("%m-%d", time.localtime(day_ts))
        records = prepare_records_for_knife_report(
            await pcr_sqla.get_day_records_for_pcrids(day_ts, group_id, pcrids)
        )
        grouped = _group_records_by_pcrid(records)
        for acc in accounts:
            rows = grouped.get(acc.viewer_id, [])
            gname = game_display_name(acc.name, acc.viewer_id)
            heading = await format_user_report_section_heading(
                bot,
                group_id,
                acc.viewer_id,
                gname,
                binding_cache=binding_cache,
            )
            sec = AccountKnifeSectionDTO(
                slot=acc.slot,
                game_name=gname,
                heading=heading,
            )
            header = f"【{day_label}】{heading.rstrip('：')}"
            if rows:
                sec.lines = [header] + [
                    format_record_line(r, query_day_ts=day_ts) for r in rows
                ]
            else:
                sec.lines = [header, "  当日暂无出刀记录"]
            sections.append(sec)
    return UserKnifeReportDTO(title=title, subtitle="", sections=sections)


async def _build_day_knife_count_section(
    bot,
    group_id: int,
    day_ts: int,
    *,
    clan_info=None,
) -> GuildKnifeCountDayDTO:
    names = await collect_guild_viewer_names(group_id, day_ts, clan_info=clan_info)
    agg = await guild_today_knife_aggregate(
        group_id, day_ts, clan_info=clan_info
    )
    used_sum = agg.used_points
    full_n = agg.full_knife_count
    comp_n = agg.comp_knife_count

    used_by_viewer: Dict[int, float] = {}
    for vid in names:
        used_by_viewer[vid] = await knife_budget_service.get_used_points(
            vid, day_ts
        )

    binding_cache = await build_viewer_binding_cache(bot, group_id, names.keys())

    buckets: Dict[str, List[str]] = defaultdict(list)
    pending_parts: List[str] = []

    for vid in sorted(names.keys(), key=lambda x: names[x]):
        key = _format_used_bucket_key(used_by_viewer.get(vid, 0.0))
        label = await format_viewer_account_label(
            bot,
            group_id,
            vid,
            names[vid],
            binding_cache=binding_cache,
        )
        buckets[key].append(label)

        pend = await _pending_comp_for_viewer(vid, day_ts=day_ts)
        if pend:
            pending_parts.append(f"{label}：{_format_pending_comp_text(pend)}")

    ordered_buckets: Dict[str, List[str]] = {}
    for pts in _BUCKET_ORDER:
        k = _format_used_bucket_key(pts)
        if buckets.get(k):
            ordered_buckets[k] = buckets[k]
    for k in sorted(buckets.keys(), key=_bucket_sort_key, reverse=True):
        if k not in ordered_buckets:
            ordered_buckets[k] = buckets[k]

    logger.debug(
        "公会出刀统计: group={} day={} viewers={} used_sum={} full={} comp={}",
        group_id,
        _yymmdd(day_ts),
        len(names),
        used_sum,
        full_n,
        comp_n,
    )

    return GuildKnifeCountDayDTO(
        yymmdd=_yymmdd(day_ts),
        total_used_points=used_sum,
        full_knife_count=full_n,
        comp_knife_count=comp_n,
        buckets=ordered_buckets,
        pending_comp_parts=pending_parts,
    )


async def build_guild_knife_count_report_dto(
    group_id: int,
    bot,
    *,
    mode: str,
    clan_info=None,
) -> Union[GuildKnifeCountReportDTO, str]:
    if mode == "today":
        day_ts = int(time.time())
        names = await collect_guild_viewer_names(
            group_id, day_ts, clan_info=clan_info
        )
        if not names:
            return "数据库为空，请确保开启出刀监控"
        section = await _build_day_knife_count_section(
            bot, group_id, day_ts, clan_info=clan_info
        )
        return GuildKnifeCountReportDTO(day_sections=[section])

    days = await pcr_sqla.get_season_day_timestamps(group_id)
    if not days:
        return "本期会战目前暂无出刀数据"
    sections: List[GuildKnifeCountDayDTO] = []
    for day_ts in days:
        names = await collect_guild_viewer_names(
            group_id, day_ts, clan_info=clan_info
        )
        if not names and not await pcr_sqla.get_day_rcords(day_ts, group_id):
            continue
        sections.append(
            await _build_day_knife_count_section(
                bot, group_id, day_ts, clan_info=clan_info
            )
        )
    if not sections:
        return "本期会战目前暂无出刀数据"
    return GuildKnifeCountReportDTO(day_sections=sections)


async def _build_day_points_buckets(
    bot,
    group_id: int,
    day_ts: int,
    *,
    clan_info=None,
) -> DayPointsBucketDTO:
    names = await collect_guild_viewer_names(group_id, day_ts, clan_info=clan_info)
    used_by_viewer: Dict[int, float] = {}
    for vid in names:
        used_by_viewer[vid] = await knife_budget_service.get_used_points(vid, day_ts)
    binding_cache = await build_viewer_binding_cache(bot, group_id, names.keys())
    buckets: Dict[str, List[str]] = defaultdict(list)
    for vid in sorted(names.keys(), key=lambda x: names[x]):
        key = _format_used_bucket_key(used_by_viewer.get(vid, 0.0))
        label = await format_viewer_account_label(
            bot,
            group_id,
            vid,
            names[vid],
            binding_cache=binding_cache,
        )
        buckets[key].append(label)
    day_label = time.strftime("%m-%d", time.localtime(day_ts))
    ordered = {
        k: buckets[k]
        for k in sorted(buckets.keys(), key=_bucket_sort_key, reverse=True)
        if buckets[k]
    }
    return DayPointsBucketDTO(day_label=f"【{day_label}】", buckets=ordered)


async def build_guild_points_report_dto(
    group_id: int,
    bot,
    *,
    mode: str,
    clan_info=None,
) -> Union[GuildPointsReportDTO, str]:
    """旧版分桶战报（保留供 Web/预览）；QQ 公会指令请用 build_guild_knife_count_report_dto。"""
    if mode == "today":
        day_ts = int(time.time())
        names = await collect_guild_viewer_names(
            group_id, day_ts, clan_info=clan_info
        )
        if not names:
            return "数据库为空，请确保开启出刀监控"
        section = await _build_day_points_buckets(
            bot, group_id, day_ts, clan_info=clan_info
        )
        return GuildPointsReportDTO(
            title=f"今日战报 · 公会 · 已用出刀点数 · {time.strftime('%m-%d')}",
            subtitle=USED_POINTS_FOOTNOTE,
            footnote="",
            day_sections=[section],
        )

    days = await pcr_sqla.get_season_day_timestamps(group_id)
    if not days:
        return "本期会战目前暂无出刀数据"
    sections: List[DayPointsBucketDTO] = []
    for day_ts in days:
        recs = await pcr_sqla.get_day_rcords(day_ts, group_id)
        if not recs:
            continue
        sections.append(
            await _build_day_points_buckets(
                bot, group_id, day_ts, clan_info=clan_info
            )
        )
    if not sections:
        return "本期会战目前暂无出刀数据"
    return GuildPointsReportDTO(
        title="当期战报 · 公会 · 已用出刀点数",
        subtitle=USED_POINTS_FOOTNOTE,
        footnote="每日为该日结束时 used_points 快照",
        day_sections=sections,
    )


def _format_total_used_points(value: float) -> str:
    v = round(float(value) * 2) / 2
    if abs(v - round(v)) < 0.01:
        return str(int(round(v)))
    return f"{v:.1f}".rstrip("0").rstrip(".")


def guild_knife_count_dto_to_report_lines(
    dto: GuildKnifeCountReportDTO,
) -> List[ReportLine]:
    lines: List[ReportLine] = []
    for day in dto.day_sections:
        lines.append(ReportLine(kind="sep"))
        lines.append(
            ReportLine(kind="accent", text=f"以下是{day.yymmdd}出刀次数统计：")
        )
        lines.append(
            ReportLine(
                kind="body",
                text=(
                    f"总计出刀：{_format_total_used_points(day.total_used_points)}，"
                    f"其中整刀{day.full_knife_count}刀，补偿{day.comp_knife_count}刀"
                ),
            )
        )
        for key in sorted(day.buckets.keys(), key=_bucket_sort_key, reverse=True):
            members = day.buckets.get(key) or []
            if not members:
                continue
            lines.append(ReportLine(kind="sep"))
            lines.append(
                ReportLine(kind="accent", text=f"以下是出了{key}刀的成员：")
            )
            lines.append(ReportLine(kind="pipes", items=tuple(members)))
        if day.pending_comp_parts:
            lines.append(ReportLine(kind="sep"))
            lines.append(ReportLine(kind="accent", text="未出的补偿刀："))
            lines.append(
                ReportLine(kind="pipes", items=tuple(day.pending_comp_parts))
            )
        lines.append(ReportLine(kind="sep"))
    return lines


def guild_knife_count_dto_to_lines(dto: GuildKnifeCountReportDTO) -> List[str]:
    """纯文本预览（测试/日志）；QQ 图请用 guild_knife_count_dto_to_report_lines。"""
    out: List[str] = []
    for row in guild_knife_count_dto_to_report_lines(dto):
        if row.kind == "sep":
            out.append(SEP_LINE)
        elif row.kind == "accent":
            out.append(row.text)
        elif row.kind == "body":
            out.append(row.text)
        elif row.kind == "pipes":
            out.append(PIPE_SEP.join(row.items))
    return out


def user_dto_to_report_lines(dto: UserKnifeReportDTO) -> List[ReportLine]:
    lines: List[ReportLine] = []
    for sec in dto.sections:
        heading = getattr(sec, "heading", None) or f"{sec.slot}-{sec.game_name}："
        if sec.lines and sec.lines[0].startswith("【"):
            for raw in sec.lines:
                if raw.startswith("【"):
                    lines.append(ReportLine(kind="heading", text=raw))
                else:
                    lines.append(ReportLine(kind="body", text=raw))
            continue
        lines.append(ReportLine(kind="heading", text=heading))
        if sec.empty_text:
            lines.append(ReportLine(kind="body", text=f"  {sec.empty_text}"))
        else:
            for raw in sec.lines:
                lines.append(ReportLine(kind="body", text=raw))
            if sec.pending_comp:
                lines.append(
                    ReportLine(
                        kind="body",
                        text=f"  ▸ 未出补偿：{_format_pending_comp_text(sec.pending_comp)}",
                    )
                )
    return lines


def user_dto_to_lines(dto: UserKnifeReportDTO) -> List[str]:
    """纯文本预览；PNG 请用 user_dto_to_report_lines。"""
    out: List[str] = []
    for row in user_dto_to_report_lines(dto):
        out.append(row.text)
    return out


def guild_dto_to_lines(dto: GuildPointsReportDTO) -> List[str]:
    lines: List[str] = []
    for day in dto.day_sections:
        lines.append(day.day_label)
        for key in sorted(day.buckets.keys(), key=_bucket_sort_key, reverse=True):
            joined = "、".join(day.buckets[key])
            lines.append(f"{key}：{joined}")
    if dto.footnote:
        lines.append(dto.footnote)
    return lines
