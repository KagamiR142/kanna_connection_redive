"""申请刀型展示推断单元测试。"""
from __future__ import annotations

from tests._module_loader import load_module

_akp = load_module("clanbattle/apply_knife_presentation.py", "kcr_apply_knife_presentation")
infer_queue_knife_presentation = _akp.infer_queue_knife_presentation


def _s(full: int, comp: int, comp_seconds: int = 0) -> dict:
    return {"full": full, "comp": comp, "comp_seconds": comp_seconds}


def test_kill_then_apply_infer_comp() -> None:
    pres = infer_queue_knife_presentation(_s(2, 1, 90), declared_comp=False)
    assert pres.kind == "infer_comp"
    assert pres.mark_comp_in_queue
    assert "推断为补偿" in pres.type_suffix


def test_only_full() -> None:
    pres = infer_queue_knife_presentation(_s(2, 0, 0), declared_comp=False)
    assert pres.kind == "full"
    assert not pres.mark_comp_in_queue


def test_declared_comp() -> None:
    pres = infer_queue_knife_presentation(_s(2, 1, 90), declared_comp=True)
    assert pres.kind == "comp"
    assert pres.mark_comp_in_queue


def test_no_full_only_comp() -> None:
    pres = infer_queue_knife_presentation(_s(0, 1, 0), declared_comp=False)
    assert pres.kind == "comp"
    assert pres.mark_comp_in_queue


def test_dual_no_comp_seconds_infer_comp() -> None:
    pres = infer_queue_knife_presentation(_s(2, 1, 0), declared_comp=False)
    assert pres.kind == "infer_comp"
    assert pres.mark_comp_in_queue
