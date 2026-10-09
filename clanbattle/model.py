import asyncio
import contextlib
import time
from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from loguru import logger
from nonebot import get_bot

from ..basedata import ItemID, NoticeType, clan_stage_num
from ..client import (
    BaseClient,
    LoadIndexResponse,
    check_client,
)
from ..client.response import (
    BattleInfo,
    ClanBattleLogListResponse,
    ClanBattleTopResponse,
)
from ..database.dal import pcr_sqla
from ..database.models import RecordDao
from ..errorclass import CancelledError
from ..login import run_group
from ..util.task_pool import PoolBase, PrioritizedQueryItemBase
from ..util.tools import anywhere_send
from ..challenge.service import challenge_service
from ..knife_budget.classifier import TimelineInfo, timeline_flag
from ..knife_budget.timeline_cache import (
    put_timeline,
    put_timeline_battle_context,
    resolve_timeline_for_settlement,
)
from ..knife_budget.timeline_knife import log_timeline_comp_entry
from ..knife_budget.knife_pipeline import settle_from_damage_history
from ..knife_budget.record_semantics import provisional_knife_state_from_timeline
from .record_persist import persist_settlement_record
from ..knife_budget.kill_comp import (
    KillCompKind,
    classify_kill_comp,
    format_kill_comp_push_prefix,
    resolve_kill_comp_seconds,
)
from ..knife_budget.settlement_ledger import SettlementLedger
from ..knife_budget.service import knife_budget_service
from .apply_notice_utils import apply_declared_comp_for_viewer
from ..util.auto_boss import clan_boss_info
from .base import find_item, format_bignum, format_precent
from .knife_type_text import build_knife_type_sentence
from .damage_history_watermark import (
    collect_damage_histories_to_process,
    format_history_batch_for_log,
    has_unsettled_damage_history,
    list_unsettled_damage_histories,
    orders_with_pending_damage_history,
)
from .reserve_service import (
    clear_board_messages_on_boss_kill,
    freeze_zero_sync_orders,
)
from .status_cache import notify_display_data_changed
from .damage_push_batch import DamagePushBlock, flush_damage_push_batch
from .response_builder import build_damage_push_block
from .status_cache import status_render_batch

from traceback import format_exc


