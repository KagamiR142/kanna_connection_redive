"""无绑定 SL（QQ 维度）与绑号后同步到 viewer。"""
from __future__ import annotations

from loguru import logger

from ..database.dal import pcr_sqla


async def mirror_qq_sl_to_viewer(
    user_id: int, viewer_id: int, group_id: int
) -> None:
    if not group_id or not viewer_id:
        return
    if await pcr_sqla.check_sl(user_id, group_id):
        if await pcr_sqla.check_sl_viewer(viewer_id, group_id):
            return
        ok = await pcr_sqla.add_sl_viewer(group_id, viewer_id)
        logger.info(
            "SL 绑号同步: user={} viewer={} group={} ok={}",
            user_id,
            viewer_id,
            group_id,
            ok,
        )
