"""Boss 实例结算前剩余血量 R_inst（设计文档 §1.3.2）；仅用于补偿秒数，不改 top 展示。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from loguru import logger

from ..database.dal import pcr_sqla

if TYPE_CHECKING:
    from ..clanbattle.model import Boss

ZERO_CONFIRM_POLLS = 2
PENDING_DROP_MAX_POLLS = 30


@dataclass(frozen=True)
class BossInstanceKey:
    lap: int
    order: int


class SettlementLedger:
    def __init__(self, group_id: int) -> None:
        self.group_id = group_id
        self._remaining: Dict[BossInstanceKey, int] = {}
        self._pending_zero: Dict[BossInstanceKey, int] = {}
        # 周目进位瞬间的实例余额（非历史 top 峰值）
        self._stale_lap_r: Dict[BossInstanceKey, int] = {}
        self._pending_drop: Dict[BossInstanceKey, int] = {}

    def _set_r(self, key: BossInstanceKey, r: int) -> None:
        self._remaining[key] = max(0, int(r))

    def _valid_keys(self, bosses: List["Boss"]) -> Set[BossInstanceKey]:
        return {
            BossInstanceKey(int(b.lap_num or 0), int(b.order or i + 1))
            for i, b in enumerate(bosses)
            if int(b.lap_num or 0) > 0
        }

    def _slot_lap(self, bosses: List["Boss"], order: int) -> int:
        if 1 <= order <= len(bosses):
            return int(bosses[order - 1].lap_num or 0)
        return 0

    def mark_stale_laps(self, bosses: List["Boss"]) -> None:
        """周目进位：旧实例进入待丢弃队列（记录进位瞬间 R，供延迟击杀结算）。"""
        valid = self._valid_keys(bosses)
        for key in list(self._remaining):
            if key in valid:
                continue
            r = int(self._remaining.get(key, 0))
            if key not in self._stale_lap_r:
                self._stale_lap_r[key] = r
            if key not in self._pending_drop:
                self._pending_drop[key] = 0
                logger.debug(
                    "ledger 待丢弃实例: group={} lap={} order={} R={} stale_mark={}",
                    self.group_id,
                    key.lap,
                    key.order,
                    r,
                    self._stale_lap_r.get(key, 0),
                )

    def finalize_stale_laps(self, bosses: List["Boss"]) -> None:
        """结算 poll 结束后真正移除旧周目账本（带 pending 计数兜底）。"""
        valid = self._valid_keys(bosses)
        for key in list(self._pending_drop):
            if key in valid:
                self._pending_drop.pop(key, None)
                continue
            self._pending_drop[key] = int(self._pending_drop.get(key, 0)) + 1
            if self._pending_drop[key] < PENDING_DROP_MAX_POLLS:
                continue
            stale = int(self._stale_lap_r.get(key, 0))
            logger.debug(
                "ledger 丢弃旧实例: group={} lap={} order={} stale_mark={} pending_polls={}",
                self.group_id,
                key.lap,
                key.order,
                stale,
                self._pending_drop[key],
            )
            self._remaining.pop(key, None)
            self._pending_zero.pop(key, None)
            self._pending_drop.pop(key, None)
            self._stale_lap_r.pop(key, None)

    def drop_stale_laps(self, bosses: List["Boss"]) -> None:
        """兼容旧调用：标记并立即 finalize（单步丢弃）。"""
        self.mark_stale_laps(bosses)
        for key in list(self._pending_drop):
            if key not in self._valid_keys(bosses):
                self._pending_drop[key] = PENDING_DROP_MAX_POLLS
        self.finalize_stale_laps(bosses)

    def sync_from_top(
        self,
        bosses: List["Boss"],
        *,
        freeze_zero_orders: Optional[Set[int]] = None,
    ) -> None:
        """top 校正账本：存活立即对齐；死亡双确认归零。"""
        frozen = freeze_zero_orders or set()
        for i, b in enumerate(bosses):
            lap = int(b.lap_num or 0)
            if lap <= 0:
                continue
            order = int(b.order or i + 1)
            top_hp = int(b.current_hp or 0)
            key = BossInstanceKey(lap, order)
            ledger_r = int(self._remaining.get(key, 0))

            if top_hp > 0:
                self._pending_zero.pop(key, None)
                if ledger_r != top_hp:
                    prev = ledger_r
                    self._set_r(key, top_hp)
                    logger.debug(
                        "ledger top同步: group={} lap={} order={} R={} (prev={})",
                        self.group_id,
                        lap,
                        order,
                        top_hp,
                        prev,
                    )
                continue

            if ledger_r <= 0:
                self._pending_zero.pop(key, None)
                continue

            if order in frozen:
                logger.debug(
                    "ledger 跳过归零(合刀冻结): group={} lap={} order={} R={}",
                    self.group_id,
                    lap,
                    order,
                    ledger_r,
                )
                continue

            pending = self._pending_zero.get(key, 0) + 1
            self._pending_zero[key] = pending
            if pending < ZERO_CONFIRM_POLLS:
                logger.debug(
                    "ledger 待归零: group={} lap={} order={} R={} pending={}/{}",
                    self.group_id,
                    lap,
                    order,
                    ledger_r,
                    pending,
                    ZERO_CONFIRM_POLLS,
                )
                continue

            self._set_r(key, 0)
            self._pending_zero.pop(key, None)
            logger.info(
                "ledger 双确认归零: group={} lap={} order={} prev_R={}",
                self.group_id,
                lap,
                order,
                ledger_r,
            )

    def _max_hp_for(self, bosses: List["Boss"], order: int, lap: int) -> int:
        if 1 <= order <= len(bosses):
            b = bosses[order - 1]
            if int(b.lap_num or 0) == lap and b.max_hp:
                return int(b.max_hp)
            if b.max_hp:
                return int(b.max_hp)
        return 0

    async def ensure_instance(
        self,
        lap: int,
        order: int,
        bosses: List["Boss"],
        *,
        before_create_time: int,
    ) -> None:
        """结算扣血前保证账本已初始化（非击杀 apply_damage 不能默认 R=0）。"""
        key = BossInstanceKey(int(lap), int(order))
        if key not in self._remaining:
            await self._bootstrap(
                key, bosses, before_create_time=before_create_time
            )

    async def remaining_before(
        self,
        lap: int,
        order: int,
        bosses: List["Boss"],
        *,
        before_create_time: int,
        damage: int = 0,
        is_kill: bool = False,
    ) -> int:
        key = BossInstanceKey(int(lap), int(order))
        r_mem = int(self._remaining.get(key, 0)) if key in self._remaining else 0
        stale_mark = int(self._stale_lap_r.get(key, 0)) if key in self._stale_lap_r else None
        await self.ensure_instance(
            lap, order, bosses, before_create_time=before_create_time
        )
        r = int(self._remaining.get(key, 0))
        if is_kill:
            r = await self._reconcile_kill_remaining(
                key,
                bosses,
                r,
                damage=int(damage),
                before_create_time=before_create_time,
                r_mem=r_mem,
                stale_mark=stale_mark,
            )
        logger.debug(
            "ledger R_before: group={} lap={} order={} R={}",
            self.group_id,
            lap,
            order,
            r,
        )
        return r

    async def _reconcile_kill_remaining(
        self,
        key: BossInstanceKey,
        bosses: List["Boss"],
        r: int,
        *,
        damage: int,
        before_create_time: int,
        r_mem: int = 0,
        stale_mark: Optional[int] = None,
    ) -> int:
        slot_lap = self._slot_lap(bosses, key.order)
        cross_lap = slot_lap > 0 and slot_lap != key.lap
        source = "ledger"

        if not cross_lap and 1 <= key.order <= len(bosses):
            b = bosses[key.order - 1]
            if int(b.lap_num or 0) == key.lap:
                top_hp = int(b.current_hp or 0)
                if top_hp > 0:
                    out = max(r, r_mem, top_hp)
                    logger.debug(
                        "ledger 击杀 R 选用: group={} lap={} order={} R={} source=top_alive",
                        self.group_id,
                        key.lap,
                        key.order,
                        out,
                    )
                    return out
                if r_mem > 0:
                    logger.debug(
                        "ledger 击杀 R 选用: group={} lap={} order={} R={} source=mem",
                        self.group_id,
                        key.lap,
                        key.order,
                        r_mem,
                    )
                    return r_mem
                if r > 0:
                    return r

        if cross_lap and r_mem > 0:
            logger.debug(
                "ledger 击杀 R 选用: group={} lap={} order={} R={} source=mem_cross_lap",
                self.group_id,
                key.lap,
                key.order,
                r_mem,
            )
            return r_mem

        if r > 0 and not cross_lap:
            return r
        if r > 0 and cross_lap:
            logger.debug(
                "ledger 击杀 R 选用: group={} lap={} order={} R={} source=replay_ledger",
                self.group_id,
                key.lap,
                key.order,
                r,
            )
            return r

        if damage <= 0:
            return max(0, r)

        await self._bootstrap(
            key,
            bosses,
            before_create_time=before_create_time,
            force=True,
        )
        r = int(self._remaining.get(key, 0))
        source = "replay"

        if r <= 0 and cross_lap and stale_mark is not None and stale_mark > 0:
            r = stale_mark
            source = "stale_mark"

        if (
            r <= 0
            and cross_lap
            and stale_mark is not None
            and stale_mark == 0
            and r_mem == 0
        ):
            source = "replay_zero"

        if r <= 0 and damage > 0:
            logger.warning(
                "ledger 击杀 R 仍为 0: group={} lap={} order={} D={} mem={} stale={} cross={}",
                self.group_id,
                key.lap,
                key.order,
                damage,
                r_mem,
                stale_mark,
                cross_lap,
            )
        else:
            logger.info(
                "ledger 击杀 R 选用: group={} lap={} order={} R={} source={} mem={} stale={}",
                self.group_id,
                key.lap,
                key.order,
                r,
                source,
                r_mem,
                stale_mark,
            )
        return r

    async def _bootstrap(
        self,
        key: BossInstanceKey,
        bosses: List["Boss"],
        *,
        before_create_time: int,
        force: bool = False,
    ) -> None:
        if not force and key in self._remaining:
            return
        max_hp = self._max_hp_for(bosses, key.order, key.lap)
        if max_hp <= 0 and 1 <= key.order <= len(bosses):
            b = bosses[key.order - 1]
            if int(b.current_hp or 0) > 0:
                max_hp = int(b.current_hp)
        r = max_hp
        rows = await pcr_sqla.get_boss_instance_records(
            self.group_id,
            key.lap,
            key.order,
            before_time=before_create_time,
        )
        for row in rows:
            dmg = int(row.damage or 0)
            if dmg <= 0:
                continue
            r = max(0, r - dmg)
            if int(row.is_kill or 0):
                r = 0
                break
        if 1 <= key.order <= len(bosses):
            b = bosses[key.order - 1]
            if int(b.lap_num or 0) == key.lap:
                top_hp = int(b.current_hp or 0)
                if top_hp > 0:
                    if r == 0:
                        r = top_hp
                    else:
                        r = min(r, top_hp)
        self._set_r(key, r)
        logger.info(
            "ledger 初始化: group={} lap={} order={} R={} replay_rows={} max_hp={}",
            self.group_id,
            key.lap,
            key.order,
            self._remaining[key],
            len(rows),
            max_hp,
        )

    def apply_damage(
        self,
        lap: int,
        order: int,
        damage: int,
        *,
        is_kill: bool,
    ) -> None:
        key = BossInstanceKey(int(lap), int(order))
        r = int(self._remaining.get(key, 0))
        dmg = int(damage or 0)
        if is_kill:
            self._set_r(key, 0)
            self._pending_zero.pop(key, None)
            logger.debug(
                "ledger 击杀清零: group={} lap={} order={} R_before={} D={}",
                self.group_id,
                lap,
                order,
                r,
                dmg,
            )
            return
        self._set_r(key, max(0, r - dmg))
        logger.debug(
            "ledger 扣血: group={} lap={} order={} R {}→{} D={}",
            self.group_id,
            lap,
            order,
            r,
            self._remaining[key],
            dmg,
        )

    def note_settlement_for_instance(self, lap: int, order: int) -> None:
        """本 poll 已处理该实例战报后，可提前 finalize 对应待丢弃 key。"""
        key = BossInstanceKey(int(lap), int(order))
        if key in self._pending_drop:
            self._pending_drop[key] = PENDING_DROP_MAX_POLLS
            logger.debug(
                "ledger 结算后加速丢弃: group={} lap={} order={}",
                self.group_id,
                lap,
                order,
            )