class ClanBattle:
    def __init__(self, group_id: int) -> None:
        self.rank = 0  # 会战排名
        self.lap_num = 0  # 周目（会战周目，boss可能多一周目）
        self.loop_num = 0  # 循环编号
        self.error_count = 0  # 失败计数
        self.loop_check = 0  # 循环检查(时间戳)
        self.group_id = group_id
        self.notice_dao = []
        self.notice_tree = []
        self.notice_fighter = []
        self.notice_subscribe = []
        self.pending_kills: List[Tuple[int, int, int, int]] = []
        self.boss = [Boss(), Boss(), Boss(), Boss(), Boss()]
        self.clan_name = ""
        self.period = ""
        self.dao_update_time = 0  # 网页端更新标记
        self.status_png: Optional[bytes] = None
        self.status_png_version = 0
        self.status_content_hash = ""
        self.status_image_update_time = 0
        self.status_png_at = 0.0
        self.status_dirty = False
        self.status_render_pending = False
        self.status_render_task = None
        self.fighter_update_time = 0
        self.latest_time = 0
        self.monitor_slot: int = 1
        self.monitor_account_id: Optional[int] = None
        self.monitor_account_name: str = ""
        self.settlement_ledger = SettlementLedger(group_id)

    async def init(self, client: BaseClient, user_id: int, bot_id: int):
        self.loop_num += 1
        self.client = client
        self.bot_id = bot_id
        self.user_id = user_id
        for _ in range(3):
            with contextlib.suppress(Exception):
                home_index = await self.client.home_index()
                self.clan_id = home_index.user_clan.clan_id
                self.coin = await self.get_coin()
                clan_battle_top = await self.get_clanbattle_top()
                break
        else:
            home_index = await self.client.home_index()
            self.clan_id = home_index.user_clan.clan_id
            self.coin = await self.get_coin()
            clan_battle_top = await self.get_clanbattle_top()

        self.clan_battle_id = clan_battle_top.clan_battle_id
        self.clan_name = clan_battle_top.user_clan.clan_name
        self.lap_num = clan_battle_top.lap_num
        self.period = clan_boss_info.lap2stage(self.lap_num)
        self.refresh_latest_time(clan_battle_top)
        for i, boss in enumerate(self.boss):
            if i < len(clan_battle_top.boss_info):
                cb = clan_battle_top.boss_info[i]
                boss.refresh(
                    cb.current_hp,
                    cb.lap_num,
                    cb.order_num,
                    cb.max_hp,
                )
        self.members: Dict[int, str] = await self.all_member()
        self.dao_update_time = int(time.time())

    async def get_coin(self) -> int:
        load_index: LoadIndexResponse = await self.client.load_index()
        return find_item(load_index.item_list, ItemID.clanbattle_coin.value)

    async def get_clanbattle_top(self) -> ClanBattleTopResponse:
        try:
            return await self.client.clan_battle_top(self.clan_id, self.coin)
        except Exception:
            self.coin = await self.get_coin()  # 更新coin
            return await self.client.clan_battle_top(self.clan_id, self.coin)

    async def sync_fighter_num(self, lap_num: int, order: int) -> int:
        """reload_detail_info；上升沿播报。始终写回 fighter_num。"""
        boss = self.boss[order - 1]
        announce = 0
        try:
            if not boss.current_hp:
                if boss.fighter_num:
                    boss.fighter_num = 0
                return 0
            reload_detail_info = await self.client.clan_battle_detail_info(
                self.clan_id, self.clan_battle_id, lap_num, order
            )
            old_num = boss.fighter_num
            new_num = reload_detail_info.fighter_num or 0
            if new_num != old_num:
                self.fighter_update_time = int(time.time())
            boss.fighter_num = new_num
            if new_num > old_num:
                logger.info(
                    "fighter_num 上升: group={} boss={} {}→{}",
                    self.group_id,
                    order,
                    old_num,
                    new_num,
                )
                await challenge_service.on_fighter_delta(
                    self.group_id, order, old_num, new_num
                )
                state = await challenge_service.get_state(self.group_id, order)
                announce = int(state.enter_signal or 0)
                logger.info(
                    "enter_signal 上升播报: group={} boss={} api={}→{} signal={}",
                    self.group_id,
                    order,
                    old_num,
                    new_num,
                    announce,
                )
            elif new_num < old_num:
                logger.debug(
                    "fighter_num 下降忽略: group={} boss={} {}→{}",
                    self.group_id,
                    order,
                    old_num,
                    new_num,
                )
        except Exception:
            return 0
        return announce

    async def refresh_fighter_num(self, lap_num: int, order: int) -> int:
        return await self.sync_fighter_num(lap_num, order)

    async def get_battle_log(self, page: int) -> ClanBattleLogListResponse:
        return await self.client.clan_battle_log(page, self.clan_battle_id)

    async def add_record(self, loop_num: int):
        log_list: List[BattleInfo] = []
        dao_list = []
        with contextlib.suppress(Exception):
            # 故意不重试，这循环极端情况下运行10分钟也正常，不如报错趁早退出，下次再来
            log_temp = await self.get_battle_log(1)  # 获取最大页数
            if not log_temp.battle_list:
                return  # 数据空

            latest_time = await pcr_sqla.get_latest_time(self.group_id)
            for page in range(log_temp.max_page, 0, -1):
                log = await self.get_battle_log(page)
                if log.battle_list[-1].battle_end_time <= latest_time:
                    break
                log_list += log.battle_list[::-1]
            for record in log_list[::-1]:
                if loop_num != self.loop_num:
                    raise CancelledError
                if (time := record.battle_end_time) > latest_time:
                    record_dao = await self.general_single_record(record, time)
                    dao_list.append(record_dao)
        if dao_list:
            await pcr_sqla.add_record(dao_list)

    async def _raw_fetch_timeline_info(
        self, viewer_id: int, log_id: int
    ) -> Optional[TimelineInfo]:
        if not viewer_id or not log_id:
            return None
        try:
            tl = await self.client.time_line_report(
                int(viewer_id), self.clan_battle_id, int(log_id)
            )
            return TimelineInfo(
                battle_time=int(tl.battle_time or 0),
                start_remain_time=int(tl.start_remain_time or 0),
            )
        except Exception as e:
            logger.debug(
                "timeline API 未就绪: viewer={} log_id={} err={}",
                viewer_id,
                log_id,
                e,
            )
            return None

    async def _fetch_timeline_info(
        self,
        viewer_id: int,
        log_id: int,
        *,
        lap: int = 0,
        boss_order: int = 0,
        settlement_time: int = 0,
        is_kill: bool = False,
    ) -> Optional[TimelineInfo]:
        if not viewer_id or not log_id:
            return None
        hint = await pcr_sqla.get_record_timeline_hint(self.group_id, log_id)
        record_remain = hint[0] if hint else None
        record_bt = hint[1] if hint else None
        if (int(record_remain or 0) <= 0) and lap > 0 and boss_order > 0:
            near = await pcr_sqla.get_record_timeline_hint_near_match(
                self.group_id,
                viewer_id,
                lap,
                boss_order,
                settlement_time,
            )
            if near:
                record_remain, record_bt = near
        return await resolve_timeline_for_settlement(
            self.group_id,
            viewer_id,
            log_id,
            self._raw_fetch_timeline_info,
            record_remain_time=record_remain,
            record_battle_time=record_bt,
            lap=lap,
            boss_order=boss_order,
            settlement_time=settlement_time,
            is_kill=is_kill,
        )

    async def general_single_record(self, record: BattleInfo, time: int) -> RecordDao:
        pcrid = record.target_viewer_id
        time_line = await self.client.time_line_report(
            pcrid, self.clan_battle_id, record.battle_log_id
        )
        timeline = TimelineInfo(
            battle_time=time_line.battle_time,
            start_remain_time=time_line.start_remain_time,
        )
        log_id = int(record.battle_log_id or (time % 10000000))
        put_timeline(self.group_id, pcrid, log_id, timeline)
        put_timeline_battle_context(
            self.group_id,
            pcrid,
            int(record.lap_num or 0),
            int(record.order_num or 0),
            int(time),
            log_id,
            timeline,
        )
        is_kill = bool(
            self._match_pending_kill(pcrid, record.order_num, record.lap_num, time)
        )
        budget = await knife_budget_service.get_budget(pcrid, time)
        flag = timeline_flag(timeline, budget=budget)
        knife_state = provisional_knife_state_from_timeline(
            timeline, is_kill=is_kill, budget=budget
        )
        temp_dict = {
            "group_id": self.group_id,
            "battle_log_id": log_id,
            "name": record.user_name,
            "lap": record.lap_num,
            "boss": record.order_num,
            "damage": record.total_damage,
            "time": time,
            "pcrid": pcrid,
            "remain_time": time_line.start_remain_time,
            "battle_time": time_line.battle_time,
            "flag": flag,
            "is_kill": int(is_kill),
            "knife_state": int(knife_state),
        }
        for i, unit in enumerate(record.units):
            temp_dict[f"unit{i+1}"] = unit.unit_id
            temp_dict[f"unit{i+1}_level"] = unit.unit_level
            temp_dict[f"unit{i+1}_damage"] = unit.damage
            temp_dict[f"unit{i+1}_rarity"] = unit.unit_rarity
            temp_dict[f"unit{i+1}_rank"] = unit.promotion_level
            temp_dict[f"unit{i+1}_unique_equip"] = (
                unit.unique_equip_slot[0].enhancement_level
                if unit.unique_equip_slot
                else 0
            )
        return RecordDao(**temp_dict)

    def _match_pending_kill(
        self, pcrid: int, boss: int, lap: int, record_time: int
    ) -> bool:
        for idx, (vid, b, l, t) in enumerate(self.pending_kills):
            if vid == pcrid and b == boss and l == lap and abs(t - record_time) < 180:
                self.pending_kills.pop(idx)
                return True
        return False

    async def notify_subscribe_spawn(self, order: int, lap: int) -> None:
        info = await pcr_sqla.get_notice_exact_lap(
            NoticeType.subscribe.value, self.group_id, order, lap
        )
        if not info:
            return
        logger.info(
            "预约触发: group={} lap={} boss={} users={}",
            self.group_id,
            lap,
            order,
            len(info),
        )
        await pcr_sqla.delete_notice_exact_lap(
            NoticeType.subscribe.value, self.group_id, order, lap
        )
        ats = " ".join(f"[CQ:at,qq={n.user_id}]" for n in info)
        self.notice_subscribe.append(f"您预约的{lap}周目{order}王已出现\n{ats}")

    async def notify_tree_off(self, order: int) -> str:
        info = await pcr_sqla.get_notice(
            NoticeType.tree.value, self.group_id, order
        )
        if not info:
            return ""
        await pcr_sqla.delete_notice(NoticeType.tree.value, self.group_id, order)
        ats = " ".join(f"[CQ:at,qq={n.user_id}]" for n in info)
        return f"{order}王已被击杀，可下树\n{ats}"

    async def send_notice(self, types: List[int]):
        if NoticeType.subscribe.value in types:
            await anywhere_send(
                "\n".join(self.notice_subscribe), self.group_id, self.bot_id
            )
            self.notice_subscribe.clear()
        if NoticeType.fighter.value in types:
            await anywhere_send(
                "\n".join(self.notice_fighter), self.group_id, self.bot_id
            )
            self.notice_fighter.clear()
        if NoticeType.dao.value in types:
            for msg in self.notice_dao:
                if msg:
                    await anywhere_send(msg, self.group_id, self.bot_id)
            if self.notice_dao:
                logger.debug(
                    "报刀发送: group={} messages={}",
                    self.group_id,
                    len(self.notice_dao),
                )
            self.notice_dao.clear()
        if NoticeType.tree.value in types:
            await anywhere_send("\n".join(self.notice_tree), self.group_id, self.bot_id)
            self.notice_tree.clear()

    async def has_new_damage_history(
        self, clan_battle_top: ClanBattleTopResponse
    ) -> bool:
        if not clan_battle_top.damage_history:
            return False
        return await has_unsettled_damage_history(
            self.group_id,
            clan_battle_top.damage_history,
            self.latest_time,
        )

    async def apply_boss_snapshot_from_top(
        self, clan_battle_top: ClanBattleTopResponse
    ) -> None:
        """用 top.boss_info 覆盖镜像（权威来源）。"""
        for i, boss in enumerate(self.boss):
            current_boss = clan_battle_top.boss_info[i]
            old_lap = boss.lap_num
            if (
                current_boss.lap_num
                and current_boss.lap_num > old_lap
                and current_boss.current_hp
            ):
                await self.notify_subscribe_spawn(
                    current_boss.order_num, current_boss.lap_num
                )
            boss.refresh(
                current_boss.current_hp,
                current_boss.lap_num,
                current_boss.order_num,
                current_boss.max_hp,
            )
            if enter_signal := await self.sync_fighter_num(
                current_boss.lap_num, current_boss.order_num
            ):
                from .queue_display_service import build_fighter_enter_message

                bot = get_bot()
                self.notice_fighter.append(
                    await build_fighter_enter_message(
                        bot,
                        self.group_id,
                        i + 1,
                        enter_signal,
                    )
                )
        pending_orders = await orders_with_pending_damage_history(
            self.group_id,
            clan_battle_top.damage_history,
            self.latest_time,
        )
        freeze_orders = await freeze_zero_sync_orders(
            self.group_id, extra_orders=pending_orders
        )
        self.settlement_ledger.sync_from_top(
            self.boss, freeze_zero_orders=freeze_orders
        )
        self.settlement_ledger.mark_stale_laps(self.boss)

    def finalize_ledger_after_settlement(self) -> None:
        """damage_history 处理完毕后丢弃旧周目账本。"""
        self.settlement_ledger.finalize_stale_laps(self.boss)

    async def refresh_boss(self, clan_battle_top: ClanBattleTopResponse) -> bool:
        """兼容旧调用：返回是否有 HP/周目变化。"""
        change = False
        for i, boss in enumerate(self.boss):
            current_boss = clan_battle_top.boss_info[i]
            if (
                current_boss.current_hp != boss.current_hp
                or current_boss.lap_num != boss.lap_num
            ):
                change = True
        await self.apply_boss_snapshot_from_top(clan_battle_top)
        self.finalize_ledger_after_settlement()
        return change

    async def record_change(self, clan_battle_top: ClanBattleTopResponse):
        bot = None
        with contextlib.suppress(Exception):
            bot = get_bot()
        new_histories = collect_damage_histories_to_process(
            clan_battle_top.damage_history, self.latest_time
        )
        watermark_before = self.latest_time
        if new_histories and watermark_before > 0:
            same_second = [
                h
                for h in new_histories
                if int(getattr(h, "create_time", None) or 0) == watermark_before
            ]
            if same_second:
                logger.info(
                    "damage_history 同秒续处理: group={} watermark={} count={} batch={}",
                    self.group_id,
                    watermark_before,
                    len(same_second),
                    format_history_batch_for_log(same_second),
                )
        logger.info(
            "damage_history 本 poll 待处理: group={} watermark={} count={} batch={}",
            self.group_id,
            watermark_before,
            len(new_histories),
            format_history_batch_for_log(new_histories),
        )
        push_batch: List[DamagePushBlock] = []
        for history in new_histories:
            history_time = int(history.create_time or 0)
            try:
                await self._process_damage_history_entry(
                    history, bot=bot, push_batch=push_batch
                )
            finally:
                if history_time > self.latest_time:
                    self.latest_time = history_time
        if push_batch:
            for msg in flush_damage_push_batch(
                push_batch, group_id=self.group_id
            ):
                self.notice_dao.append(msg)
        self.dao_update_time = int(time.time())
        self.refresh_latest_time(clan_battle_top)
        remaining = await list_unsettled_damage_histories(
            self.group_id,
            clan_battle_top.damage_history,
            self.latest_time,
        )
        if remaining:
            logger.warning(
                "damage_history 本轮处理后仍有未结算: group={} watermark={} remaining={}",
                self.group_id,
                self.latest_time,
                format_history_batch_for_log(remaining),
            )

    async def _process_damage_history_entry(
        self, history, *, bot, push_batch: Optional[List[DamagePushBlock]] = None
    ) -> None:
        viewer_id = history.viewer_id or 0
        log_id = int(history.history_id or 0)
        if log_id > 0 and await pcr_sqla.is_record_settlement_locked(
            self.group_id, log_id
        ):
            logger.debug(
                "damage_history 幂等跳过: group={} log_id={} viewer={}",
                self.group_id,
                log_id,
                viewer_id,
            )
            return
        if history.kill and viewer_id:
            self.pending_kills.append(
                (viewer_id, history.order_num, history.lap_num, history.create_time)
            )
        if history.kill:
            if tree_text := await self.notify_tree_off(history.order_num):
                self.notice_tree.append(tree_text)
        boss_order = int(history.order_num or 0)
        lap = int(history.lap_num or 0)
        dmg = int(history.damage or 0)
        is_kill = bool(history.kill)
        r_inst = 0
        if lap > 0 and 1 <= boss_order <= len(self.boss):
            await self.settlement_ledger.ensure_instance(
                lap,
                boss_order,
                self.boss,
                before_create_time=int(history.create_time or 0),
            )
        r_inst = 0
        if is_kill and 1 <= boss_order <= len(self.boss) and lap > 0:
            r_inst = await self.settlement_ledger.remaining_before(
                lap,
                boss_order,
                self.boss,
                before_create_time=int(history.create_time or 0),
                damage=dmg,
                is_kill=True,
            )
        timeline: Optional[TimelineInfo] = None
        battle_time = None
        if viewer_id and log_id:
            timeline = await self._fetch_timeline_info(
                viewer_id,
                log_id,
                lap=lap,
                boss_order=boss_order,
                settlement_time=int(history.create_time or 0),
                is_kill=is_kill,
            )
            if timeline:
                battle_time = timeline.battle_time
                budget_for_log = await knife_budget_service.get_budget(
                    viewer_id, history.create_time
                )
                log_timeline_comp_entry(
                    timeline,
                    viewer_id=viewer_id,
                    log_id=log_id,
                    context="damage_settlement",
                    budget=budget_for_log,
                )
        kill_comp = resolve_kill_comp_seconds(
            r_inst,
            dmg,
            is_kill=is_kill,
            battle_time=battle_time,
            viewer_id=viewer_id or None,
            context="damage_settlement",
        )
        kill_comp_seconds = kill_comp.seconds
        if kill_comp.kind not in (KillCompKind.MERGE, KillCompKind.CLEANUP):
            kill_comp_seconds = None
        settled_kind = "full"
        settlement = None
        if viewer_id:
            declared_comp_apply = False
            if is_kill:
                declared_comp_apply = await apply_declared_comp_for_viewer(
                    self.group_id, boss_order, viewer_id
                )
            settlement = await settle_from_damage_history(
                viewer_id,
                is_kill=is_kill,
                damage=dmg,
                create_time=history.create_time,
                boss_order=boss_order,
                boss_hp_before=r_inst if is_kill else None,
                kill_comp_seconds=kill_comp_seconds,
                kill_comp_kind=kill_comp.kind,
                declared_comp_apply=declared_comp_apply,
                timeline=timeline,
            )
            settled_kind = (
                "comp" if settlement.settled_kind == "comp" else "full"
            )
            await persist_settlement_record(
                self.group_id,
                log_id,
                settlement,
                pcrid=int(viewer_id),
                name=str(history.name or ""),
                lap=lap,
                boss=boss_order,
                damage=dmg,
                record_time=int(history.create_time or 0),
                kill_comp_seconds=kill_comp_seconds,
            )
            from ..knife_budget.knife_state import KnifeDisplayState
            from .merge_line.service import on_full_knife_settled

            if (
                not is_kill
                and settlement.display_state == KnifeDisplayState.FULL
            ):
                await on_full_knife_settled(
                    self.group_id,
                    boss_order,
                    dmg,
                    battle_log_id=log_id,
                    record_time=int(history.create_time or 0),
                )
        if lap > 0 and boss_order >= 1:
            self.settlement_ledger.apply_damage(
                lap, boss_order, dmg, is_kill=is_kill
            )
            self.settlement_ledger.note_settlement_for_instance(
                lap, boss_order
            )
        if is_kill and boss_order >= 1:
            cleared = await clear_board_messages_on_boss_kill(
                self.group_id, boss_order
            )
            if cleared:
                await notify_display_data_changed(
                    self.group_id, "boss_kill_clear_board_message"
                )
        if bot:
            knife_sentence = ""
            if viewer_id:
                summary = await knife_budget_service.remaining_summary(viewer_id)
                knife_sentence = build_knife_type_sentence(
                    summary,
                    settled_kind="comp" if settled_kind == "comp" else "full",
                )
                if history.kill and settlement:
                    from ..knife_budget.knife_state import KnifeDisplayState

                    if settlement.display_state == KnifeDisplayState.COMP_KILL:
                        knife_sentence = (
                            "成功击杀，未能获得补偿。" + knife_sentence
                        )
                    elif settlement.display_state in (KnifeDisplayState.KILL,):
                        prefix = format_kill_comp_push_prefix(kill_comp)
                        if prefix:
                            knife_sentence = prefix + knife_sentence
                        else:
                            knife_sentence = (
                                "成功击杀，补偿秒数异常，请联系管理。"
                                + knife_sentence
                            )
            from .actor_display import resolve_qq_user_for_viewer

            qq_uid = (
                await resolve_qq_user_for_viewer(viewer_id) or 0
                if viewer_id
                else 0
            )
            block = await build_damage_push_block(
                bot,
                self.group_id,
                history.order_num,
                create_time=int(history.create_time or 0),
                viewer_id=viewer_id or 0,
                user_id=qq_uid,
                game_name=history.name or "",
                lap=history.lap_num,
                damage=history.damage or 0,
                knife_sentence=knife_sentence,
                clan_info=self,
                is_kill=is_kill,
                settler_user_id=int(qq_uid or 0),
            )
            if push_batch is not None:
                push_batch.append(block)
            else:
                self.notice_dao.append(
                    flush_damage_push_batch(
                        [block], group_id=self.group_id
                    )[0]
                )
            logger.info(
                "报刀推送块: group={} boss={} viewer={} damage={} qq_bound={}",
                self.group_id,
                history.order_num,
                viewer_id,
                history.damage,
                bool(qq_uid),
            )
        # 报刀已用结算前队列展示挑战者；此处再扣申请/击杀清队
        await challenge_service.on_settlement(
            self.group_id,
            viewer_id,
            history.order_num,
            is_kill,
        )

    async def all_member(self):
        clan = await self.client.clan_info(self.clan_id)
        return {player.viewer_id: player.name for player in clan.clan.members}

    def refresh_latest_time(self, clan_battle_top: ClanBattleTopResponse) -> int:
        self.latest_time = (
            clan_battle_top.damage_history[0].create_time
            if clan_battle_top.damage_history
            else 0
        )

    def general_boss(self) -> str:
        return (
            "当前进度："
            + f"{self.period}面{clan_stage_num.get(self.period, 0)}阶段\n"
            + "\n".join([boss.boss_info() for boss in self.boss])
        )


