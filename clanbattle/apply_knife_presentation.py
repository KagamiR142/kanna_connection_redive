"""申请时刻刀型句与挑战队列（补偿）标记 — 单管道（设计文档 §5.3.4、阶段 L）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Mapping

from loguru import logger

KnifeKind = Literal["full", "comp", "infer_full", "infer_comp"]

_KIND_SUFFIX: Dict[KnifeKind, str] = {
    "comp": "此刀为补偿",
    "full": "此刀为整刀",
    "infer_comp": "此刀推断为补偿",
    "infer_full": "此刀推断为整刀",
}


@dataclass(frozen=True)
class ApplyKnifePresentation:
    kind: KnifeKind
    mark_comp_in_queue: bool

    @property
    def type_suffix(self) -> str:
        return _KIND_SUFFIX[self.kind]


def _comp_seconds_list(summary: Mapping[str, float]) -> list:
    raw = summary.get("comp_seconds_list")
    if raw:
        return [int(x) for x in raw if int(x) > 0]
    sec = int(summary.get("comp_seconds", 0) or 0)
    return [sec] if sec > 0 else []


def account_has_comp_resources(summary: Mapping[str, float]) -> bool:
    """账号是否仍有补偿刀额度或未消耗补偿秒数（与 `_account_has_comp` 同源）。"""
    return int(summary.get("comp", 0) or 0) > 0 or bool(
        _comp_seconds_list(summary)
    )


def infer_queue_knife_presentation(
    summary: Mapping[str, float],
    *,
    declared_comp: bool = False,
    log_context: str = "",
) -> ApplyKnifePresentation:
    """
    申请成功 / 状态图 / 查x 队列：有补偿资源时优先视为补偿（§5.3.4）。
    与报刀结算刀型（timeline / §4.2）分离。
    """
    full = int(summary.get("full", 0) or 0)
    comp = int(summary.get("comp", 0) or 0)
    comp_seconds_list = _comp_seconds_list(summary)
    comp_seconds = comp_seconds_list[0] if comp_seconds_list else 0

    if declared_comp:
        pres = ApplyKnifePresentation(kind="comp", mark_comp_in_queue=True)
    elif full <= 0 and (comp > 0 or comp_seconds_list):
        pres = ApplyKnifePresentation(kind="comp", mark_comp_in_queue=True)
    elif comp <= 0 and not comp_seconds_list:
        pres = ApplyKnifePresentation(kind="full", mark_comp_in_queue=False)
    elif comp_seconds > 0:
        pres = ApplyKnifePresentation(kind="infer_comp", mark_comp_in_queue=True)
    elif comp > 0 and full > 0:
        pres = ApplyKnifePresentation(kind="infer_comp", mark_comp_in_queue=True)
    else:
        pres = ApplyKnifePresentation(kind="infer_full", mark_comp_in_queue=False)

    logger.debug(
        "queue_knife_presentation{}: declared_comp={} full={} comp={} comp_seconds={} -> kind={} mark_comp={}",
        f" {log_context}" if log_context else "",
        declared_comp,
        full,
        comp,
        comp_seconds,
        pres.kind,
        pres.mark_comp_in_queue,
    )
    return pres


def infer_apply_knife_presentation(
    summary: Mapping[str, float],
    *,
    declared_comp: bool = False,
    log_context: str = "",
) -> ApplyKnifePresentation:
    """兼容别名：队列/申请展示请用 `infer_queue_knife_presentation`。"""
    return infer_queue_knife_presentation(
        summary, declared_comp=declared_comp, log_context=log_context
    )
