"""会战日 5:00（pcr_date）清空全库挑战区：申请 + 挂树 + enter_signal。"""
from __future__ import annotations

import time

from loguru import logger

from ..basedata import NoticeType
from ..database.dal import pcr_date, pcr_sqla
from .registry import clanbattle_info
from .status_cache import notify_display_data_changed


async def run_daily_challenge_area_reset(*, source: str = "cron_5am") -> dict:
    """全库清空挑战区；预约保留。"""
    apply_n = await pcr_sqla.delete_all_notices_by_type(NoticeType.apply.value)
    tree_n = await pcr_sqla.delete_all_notices_by_type(NoticeType.tree.value)
    state_n = await pcr_sqla.reset_all_challenge_states()
    day_key = pcr_date(int(time.time())).strftime("%Y-%m-%d")
    logger.info(
        "daily_challenge_reset: source={} pcr_date={} apply={} tree={} states={}",
        source,
        day_key,
        apply_n,
        tree_n,
        state_n,
    )
    for group_id in list(clanbattle_info.keys()):
        try:
            await notify_display_data_changed(group_id, "daily_reset")
        except Exception:
            logger.debug("daily_reset notify skip group={}", group_id)
    return {
        "apply": apply_n,
        "tree": tree_n,
        "states": state_n,
        "pcr_date": day_key,
    }
