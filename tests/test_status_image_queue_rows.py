"""状态图队列行布局：多绑 full_row，单绑可 pair。"""
from __future__ import annotations

import sys

from tests._module_loader import PKG, load_module

_si = load_module("status_image.py", "kcr_status_image")
_build_queue_rows = _si._build_queue_rows
QueueActor = sys.modules[f"{PKG}.status_dto"].QueueActor


def test_multi_bind_actor_uses_full_row() -> None:
    rows = _build_queue_rows(
        [
            QueueActor(label="用户A-1-账号1", full_row=True),
            QueueActor(label="用户B", full_row=False),
            QueueActor(label="用户C", full_row=False),
        ]
    )
    kinds = [r.kind for r in rows]
    assert kinds[0] == "full"
    assert "pair" in kinds


def test_single_bind_actors_pair_when_no_full_row() -> None:
    rows = _build_queue_rows(
        [
            QueueActor(label="用户A", full_row=False),
            QueueActor(label="用户B", full_row=False),
        ]
    )
    assert len(rows) == 1
    assert rows[0].kind == "pair"


def test_queue_priority_tree_comp_full_half() -> None:
    rows = _build_queue_rows(
        [
            QueueActor(label="半行A", full_row=False),
            QueueActor(label="整行", full_row=True),
            QueueActor(label="补偿", is_comp=True, full_row=False),
            QueueActor(label="挂树", is_tree=True, full_row=False),
            QueueActor(label="半行B", full_row=False),
        ]
    )
    order: list[str] = []
    for row in rows:
        for actor in row.actors:
            order.append(actor.label)
    assert order.index("挂树") < order.index("补偿")
    assert order.index("补偿") < order.index("整行")
    assert order.index("整行") < order.index("半行A")
    assert order.index("整行") < order.index("半行B")
