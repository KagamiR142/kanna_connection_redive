import time
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .classifier import TimelineInfo

from loguru import logger

from ..database.dal import pcr_date, pcr_sqla
from ..database.models import KnifeBudget
from .classifier import TimelineInfo, classify_hybrid
from .knife_state import KnifeDisplayState
from .budget_drift import sanitize_budget_counters
from .kill_comp import KillCompKind
from .settlement import SettlementResult, apply_settlement_to_budget


def _pcr_date_str(ts: Optional[int] = None) -> str:
    return pcr_date(ts or int(time.time())).strftime("%Y-%m-%d")


class KnifeBudgetService:
    async def get_budget(
        self, viewer_id: int, ts: Optional[int] = None
    ) -> KnifeBudget:
        budget = await pcr_sqla.get_knife_budget(viewer_id, _pcr_date_str(ts))
        sanitize_budget_counters(budget, viewer_id=viewer_id, context="read")
        return budget

    async def apply_settlement(
        self,
        viewer_id: int,
        is_kill: bool,
        damage: int,
        settlement_time: int,
        boss_order: int = 0,
        boss_hp_before: Optional[int] = None,
        kill_comp_seconds: Optional[int] = None,
        kill_comp_kind: Optional[KillCompKind] = None,
        declared_comp_apply: bool = False,
        timeline: Optional["TimelineInfo"] = None,
    ) -> SettlementResult:
        """监控结算主路径：更新 budget 并返回四态结果。"""
        budget = await self.get_budget(viewer_id, settlement_time)
        try:
            result = apply_settlement_to_budget(
                budget,
                is_kill=is_kill,
                damage=damage,
                boss_order=boss_order,
                boss_hp_before=boss_hp_before,
                viewer_id=viewer_id,
                kill_comp_seconds=kill_comp_seconds,
                kill_comp_kind=kill_comp_kind,
                declared_comp_apply=declared_comp_apply,
                timeline=timeline,
            )
        except Exception:
            logger.exception(
                "knife_budget 结算计算异常，已降级为仅记刀 viewer={} boss={} kill={}",
                viewer_id,
                boss_order,
                is_kill,
            )
            sanitize_budget_counters(
                budget, viewer_id=viewer_id, context="settlement_fallback"
            )
            state = KnifeDisplayState.KILL if is_kill else KnifeDisplayState.FULL
            result = SettlementResult(
                display_state=state,
                settled_kind="full",
                points_delta=0.0,
                record_flag=1.0 if is_kill else 0.0,
                record_is_kill=1 if is_kill else 0,
            )
        budget.updated_at = int(time.time())
        try:
            await pcr_sqla.save_knife_budget(budget)
        except Exception:
            logger.exception(
                "knife_budget 落库失败（不影响其它账号/群） viewer={} date={}",
                viewer_id,
                budget.pcr_date,
            )
        return result

    async def classify_record(
        self,
        viewer_id: int,
        battle_time: int,
        start_remain_time: int,
        settlement_time: int,
        is_kill: bool = False,
        boss_hp_before: Optional[int] = None,
        damage: Optional[int] = None,
    ) -> float:
        budget = await self.get_budget(viewer_id, settlement_time)
        flag, budget, anomaly = classify_hybrid(
            TimelineInfo(battle_time, start_remain_time),
            budget,
            is_kill=is_kill,
            boss_hp_before=boss_hp_before,
            damage=damage,
        )
        budget.updated_at = int(time.time())
        await pcr_sqla.save_knife_budget(budget)
        if anomaly:
            logger.warning("viewer_id={} 刀型需人工核查", viewer_id)
        return flag

    async def reset_budget(self, viewer_id: int, ts: Optional[int] = None) -> None:
        budget = KnifeBudget(
            viewer_id=viewer_id,
            pcr_date=_pcr_date_str(ts),
            used_full=3,
            avail_comp=0,
            used_points=3.0,
            comp_seconds=0,
            comp_boss=0,
            comp_pool="[]",
            updated_at=int(time.time()),
        )
        await pcr_sqla.save_knife_budget(budget)

    async def record_drop(self, viewer_id: int, *, is_comp: bool = False) -> None:
        from .comp_pool import consume_comp_from_pool

        budget = await self.get_budget(viewer_id)
        if is_comp:
            budget.used_points = min(3.0, budget.used_points + 0.5)
            if budget.avail_comp > 0:
                budget.avail_comp -= 1
            consume_comp_from_pool(budget, viewer_id=viewer_id)
        else:
            if budget.used_full < 3:
                budget.used_full += 1
            budget.used_points = min(3.0, budget.used_points + 1.0)
        sanitize_budget_counters(budget, viewer_id=viewer_id, context="drop")
        budget.updated_at = int(time.time())
        try:
            await pcr_sqla.save_knife_budget(budget)
        except Exception:
            logger.exception("掉刀落库失败 viewer_id={}", viewer_id)
        logger.info(
            "掉刀记录: viewer_id={} is_comp={} used_points={}",
            viewer_id,
            is_comp,
            budget.used_points,
        )

    async def remaining_summary(self, viewer_id: int) -> Dict[str, float]:
        from .comp_pool import ensure_comp_pool_migrated, read_comp_pool

        budget = await self.get_budget(viewer_id)
        ensure_comp_pool_migrated(budget)
        pool = read_comp_pool(budget)
        comp_seconds_list = [int(e.seconds) for e in pool]
        return {
            "full": max(0, 3 - budget.used_full),
            "comp": budget.avail_comp,
            "points": max(0.0, 3.0 - budget.used_points),
            "used_points": budget.used_points,
            "comp_seconds": budget.comp_seconds,
            "comp_boss": int(getattr(budget, "comp_boss", 0) or 0),
            "comp_seconds_list": comp_seconds_list,
        }

    async def get_used_points(
        self, viewer_id: int, ts: Optional[int] = None
    ) -> float:
        budget = await self.get_budget(viewer_id, ts)
        return float(budget.used_points)

    async def group_compensation_labels(
        self, viewer_ids: List[int], name_map: Dict[int, str]
    ) -> Tuple[List[str], int]:
        """兼容旧调用：返回字符串标签与整刀余量合计。"""
        remaining_full = 0
        for vid in viewer_ids:
            if not vid:
                continue
            summary = await self.remaining_summary(vid)
            remaining_full += int(summary["full"])
        entries = await self.group_guild_compensation_entries(
            viewer_ids, name_map
        )
        labels = []
        for e in entries:
            parts = []
            if e.comp_knives > 0:
                parts.append(f"{e.comp_knives}补")
            if e.comp_seconds > 0:
                parts.append(f"{e.comp_seconds}s")
            labels.append(f"{e.label}({'/'.join(parts)})")
        return labels, remaining_full

    async def group_guild_compensation_entries(
        self, viewer_ids: List[int], name_map: Dict[int, str]
    ) -> List["CompensationEntry"]:
        """状态图补偿详情：未出补偿池（与当日已出刀数 chip 分离）。"""
        from ..status_dto import CompensationEntry

        entries: List[CompensationEntry] = []
        for vid in viewer_ids:
            if not vid:
                continue
            summary = await self.remaining_summary(vid)
            name = name_map.get(vid, str(vid))
            pool_secs = list(summary.get("comp_seconds_list") or [])
            if pool_secs:
                for sec in pool_secs:
                    entries.append(
                        CompensationEntry(
                            label=name,
                            comp_knives=1,
                            comp_seconds=int(sec),
                            boss_order=int(summary.get("comp_boss") or 0),
                        )
                    )
            elif summary["comp"] > 0 or summary["comp_seconds"] > 0:
                entries.append(
                    CompensationEntry(
                        label=name,
                        comp_knives=int(summary["comp"]),
                        comp_seconds=int(summary["comp_seconds"]),
                        boss_order=int(summary.get("comp_boss") or 0),
                    )
                )
        return entries

    async def group_guild_knife_status(
        self, viewer_ids: List[int], name_map: Dict[int, str]
    ) -> Tuple[int, int, List["CompensationEntry"]]:
        """已废弃口径：剩余整刀/补偿合计。请用 guild_today_knife_aggregate + group_guild_compensation_entries。"""
        remaining_full = 0
        remaining_comp = 0
        for vid in viewer_ids:
            if not vid:
                continue
            summary = await self.remaining_summary(vid)
            remaining_full += int(summary["full"])
            remaining_comp += int(summary["comp"])
        entries = await self.group_guild_compensation_entries(
            viewer_ids, name_map
        )
        return remaining_full, remaining_comp, entries


knife_budget_service = KnifeBudgetService()

__all__ = [
    "KnifeBudgetService",
    "KnifeDisplayState",
    "SettlementResult",
    "knife_budget_service",
]
