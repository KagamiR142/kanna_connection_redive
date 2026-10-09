"""生成「查1」～「查5」单 Boss 预览 PNG。"""
from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from devtools.paths import MODULE_ROOT
from devtools.previews._boss_meta import fetch_boss_phases, load_boss_tables
from devtools.previews._common import output_dir, save_png
from devtools.previews._readme_sample import (
    README_ASSET_DIR_NAME,
    readme_current_hp,
    readme_lap,
    readme_max_hp,
    readme_max_lap,
    sample_challenge,
    sample_subscribe,
)
from kanna_connection_redive.util.boss_assets import ensure_boss_icon
from kanna_connection_redive.status_dto import BossStatusDTO
from kanna_connection_redive.status_image import render_boss_query_image


def _build_boss(order: int, boss_info) -> BossStatusDTO:
    meta = boss_info[order - 1]
    unit_id = int(meta.boss_id)
    lap = readme_lap(order)
    return BossStatusDTO(
        order=order,
        name=meta.name,
        unit_id=unit_id,
        lap=lap,
        current_hp=readme_current_hp(order),
        max_hp=readme_max_hp(order),
        is_behind=lap < readme_max_lap(),
        subscribe=sample_subscribe(order),
        challenge=sample_challenge(order) if order == 3 else [],
    )


def _readme_asset_path(name: str) -> Path:
    return MODULE_ROOT / "docs" / "assets" / README_ASSET_DIR_NAME / name


async def main() -> None:
    phases = fetch_boss_phases()
    boss_info, _, _ = load_boss_tables(phases)
    out = output_dir()
    for order in range(1, 6):
        await ensure_boss_icon(int(boss_info[order - 1].boss_id))
        boss = _build_boss(order, boss_info)
        path = out / f"boss_query_{order}.png"
        png = render_boss_query_image(boss)
        save_png(png, path)
        if order == 3:
            save_png(png, _readme_asset_path("boss_query.png"))
        logger.info("查{} 预览: {} ({})", order, path, boss.name)


if __name__ == "__main__":
    asyncio.run(main())
