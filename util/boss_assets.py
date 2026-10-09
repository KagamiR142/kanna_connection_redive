from pathlib import Path

import httpx
from loguru import logger

from ..basedata import FilePath

BOSS_ICON_DIR = FilePath.img.value / "boss_icon"
BOSS_ICON_PRIMARY = "https://redive.estertion.win/icon/unit/{unit_id}.webp"
BOSS_ICON_FALLBACK = "https://wthee.xyz/redive/jp/resource/icon/unit/{unit_id}.webp"


def boss_icon_path(unit_id: int) -> Path:
    return BOSS_ICON_DIR / f"{unit_id}.webp"


def boss_icon_cdn_urls(unit_id: int) -> tuple[str, str]:
    """Web 与状态图共用的 CDN 顺序：estertion 优先，wthee 备用。"""
    return (
        BOSS_ICON_PRIMARY.format(unit_id=unit_id),
        BOSS_ICON_FALLBACK.format(unit_id=unit_id),
    )


async def ensure_boss_icon(unit_id: int) -> Path:
    """下载 Boss 头像到本地缓存（PIL 状态图使用）；顺序与 Web 一致。"""
    BOSS_ICON_DIR.mkdir(parents=True, exist_ok=True)
    path = boss_icon_path(unit_id)
    if path.is_file() and path.stat().st_size > 0:
        return path
    for url in boss_icon_cdn_urls(unit_id):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.content:
                    path.write_bytes(resp.content)
                    logger.debug("Boss 头像已缓存 unit_id={} url={}", unit_id, url)
                    return path
        except Exception as e:
            logger.warning("Boss 头像下载失败 unit_id={} url={} err={}", unit_id, url, e)
    return path