class Boss:
    def __init__(self) -> None:
        self.stage = 0
        self.order = 0
        self.max_hp = 0
        self.lap_num = 0
        self.stage_num = 0
        self.current_hp = 0
        self.fighter_num = 0
        self.lap_spawn_at: int = 0

    def refresh(self, current_hp, lap_num, order, max_hp):
        new_lap = int(lap_num or 0)
        if new_lap > 0 and new_lap != int(self.lap_num or 0):
            self.lap_spawn_at = int(time.time())
        self.current_hp = current_hp
        self.lap_num = lap_num
        self.order = order
        self.max_hp = max_hp
        self.stage = clan_boss_info.lap2stage(lap_num)
        self.stage_num = clan_stage_num.get(self.stage, 0)

    def boss_info(self):
        msg = f"{self.lap_num}周目{self.order}王: "
        if self.current_hp:
            msg += f"HP: {format_bignum(self.current_hp)}/{format_bignum(self.max_hp)} {format_precent(self.current_hp/self.max_hp)}"
            if self.fighter_num:
                msg += f" 当前有{self.fighter_num}人挑战"
        else:
            msg += "无法挑战"
        return msg


@dataclass
class ClanbattleItem:
    clan_info: ClanBattle
    loop_num: int


class PrioritizedQueryItem(PrioritizedQueryItemBase):
    data: ClanbattleItem


