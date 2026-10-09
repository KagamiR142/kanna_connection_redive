"""自动报刀报告生成（兼容层，委托 detail_reports）。"""
from __future__ import annotations

from .detail_reports import (
    format_season_guild_detail as format_season_guild_report,
    format_season_user_detail as format_season_user_knives,
    format_today_guild_detail as format_today_guild_report,
    format_today_user_detail as format_today_user_knives,
)
from .account_service import list_bound_accounts
from ..knife_budget.service import knife_budget_service


async def resolve_user_viewer_ids(user_id: int):
    return [a.viewer_id for a in await list_bound_accounts(user_id)]


async def user_has_comp_knife(user_id: int) -> bool:
    for vid in await resolve_user_viewer_ids(user_id):
        summary = await knife_budget_service.remaining_summary(vid)
        if summary["comp"] > 0 or summary["comp_seconds"] > 0:
            return True
    return False
