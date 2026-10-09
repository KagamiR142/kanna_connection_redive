"""指令正则：支持末尾 CQ @ 代发（蓝图 §1.4）。"""
from __future__ import annotations

# 末尾可选 CQ @（非 @all）
PROXY_SUFFIX = r"(?:\s*(?:\[CQ:at,qq=(?!all)\d+\])?)*\s*$"

# 参数间允许空格（与 command_parser.normalize_body 等价）
_BOSS_FLEX = r"\s*[1-5]"


def strict_rex(body: str) -> str:
    """严格整句，不允许末尾代发。"""
    return rf"^\s*{body}\s*$"


def proxy_rex(body: str) -> str:
    """允许末尾 @ 一位群成员代发。"""
    return rf"^\s*{body}{PROXY_SUFFIX}"


def flex_strict_rex(body: str) -> str:
    """strict_rex + 参数间可选空白（与 normalize_body 一致）。"""
    return strict_rex(body)


def flex_proxy_rex(body: str) -> str:
    """proxy_rex + 参数间可选空白。"""
    return proxy_rex(body)


# --- 会战指令：路由与 parse_* 共用同一套「去空格」语义 ---

REX_BOSS_LAP_RECORDS = (
    rf"出刀记录{_BOSS_FLEX}(?:周目\s*\d+|\s*\d+|\s*a\s*[ytYT]?)?"
)
REX_QUERY_BOSS = rf"查{_BOSS_FLEX}"
REX_APPLY = r"(?:申请出刀|进)\s*(?:[1-5]|\d|b|[:：]).*"
REX_CANCEL_APPLY = rf"取消(?:申请|出刀)(?:{_BOSS_FLEX})?"
REX_SUBSCRIBE = r"预约(?!表)\s*(?:[1-5]|周目|[:：]).*"
REX_BOARD_MESSAGE = rf"留言{_BOSS_FLEX}[:：﹕︰].+"
REX_CANCEL_BOARD = rf"取消留言{_BOSS_FLEX}"
REX_CANCEL_SUBSCRIBE = rf"取消预约(?:{_BOSS_FLEX})?"
REX_CLEAR_SUBSCRIBE = rf"清空预约{_BOSS_FLEX}"
REX_CLEAR_APPLY = r"清空申请\s*([1-5aA])"
REX_CLEAR_UNKNOWN_APPLY = r"清空未知申请\s*([1-5aA])"
REX_TREE = rf"挂树(?:{_BOSS_FLEX})?(?:[:：].*)?"
REX_SL = r"(?:sl|SL|Sl)\s*(?:\d{1,2})?"
REX_SL_QUERY = r"(?:sl|SL|Sl)\s*(?:\d{1,2})?(?:\?|？)"
REX_DROP_KNIFE = r"掉刀\s*(?:\d{1,2})?"
REX_DROP_KNIFE_B = r"掉刀b\s*(?:\d{1,2})?"
REX_CLEAR_POINTS = r"清空出刀点数\s*(?:\d{1,2})?"
REX_TODAY_REPORT_SLOT = r"今日战报\s*(?:\d{1,2})?"
REX_SEASON_REPORT_SLOT = r"当期战报\s*(?:\d{1,2})?"
REX_KNIFE_DETAIL = r"出刀详情\s*(\d+)"
REX_MONITOR_3 = r"(?:开启)?出刀监控\s*3"
REX_MONITOR_2 = r"(?:开启)?出刀监控\s*2"
REX_MONITOR_1 = r"(?:开启)?出刀监控\s*1"
REX_MONITOR = r"(?:开启)?出刀监控\s*"
