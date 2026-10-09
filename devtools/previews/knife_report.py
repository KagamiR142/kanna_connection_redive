"""生成名下战报 PNG 样例。"""
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


def _load(dotted: str, file: Path):
    spec = importlib.util.spec_from_file_location(dotted, file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = mod
    spec.loader.exec_module(mod)
    return mod


def _user_dto_to_report_lines(dto) -> list:
    from hoshino.modules.kanna_connection_redive.clanbattle.report_image import ReportLine

    lines: list = []
    for sec in dto.sections:
        heading = getattr(sec, "heading", None) or f"{sec.slot}-{sec.game_name}："
        lines.append(ReportLine(kind="heading", text=heading))
        if sec.empty_text:
            lines.append(ReportLine(kind="body", text=f"  {sec.empty_text}"))
        else:
            for raw in sec.lines:
                lines.append(ReportLine(kind="body", text=raw))
            if sec.pending_comp:
                parts = [f"{boss}-{sec}s" for boss, sec in sec.pending_comp.entries]
                lines.append(
                    ReportLine(kind="body", text=f"  ▸ 未出补偿：{'，'.join(parts)}")
                )
    return lines


def main() -> None:
    _ensure_pkg("hoshino")
    _ensure_pkg("hoshino.modules")
    _ensure_pkg("hoshino.modules.kanna_connection_redive", KCR)
    _ensure_pkg("hoshino.modules.kanna_connection_redive.clanbattle", KCR / "clanbattle")
    _load("hoshino.modules.kanna_connection_redive.basedata", KCR / "basedata.py")
    _load(
        "hoshino.modules.kanna_connection_redive.clanbattle.knife_report_dto",
        KCR / "clanbattle" / "knife_report_dto.py",
    )
    _load(
        "hoshino.modules.kanna_connection_redive.clanbattle.report_image",
        KCR / "clanbattle" / "report_image.py",
    )
    from hoshino.modules.kanna_connection_redive.clanbattle.knife_report_dto import (
        AccountKnifeSectionDTO,
        PendingCompDTO,
        UserKnifeReportDTO,
    )
    from hoshino.modules.kanna_connection_redive.clanbattle.report_image import (
        render_report_png,
    )

    user = UserKnifeReportDTO(
        title="今日战报 · 用户C · 10-06",
        subtitle="",
        sections=[
            AccountKnifeSectionDTO(
                slot=1,
                game_name="账号3",
                heading="1-账号3：",
                lines=[
                    "  14:32:05  30-3  360000000  整刀",
                    "  16:01:22  30-3  370000000  击杀(50s)",
                ],
                pending_comp=PendingCompDTO(entries=[(2, 21)]),
            ),
            AccountKnifeSectionDTO(
                slot=2,
                game_name="账号4",
                heading="2-账号4：",
                lines=[
                    "  11:20:10  30-3  3000000  补偿",
                ],
                pending_comp=PendingCompDTO(entries=[(2, 50)]),
            ),
        ],
    )
    png = render_report_png(user.title, _user_dto_to_report_lines(user))
    out = output_dir() / "knife_report_user_sample.png"
    out.write_bytes(png)
    readme = (
        MODULE_ROOT / "docs" / "assets" / README_ASSET_DIR_NAME / "today_knife_report.png"
    )
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_bytes(png)
    print("wrote", out)
    print("wrote", readme)


if __name__ == "__main__":
    main()
