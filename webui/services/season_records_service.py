"""个人当期出刀（按会战日 + 账号分组，复用 detail_reports DTO）。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from ...clanbattle.account_service import list_bound_accounts
from ...clanbattle.knife_report_builder import _group_records_by_pcrid
from ...clanbattle.detail_reports import record_to_web_row
from ...clanbattle.member_identity import dedupe_record_daos
from ...database.dal import pcr_date, pcr_sqla


async def build_season_records(group_id: int, user_id: int) -> List[Dict[str, Any]]:
    accounts = await list_bound_accounts(user_id, group_id=group_id)
    if not accounts:
        return []
    viewer_ids = [a.viewer_id for a in accounts]
    name_by_viewer = {a.viewer_id: a.name for a in accounts}
    slot_by_viewer = {a.viewer_id: a.slot for a in accounts}
    days = await pcr_sqla.get_season_day_timestamps(group_id)
    by_day_accounts: Dict[str, Dict[int, List[Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for day_ts in days:
        records = dedupe_record_daos(
            await pcr_sqla.get_day_records_for_pcrids(
                day_ts, group_id, viewer_ids
            )
        )
        if not records:
            continue
        day_key = pcr_date(day_ts).strftime("%Y-%m-%d")
        grouped = _group_records_by_pcrid(records)
        for vid in viewer_ids:
            for rec in grouped.get(vid, []):
                item = record_to_web_row(rec)
                item["game_name"] = name_by_viewer.get(vid, "")
                item["viewer_id"] = vid
                by_day_accounts[day_key][vid].append(item)
    sections: List[Dict[str, Any]] = []
    for day_key in sorted(by_day_accounts.keys(), reverse=True):
        mmdd = day_key[5:].replace("-", "-")
        account_blocks: List[Dict[str, Any]] = []
        for acc in accounts:
            vid = acc.viewer_id
            rows = sorted(
                by_day_accounts[day_key].get(vid, []),
                key=lambda x: x["time"],
                reverse=True,
            )
            if not rows:
                continue
            account_blocks.append(
                {
                    "slot": slot_by_viewer.get(vid, acc.slot),
                    "viewer_id": vid,
                    "name": name_by_viewer.get(vid, acc.name),
                    "records": rows,
                }
            )
        if not account_blocks:
            continue
        flat_records: List[Dict[str, Any]] = []
        for block in account_blocks:
            flat_records.extend(block["records"])
        sections.append(
            {
                "day": day_key,
                "day_label": f"【{mmdd}】",
                "accounts": account_blocks,
                "records": flat_records,
            }
        )
    return sections
