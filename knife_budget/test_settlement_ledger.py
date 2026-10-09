"""settlement_ledger top 同步与扣血链（`python test_settlement_ledger.py`）。"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

try:
    from .settlement_ledger import (
        ZERO_CONFIRM_POLLS,
        BossInstanceKey,
        SettlementLedger,
    )
    from .comp_seconds import calc_comp_seconds
except ImportError:
    from settlement_ledger import (
        ZERO_CONFIRM_POLLS,
        BossInstanceKey,
        SettlementLedger,
    )
    from comp_seconds import calc_comp_seconds


def _boss(lap: int, order: int, hp: int, max_hp: int = 1_480_000_000) -> SimpleNamespace:
    return SimpleNamespace(
        lap_num=lap,
        order=order,
        current_hp=hp,
        max_hp=max_hp,
    )


class SettlementLedgerSyncTests(unittest.TestCase):
    def test_sync_from_top_sets_remaining(self) -> None:
        ledger = SettlementLedger(1)
        bosses = [_boss(29, 5, 290_700_000)]
        ledger.sync_from_top(bosses)
        key = BossInstanceKey(29, 5)
        self.assertEqual(ledger._remaining[key], 290_700_000)

    def test_sync_same_hp_no_op(self) -> None:
        ledger = SettlementLedger(1)
        key = BossInstanceKey(29, 5)
        ledger._remaining[key] = 100
        bosses = [_boss(29, 5, 100)]
        ledger.sync_from_top(bosses)
        self.assertEqual(ledger._remaining[key], 100)

    def test_double_confirm_zero(self) -> None:
        ledger = SettlementLedger(1)
        key = BossInstanceKey(29, 5)
        ledger._remaining[key] = 50_000_000
        bosses = [_boss(29, 5, 0)]
        for _ in range(ZERO_CONFIRM_POLLS - 1):
            ledger.sync_from_top(bosses)
            self.assertEqual(ledger._remaining[key], 50_000_000)
        ledger.sync_from_top(bosses)
        self.assertEqual(ledger._remaining[key], 0)

    def test_freeze_skips_zero_confirm(self) -> None:
        ledger = SettlementLedger(1)
        key = BossInstanceKey(29, 5)
        ledger._remaining[key] = 50_000_000
        bosses = [_boss(29, 5, 0)]
        for _ in range(ZERO_CONFIRM_POLLS + 2):
            ledger.sync_from_top(bosses, freeze_zero_orders={5})
        self.assertEqual(ledger._remaining[key], 50_000_000)

    def test_drop_stale_keeps_instance_when_hp_zero(self) -> None:
        ledger = SettlementLedger(1)
        key = BossInstanceKey(29, 5)
        ledger._remaining[key] = 290_700_000
        bosses = [_boss(29, 5, 0)]
        ledger.drop_stale_laps(bosses)
        self.assertIn(key, ledger._remaining)

    def test_apply_damage_after_sync(self) -> None:
        ledger = SettlementLedger(1)
        bosses = [_boss(29, 5, 609_716_612)]
        ledger.sync_from_top(bosses)
        ledger.apply_damage(29, 5, 319_016_612, is_kill=False)
        self.assertEqual(ledger._remaining[BossInstanceKey(29, 5)], 290_700_000)

    def test_kill_comp_after_chain(self) -> None:
        r = 290_700_000
        d = 311_884_638
        sec = calc_comp_seconds(r, d)
        self.assertEqual(sec, 27)

    def test_reconcile_kill_uses_memory_when_top_dead(self) -> None:
        async def _run() -> None:
            ledger = SettlementLedger(1)
            key = BossInstanceKey(29, 5)
            ledger._remaining[key] = 290_700_000
            bosses = [_boss(29, 5, 0)]
            r = await ledger._reconcile_kill_remaining(
                key,
                bosses,
                290_700_000,
                damage=311_884_638,
                before_create_time=0,
                r_mem=290_700_000,
            )
            self.assertEqual(r, 290_700_000)

        asyncio.run(_run())

    def test_mark_stale_records_stale_mark_not_peak(self) -> None:
        ledger = SettlementLedger(1)
        key = BossInstanceKey(32, 3)
        ledger._remaining[key] = 66_704_194
        ledger.sync_from_top([_boss(32, 3, 749_664_146)])
        ledger._remaining[key] = 66_704_194
        bosses = [_boss(33, 3, 1_400_000_000)]
        ledger.mark_stale_laps(bosses)
        self.assertEqual(ledger._stale_lap_r[key], 66_704_194)
        self.assertIn(key, ledger._remaining)

    def test_reconcile_cross_lap_uses_mem_not_historical_peak(self) -> None:
        async def _run() -> None:
            ledger = SettlementLedger(1)
            key = BossInstanceKey(32, 3)
            ledger._remaining[key] = 66_704_194
            ledger._stale_lap_r[key] = 66_704_194
            ledger._pending_drop[key] = 0
            bosses = [_boss(33, 3, 0)]
            r = await ledger._reconcile_kill_remaining(
                key,
                bosses,
                0,
                damage=295_718_651,
                before_create_time=0,
                r_mem=66_704_194,
                stale_mark=66_704_194,
            )
            self.assertEqual(r, 66_704_194)
            sec = calc_comp_seconds(r, 295_718_651)
            self.assertGreater(sec, 0)
            self.assertLessEqual(sec, 90)

        asyncio.run(_run())

    def test_reconcile_cross_lap_zero_mem_uses_replay_not_peak(self) -> None:
        async def _run() -> None:
            ledger = SettlementLedger(1)
            key = BossInstanceKey(32, 2)
            ledger._remaining[key] = 0
            ledger._stale_lap_r[key] = 0
            ledger._pending_drop[key] = 0
            bosses = [_boss(33, 2, 0)]
            r = await ledger._reconcile_kill_remaining(
                key,
                bosses,
                0,
                damage=316_550_774,
                before_create_time=0,
                r_mem=0,
                stale_mark=0,
            )
            self.assertEqual(r, 0)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
