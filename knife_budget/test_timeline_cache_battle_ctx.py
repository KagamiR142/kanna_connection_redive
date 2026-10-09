import asyncio

from hoshino.modules.kanna_connection_redive.knife_budget.classifier import TimelineInfo
from hoshino.modules.kanna_connection_redive.knife_budget.timeline_cache import (
    get_timeline_by_battle_context,
    put_timeline_battle_context,
    resolve_timeline_for_settlement,
)


async def _noop_fetch(_vid: int, _lid: int):
    return None


def test_battle_context_resolves_different_log_id():
    gid, vid = 1, 2
    tl = TimelineInfo(battle_time=87, start_remain_time=90)
    put_timeline_battle_context(gid, vid, 33, 3, 1_700_000_000, 38885, tl)
    got = get_timeline_by_battle_context(
        gid, vid, 33, 3, 1_700_000_000 + 5
    )
    assert got is not None
    assert got.battle_time == 87

    resolved = asyncio.run(
        resolve_timeline_for_settlement(
            gid,
            vid,
            591331,
            _noop_fetch,
            lap=33,
            boss_order=3,
            settlement_time=1_700_000_000 + 5,
        )
    )
    assert resolved is not None
    assert resolved.battle_time == 87


def test_settlement_cleanup_no_merge_fallback():
    from hoshino.modules.kanna_connection_redive.database.models import KnifeBudget
    from hoshino.modules.kanna_connection_redive.knife_budget.kill_comp import (
        KillCompKind,
    )
    from hoshino.modules.kanna_connection_redive.knife_budget.settlement import (
        _assign_kill_comp_seconds,
    )

    budget = KnifeBudget(viewer_id=1, pcr_date="2026-01-01")
    r = d = 315386813
    _assign_kill_comp_seconds(
        budget,
        kill_comp_seconds=None,
        hp_before=r,
        damage=d,
        boss_order=3,
        viewer_id=1,
        kill_comp_kind=KillCompKind.CLEANUP,
    )
    assert int(budget.comp_seconds or 0) == 0