class ClanBattlePool(PoolBase):
    async def do_single(self, item: PrioritizedQueryItem):
        clan_info: ClanBattle = item.data.clan_info
        loop_num: int = item.data.loop_num
        async with ClanbattleHandle(clan_info, loop_num):
            if loop_num != clan_info.loop_num:
                raise CancelledError

            clan_info.loop_check = time.time()

            async with status_render_batch(clan_info):
                clan_battle_top = await clan_info.get_clanbattle_top()
                clan_info.lap_num = clan_battle_top.lap_num
                clan_info.rank = clan_battle_top.period_rank

                if clan_battle_top.lap_num:
                    if clan_info.period < (
                        temp := clan_boss_info.lap2stage(clan_battle_top.lap_num)
                    ):
                        await anywhere_send(
                            f"会战阶段从{clan_info.period}面到了{temp}面，请注意轴的切换喵",
                            clan_info.group_id,
                            clan_info.bot_id,
                        )
                        clan_info.period = temp

                await clan_info.apply_boss_snapshot_from_top(clan_battle_top)
                await clan_info.send_notice(
                    [NoticeType.subscribe.value, NoticeType.fighter.value]
                )

                if await clan_info.has_new_damage_history(clan_battle_top):
                    await clan_info.record_change(clan_battle_top)
                    await clan_info.send_notice(
                        [NoticeType.dao.value, NoticeType.tree.value]
                    )
                clan_info.finalize_ledger_after_settlement()

                clan_info.error_count = 0

            asyncio.create_task(_safe_add_record(clan_info, loop_num))

        asyncio.create_task(
            self.add_task(
                PrioritizedQueryItem(data=ClanbattleItem(clan_info, loop_num)),
                int(time.time() - clan_info.loop_check),
                True,
                f"会战群{str(clan_info.group_id)}",
            )
        )


