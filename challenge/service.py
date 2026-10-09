import time
from typing import List, Optional

from loguru import logger

from ..basedata import NoticeType
from ..database.dal import pcr_sqla
from ..database.models import ChallengeState


class ChallengeService:
    async def on_fighter_delta(
        self, group_id: int, boss: int, old_num: int, new_num: int
    ) -> None:
        state = await pcr_sqla.get_challenge_state(group_id, boss)
        if new_num > old_num:
            state.enter_signal += new_num - old_num
        state.last_fighter_num = new_num
        state.updated_at = int(time.time())
        await pcr_sqla.save_challenge_state(state)

    async def on_settlement(
        self, group_id: int, viewer_id: int, boss: int, is_kill: bool
    ) -> None:
        if is_kill:
            await pcr_sqla.delete_notice(NoticeType.apply.value, group_id, boss)
            state = await pcr_sqla.get_challenge_state(group_id, boss)
            state.enter_signal = 0
            state.unknown_labels = "[]"
            state.last_fighter_num = 0
            state.updated_at = int(time.time())
            await pcr_sqla.save_challenge_state(state)
            return

        if viewer_id:
            removed = await pcr_sqla.delete_apply_by_viewer(group_id, boss, viewer_id)
            if removed:
                logger.debug(
                    "结算清除绑定申请: group={} boss={} viewer={} n={}",
                    group_id,
                    boss,
                    viewer_id,
                    removed,
                )
                if removed > 1:
                    logger.warning(
                        "结算删除多条申请(应仅一条): group={} boss={} viewer={} n={}",
                        group_id,
                        boss,
                        viewer_id,
                        removed,
                    )
            elif not is_kill:
                if await pcr_sqla.pop_oldest_unbound_apply(group_id, boss):
                    logger.info(
                        "FIFO 清除无绑定申请: group={} boss={} viewer={}",
                        group_id,
                        boss,
                        viewer_id,
                    )
        elif not is_kill:
            if await pcr_sqla.pop_oldest_unbound_apply(group_id, boss):
                logger.info(
                    "FIFO 清除无绑定申请: group={} boss={} viewer=0",
                    group_id,
                    boss,
                )

        state = await pcr_sqla.get_challenge_state(group_id, boss)
        state.enter_signal = max(0, int(state.enter_signal or 0) - 1)
        state.updated_at = int(time.time())
        await pcr_sqla.save_challenge_state(state)

    async def unknown_count(self, group_id: int, boss: int) -> int:
        state = await pcr_sqla.get_challenge_state(group_id, boss)
        applies = await pcr_sqla.get_notice(
            NoticeType.apply.value, group_id, boss
        )
        return max(0, state.enter_signal - len(applies))

    async def on_self_report(self, group_id: int, boss: Optional[int] = None) -> None:
        """sl / 掉刀：进入信号 −1。"""
        bosses = [boss] if boss else range(1, 6)
        for b in bosses:
            state = await pcr_sqla.get_challenge_state(group_id, b)
            if state.enter_signal > 0:
                state.enter_signal -= 1
                state.updated_at = int(time.time())
                await pcr_sqla.save_challenge_state(state)
                return

    async def get_state(self, group_id: int, boss: int) -> ChallengeState:
        return await pcr_sqla.get_challenge_state(group_id, boss)

    async def clear_unknown_slots(
        self, group_id: int, boss: Optional[int] = None
    ) -> int:
        """将 enter_signal 收到与已知申请数一致，清空未知玩家胶囊。"""
        bosses = [boss] if boss else list(range(1, 6))
        cleared = 0
        for b in bosses:
            if b is None:
                continue
            state = await pcr_sqla.get_challenge_state(group_id, b)
            applies = await pcr_sqla.get_notice(
                NoticeType.apply.value, group_id, b
            )
            unknown = max(0, int(state.enter_signal or 0) - len(applies))
            if unknown <= 0:
                continue
            state.enter_signal = len(applies)
            state.updated_at = int(time.time())
            await pcr_sqla.save_challenge_state(state)
            cleared += unknown
            logger.info(
                "清空未知申请: group={} boss={} slots={}",
                group_id,
                b,
                unknown,
            )
        return cleared


challenge_service = ChallengeService()
