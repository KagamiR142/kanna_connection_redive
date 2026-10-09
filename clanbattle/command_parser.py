"""自动报刀指令解析（忽略参数间空格，严格整句匹配）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..util.message_sanitize import sanitize_remark

_COMP_PREFIX = "[补偿]"
_COLON = r"[:：﹕︰]"


def normalize_body(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


@dataclass
class SubscribeParse:
    boss: int
    lap: int = 0
    remark: str = ""


@dataclass
class BoardMessageParse:
    boss: int
    remark: str = ""


@dataclass
class ApplyParse:
    boss: int
    is_comp: bool = False
    remark: str = ""
    account_slot: Optional[int] = None


@dataclass
class CancelApplyParse:
    boss: Optional[int] = None


@dataclass
class TreeParse:
    boss: Optional[int] = None
    remark: str = ""


@dataclass
class AccountSlotParse:
    account_slot: Optional[int] = None


@dataclass
class BossLapRecordsParse:
    boss: int
    lap: Optional[int] = None
    all_laps: bool = False
    day_token: Optional[str] = None  # a 模式下：y/t 或 None（默认昨天，首日改今天）


def _parse_tail(tail: str) -> tuple[bool, Optional[int], str]:
    """解析 [b][账号编号][:留言]；normalize_body 已去空格，故「进3b 2」等价「进3b2」。"""
    is_comp = False
    account_slot: Optional[int] = None
    remark = ""
    rest = tail or ""
    if rest.lower().startswith("b"):
        is_comp = True
        rest = rest[1:]
    if rest and rest[0].isdigit():
        m = re.match(r"^(\d{1,2})", rest)
        if m:
            slot = int(m.group(1))
            if 1 <= slot <= 30:
                account_slot = slot
            rest = rest[m.end() :]
    if rest and rest[0] in ":：":
        remark = sanitize_remark(rest[1:])
    return is_comp, account_slot, remark


def parse_subscribe(text: str) -> Optional[SubscribeParse]:
    body = normalize_body(text)
    m = re.fullmatch(r"预约([1-5])(?:周目(\d+))?(?:[:：](.+))?", body, flags=re.I)
    if not m:
        return None
    return SubscribeParse(
        boss=int(m.group(1)),
        lap=int(m.group(2)) if m.group(2) else 0,
        remark=sanitize_remark(m.group(3) or ""),
    )


def parse_board_message(text: str) -> Optional[BoardMessageParse]:
    body = normalize_body(text)
    m = re.fullmatch(rf"留言([1-5]){_COLON}(.+)", body, flags=re.I)
    if not m:
        return None
    remark = sanitize_remark(m.group(2))
    if not remark:
        return None
    return BoardMessageParse(boss=int(m.group(1)), remark=remark)


def parse_cancel_board_message(text: str) -> tuple[Optional[int], bool]:
    """(boss, matched)。仅匹配「取消留言<boss>」。"""
    body = normalize_body(text)
    m = re.fullmatch(r"取消留言([1-5])", body, flags=re.I)
    if m:
        return int(m.group(1)), True
    return None, False


def parse_boss_lap_records(text: str) -> Optional[BossLapRecordsParse]:
    # 与其它指令一致：参数间空格会被去掉，故「出刀记录2 29」→「出刀记录229」
    body = normalize_body(text)
    m = re.fullmatch(r"出刀记录([1-5])(.*)", body, flags=re.I)
    if not m:
        return None
    boss = int(m.group(1))
    rest = (m.group(2) or "").strip()
    if not rest:
        return BossLapRecordsParse(boss=boss)
    m_lap = re.fullmatch(r"周目(\d+)", rest, flags=re.I)
    if m_lap:
        return BossLapRecordsParse(boss=boss, lap=int(m_lap.group(1)))
    m_all = re.fullmatch(r"a([ytYT])?", rest, flags=re.I)
    if m_all:
        tok = m_all.group(1)
        return BossLapRecordsParse(
            boss=boss,
            all_laps=True,
            day_token=tok.lower() if tok else None,
        )
    if rest.isdigit():
        return BossLapRecordsParse(boss=boss, lap=int(rest))
    return None


def parse_apply(text: str) -> Optional[ApplyParse]:
    body = normalize_body(text)
    m = re.fullmatch(r"(?:申请出刀|进)([1-5])(.*)", body, flags=re.I)
    if not m:
        return None
    is_comp, account_slot, remark = _parse_tail(m.group(2))
    if is_comp:
        remark = f"{_COMP_PREFIX}{remark}" if remark else _COMP_PREFIX
    return ApplyParse(
        boss=int(m.group(1)),
        is_comp=is_comp,
        remark=remark,
        account_slot=account_slot,
    )


def parse_tree(text: str) -> Optional[TreeParse]:
    """挂树 / 挂树：留言 / 挂树<boss> / 挂树<boss>：留言；boss 可省略。"""
    body = normalize_body(text)
    m = re.fullmatch(
        r"挂树(?:([1-5])(?:[:：](.+))?|(?:[:：](.+))?)?$",
        body,
        flags=re.I,
    )
    if not m:
        return None
    boss = int(m.group(1)) if m.group(1) else None
    remark = sanitize_remark(m.group(2) or m.group(3) or "")
    return TreeParse(boss=boss, remark=remark)


def parse_cancel_tree(text: str) -> bool:
    body = normalize_body(text)
    return re.fullmatch(r"取消挂树", body, flags=re.I) is not None


def parse_account_slot_command(text: str, cmd: str) -> Optional[AccountSlotParse]:
    body = normalize_body(text)
    m = re.fullmatch(rf"{cmd}(\d{{1,2}})?", body, flags=re.I)
    if not m:
        return None
    slot = int(m.group(1)) if m.group(1) else None
    if slot is not None and not (1 <= slot <= 30):
        slot = None
    return AccountSlotParse(account_slot=slot)


def parse_sl_query_command(text: str) -> Optional[AccountSlotParse]:
    """sl[账号编号]?（全角 ？ 同义）；编号在 ? 之前。"""
    body = normalize_body(text)
    m = re.fullmatch(r"(?:sl|SL|Sl)(\d{1,2})?(?:\?|？)", body, flags=re.I)
    if not m:
        return None
    slot = int(m.group(1)) if m.group(1) else None
    if slot is not None and not (1 <= slot <= 30):
        slot = None
    return AccountSlotParse(account_slot=slot)


def parse_cancel_subscribe(text: str) -> tuple[Optional[int], bool]:
    """(boss, matched)。boss 为 None 且 matched 表示「取消预约」缺 boss。"""
    body = normalize_body(text)
    if body == "取消预约":
        return None, True
    m = re.fullmatch(r"取消预约([1-5])", body, flags=re.I)
    if m:
        return int(m.group(1)), True
    return None, False


def parse_cancel_apply(text: str) -> Optional[CancelApplyParse]:
    body = normalize_body(text)
    m = re.fullmatch(r"取消(?:申请|出刀)(?:([1-5]))?", body, flags=re.I)
    if not m:
        return None
    boss = int(m.group(1)) if m.group(1) else None
    return CancelApplyParse(boss=boss)


def parse_clear_subscribe(text: str) -> Optional[int]:
    body = normalize_body(text)
    m = re.fullmatch(r"清空预约([1-5])", body, flags=re.I)
    return int(m.group(1)) if m else None


def parse_clear_apply(text: str) -> tuple[Optional[int], bool, bool]:
    """(boss, all_bosses, matched)。all_bosses 表示 清空申请a。"""
    body = normalize_body(text)
    m = re.fullmatch(r"清空申请([1-5aA])", body, flags=re.I)
    if not m:
        return None, False, False
    token = m.group(1).lower()
    if token == "a":
        return None, True, True
    return int(token), False, True


def parse_clear_unknown_apply(text: str) -> tuple[Optional[int], bool, bool]:
    body = normalize_body(text)
    m = re.fullmatch(r"清空未知申请([1-5aA])", body, flags=re.I)
    if not m:
        return None, False, False
    token = m.group(1).lower()
    if token == "a":
        return None, True, True
    return int(token), False, True


def is_exact_command(text: str, *commands: str) -> bool:
    body = text.strip()
    return body in commands or normalize_body(body) in {normalize_body(c) for c in commands}


def match_exact(text: str, pattern: str) -> Optional[re.Match]:
    body = normalize_body(text)
    return re.fullmatch(pattern, body, flags=re.I)
