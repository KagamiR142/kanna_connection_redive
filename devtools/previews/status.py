"""生成会战状态图示例 PNG（Boss 名称/头像在线拉取，无需游戏账号）。

用法（模块根目录）:
    python -m devtools.previews.status
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from devtools.paths import MODULE_ROOT
from devtools.previews._boss_meta import lap2stage, fetch_boss_phases, load_boss_tables
from devtools.previews._common import output_dir, save_png
from devtools.previews._readme_sample import (
    README_ASSET_DIR_NAME,
    readme_current_hp,
    readme_lap,
    readme_max_hp,
    readme_max_lap,
    sample_challenge,
    sample_compensation_entries,
    sample_subscribe,
)
from kanna_connection_redive.util.boss_assets import ensure_boss_icon
from kanna_connection_redive.status_dto import BossStatusDTO, ClanStatusDTO, StatusSummaryDTO
from kanna_connection_redive.status_image import render_status_image


async def build_sample_status() -> ClanStatusDTO:
    phases = fetch_boss_phases()
    boss_info, _boss_value, stages = load_boss_tables(phases)
    max_lap = readme_max_lap()
    bosses: list[BossStatusDTO] = []

    for order in range(1, 6):
        meta = boss_info[order - 1]
        unit_id = int(meta.boss_id)
        await ensure_boss_icon(unit_id)
        lap = readme_lap(order)
        bosses.append(
            BossStatusDTO(
                order=order,
                name=meta.name,
                unit_id=unit_id,
                lap=lap,
                current_hp=readme_current_hp(order),
                max_hp=readme_max_hp(order),
                is_behind=lap < max_lap,
                subscribe=sample_subscribe(order),
                challenge=sample_challenge(order),
            )
        )

    ref_lap = readme_lap(3)
    return ClanStatusDTO(
        summary=StatusSummaryDTO(
            full_knives=11,
            comp_knives=6,
            phase=str(lap2stage(ref_lap, stages)),
            guild_rank=128,
            compensation=sample_compensation_entries(),
        ),
        bosses=bosses,
    )


def _readme_asset_path(name: str) -> Path:
    return MODULE_ROOT / "docs" / "assets" / README_ASSET_DIR_NAME / name


async def main() -> None:
    out = output_dir()
    status = await build_sample_status()
    img = render_status_image(status)

    for filename in (
        "status_sample_comfort.png",
        "status_sample_compact.png",
        "status_sample.png",
    ):
        save_png(img, out / filename)

    save_png(img, _readme_asset_path("status.png"))

    logger.info("状态示例: {} + docs/assets/readme/status.png", out)
    for b in status.bosses:
        logger.info("  {} {} lap={}", b.order, b.name, b.lap)


if __name__ == "__main__":
    asyncio.run(main())
