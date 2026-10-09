"""刀型句（蓝图 §5.3.4）。"""
from __future__ import annotations

from typing import Dict

from .apply_knife_presentation import KnifeKind, infer_queue_knife_presentation


def _prefix(summary: Dict[str, float]) -> str:
    full = int(summary.get("full", 0))
    comp = int(summary.get("comp", 0))
    text = f"今日剩余{full}整刀"
    if comp > 0:
        text += f"{comp}补偿"
    return text + "未出"


def build_knife_type_sentence(
    summary: Dict[str, float],
    *,
    declared_comp: bool = False,
    settled_kind: KnifeKind | None = None,
) -> str:
    prefix = _prefix(summary)
    if declared_comp:
        return f"{prefix}，此刀为补偿"
    if settled_kind == "comp":
        return f"{prefix}，此刀为补偿"
    if settled_kind == "full":
        return f"{prefix}，此刀为整刀"
    if settled_kind == "infer_comp":
        return f"{prefix}，此刀推断为补偿"
    if settled_kind == "infer_full":
        return f"{prefix}，此刀推断为整刀"

    pres = infer_queue_knife_presentation(
        summary, declared_comp=declared_comp, log_context="knife_type_sentence"
    )
    return f"{prefix}，{pres.type_suffix}"


def settled_kind_from_budget_change(
    before: Dict[str, float], after: Dict[str, float], *, is_kill: bool
) -> KnifeKind:
    if after.get("comp", 0) < before.get("comp", 0):
        return "comp"
    if after.get("full", 0) < before.get("full", 0):
        return "full"
    if is_kill:
        return "full"
    if before.get("full", 0) > 0 and before.get("comp", 0) > 0:
        return "infer_full"
    return "full"
