"""会战 Boss 元数据（Satroki / boss_info.json）统一刷新 — 一次性更新当期全部 Boss。"""
from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, TYPE_CHECKING

import httpx

from ..setting import BossData
from ..util.auto_boss import BossOnlineData, clan_boss_info, general_boss_info, get_boss_data
from .kcr_logging import ops_log

if TYPE_CHECKING:
    from hoshino.typing import CQEvent, HoshinoBot

# 私聊：刷新会战元数据 / 刷新会战 Boss 元数据（不指定单个 Boss）
REFRESH_BOSS_CMD_RE = re.compile(
    r"^\s*刷新会战(?:\s*Boss)?\s*元数据\s*$",
    re.IGNORECASE,
)


def fetch_boss_phases_sync(region: str = "cn") -> List[dict]:
    """同步拉取当期 phases 并写入 boss_info.json（预览脚本等复用）。"""
    today = datetime.date.today()
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"https://pcr.satroki.tech/api/Quest/GetClanBattleInfos?s={region}"
        )
        resp.raise_for_status()
        content = resp.json()
    phases = None
    for info in content:
        if info.get("year") == today.year and info.get("month") == today.month:
            phases = info["phases"]
            break
    if not phases:
        raise RuntimeError(f"未找到 {today.year}-{today.month:02d} 会战 Boss 数据")
    path = BossData.info_path.value
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(phases, ensure_ascii=False, indent=2), encoding="utf-8")
    ops_log().info(
        "Boss 元数据已写入本地 calendar={}-{:02d}",
        today.year,
        today.month,
    )
    return phases


def load_boss_online_from_phases(phases: List[dict]) -> BossOnlineData:
    return general_boss_info(phases)


async def refresh_clan_boss_metadata(source: str = "manual") -> Dict[str, Any]:
    """拉取 B 服当期全部 Boss 元数据并热加载到 clan_boss_info。"""
    if not BossData.use_online.value:
        ops_log().info("Boss 元数据刷新跳过（use_online=false） source={}", source)
        return {"ok": False, "reason": "use_online_disabled"}

    try:
        online = await get_boss_data("cn")
        clan_boss_info.load_online()
        phase_count = len(online.boss_value) if online else 0
    except Exception as e:
        ops_log().exception("Boss 元数据刷新失败 source={}", source)
        return {"ok": False, "reason": str(e)}

    names: List[str] = [b.name for b in clan_boss_info.boss_info]
    unit_ids: List[int] = [int(b.boss_id) for b in clan_boss_info.boss_info]
    today = datetime.date.today()
    info_mtime = ""
    if BossData.info_path.value.is_file():
        info_mtime = datetime.datetime.fromtimestamp(
            BossData.info_path.value.stat().st_mtime
        ).isoformat(sep=" ", timespec="seconds")

    summary = {
        "ok": True,
        "source": source,
        "calendar": f"{today.year}-{today.month:02d}",
        "boss_names": names,
        "unit_ids": unit_ids,
        "phase_count": phase_count,
        "file_mtime": info_mtime,
    }
    ops_log().info(
        "Boss 元数据已刷新（全部） source={} calendar={} phases={} bosses={}",
        source,
        summary["calendar"],
        phase_count,
        names,
    )
    return summary


def boss_metadata_status_text(summary: Dict[str, Any]) -> str:
    if not summary.get("ok"):
        return f"刷新失败：{summary.get('reason', '未知错误')}"
    names = summary.get("boss_names") or []
    line = "、".join(names) if names else "（无）"
    phases = summary.get("phase_count", 0)
    return (
        f"会战 Boss 元数据已更新（{summary.get('calendar', '')}，共 {phases} 个阶段）\n"
        f"当期五王：{line}\n"
        f"本地文件更新时间：{summary.get('file_mtime') or '未知'}"
    )


async def handle_refresh_boss_metadata_private(
    bot: "HoshinoBot", ev: "CQEvent", *, require_admin
) -> bool:
    """私聊刷新指令统一入口。返回是否已处理（匹配指令时为 True）。"""
    plain = ev.message.extract_plain_text().strip()
    if not REFRESH_BOSS_CMD_RE.match(plain):
        return False
    if not ev.is_private():
        await bot.send(ev, "请私聊机器人发送【刷新会战元数据】")
        return True
    if not require_admin(int(ev.user_id)):
        await bot.send(ev, "仅管理员及以上可用")
        return True
    summary = await refresh_clan_boss_metadata(source=f"qq_private:{ev.user_id}")
    await bot.send(ev, boss_metadata_status_text(summary))
    ops_log().info(
        "私聊刷新会战元数据 qq={} ok={}",
        ev.user_id,
        summary.get("ok"),
    )
    return True
