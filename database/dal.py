import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Union

from loguru import logger
from sqlalchemy import asc, delete, desc, insert, or_, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, func

from ..basedata import FilePath, NoticeType
from .pending_record_semantics import apply_stashed_semantics_to_row, take_stashed
from .record_row import apply_knife_semantics_to_row, knife_semantics_locked
from .models import (
    Account,
    ArenaSetting,
    ChallengeState,
    ClanBattleKPI,
    ClanBattleMember,
    ClanMergeLineBoss,
    ClanMergeLineFrozenSample,
    ClanMergeLinePendingSample,
    ClanMergeLineSettings,
    CookieCache,
    DataBase,
    GrandDefenceCache,
    KcrDelegatedAdmin,
    KnifeBudget,
    NoticeCache,
    PlayerUnit,
    RecordDao,
    RefreshAccount,
    SLDao,
    SlViewerDao,
    SupportUnit,
    UserAccount,
    WebAccount,
)


def pcr_date(timeStamp: int) -> datetime:
    now = datetime.fromtimestamp(timeStamp, tz=timezone(timedelta(hours=8)))
    if now.hour < 5:
        now -= timedelta(days=1)
    return now.replace(hour=5, minute=0, second=0, microsecond=0)  # 用5点做基准


class SQALA:
    def __init__(self, url: str):
        self.url = f"sqlite+aiosqlite:///{url}"
        self.engine = create_async_engine(
            self.url,
            pool_recycle=1500,  # 连接回收时间
            pool_pre_ping=True,  # 使用前检查连接是否有效
            echo=False,  # 关闭 SQL 日志减少内存
        )
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def refresh(self, table: SQLModel, day: int, group_id: Optional[int] = 0):
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(datetime.now().timestamp())
                time = date - timedelta(days=day)
                sql = delete(table).where(table.time < time.timestamp())
                if group_id:
                    sql = sql.filter(table.group_id == group_id)
                await session.execute(sql)

    async def create_all(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(DataBase.metadata.create_all)
        await self.ensure_schema_upgrades()

    async def ensure_schema_upgrades(self):
        """为已有库补齐蓝图新增字段（幂等）。"""
        from sqlalchemy import inspect, text

        async with self.engine.begin() as conn:
            def _upgrade(connection):
                insp = inspect(connection)
                if insp.has_table("recorddao"):
                    cols = {c["name"] for c in insp.get_columns("recorddao")}
                    if "is_kill" not in cols:
                        connection.execute(
                            text(
                                "ALTER TABLE recorddao ADD COLUMN is_kill INTEGER DEFAULT 0"
                            )
                        )
                if not insp.has_table("slviewerdao"):
                    DataBase.metadata.tables.get("slviewerdao")
                    if "slviewerdao" in DataBase.metadata.tables:
                        DataBase.metadata.tables["slviewerdao"].create(
                            connection, checkfirst=True
                        )
                if insp.has_table("webaccount"):
                    cols = {c["name"] for c in insp.get_columns("webaccount")}
                    if "is_initial_password" not in cols:
                        connection.execute(
                            text(
                                "ALTER TABLE webaccount "
                                "ADD COLUMN is_initial_password INTEGER DEFAULT 1"
                            )
                        )
                if insp.has_table("knifebudget"):
                    cols = {c["name"] for c in insp.get_columns("knifebudget")}
                    if "comp_boss" not in cols:
                        connection.execute(
                            text(
                                "ALTER TABLE knifebudget "
                                "ADD COLUMN comp_boss INTEGER DEFAULT 0"
                            )
                        )
                    if "comp_pool" not in cols:
                        connection.execute(
                            text(
                                "ALTER TABLE knifebudget "
                                "ADD COLUMN comp_pool TEXT DEFAULT '[]'"
                            )
                        )
                if insp.has_table("recorddao"):
                    rcols = {c["name"] for c in insp.get_columns("recorddao")}
                    if "knife_state" not in rcols:
                        connection.execute(
                            text(
                                "ALTER TABLE recorddao "
                                "ADD COLUMN knife_state INTEGER DEFAULT 0"
                            )
                        )
                    if "knife_settled_at" not in rcols:
                        connection.execute(
                            text(
                                "ALTER TABLE recorddao "
                                "ADD COLUMN knife_settled_at INTEGER DEFAULT 0"
                            )
                        )
                    if "kill_comp_seconds" not in rcols:
                        connection.execute(
                            text(
                                "ALTER TABLE recorddao "
                                "ADD COLUMN kill_comp_seconds INTEGER DEFAULT 0"
                            )
                        )
                if insp.has_table("account"):
                    acols = {c["name"] for c in insp.get_columns("account")}
                    if "monitor_slot" not in acols:
                        connection.execute(
                            text(
                                "ALTER TABLE account "
                                "ADD COLUMN monitor_slot INTEGER DEFAULT 1"
                            )
                        )

            await conn.run_sync(_upgrade)

    # 账号部分
    async def query_account_for_group(
        self, user_id: int, group_id: int
    ) -> Optional[Account]:
        """Web：成员是否有可用于出刀身份的游戏账号（V1 取首个绑定）。"""
        accs = await self.query_account(user_id)
        return accs[0] if accs else None

    async def query_account(self, user_id: int) -> List[Account]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Account)
                    .where(Account.user_id == user_id)
                    .order_by(Account.monitor_slot, Account.id)
                )
                return list(result.scalars().all())

    async def query_monitor_account(
        self, user_id: int, slot: int
    ) -> Optional[Account]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Account).where(
                        Account.user_id == user_id,
                        Account.monitor_slot == int(slot),
                    )
                )
                return result.scalar_one_or_none()

    async def upsert_monitor_account(
        self, user_id: int, slot: int, account: dict
    ) -> None:
        payload = dict(account)
        payload["user_id"] = user_id
        payload["monitor_slot"] = int(slot)
        existing = await self.query_monitor_account(user_id, slot)
        async with self.async_session() as session:
            async with session.begin():
                if existing and existing.id is not None:
                    await session.execute(
                        update(Account)
                        .where(Account.id == existing.id)
                        .values(**payload)
                    )
                else:
                    await session.execute(insert(Account).values(**payload))

    async def add_account(self, user_id: int, account: dict, slot: int = 1):
        await self.upsert_monitor_account(user_id, slot, account)

    async def change_access(self, user_id: int, level: int):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(Account)
                    .where(Account.user_id == user_id)
                    .values(allow_others=level)
                )

    async def query_refresh(self, account: str) -> RefreshAccount:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RefreshAccount).where(RefreshAccount.account == account)
                )
                return result.scalar_one_or_none()

    async def add_refresh(self, account: RefreshAccount):
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(account)

    # 会战部分
    async def is_record_settlement_locked(
        self, group_id: int, battle_log_id: int
    ) -> bool:
        gid = int(group_id)
        log_id = int(battle_log_id)
        if log_id <= 0:
            return False
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao.knife_settled_at).where(
                        RecordDao.group_id == gid,
                        RecordDao.battle_log_id == log_id,
                    )
                )
                val = result.scalar_one_or_none()
                return int(val or 0) > 0

    async def get_record_timeline_hint(
        self, group_id: int, battle_log_id: int
    ) -> Optional[tuple[int, int]]:
        """battle_log 行上的 (start_remain_time, battle_time)，供 timeline 缓存兜底。"""
        gid = int(group_id)
        log_id = int(battle_log_id)
        if log_id <= 0:
            return None
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao.remain_time, RecordDao.battle_time).where(
                        RecordDao.group_id == gid,
                        RecordDao.battle_log_id == log_id,
                    )
                )
                row = result.one_or_none()
                if not row:
                    return None
                srt, bt = int(row[0] or 0), int(row[1] or 0)
                if srt <= 0 and bt <= 0:
                    return None
                return srt, bt

    async def get_record_timeline_hint_near_match(
        self,
        group_id: int,
        viewer_id: int,
        lap: int,
        boss: int,
        settlement_time: int,
        *,
        window_sec: int = 180,
    ) -> Optional[tuple[int, int]]:
        """按账号+周目+王+时间邻近匹配 battle_log 行上的 timeline 字段。"""
        gid = int(group_id)
        vid = int(viewer_id)
        lap_i = int(lap or 0)
        boss_i = int(boss or 0)
        st = int(settlement_time or 0)
        if gid <= 0 or vid <= 0 or lap_i <= 0 or not (1 <= boss_i <= 5) or st <= 0:
            return None
        lo = st - int(window_sec)
        hi = st + int(window_sec)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(
                        RecordDao.remain_time,
                        RecordDao.battle_time,
                        RecordDao.time,
                    )
                    .where(
                        RecordDao.group_id == gid,
                        RecordDao.pcrid == vid,
                        RecordDao.lap == lap_i,
                        RecordDao.boss == boss_i,
                        RecordDao.time >= lo,
                        RecordDao.time <= hi,
                    )
                    .order_by(desc(RecordDao.time))
                    .limit(5)
                )
                rows = result.all()
        best: Optional[tuple[int, int]] = None
        best_diff = window_sec + 1
        for srt, bt, row_time in rows:
            srt_i, bt_i = int(srt or 0), int(bt or 0)
            if srt_i <= 0 and bt_i <= 0:
                continue
            diff = abs(int(row_time or 0) - st)
            if diff < best_diff:
                best_diff = diff
                best = (srt_i, bt_i)
        if best:
            logger.debug(
                "record timeline hint near match: group={} viewer={} lap={} boss={} "
                "settle_time={} diff={} srt={} bt={}",
                gid,
                vid,
                lap_i,
                boss_i,
                st,
                best_diff,
                best[0],
                best[1],
            )
        return best

    async def upsert_record_settlement_semantics(
        self,
        group_id: int,
        battle_log_id: int,
        *,
        semantics: Dict[str, Any],
        stub: Dict[str, Any],
        settled_at: int,
    ) -> str:
        """结算写四态：有行 UPDATE，无行 INSERT stub（阵容由 add_record 补全）。"""
        gid = int(group_id)
        log_id = int(battle_log_id)

        async def _write(session: AsyncSession) -> str:
            result = await session.execute(
                select(RecordDao).where(
                    RecordDao.group_id == gid,
                    RecordDao.battle_log_id == log_id,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                apply_knife_semantics_to_row(
                    row, semantics, settled_at=int(settled_at), stub=stub
                )
                await session.merge(row)
                return "updated"
            row = RecordDao.from_settlement_stub(
                group_id=gid,
                battle_log_id=log_id,
                stub=stub,
                semantics=semantics,
                settled_at=int(settled_at),
            )
            session.add(row)
            return "inserted"

        try:
            async with self.async_session() as session:
                async with session.begin():
                    action = await _write(session)
        except Exception as first_err:
            async with self.async_session() as session:
                async with session.begin():
                    result = await session.execute(
                        select(RecordDao).where(
                            RecordDao.group_id == gid,
                            RecordDao.battle_log_id == log_id,
                        )
                    )
                    row = result.scalar_one_or_none()
                    if not row:
                        raise first_err
                    apply_knife_semantics_to_row(
                        row, semantics, settled_at=int(settled_at), stub=stub
                    )
                    await session.merge(row)
                    action = "updated_race"
                    logger.debug(
                        "RecordDao 结算四态竞态重试 UPDATE: group={} log_id={}",
                        gid,
                        log_id,
                    )
        take_stashed(gid, log_id)
        return action

    @staticmethod
    def _merge_battle_log_into_row(
        row: RecordDao, incoming: RecordDao, *, preserve_semantics: bool
    ) -> None:
        """战报 API 字段覆盖；preserve_semantics 时保留结算四态。"""
        row.name = incoming.name
        row.lap = incoming.lap
        row.boss = incoming.boss
        row.damage = incoming.damage
        row.time = incoming.time
        row.pcrid = incoming.pcrid
        row.remain_time = incoming.remain_time
        row.battle_time = incoming.battle_time
        for i in range(1, 6):
            for suffix in ("", "_level", "_damage", "_rarity", "_rank", "_unique_equip"):
                attr = f"unit{i}{suffix}"
                if hasattr(incoming, attr) and hasattr(row, attr):
                    setattr(row, attr, getattr(incoming, attr))
        if not preserve_semantics:
            row.flag = incoming.flag
            row.is_kill = incoming.is_kill
            row.knife_state = incoming.knife_state

    async def add_record(self, dao_list: List[RecordDao]):
        if not dao_list:
            return
        group_id = int(dao_list[0].group_id)
        log_ids = [int(d.battle_log_id) for d in dao_list if d.battle_log_id]
        to_insert: List[RecordDao] = []
        merged = 0
        async with self.async_session() as session:
            async with session.begin():
                by_log: Dict[int, RecordDao] = {}
                if log_ids:
                    result = await session.execute(
                        select(RecordDao).where(
                            RecordDao.group_id == group_id,
                            RecordDao.battle_log_id.in_(log_ids),
                        )
                    )
                    for row in result.scalars().all():
                        by_log[int(row.battle_log_id)] = row
                for incoming in dao_list:
                    lid = int(incoming.battle_log_id or 0)
                    if not lid:
                        continue
                    existing = by_log.get(lid)
                    if existing:
                        locked = knife_semantics_locked(existing)
                        self._merge_battle_log_into_row(
                            existing, incoming, preserve_semantics=locked
                        )
                        if not locked:
                            apply_stashed_semantics_to_row(existing)
                        merged += 1
                    else:
                        if not knife_semantics_locked(incoming):
                            apply_stashed_semantics_to_row(incoming)
                        to_insert.append(incoming)
                if to_insert:
                    session.add_all(to_insert)
        logger.debug(
            "RecordDao 入库: group={} inserted={} merged={}",
            group_id,
            len(to_insert),
            merged,
        )

    async def get_history(self, id: int, group_id: int) -> RecordDao:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.battle_log_id == id, RecordDao.group_id == group_id
                    )
                )
                return result.scalars().one_or_none()

    async def get_monitor_account_name_by_viewer(
        self, viewer_id: int
    ) -> Optional[str]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Account.name)
                    .where(Account.viewer_id == int(viewer_id))
                    .order_by(desc(Account.id))
                    .limit(1)
                )
                name = result.scalar_one_or_none()
                text = str(name or "").strip()
                return text or None

    async def get_latest_record_name_any_group(
        self, viewer_id: int
    ) -> Optional[str]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao.name)
                    .where(RecordDao.pcrid == int(viewer_id))
                    .order_by(desc(RecordDao.time))
                    .limit(1)
                )
                name = result.scalar_one_or_none()
                text = str(name or "").strip()
                return text or None

    async def get_latest_record_name(
        self, viewer_id: int, group_id: int
    ) -> Optional[str]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao.name)
                    .where(
                        RecordDao.pcrid == int(viewer_id),
                        RecordDao.group_id == int(group_id),
                    )
                    .order_by(desc(RecordDao.time))
                    .limit(1)
                )
                name = result.scalar_one_or_none()
                text = str(name or "").strip()
                return text or None

    async def get_latest_time(self, group_id: int) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.max(RecordDao.time)).where(
                        RecordDao.group_id == group_id
                    )
                )
                return result.fetchone()[0] or 0

    async def get_player_records(
        self, pcrid: int, day: int, group_id: int
    ) -> List[RecordDao]:
        latest_time = await self.get_latest_time(group_id)
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(latest_time)
                start_day = date - timedelta(days=day)
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.pcrid == pcrid,
                        RecordDao.group_id == group_id,
                    )
                    .order_by(asc(RecordDao.time))
                )
                return result.scalars().all()

    async def get_clan_day(self, group_id: int) -> int:
        latest_time = await self.get_latest_time(group_id)
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(latest_time)
                start_day = date - timedelta(days=5)
                result = await session.execute(
                    select(func.min(RecordDao.time)).where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.group_id == group_id,
                    )
                )
                time = result.fetchone()[0] or 0
                return ((latest_time - time) // (3600 * 24)) + 1

    async def get_max_dao(self, group_id: int) -> int:
        day = await self.get_clan_day(group_id)
        return day * 3

    async def get_all_records(self, group_id: int) -> List[RecordDao]:
        latest_time = await self.get_latest_time(group_id)
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(latest_time)
                start_day = date - timedelta(days=5)
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.group_id == group_id,
                    )
                )
                return result.scalars().all()

    async def get_boss_records_for_day(
        self, group_id: int, boss: int, day_ts: int
    ) -> List[RecordDao]:
        """指定 PCR 日某 Boss 全部出刀（跨周目），按 lap、time 升序。"""
        date = pcr_date(day_ts)
        tomorrow = date + timedelta(days=1)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.group_id == group_id,
                        RecordDao.boss == int(boss),
                        RecordDao.time >= date.timestamp(),
                        RecordDao.time < tomorrow.timestamp(),
                    )
                    .order_by(asc(RecordDao.lap), asc(RecordDao.time))
                )
                return result.scalars().all()

    async def get_boss_lap_records(
        self, group_id: int, lap: int, boss: int
    ) -> List[RecordDao]:
        """本期会战窗口内某周目某王的全部出刀，按时间升序。"""
        latest_time = await self.get_latest_time(group_id)
        date = pcr_date(latest_time)
        start_day = date - timedelta(days=5)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.group_id == group_id,
                        RecordDao.lap == int(lap),
                        RecordDao.boss == int(boss),
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                    )
                    .order_by(asc(RecordDao.time))
                )
                return result.scalars().all()

    async def get_boss_instance_records(
        self,
        group_id: int,
        lap: int,
        boss: int,
        *,
        before_time: int,
    ) -> List[RecordDao]:
        """同一 Boss 实例（周目+槽位）在 before_time 之前的战报，按时间升序。"""
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.group_id == group_id,
                        RecordDao.lap == lap,
                        RecordDao.boss == boss,
                        RecordDao.time < before_time,
                    )
                    .order_by(asc(RecordDao.time))
                )
                return result.scalars().all()

    async def get_day_rcords(self, timestamp: int, group_id: int) -> List[RecordDao]:
        date = pcr_date(timestamp)
        tomorrow = date + timedelta(days=1)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.time >= date.timestamp(),
                        RecordDao.time <= tomorrow.timestamp(),
                        RecordDao.group_id == group_id,
                    )
                )
                return result.scalars().all()

    async def get_day_records_for_pcrids(
        self, timestamp: int, group_id: int, pcrids: List[int]
    ) -> List[RecordDao]:
        if not pcrids:
            return []
        date = pcr_date(timestamp)
        tomorrow = date + timedelta(days=1)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.time >= date.timestamp(),
                        RecordDao.time < tomorrow.timestamp(),
                        RecordDao.group_id == group_id,
                        RecordDao.pcrid.in_(pcrids),
                    )
                    .order_by(asc(RecordDao.time))
                )
                return result.scalars().all()

    async def get_season_day_timestamps(self, group_id: int) -> List[int]:
        """返回本期会战每个 PCR 日的 5:00 时间戳（截至今日）。"""
        latest_time = await self.get_latest_time(group_id)
        if not latest_time:
            return []
        end_date = pcr_date(latest_time)
        start_date = end_date - timedelta(days=max(await self.get_clan_day(group_id) - 1, 0))
        today_date = pcr_date(int(time.time()))
        if end_date > today_date:
            end_date = today_date
        days: List[int] = []
        cur = start_date
        while cur <= end_date:
            days.append(int(cur.timestamp()))
            cur += timedelta(days=1)
        return days

    async def clanbattle_name2pcrid(self, group_id: int, name: str) -> List[int]:
        latest_time = await self.get_latest_time(group_id)
        date = pcr_date(latest_time)
        start_day = date - timedelta(days=5)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao.pcrid)
                    .where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.name == name,
                        RecordDao.group_id == group_id,
                    )
                    .distinct()
                )
                return result.scalars().all()

    async def correct_dao(self, dao_id: int, flag: int, group_id: int):
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.battle_log_id == dao_id,
                        RecordDao.group_id == group_id,
                    )
                )
                if result.scalar_one_or_none():
                    await session.execute(
                        update(RecordDao)
                        .where(
                            RecordDao.battle_log_id == dao_id,
                            RecordDao.group_id == group_id,
                        )
                        .values(flag=flag)
                    )
                    return True
        return False

    # 通知部分
    async def get_notice(
        self,
        item: int,
        group_id: int,
        boss: Optional[int] = None,
        lap: Optional[int] = None,
        user_id: Optional[int] = None,
        viewer_id: Optional[int] = None,
        exact_lap: bool = False,
    ) -> List[NoticeCache]:
        async with self.async_session() as session:
            async with session.begin():
                sql = select(NoticeCache).where(
                    NoticeCache.notice_type == item,
                    NoticeCache.group_id == group_id,
                    NoticeCache.time - int(time.time()) <= 24 * 3600,
                )
                if boss:
                    sql = sql.filter(NoticeCache.boss == boss)
                if lap is not None:
                    if exact_lap:
                        sql = sql.filter(NoticeCache.lap == lap)
                    else:
                        sql = sql.filter(NoticeCache.lap <= lap)
                if user_id:
                    sql = sql.filter(NoticeCache.user_id == user_id)
                if viewer_id:
                    sql = sql.filter(NoticeCache.viewer_id == viewer_id)
                result = await session.execute(sql)
                return result.scalars().all()

    async def get_notice_exact_lap(
        self, item: int, group_id: int, boss: int, lap: int
    ) -> List[NoticeCache]:
        return await self.get_notice(
            item, group_id, boss=boss, lap=lap, exact_lap=True
        )

    async def get_user_subscribe(
        self, group_id: int, boss: int, user_id: int
    ) -> Optional[NoticeCache]:
        rows = await self.get_notice(
            NoticeType.subscribe.value, group_id, boss, user_id=user_id
        )
        return rows[0] if rows else None

    async def get_user_board_message(
        self, group_id: int, boss: int, user_id: int
    ) -> Optional[NoticeCache]:
        rows = await self.get_notice(
            NoticeType.board_message.value, group_id, boss, user_id=user_id
        )
        return rows[0] if rows else None

    async def delete_user_reserve(
        self, group_id: int, boss: int, user_id: int
    ) -> None:
        await self.delete_notice(
            NoticeType.subscribe.value, group_id, boss, user_id=user_id
        )
        await self.delete_notice(
            NoticeType.board_message.value, group_id, boss, user_id=user_id
        )

    async def delete_all_reserve(self, group_id: int, boss: int) -> int:
        n = await self.count_reserve_for_boss(group_id, boss)
        await self.delete_notice(NoticeType.subscribe.value, group_id, boss)
        await self.delete_notice(NoticeType.board_message.value, group_id, boss)
        return n

    async def count_reserve_for_boss(self, group_id: int, boss: int) -> int:
        return (
            await self.count_notice(NoticeType.subscribe.value, group_id, boss)
            + await self.count_notice(
                NoticeType.board_message.value, group_id, boss
            )
        )

    async def clear_board_messages_for_boss(self, group_id: int, boss: int) -> int:
        n = await self.count_notice(
            NoticeType.board_message.value, group_id, boss
        )
        await self.delete_notice(
            NoticeType.board_message.value, group_id, boss
        )
        return n

    async def _one_user_reserve_row(
        self,
        session: AsyncSession,
        group_id: int,
        boss: int,
        user_id: int,
        notice_type: int,
    ) -> Optional[NoticeCache]:
        result = await session.execute(
            select(NoticeCache).where(
                NoticeCache.group_id == group_id,
                NoticeCache.boss == boss,
                NoticeCache.user_id == user_id,
                NoticeCache.notice_type == notice_type,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_reserve_subscribe(self, notice: NoticeCache) -> str:
        async with self.async_session() as session:
            async with session.begin():
                notice.time = int(time.time())
                await session.execute(
                    delete(NoticeCache).where(
                        NoticeCache.notice_type
                        == NoticeType.board_message.value,
                        NoticeCache.group_id == notice.group_id,
                        NoticeCache.boss == notice.boss,
                        NoticeCache.user_id == notice.user_id,
                    )
                )
                existing = await self._one_user_reserve_row(
                    session,
                    notice.group_id,
                    notice.boss,
                    notice.user_id,
                    NoticeType.subscribe.value,
                )
                if existing and existing.id is not None:
                    await session.execute(
                        update(NoticeCache)
                        .where(NoticeCache.id == existing.id)
                        .values(
                            text=notice.text,
                            lap=notice.lap,
                            time=notice.time,
                            viewer_id=notice.viewer_id,
                            account_id=notice.account_id,
                        )
                    )
                    return "updated"
                await session.merge(notice)
                return "inserted"

    async def upsert_reserve_board_message(self, notice: NoticeCache) -> str:
        if not str(notice.text or "").strip():
            raise ValueError("留言内容不能为空")
        async with self.async_session() as session:
            async with session.begin():
                notice.time = int(time.time())
                notice.lap = 0
                notice.notice_type = NoticeType.board_message.value
                existing_sub = await self._one_user_reserve_row(
                    session,
                    notice.group_id,
                    notice.boss,
                    notice.user_id,
                    NoticeType.subscribe.value,
                )
                if existing_sub and existing_sub.id is not None:
                    await session.execute(
                        update(NoticeCache)
                        .where(NoticeCache.id == existing_sub.id)
                        .values(text=notice.text, time=notice.time)
                    )
                    return "subscribe_text_updated"
                existing_msg = await self._one_user_reserve_row(
                    session,
                    notice.group_id,
                    notice.boss,
                    notice.user_id,
                    NoticeType.board_message.value,
                )
                if existing_msg and existing_msg.id is not None:
                    await session.execute(
                        update(NoticeCache)
                        .where(NoticeCache.id == existing_msg.id)
                        .values(
                            text=notice.text,
                            time=notice.time,
                            viewer_id=notice.viewer_id,
                            account_id=notice.account_id,
                        )
                    )
                    return "updated"
                await session.merge(notice)
                return "inserted"

    async def has_apply_for_viewer(
        self, group_id: int, boss: int, viewer_id: int
    ) -> bool:
        rows = await self.get_notice(
            NoticeType.apply.value,
            group_id,
            boss,
            viewer_id=viewer_id,
        )
        return bool(rows)

    async def has_any_apply_for_viewer(
        self, group_id: int, viewer_id: int
    ) -> bool:
        """该账号是否已有任意 Boss 的进行中申请（每账号同时仅一条）。"""
        rows = await self.get_notice(
            NoticeType.apply.value,
            group_id,
            viewer_id=viewer_id,
        )
        return bool(rows)

    async def has_apply_for_user(
        self, group_id: int, boss: int, user_id: int
    ) -> bool:
        rows = await self.get_notice(
            NoticeType.apply.value,
            group_id,
            boss,
            user_id=user_id,
        )
        return bool(rows)

    async def has_any_apply_for_user(
        self, group_id: int, user_id: int
    ) -> bool:
        """无绑定用户：是否已有任意 Boss 的进行中申请。"""
        rows = await self.get_notice(
            NoticeType.apply.value,
            group_id,
            user_id=user_id,
        )
        return bool(rows)

    async def find_user_active_apply(
        self,
        group_id: int,
        user_id: int,
        *,
        viewer_ids: Optional[Iterable[int]] = None,
    ) -> Optional[NoticeCache]:
        """查找用户当前唯一进行中申请（QQ 维度 + 绑定账号 viewer）。"""
        found: List[NoticeCache] = []
        rows = await self.get_notice(
            NoticeType.apply.value, group_id, user_id=user_id
        )
        found.extend(rows)
        for vid in viewer_ids or ():
            vrows = await self.get_notice(
                NoticeType.apply.value, group_id, viewer_id=int(vid)
            )
            found.extend(vrows)
        if not found:
            return None
        found.sort(key=lambda n: (int(n.time or 0), int(n.id or 0)))
        return found[0]

    async def find_user_tree_notice(
        self,
        group_id: int,
        user_id: int,
        *,
        boss: Optional[int] = None,
        viewer_ids: Optional[Iterable[int]] = None,
    ) -> Optional[NoticeCache]:
        """查找用户挂树记录（可选限定 Boss）。"""
        rows = await self.get_notice(
            NoticeType.tree.value, group_id, boss=boss, user_id=user_id
        )
        if rows:
            rows.sort(key=lambda n: (int(n.time or 0), int(n.id or 0)))
            return rows[0]
        for vid in viewer_ids or ():
            vrows = await self.get_notice(
                NoticeType.tree.value,
                group_id,
                boss=boss,
                viewer_id=int(vid),
            )
            if vrows:
                vrows.sort(key=lambda n: (int(n.time or 0), int(n.id or 0)))
                return vrows[0]
        return None

    async def has_tree_for_user(
        self,
        group_id: int,
        user_id: int,
        boss: int,
        *,
        viewer_ids: Optional[Iterable[int]] = None,
    ) -> bool:
        row = await self.find_user_tree_notice(
            group_id, user_id, boss=boss, viewer_ids=viewer_ids
        )
        return row is not None

    async def resolve_unbound_apply_on_settlement(
        self, group_id: int, boss: int, viewer_id: int
    ) -> int:
        """已废弃：请用 pop_oldest_unbound_apply（FIFO）。保留兼容，始终返回 0。"""
        return 0

    async def pop_oldest_unbound_apply(self, group_id: int, boss: int) -> bool:
        """非击杀结算：按时间先进先出删除一条无 viewer 的申请。"""
        applies = await self.get_notice(NoticeType.apply.value, group_id, boss)
        unbound = [n for n in applies if not n.viewer_id]
        if not unbound:
            return False
        unbound.sort(key=lambda n: (int(n.time or 0), int(n.id or 0)))
        row = unbound[0]
        if row.id is None:
            return False
        ok = await self.delete_notice_by_id(int(row.id), group_id)
        return bool(ok)

    async def delete_apply_by_viewer(
        self, group_id: int, boss: int, viewer_id: int
    ) -> int:
        """删除该 viewer 在本 Boss 上的申请（同 QQ 多游戏号互不牵连），返回删除条数。"""
        async with self.async_session() as session:
            async with session.begin():
                sql = select(NoticeCache).where(
                    NoticeCache.notice_type == NoticeType.apply.value,
                    NoticeCache.group_id == group_id,
                    NoticeCache.boss == boss,
                    NoticeCache.viewer_id == viewer_id,
                )
                result = await session.execute(sql)
                rows = result.scalars().all()
                if not rows:
                    return 0
                ids = [int(r.id) for r in rows if r.id is not None]
                await session.execute(
                    delete(NoticeCache).where(NoticeCache.id.in_(ids))
                )
                return len(ids)

    async def count_notice(
        self,
        item: int,
        group_id: int,
        boss: Optional[int] = None,
    ) -> int:
        rows = await self.get_notice(item, group_id, boss)
        return len(rows)

    async def delete_user_tree_notices(
        self,
        group_id: int,
        user_id: int,
        boss: Optional[int] = None,
    ) -> int:
        rows = await self.get_notice(NoticeType.tree.value, group_id, boss)
        count = sum(1 for n in rows if n.user_id == user_id)
        if boss:
            await self.delete_notice(
                NoticeType.tree.value, group_id, boss, user_id=user_id
            )
        else:
            await self.delete_notice(
                NoticeType.tree.value, group_id, user_id=user_id
            )
        return count

    async def delete_user_applies(
        self,
        group_id: int,
        user_id: int,
        boss: Optional[int] = None,
    ) -> int:
        accounts = await self.query_user_accounts(user_id)
        viewer_ids = {a.viewer_id for a in accounts if a.viewer_id}
        all_applies = await self.get_notice(
            NoticeType.apply.value, group_id, boss
        )
        count = sum(
            1
            for n in all_applies
            if n.user_id == user_id
            or (n.viewer_id and n.viewer_id in viewer_ids)
        )
        if boss:
            await self.delete_notice(
                NoticeType.apply.value, group_id, boss, user_id=user_id
            )
            for vid in viewer_ids:
                await self.delete_apply_by_viewer(group_id, boss, vid)
        else:
            await self.delete_notice(NoticeType.apply.value, group_id, user_id=user_id)
            for vid in viewer_ids:
                for b in range(1, 6):
                    await self.delete_apply_by_viewer(group_id, b, vid)
        return count

    async def delete_notice_by_id(self, notice_id: int, group_id: int) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(NoticeCache).where(
                        NoticeCache.id == notice_id,
                        NoticeCache.group_id == group_id,
                    )
                )
                row = result.scalar_one_or_none()
                if not row:
                    return False
                await session.delete(row)
                return True

    async def delete_notice(
        self,
        item: int,
        group_id: int,
        boss: Optional[int] = None,
        user_id: Optional[int] = None,
        lap: Optional[int] = None,
        exact_lap: bool = False,
    ):
        async with self.async_session() as session:
            async with session.begin():
                sql = delete(NoticeCache).where(
                    NoticeCache.notice_type == item, NoticeCache.group_id == group_id
                )
                if boss:
                    sql = sql.filter(NoticeCache.boss == boss)
                if lap is not None:
                    if exact_lap:
                        sql = sql.filter(NoticeCache.lap == lap)
                    else:
                        sql = sql.filter(NoticeCache.lap <= lap)
                if user_id:
                    sql = sql.filter(NoticeCache.user_id == user_id)
                await session.execute(sql)

    async def delete_notice_exact_lap(
        self, item: int, group_id: int, boss: int, lap: int
    ) -> None:
        await self.delete_notice(
            item, group_id, boss=boss, lap=lap, exact_lap=True
        )

    async def add_notice(self, notice: NoticeCache):
        if notice.notice_type == NoticeType.subscribe.value:
            await self.upsert_reserve_subscribe(notice)
            return
        if notice.notice_type == NoticeType.board_message.value:
            await self.upsert_reserve_board_message(notice)
            return
        async with self.async_session() as session:
            async with session.begin():
                notice.time = int(time.time())
                if notice.notice_type == NoticeType.tree.value:
                    rows = await self.get_notice(
                        NoticeType.tree.value,
                        notice.group_id,
                        notice.boss,
                        user_id=notice.user_id,
                    )
                    if rows:
                        await session.execute(
                            update(NoticeCache)
                            .where(NoticeCache.id == rows[0].id)
                            .values(
                                text=notice.text,
                                time=notice.time,
                                viewer_id=notice.viewer_id,
                                account_id=notice.account_id,
                            )
                        )
                        return
                elif notice.notice_type == NoticeType.apply.value:
                    if notice.viewer_id and await self.has_any_apply_for_viewer(
                        notice.group_id, notice.viewer_id
                    ):
                        return
                    if (
                        not notice.viewer_id
                        and await self.has_any_apply_for_user(
                            notice.group_id, notice.user_id
                        )
                    ):
                        return

                await session.merge(notice)

    async def add_sl(self, sl: SLDao) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                if await self.check_sl(sl.user_id, sl.group_id):
                    return False
                await session.merge(sl)
                return True

    async def check_sl(self, uid: int, group_id: int) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(SLDao).where(
                        SLDao.user_id == uid,
                        SLDao.group_id == group_id,
                        SLDao.time > pcr_date(datetime.now().timestamp()).timestamp(),
                    )
                )
                return bool(result.scalar_one_or_none())

    async def add_sl_viewer(self, group_id: int, viewer_id: int) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                if await self.check_sl_viewer(viewer_id, group_id):
                    return False
                await session.merge(
                    SlViewerDao(
                        group_id=group_id,
                        viewer_id=viewer_id,
                        time=int(time.time()),
                    )
                )
                return True

    async def check_sl_viewer(self, viewer_id: int, group_id: int) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(SlViewerDao).where(
                        SlViewerDao.viewer_id == viewer_id,
                        SlViewerDao.group_id == group_id,
                        SlViewerDao.time
                        > pcr_date(datetime.now().timestamp()).timestamp(),
                    )
                )
                return bool(result.scalar_one_or_none())

    async def get_kpis(self, group_id: int) -> List[ClanBattleKPI]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleKPI).where(ClanBattleKPI.group_id == group_id)
                )
                return result.scalars().all()

    async def add_kpi_special(self, kpi: ClanBattleKPI):
        async with self.async_session() as session:
            async with session.begin():
                kpi.time = int(time.time())
                await session.merge(kpi)

    async def delete_kpi(self, group_id: int, pcrid: Optional[int] = None):
        async with self.async_session() as session:
            async with session.begin():
                sql = delete(ClanBattleKPI).where(ClanBattleKPI.group_id == group_id)
                if pcrid:
                    sql = sql.filter(ClanBattleKPI.pcrid == pcrid)
                await session.execute(sql)

    # BOX部分
    async def refresh_player_units(self, unit_list: List[PlayerUnit], user_id: int):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(PlayerUnit).where(PlayerUnit.user_id == user_id)
                )
                session.add_all(unit_list)

    async def get_player_units(self, user_id: int) -> List[PlayerUnit]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(PlayerUnit).where(PlayerUnit.user_id == user_id)
                )
                return result.scalars().all()

    async def get_player_support_units(self, user_id: int) -> List[PlayerUnit]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(PlayerUnit).where(
                        PlayerUnit.user_id == user_id, PlayerUnit.support_position != 0
                    )
                )
                return result.scalars().all()

    async def refresh_support_units(
        self, support_list: List[SupportUnit], group_id: int
    ):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(SupportUnit).where(SupportUnit.group_id == group_id)
                )
                session.add_all(support_list)

    async def get_support_units(self, group_id: int) -> List[SupportUnit]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(SupportUnit).where(SupportUnit.group_id == group_id)
                )
                return result.scalars().all()

    # 成员部分
    async def add_member(self, member: ClanBattleMember):
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(member)

    async def delete_member(self, group_id: int, user_id: int):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(ClanBattleMember).where(
                        ClanBattleMember.user_id == user_id,
                        ClanBattleMember.group_id == group_id,
                    )
                )

    async def get_group_member(self, group_id: int) -> List[ClanBattleMember]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleMember).where(
                        ClanBattleMember.group_id == group_id
                    )
                )
                return result.scalars().all()

    async def get_member_group(self, user_id: int) -> List[ClanBattleMember]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleMember).where(ClanBattleMember.user_id == user_id)
                )
                return result.scalars().all()

    # 竞技场设置
    async def init_jjc_setting(self, user_setting: ArenaSetting):
        async with self.async_session() as session:
            async with session.begin():
                if not await self.get_jjc_setting(user_setting.user_id):
                    session.add(user_setting)

    async def get_jjc_setting(self, user_id: int) -> Union[ArenaSetting, None]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ArenaSetting).where(ArenaSetting.user_id == user_id)
                )
                return result.scalar_one_or_none()

    async def update_jjc_setting(self, user_id: int, update_valuse: dict):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(ArenaSetting)
                    .where(ArenaSetting.user_id == user_id)
                    .values(**update_valuse)
                )

    # 公主竞技场防守缓存

    async def add_grand_cache(self, historys: List[GrandDefenceCache]):
        if not historys:
            return
        async with self.async_session() as session:
            async with session.begin():
                for history in historys[::-1]:
                    await session.merge(history)

    async def query_grand_cache(self, pcrid: int, row: int) -> Union[int, None]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GrandDefenceCache.defence)
                    .where(
                        GrandDefenceCache.pcrid == pcrid, GrandDefenceCache.row == row
                    )
                    .order_by(desc(GrandDefenceCache.vs_time))
                )
                return int(result) if (result := result.scalars().first()) else result

    async def cache_latest_time(self, user_id: int) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.max(GrandDefenceCache.vs_time)).where(
                        GrandDefenceCache.user_id == user_id
                    )
                )
                return result.scalar_one_or_none() or 0

    # Web
    async def web_check_user(self, account: str, password: str) -> WebAccount:
        from ..webui.password_util import needs_rehash, verify_password
        from ..webui.password_util import hash_password as _hash_password

        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(WebAccount).where(WebAccount.account == account)
                )
                row = result.scalar_one_or_none()
                if not row or not verify_password(password, row.password):
                    return None
                if needs_rehash(row.password):
                    row.password = _hash_password(password)
                    await session.merge(row)
                return row

    async def web_query_user(self, account) -> WebAccount:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(WebAccount).where(WebAccount.account == account)
                )
                return result.scalar_one_or_none()

    async def web_add_user(self, account: WebAccount):
        async with self.async_session() as session:
            async with session.begin():
                account.create_time = int(time.time())
                if user := await self.web_query_user(account.account):
                    account.priority = user.priority
                await session.merge(account)

    async def web_upsert_user(self, account: WebAccount) -> None:
        async with self.async_session() as session:
            async with session.begin():
                account.create_time = int(time.time())
                await session.merge(account)

    async def change_web_password(
        self, account: str, old_password: str, new_password: str
    ) -> bool:
        from ..webui.password_util import hash_password, verify_password

        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(WebAccount).where(WebAccount.account == account)
                )
                row = result.scalar_one_or_none()
                if not row or not verify_password(old_password, row.password):
                    return False
                row.password = hash_password(new_password)
                row.is_initial_password = False
                row.temp = False
                await session.merge(row)
                return True

    async def get_bound_groups(self):
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(ClanBattleMember))
                return result.scalars().all()

    async def web_add_cookie(self, token: str, user_id: str):
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(CookieCache(token=token, user_id=user_id))

    async def web_delete_cookie(
        self, token: Optional[str] = None, user_id: Optional[str] = None
    ):
        async with self.async_session() as session:
            async with session.begin():
                if not token or user_id:
                    raise ValueError("需要指定token或者user")
                sql = delete(CookieCache)
                if token:
                    sql = sql.filter(CookieCache.token == token)
                if user_id:
                    sql = sql.filter(CookieCache.user_id == user_id)
                await session.execute(sql)

    async def web_query_cookie(self, token: str) -> CookieCache:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(CookieCache).where(CookieCache.token == token)
                )
                return result.scalar_one_or_none()

    async def add_user_account(self, user_account: UserAccount) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(user_account)

    async def query_user_accounts(self, user_id: int) -> List[UserAccount]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserAccount)
                    .where(UserAccount.user_id == user_id, UserAccount.is_active == True)
                    .order_by(UserAccount.sort_order)
                )
                return result.scalars().all()

    async def query_accounts_by_viewer(self, viewer_id: int) -> List[UserAccount]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserAccount).where(
                        UserAccount.viewer_id == viewer_id,
                        UserAccount.is_active == True,
                    )
                )
                return result.scalars().all()

    async def delete_all_notices_by_type(self, notice_type: int) -> int:
        async with self.async_session() as session:
            async with session.begin():
                count_result = await session.execute(
                    select(func.count())
                    .select_from(NoticeCache)
                    .where(NoticeCache.notice_type == notice_type)
                )
                count = int(count_result.scalar_one() or 0)
                await session.execute(
                    delete(NoticeCache).where(NoticeCache.notice_type == notice_type)
                )
                return count

    async def reset_all_challenge_states(self) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(ChallengeState))
                rows = list(result.scalars().all())
                now = int(time.time())
                for state in rows:
                    state.enter_signal = 0
                    state.unknown_labels = "[]"
                    state.last_fighter_num = 0
                    state.updated_at = now
                    session.add(state)
                return len(rows)

    async def get_challenge_state(self, group_id: int, boss: int) -> ChallengeState:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ChallengeState).where(
                        ChallengeState.group_id == group_id,
                        ChallengeState.boss == boss,
                    )
                )
                state = result.scalar_one_or_none()
                if not state:
                    state = ChallengeState(group_id=group_id, boss=boss)
                    session.add(state)
                return state

    async def save_challenge_state(self, state: ChallengeState) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(state)

    async def get_knife_budget(self, viewer_id: int, pcr_date_key: str) -> KnifeBudget:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(KnifeBudget).where(
                        KnifeBudget.viewer_id == viewer_id,
                        KnifeBudget.pcr_date == pcr_date_key,
                    )
                )
                budget = result.scalar_one_or_none()
                if not budget:
                    budget = KnifeBudget(viewer_id=viewer_id, pcr_date=pcr_date_key)
                    session.add(budget)
                from ..knife_budget.comp_pool import ensure_comp_pool_migrated

                ensure_comp_pool_migrated(budget)
                return budget

    async def save_knife_budget(self, budget: KnifeBudget) -> None:
        async with self.async_session() as session:
            async with session.begin():
                budget.updated_at = int(time.time())
                await session.merge(budget)

    async def list_knife_budgets(self, pcr_date_key: str) -> List[KnifeBudget]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(KnifeBudget).where(KnifeBudget.pcr_date == pcr_date_key)
                )
                return result.scalars().all()

    async def list_accounts(self) -> List[Account]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(Account))
                return result.scalars().all()

    async def get_account_by_id(self, account_id: int) -> Optional[Account]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Account).where(Account.id == account_id)
                )
                return result.scalar_one_or_none()

    async def delete_account(self, user_id: int) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(delete(Account).where(Account.user_id == user_id))

    async def list_user_account_bindings(self, user_id: Optional[int] = None) -> List[UserAccount]:
        async with self.async_session() as session:
            async with session.begin():
                sql = select(UserAccount)
                if user_id is not None:
                    sql = sql.where(UserAccount.user_id == user_id)
                result = await session.execute(sql.order_by(UserAccount.user_id, UserAccount.sort_order))
                return result.scalars().all()

    async def get_user_account_by_id(self, binding_id: int) -> Optional[UserAccount]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserAccount).where(UserAccount.id == int(binding_id))
                )
                return result.scalar_one_or_none()

    async def delete_user_account_binding(self, binding_id: int) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(UserAccount).where(UserAccount.id == binding_id)
                )

    async def list_kcr_delegated_admin_qqs(self) -> List[int]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(select(KcrDelegatedAdmin.qq_id))
                return [int(x) for x in result.scalars().all()]

    async def list_kcr_delegated_admin_rows(self) -> List[dict]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(KcrDelegatedAdmin).order_by(KcrDelegatedAdmin.appointed_at)
                )
                rows = result.scalars().all()
                return [
                    {
                        "qq_id": int(r.qq_id),
                        "appointed_at": int(r.appointed_at or 0),
                        "appointed_by": int(r.appointed_by or 0),
                    }
                    for r in rows
                ]

    async def count_kcr_delegated_admins(self) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.count()).select_from(KcrDelegatedAdmin)
                )
                return int(result.scalar_one() or 0)

    async def add_kcr_delegated_admin(
        self, qq_id: int, *, appointed_by: int, appointed_at: int
    ) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(
                    KcrDelegatedAdmin(
                        qq_id=int(qq_id),
                        appointed_by=int(appointed_by),
                        appointed_at=int(appointed_at),
                    )
                )

    async def remove_kcr_delegated_admin(self, qq_id: int) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    delete(KcrDelegatedAdmin).where(
                        KcrDelegatedAdmin.qq_id == int(qq_id)
                    )
                )
                return bool(result.rowcount)

    async def get_merge_line_settings(self, group_id: int) -> ClanMergeLineSettings:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanMergeLineSettings).where(
                        ClanMergeLineSettings.group_id == int(group_id)
                    )
                )
                row = result.scalar_one_or_none()
                if not row:
                    row = ClanMergeLineSettings(group_id=int(group_id))
                    session.add(row)
                return row

    async def save_merge_line_settings(self, row: ClanMergeLineSettings) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(row)

    async def get_merge_line_boss(
        self, group_id: int, boss: int
    ) -> ClanMergeLineBoss:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanMergeLineBoss).where(
                        ClanMergeLineBoss.group_id == int(group_id),
                        ClanMergeLineBoss.boss == int(boss),
                    )
                )
                row = result.scalar_one_or_none()
                if not row:
                    from ..clanbattle.merge_line.constants import DEFAULT_MERGE_LINE

                    row = ClanMergeLineBoss(
                        group_id=int(group_id),
                        boss=int(boss),
                        threshold=DEFAULT_MERGE_LINE,
                    )
                    session.add(row)
                return row

    async def save_merge_line_boss(self, row: ClanMergeLineBoss) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(row)

    async def clear_merge_line_for_group(self, group_id: int) -> None:
        gid = int(group_id)
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(ClanMergeLinePendingSample).where(
                        ClanMergeLinePendingSample.group_id == gid
                    )
                )
                await session.execute(
                    delete(ClanMergeLineFrozenSample).where(
                        ClanMergeLineFrozenSample.group_id == gid
                    )
                )
                await session.execute(
                    delete(ClanMergeLineBoss).where(
                        ClanMergeLineBoss.group_id == gid
                    )
                )

    async def add_merge_line_pending(
        self,
        group_id: int,
        boss: int,
        damage: int,
        *,
        battle_log_id: int,
        record_time: int,
    ) -> int:
        async with self.async_session() as session:
            async with session.begin():
                row = ClanMergeLinePendingSample(
                    group_id=int(group_id),
                    boss=int(boss),
                    damage=int(damage),
                    battle_log_id=int(battle_log_id),
                    record_time=int(record_time),
                )
                session.add(row)
                await session.flush()
                return int(row.id or 0)

    async def count_merge_line_pending(self, group_id: int, boss: int) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.count())
                    .select_from(ClanMergeLinePendingSample)
                    .where(
                        ClanMergeLinePendingSample.group_id == int(group_id),
                        ClanMergeLinePendingSample.boss == int(boss),
                    )
                )
                return int(result.scalar_one() or 0)

    async def list_merge_line_pending(
        self, group_id: int, boss: int, limit: int = 20
    ) -> List[ClanMergeLinePendingSample]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanMergeLinePendingSample)
                    .where(
                        ClanMergeLinePendingSample.group_id == int(group_id),
                        ClanMergeLinePendingSample.boss == int(boss),
                    )
                    .order_by(asc(ClanMergeLinePendingSample.id))
                    .limit(limit)
                )
                return list(result.scalars().all())

    async def delete_merge_line_pending(self, group_id: int, boss: int) -> None:
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(ClanMergeLinePendingSample).where(
                        ClanMergeLinePendingSample.group_id == int(group_id),
                        ClanMergeLinePendingSample.boss == int(boss),
                    )
                )

    async def replace_merge_line_frozen(
        self,
        group_id: int,
        boss: int,
        samples: List[tuple[int, int, int]],
    ) -> None:
        gid, b = int(group_id), int(boss)
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(ClanMergeLineFrozenSample).where(
                        ClanMergeLineFrozenSample.group_id == gid,
                        ClanMergeLineFrozenSample.boss == b,
                    )
                )
                for seq, (dmg, log_id, rtime) in enumerate(samples, start=1):
                    session.add(
                        ClanMergeLineFrozenSample(
                            group_id=gid,
                            boss=b,
                            seq=seq,
                            damage=int(dmg),
                            battle_log_id=int(log_id),
                            record_time=int(rtime),
                        )
                    )

    async def list_season_full_knife_for_merge_line(
        self,
        group_id: int,
        boss: int,
        since_ts: int,
        *,
        min_damage: int,
        knife_state_full: int,
        limit: int,
    ) -> List[RecordDao]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.group_id == int(group_id),
                        RecordDao.boss == int(boss),
                        RecordDao.time >= int(since_ts),
                        RecordDao.knife_state == int(knife_state_full),
                        RecordDao.damage >= int(min_damage),
                    )
                    .order_by(desc(RecordDao.time))
                    .limit(limit)
                )
                return list(result.scalars().all())


pcr_sqla = SQALA(str(FilePath.data.value / "data.db"))
