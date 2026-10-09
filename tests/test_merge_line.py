"""合刀线格式与会战阶段。"""
from __future__ import annotations

from tests._module_loader import load_module

_hp = load_module("clanbattle/merge_line/hp_format.py", "kcr_hp_e")
_phase = load_module("util/clan_phase.py", "kcr_clan_phase")
_constants = load_module("clanbattle/merge_line/constants.py", "kcr_ml_const")

format_hp_e = _hp.format_hp_e
lap_to_clan_phase = _phase.lap_to_clan_phase
is_d_phase = _phase.is_d_phase


def test_format_hp_e() -> None:
    assert format_hp_e(550_000_000) == "5.5e"
    assert format_hp_e(50_000_000) == "0.5e"
    assert format_hp_e(5_000_000_000) == "50.0e"


def test_lap_to_clan_phase() -> None:
    assert lap_to_clan_phase(6) == "B"
    assert lap_to_clan_phase(7) == "C"
    assert lap_to_clan_phase(22) == "C"
    assert lap_to_clan_phase(23) == "D"
    assert is_d_phase(23)
    assert not is_d_phase(22)


def test_compute_threshold() -> None:
    import statistics

    damages = [3_000_000_000] * 20
    med = statistics.median(damages)
    mean = statistics.mean(damages)
    t = int(round(((med + mean) / 2.0) * 1.7))
    assert t == int(3_000_000_000 * 1.7)
