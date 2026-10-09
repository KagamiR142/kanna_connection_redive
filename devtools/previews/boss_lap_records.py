"""生成「出刀记录」战报 PNG 预览。"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from devtools.bootstrap import bootstrap
from devtools.paths import MODULE_ROOT
from devtools.previews._common import output_dir
from devtools.previews._readme_sample import (
    README_ASSET_DIR_NAME,
    readme_current_hp,
    readme_damage_hp,
    readme_lap,
    readme_max_hp,
)

bootstrap()
KCR = MODULE_ROOT


def _load(dotted: str, file: Path):
    spec = importlib.util.spec_from_file_location(dotted, file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name: str, path: Path | None = None) -> None:
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    if path is not None:
        mod.__path__ = [str(path)]
    sys.modules[name] = mod


def _readme_asset_path(name: str) -> Path:
    return MODULE_ROOT / "docs" / "assets" / README_ASSET_DIR_NAME / name


def main() -> None:
    kcr = KCR
    _ensure_pkg("hoshino")
    _ensure_pkg("hoshino.modules")
    _ensure_pkg("hoshino.modules.kanna_connection_redive", kcr)
    _ensure_pkg("hoshino.modules.kanna_connection_redive.util", kcr / "util")
    _ensure_pkg("hoshino.modules.kanna_connection_redive.util.image", kcr / "util" / "image")
    _ensure_pkg("hoshino.modules.kanna_connection_redive.clanbattle", kcr / "clanbattle")
    _load("hoshino.modules.kanna_connection_redive.basedata", kcr / "basedata.py")
    _load(
        "hoshino.modules.kanna_connection_redive.clanbattle.boss_lap_report_dto",
        kcr / "clanbattle" / "boss_lap_report_dto.py",
    )
    _load(
        "hoshino.modules.kanna_connection_redive.clanbattle.report_image",
        kcr / "clanbattle" / "report_image.py",
    )
    _load(
        "hoshino.modules.kanna_connection_redive.clanbattle.boss_lap_report_image",
        kcr / "clanbattle" / "boss_lap_report_image.py",
    )
    from hoshino.modules.kanna_connection_redive.clanbattle.boss_lap_report_dto import (
        BossLapKnifeEntryDTO,
        BossLapRecordsReportDTO,
    )
    from hoshino.modules.kanna_connection_redive.clanbattle.boss_lap_report_image import (
        render_boss_lap_records_png,
    )

    boss = 3
    lap = readme_lap(boss)
    max_hp = readme_max_hp(boss)
    d1 = readme_damage_hp(3.6)
    d2 = readme_damage_hp(3.7)
    d3 = readme_damage_hp(3.7)
    d_kill = readme_damage_hp(3.0)
    hp_after_a = max(0, max_hp - d1)
    hp_after_c = max(0, hp_after_a - d2)
    hp_before_kill = max(0, hp_after_c - d3)
    dto = BossLapRecordsReportDTO(
        title=f"出刀记录 · {lap}周目{boss}王 · 20261006",
        subtitle=f"共 4 刀 · 初始血量 {max_hp} · 出现 14:08:10 · 存活 01:20:34",
        max_hp=max_hp,
        entries=[
            BossLapKnifeEntryDTO(
                actor_label="用户A",
                time_text="14:10:22",
                damage=d1,
                knife_type="整刀",
                hp_before=max_hp,
                hp_after=hp_after_a,
                hp_after_percent=f"({hp_after_a / max_hp * 100:.2f}%)",
            ),
            BossLapKnifeEntryDTO(
                actor_label="用户C-1-账号3",
                time_text="15:02:18",
                damage=d2,
                knife_type="补偿",
                hp_before=hp_after_a,
                hp_after=hp_after_c,
                hp_after_percent=f"({hp_after_c / max_hp * 100:.2f}%)",
            ),
            BossLapKnifeEntryDTO(
                actor_label="用户D",
                time_text="15:18:05",
                damage=d3,
                knife_type="整刀",
                hp_before=hp_after_c,
                hp_after=hp_before_kill,
                hp_after_percent=f"({hp_before_kill / max_hp * 100:.2f}%)",
            ),
            BossLapKnifeEntryDTO(
                actor_label="用户D",
                time_text="15:28:44",
                damage=d_kill,
                knife_type="击杀(21s)",
                hp_before=hp_before_kill,
                hp_after=0,
                hp_after_percent="(0.00%)",
            ),
        ],
    )
    png = render_boss_lap_records_png(dto)
    out = output_dir() / "boss_lap_records_sample.png"
    out.write_bytes(png)
    readme = _readme_asset_path("boss_lap_records.png")
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_bytes(png)
    print("wrote", out)
    print("wrote", readme)


if __name__ == "__main__":
    main()
