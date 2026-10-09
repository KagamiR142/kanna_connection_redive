"""生成今日/当期公会出刀次数统计 PNG 样例。"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from devtools.bootstrap import bootstrap
from devtools.paths import MODULE_ROOT
from devtools.paths import MODULE_ROOT
from devtools.previews._common import output_dir
from devtools.previews._readme_sample import README_ASSET_DIR_NAME

bootstrap()
KCR = MODULE_ROOT


def _ensure_pkg(name: str, path: Path | None = None) -> None:
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    if path is not None:
        mod.__path__ = [str(path)]
    sys.modules[name] = mod


def _load_module(qualname: str, path: Path):
    spec = importlib.util.spec_from_file_location(qualname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[qualname] = mod
    spec.loader.exec_module(mod)
    return mod


def _build_report_lines(dto, report_image) -> list:
    ReportLine = report_image.ReportLine

    def fmt_pts(v: float) -> str:
        r = round(float(v) * 2) / 2
        if abs(r - round(r)) < 0.01:
            return str(int(round(r)))
        return f"{r:.1f}".rstrip("0").rstrip(".")

    lines = []
    for day in dto.day_sections:
        lines.append(ReportLine(kind="sep"))
        lines.append(ReportLine(kind="accent", text=f"以下是{day.yymmdd}出刀次数统计："))
        lines.append(
            ReportLine(
                kind="body",
                text=(
                    f"总计出刀：{fmt_pts(day.total_used_points)}，"
                    f"其中整刀{day.full_knife_count}刀，补偿{day.comp_knife_count}刀"
                ),
            )
        )
        for key in sorted(
            day.buckets.keys(),
            key=lambda x: float(x) if x.replace(".", "").isdigit() else 0,
            reverse=True,
        ):
            members = day.buckets.get(key) or []
            if not members:
                continue
            lines.append(ReportLine(kind="sep"))
            lines.append(ReportLine(kind="accent", text=f"以下是出了{key}刀的成员："))
            lines.append(ReportLine(kind="pipes", items=tuple(members)))
        if day.pending_comp_parts:
            lines.append(ReportLine(kind="sep"))
            lines.append(ReportLine(kind="accent", text="未出的补偿刀："))
            lines.append(ReportLine(kind="pipes", items=tuple(day.pending_comp_parts)))
        lines.append(ReportLine(kind="sep"))
    return lines


def main() -> None:
    _ensure_pkg("hoshino")
    _ensure_pkg("hoshino.modules")
    _ensure_pkg("hoshino.modules.kanna_connection_redive", KCR)
    _ensure_pkg("hoshino.modules.kanna_connection_redive.util", KCR / "util")
    _ensure_pkg("hoshino.modules.kanna_connection_redive.util.image", KCR / "util" / "image")
    _ensure_pkg("hoshino.modules.kanna_connection_redive.clanbattle", KCR / "clanbattle")
    _load_module("hoshino.modules.kanna_connection_redive.basedata", KCR / "basedata.py")
    report_image = _load_module(
        "hoshino.modules.kanna_connection_redive.clanbattle.report_image",
        KCR / "clanbattle" / "report_image.py",
    )
    dto_mod = _load_module(
        "hoshino.modules.kanna_connection_redive.clanbattle.knife_report_dto",
        KCR / "clanbattle" / "knife_report_dto.py",
    )
    Day = dto_mod.GuildKnifeCountDayDTO
    Report = dto_mod.GuildKnifeCountReportDTO
    render = report_image.render_report_png

    today = Report(
        day_sections=[
            Day(
                yymmdd="261006",
                total_used_points=42.5,
                full_knife_count=38,
                comp_knife_count=9,
                buckets={
                    "3": ["用户A", "用户B", "用户C-1-账号3"],
                    "2.5": ["用户D"],
                    "0": ["用户E"],
                },
                pending_comp_parts=[
                    "用户C-2-账号4：2-21s",
                    "用户D：2-50s",
                ],
            )
        ]
    )
    season = Report(
        day_sections=[
            Day(
                yymmdd="261004",
                total_used_points=39.0,
                full_knife_count=35,
                comp_knife_count=8,
                buckets={"3": ["用户A", "用户C-1-账号3"], "0": ["用户E"]},
                pending_comp_parts=["用户D：2-50s"],
            ),
            Day(
                yymmdd="261006",
                total_used_points=42.5,
                full_knife_count=38,
                comp_knife_count=9,
                buckets={"3": ["用户A", "用户B"], "0": ["用户E"]},
                pending_comp_parts=["用户C-2-账号4：2-21s"],
            ),
        ]
    )

    out = output_dir()
    today_path = out / "guild_stats_today.png"
    season_path = out / "guild_stats_season.png"
    today_png = render("今日出刀 · 261006", _build_report_lines(today, report_image))
    today_path.write_bytes(today_png)
    season_path.write_bytes(
        render("当期出刀 · 261004-261006", _build_report_lines(season, report_image))
    )
    readme = (
        MODULE_ROOT
        / "docs"
        / "assets"
        / README_ASSET_DIR_NAME
        / "guild_today_knives.png"
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_bytes(today_png)
    print("wrote", today_path)
    print("wrote", season_path)
    print("wrote", readme)


if __name__ == "__main__":
    main()
