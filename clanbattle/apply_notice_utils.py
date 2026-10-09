"""申请队列 `[补偿]` 标记 — 结算与展示共用。"""
from __future__ import annotations

from ..basedata import NoticeType
from ..database.dal import pcr_sqla
from ..knife_budget.service import knife_budget_service
from .apply_knife_presentation import account_has_comp_resources

APPLY_COMP_MARK = "[补偿]"


async def apply_declared_comp_for_viewer(
    group_id: int, boss: int, viewer_id: int
) -> bool:
    """该 viewer 在本王申请是否有效携带补偿（`b` / `[补偿]` 且仍有补偿资源）。"""
    if not viewer_id:
        return False
    vid = int(viewer_id)
    rows = await pcr_sqla.get_notice(NoticeType.apply.value, int(group_id), int(boss))
    for row in rows:
        if int(row.viewer_id or 0) != vid:
            continue
        if not (row.text and str(row.text).startswith(APPLY_COMP_MARK)):
            continue
        summary = await knife_budget_service.remaining_summary(vid)
        return account_has_comp_resources(summary)
    return False
