import asyncio
import time
from typing import Dict, List, Optional, Tuple, Union

from fastapi import Cookie, Depends, HTTPException, status
from nonebot import MessageSegment, logger

from ..basedata import GroupPriority, NoticeType
from ..clanbattle.base import day_report
from ..util.auto_boss import clan_boss_info
from ..database.dal import pcr_sqla
from ..database.models import RecordDao
from ..util.tools import daoflag2str
from .permissions import (
    effective_group_priority,
    ensure_group_access,
    fetch_group_role,
    get_member_row,
    is_bot_owner,
    is_group_manager_in,
    is_web_ops_admin,
    require_group_priority,
    require_web_ops_admin,
    verify_group_access,
)
from .session import call_in_main_loop, main_event_loop, verify_cookie
from .web_model import DaoInfo

__all__ = [
    "main_event_loop",
    "call_in_main_loop",
    "verify_cookie",
    "verify_group_access",
    "effective_group_priority",
    "ensure_group_access",
    "require_group_priority",
    "is_bot_owner",
    "is_group_manager_in",
    "get_member_row",
    "fetch_group_role",
    "is_web_ops_admin",
    "require_web_ops_admin",
    "get_day_dao",
    "build_last_dao",
    "build_day_damage_rank",
    "get_notice_msg",
    "cancel_notice_msg",
]


async def get_day_dao(
    dao_data: List[RecordDao], members: Dict[int, str] = None
) -> Tuple[int, list]:
    total = 0
    state = {3: [], 2.5: [], 2: [], 1.5: [], 1: [], 0.5: [], 0: []}
    report_info = await day_report(dao_data, members or {})
    for member in report_info:
        name = member[1]
        dao = min(member[2], 3)
        state[dao].append(name)
        total += dao

    return total, [{"dao_num": dao, "names": state[dao]} for dao in state if state[dao]]


def build_last_dao(dao_data: List[RecordDao], limit: int = 20) -> List[DaoInfo]:
    """把一组出刀记录按时间倒序、取最新 N 条，转成前端 Dashboard 用的 DaoInfo 列表。"""
    sorted_list = sorted(dao_data, key=lambda r: r.time, reverse=True)
    return [
        DaoInfo(
            name=player.name,
            damage=player.damage,
            score=int(clan_boss_info.get_boss_rate(player.lap, player.boss) * player.damage),
            type=daoflag2str(player.flag),
            date=player.time,
            boss=player.boss,
            lap=player.lap,
            dao_id=player.battle_log_id,
        )
        for player in sorted_list[:limit]
    ]


def build_day_damage_rank(
    dao_data: List[RecordDao], limit: int = 10
) -> Tuple[List[dict], int, int]:
    """按玩家聚合「今日」伤害，返回 (Top N 排行, 全员总伤害, 全员总分数)。"""
    stat: Dict[int, dict] = {}
    total_damage = 0
    total_score = 0
    for record in dao_data:
        score = int(clan_boss_info.get_boss_rate(record.lap, record.boss) * record.damage)
        row = stat.setdefault(
            record.pcrid, {"name": record.name, "damage": 0, "score": 0, "dao": 0.0}
        )
        if record.name:
            row["name"] = record.name
        row["damage"] += record.damage
        row["score"] += score
        row["dao"] += 1 if record.flag == 0 else 0.5
        total_damage += record.damage
        total_score += score

    rows = sorted(stat.values(), key=lambda r: r["damage"], reverse=True)[:limit]
    for row in rows:
        row["damage_rate"] = (
            round(row["damage"] / total_damage * 100, 2) if total_damage else 0.0
        )
        row["score_rate"] = round(row["score"] / total_score * 100, 2) if total_score else 0.0
    return rows, total_damage, total_score


def get_notice_msg(type: int, user_id: int, boss: int, lap: int, msg: str) -> str:
    at_msg = MessageSegment.at(user_id)
    if type == NoticeType.subscribe.value:
        resp = "预约了"
    elif type == NoticeType.board_message.value:
        resp = "留言在了"
        resp += f"{boss}王"
        resp += f"\n留言: {msg}" if msg else ""
        return at_msg + resp
    elif type == NoticeType.apply.value:
        resp = "申请了"
    elif type == NoticeType.tree.value:
        resp = "挂树在了"
    elif type == NoticeType.sl.value:
        return at_msg + "SL了" + (f"\n留言: {msg}" if msg else "")

    resp += f"第{lap}周目" if lap else "当前周目"
    resp += f"{boss}王"
    resp += f"\n留言: {msg}" if msg else ""
    return at_msg + resp


def cancel_notice_msg(
    type: int, user_id: int, boss: int, operator: int = 114514
) -> str:
    operator_msg = (MessageSegment.at(operator) + "使") if operator != user_id else ""
    if type in (
        NoticeType.subscribe.value,
        NoticeType.board_message.value,
    ):
        resp = "取消预约/留言了"
    elif type == NoticeType.apply.value:
        resp = "取消申请了"
    elif type == NoticeType.tree.value:
        resp = "取消挂树在了"
    resp += f"{boss}王"
    return operator_msg + MessageSegment.at(user_id) + resp