async def _safe_add_record(clan_info: ClanBattle, loop_num: int) -> None:
    lock = _record_import_locks[clan_info.group_id]
    if lock.locked():
        logger.debug(
            "add_record 跳过并发: group={} loop={}",
            clan_info.group_id,
            loop_num,
        )
        return
    async with lock:
        with contextlib.suppress(CancelledError, Exception):
            await clan_info.add_record(loop_num)


_record_import_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


class ClanbattleHandle:
    def __init__(self, clan_info: ClanBattle, loop_num: int) -> None:
        self.clan_info = clan_info
        self.loop_num = loop_num

    async def __aenter__(self):
        run_group[self.clan_info.group_id] = self.clan_info.bot_id
        self.clan_info.loop_check = time.time()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return

        self.clan_info.loop_check = 0
        if self.clan_info.group_id in run_group:
            del run_group[self.clan_info.group_id]

        if self.loop_num != self.clan_info.loop_num:
            self.clan_info.dao_update_time = int(time.time())
            if not getattr(self.clan_info, "_hot_switch_quiet", False):
                await anywhere_send(
                    f"#编号HN000{self.loop_num}监控已关闭",
                    self.clan_info.group_id,
                    self.clan_info.bot_id,
                )
            return

        if not await check_client(self.clan_info.client):
            self.clan_info.dao_update_time = int(time.time())
            await anywhere_send(
                "当前账号被顶号，出刀监控已退出",
                self.clan_info.group_id,
                self.clan_info.bot_id,
            )
            return

        if self.clan_info.error_count > 3:
            self.clan_info.error_count = 0
            self.clan_info.dao_update_time = int(time.time())
            await anywhere_send(
                "出刀监控失败次数过多，请重绑账号或手动检查账号登录状态\n"
                f"错误信息：{exc_value}",
                self.clan_info.group_id,
                self.clan_info.bot_id,
            )
            return

        logger.error(
            f"公会战{self.clan_info.user_id}发生错误，{exc_value}: {traceback}"
        )
        print(format_exc())
        self.clan_info.loop_check = time.time()
        self.clan_info.error_count += 1
        run_group[self.clan_info.group_id] = self.clan_info.bot_id
        return True
