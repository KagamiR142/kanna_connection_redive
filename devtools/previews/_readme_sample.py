"""README / docs/assets 示例图统一样例数据。

队列标签：单账号=群昵称；多账号=昵称-该用户内编号-游戏名（编号非全局）。
"""
from __future__ import annotations

import random
from typing import List

from kanna_connection_redive.status_dto import CompensationEntry, QueueActor

# 满血：13.2e … 14.8e（1e = 1 亿 HP）
README_MAX_HP_E = (13.2, 13.6, 14.0, 14.4, 14.8)
README_MAX_HP = tuple(int(round(x * 1e8)) for x in README_MAX_HP_E)

# 各 Boss 展示周目（30～31）
README_LAP = (30, 30, 30, 31, 29)

# 当前血量比例（3 王约 5.6e/14.0e）
README_HP_RATIO = (0.62, 0.45, 0.40, 0.25, 0.10)

README_ASSET_DIR_NAME = "readme"

COMP_SECONDS_POOL = (21, 50, 90)

# 固定种子：每次生成 README 图时留言 e 与补偿秒随机但可复现
_README_RNG = random.Random(20261006)


def _rand_hp_e_text() -> str:
    value = _README_RNG.randint(31, 39) / 10.0
    return f"{value:.1f}e"


def _rand_comp_seconds() -> int:
    return int(_README_RNG.choice(COMP_SECONDS_POOL))


def _msg_manbu() -> str:
    return f"满补{_rand_hp_e_text()}"


def _msg_zhengdao_hedao() -> str:
    return f"整刀{_rand_hp_e_text()}合刀可喊"


def _msg_comp_note() -> str:
    sec = _rand_comp_seconds()
    return f"{sec}s补偿三千万"


def readme_lap(boss_order: int) -> int:
    return README_LAP[boss_order - 1]


def readme_max_hp(boss_order: int) -> int:
    return README_MAX_HP[boss_order - 1]


def readme_current_hp(boss_order: int) -> int:
    return max(1, int(readme_max_hp(boss_order) * README_HP_RATIO[boss_order - 1]))


def readme_max_lap() -> int:
    return max(README_LAP)


def readme_damage_hp(e_value: float) -> int:
    """刀伤示例：3.xe（≤3.9e）→ 整数 HP。"""
    v = min(3.9, max(0.1, float(e_value)))
    return int(round(v * 1e8))


def sample_compensation_entries() -> list[CompensationEntry]:
    s1 = _rand_comp_seconds()
    s2 = _rand_comp_seconds()
    s3 = _rand_comp_seconds()
    return [
        CompensationEntry(
            label="用户C-2-账号4",
            comp_knives=1,
            comp_seconds=s1,
            boss_order=3,
        ),
        CompensationEntry(
            label="用户D",
            comp_knives=2,
            comp_seconds=s2,
            boss_order=3,
            extra_comp=[(4, s3)],
        ),
    ]


def sample_subscribe(boss_order: int) -> List[QueueActor]:
    if boss_order == 1:
        return [QueueActor(label="用户A", message=_msg_manbu())]
    if boss_order == 3:
        return [
            QueueActor(label="用户A", message=_msg_manbu()),
            QueueActor(label="用户B", message=_msg_zhengdao_hedao()),
        ]
    return []


def sample_challenge(boss_order: int) -> List[QueueActor]:
    if boss_order == 3:
        return [
            QueueActor(label="未知玩家1", is_unknown=True),
            QueueActor(
                label="用户A",
                message=_msg_zhengdao_hedao(),
            ),
            QueueActor(label="用户B"),
            QueueActor(label="用户C-1-账号3", full_row=True),
            QueueActor(
                label="用户D",
                is_comp=True,
                comp_seconds=_rand_comp_seconds(),
            ),
            QueueActor(
                label="用户C-2-账号4",
                is_comp=True,
                comp_seconds=_rand_comp_seconds(),
                full_row=True,
            ),
        ]
    if boss_order == 1:
        return [
            QueueActor(
                label="用户D",
                is_comp=True,
                comp_seconds=_rand_comp_seconds(),
            ),
        ]
    if boss_order == 2:
        return [
            QueueActor(
                label="用户A",
                is_comp=True,
                comp_seconds=_rand_comp_seconds(),
            ),
        ]
    return []
