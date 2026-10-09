from typing import Optional
from sqlmodel import Field, SQLModel
import time

from sqlalchemy.orm import registry

# 防止多个sqlmodel冲突


class DataBase(SQLModel, registry=registry()):
    pass


class Account(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ")
    platform: int = Field(title="服务器编号")
    viewer_id: Optional[int] = Field(default=None, title="游戏ID")
    allow_others: Optional[int] = Field(default=0, title="允许他人触发")
    account: Optional[str] = Field(default=None, title="uid")
    password: Optional[str] = Field(default=None, title="access_key")
    name: Optional[str] = Field(default=None, title="游戏昵称")
    refresh: Optional[str] = Field(default=None, title="b站账号")
    monitor_slot: int = Field(default=1, title="监控槽位1～3")


class WebAccount(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    account: str = Field(primary_key=True, title="玩家账号")
    password: str = Field(title="密码")
    temp: Optional[bool] = Field(title="临时", default=False)
    priority: Optional[int] = Field(title="权限等级", default=0)
    create_time: Optional[int] = Field(title="创建时间", default=0)
    is_initial_password: bool = Field(default=True, title="是否仍为注册初始密码")


class RefreshAccount(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    account: str = Field(primary_key=True, title="b站账号")
    password: str = Field(title="b站密码")


class RecordDao(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    group_id: int = Field(title="所属群")
    battle_log_id: int = Field(title="出刀编号")
    lap: int = Field(title="周目")
    boss: int = Field(title="boss编号")
    time: int = Field(title="时间")
    pcrid: int = Field(title="玩家ID")
    damage: int = Field(title="伤害")
    name: str = Field(title="玩家昵称")
    remain_time: int = Field(title="战斗剩余时间")
    battle_time: int = Field(title="战斗时间")
    flag: float = Field(title="出刀类型")
    is_kill: int = Field(default=0, title="是否击杀")
    knife_state: int = Field(default=0, title="四态:0整刀1击杀2补偿3补偿击杀")
    knife_settled_at: int = Field(
        default=0, title="damage_history结算写四态时间戳，>0则battle_log不得覆盖"
    )
    kill_comp_seconds: int = Field(
        default=0, title="击杀获得的补偿秒数(战报展示)"
    )
    unit1: int = Field(title="出战角色1-ID")
    unit2: Optional[int] = Field(default=0, title="出战角色2-ID")
    unit3: Optional[int] = Field(default=0, title="出战角色3-ID")
    unit4: Optional[int] = Field(default=0, title="出战角色4-ID")
    unit5: Optional[int] = Field(default=0, title="出战角色5-ID")
    unit1_level: int = Field(title="出战角色1-等级")
    unit2_level: Optional[int] = Field(default=0, title="出战角色2-等级")
    unit3_level: Optional[int] = Field(default=0, title="出战角色3-等级")
    unit4_level: Optional[int] = Field(default=0, title="出战角色4-等级")
    unit5_level: Optional[int] = Field(default=0, title="出战角色5-等级")
    unit1_damage: int = Field(title="出战角色1-伤害")
    unit2_damage: Optional[int] = Field(default=0, title="出战角色2-伤害")
    unit3_damage: Optional[int] = Field(default=0, title="出战角色3-伤害")
    unit4_damage: Optional[int] = Field(default=0, title="出战角色4-伤害")
    unit5_damage: Optional[int] = Field(default=0, title="出战角色5-伤害")
    unit1_rarity: int = Field(title="出战角色1-星级")
    unit2_rarity: Optional[int] = Field(default=0, title="出战角色2-星级")
    unit3_rarity: Optional[int] = Field(default=0, title="出战角色3-星级")
    unit4_rarity: Optional[int] = Field(default=0, title="出战角色4-星级")
    unit5_rarity: Optional[int] = Field(default=0, title="出战角色5-星级")
    unit1_rank: int = Field(title="出战角色1-品级")
    unit2_rank: Optional[int] = Field(default=0, title="出战角色2-品级")
    unit3_rank: Optional[int] = Field(default=0, title="出战角色3-品级")
    unit4_rank: Optional[int] = Field(default=0, title="出战角色4-品级")
    unit5_rank: Optional[int] = Field(default=0, title="出战角色5-品级")
    unit1_unique_equip: int = Field(title="出战角色1-专武等级")
    unit2_unique_equip: Optional[int] = Field(default=0, title="出战角色2-专武等级")
    unit3_unique_equip: Optional[int] = Field(default=0, title="出战角色3-专武等级")
    unit4_unique_equip: Optional[int] = Field(default=0, title="出战角色4-专武等级")
    unit5_unique_equip: Optional[int] = Field(default=0, title="出战角色5-专武等级")

    @classmethod
    def from_settlement_stub(
        cls,
        *,
        group_id: int,
        battle_log_id: int,
        stub: dict,
        semantics: dict,
        settled_at: int,
    ) -> "RecordDao":
        """结算 INSERT 占位行（阵容由 add_record 补全；须满足 SQLite NOT NULL）。"""
        ts = int(stub.get("time") or settled_at)
        return cls(
            group_id=int(group_id),
            battle_log_id=int(battle_log_id),
            pcrid=int(stub["pcrid"]),
            name=str(stub.get("name") or ""),
            lap=int(stub.get("lap") or 0),
            boss=int(stub.get("boss") or 0),
            damage=int(stub.get("damage") or 0),
            time=ts,
            remain_time=0,
            battle_time=0,
            flag=float(semantics["flag"]),
            is_kill=int(semantics["is_kill"]),
            knife_state=int(semantics["knife_state"]),
            knife_settled_at=int(settled_at),
            kill_comp_seconds=int(semantics.get("kill_comp_seconds") or 0),
            unit1=0,
            unit2=0,
            unit3=0,
            unit4=0,
            unit5=0,
            unit1_level=0,
            unit2_level=0,
            unit3_level=0,
            unit4_level=0,
            unit5_level=0,
            unit1_damage=0,
            unit2_damage=0,
            unit3_damage=0,
            unit4_damage=0,
            unit5_damage=0,
            unit1_rarity=0,
            unit2_rarity=0,
            unit3_rarity=0,
            unit4_rarity=0,
            unit5_rarity=0,
            unit1_rank=0,
            unit2_rank=0,
            unit3_rank=0,
            unit4_rank=0,
            unit5_rank=0,
            unit1_unique_equip=0,
            unit2_unique_equip=0,
            unit3_unique_equip=0,
            unit4_unique_equip=0,
            unit5_unique_equip=0,
        )


class NoticeCache(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    group_id: int = Field(title="所属群")
    notice_type: int = Field(title="通知类型")
    user_id: int = Field(title="用户QQ")
    boss: int = Field(title="Boss编号")
    lap: Optional[int] = Field(default=0, title="周目")
    text: str = Field(title="留言")
    time: Optional[int] = Field(default=0, title="时间")
    viewer_id: Optional[int] = Field(default=None, title="游戏UID")
    account_id: Optional[int] = Field(default=None, title="账号表ID")


class SLDao(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    user_id: int = Field(primary_key=True, title="用户QQ")
    time: Optional[int] = Field(default=0, title="上次SL")


class SlViewerDao(DataBase, table=True):
    """按游戏账号记录 SL（蓝图：每账号每日 1 次）。"""

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    viewer_id: int = Field(primary_key=True, title="游戏UID")
    time: Optional[int] = Field(default=0, title="上次SL")


class ClanBattleKPI(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    pcrid: int = Field(primary_key=True, title="游戏ID")
    bouns: int = Field(title="补正")
    time: Optional[int] = Field(default=0, title="创建时间")


class PlayerUnit(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ")
    pcrid: int = Field(title="玩家ID")
    unit_id: int = Field(title="角色ID")
    name: str = Field(title="玩家昵称")
    rarity: int = Field(title="星级")
    battle_rarity: Optional[int] = Field(default=0, title="战斗星级")
    unique_level: Optional[int] = Field(default=0, title="专武等级")
    unique_level2: Optional[int] = Field(default=0, title="专武等级2")
    love_level: int = Field(title="好感等级")
    level: int = Field(title="等级")
    rank: int = Field(title="品级")
    main_1: Optional[int] = Field(default=0, title="1技能")
    main_2: Optional[int] = Field(default=0, title="2技能")
    ex: Optional[int] = Field(default=0, title="ex技能")
    union_burst: Optional[int] = Field(default=0, title="连结爆发")
    equip_1: str = Field(title="左上")
    equip_2: str = Field(title="右上")
    equip_3: str = Field(title="左中")
    equip_4: str = Field(title="右中")
    equip_5: str = Field(title="左下")
    equip_6: str = Field(title="右下")
    support_position: Optional[int] = Field(
        default=0, title="支援位置"
    )  # 1, 2 好友支援， 3-6 工会战地下城支援
    cb_ex_equip_1: Optional[int] = Field(default=0, title="会战ex装备1")
    cb_ex_equip_2: Optional[int] = Field(default=0, title="会战ex装备2")
    cb_ex_equip_3: Optional[int] = Field(default=0, title="会战ex装备3")
    cb_ex_equip_1_level: Optional[int] = Field(default=0, title="会战ex装备1等级")
    cb_ex_equip_2_level: Optional[int] = Field(default=0, title="会战ex装备2等级")
    cb_ex_equip_3_level: Optional[int] = Field(default=0, title="会战ex装备3等级")


class SupportUnit(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    group_id: int = Field(title="所属群")
    pcrid: int = Field(title="玩家ID")
    unit_id: int = Field(title="角色ID")
    name: str = Field(title="玩家昵称")
    rarity: int = Field(title="星级")
    battle_rarity: Optional[int] = Field(default=0, title="战斗星级")
    unique_level: Optional[int] = Field(default=0, title="专武等级")
    unique_level2: Optional[int] = Field(default=0, title="专武等级2")
    special_attribute: Optional[str] = Field(default="", title="好感加成")
    level: int = Field(title="等级")
    rank: int = Field(title="品级")
    main_1: Optional[int] = Field(default=0, title="1技能")
    main_2: Optional[int] = Field(default=0, title="2技能")
    ex: Optional[int] = Field(default=0, title="ex技能")
    union_burst: Optional[int] = Field(default=0, title="连结爆发")
    equip_1: str = Field(title="左上")
    equip_2: str = Field(title="右上")
    equip_3: str = Field(title="左中")
    equip_4: str = Field(title="右中")
    equip_5: str = Field(title="左下")
    equip_6: str = Field(title="右下")
    cb_ex_equip_1: Optional[int] = Field(default=0, title="会战ex装备1")
    cb_ex_equip_2: Optional[int] = Field(default=0, title="会战ex装备2")
    cb_ex_equip_3: Optional[int] = Field(default=0, title="会战ex装备3")
    cb_ex_equip_1_level: Optional[int] = Field(default=0, title="会战ex装备1等级")
    cb_ex_equip_2_level: Optional[int] = Field(default=0, title="会战ex装备2等级")
    cb_ex_equip_3_level: Optional[int] = Field(default=0, title="会战ex装备3等级")


class ClanBattleMember(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    user_id: int = Field(primary_key=True, title="玩家QQ")
    group_name: str = Field(title="群名称", default="环奈连结")
    priority: Optional[int] = Field(title="权限等级", default=0)


class BlackUnit(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ")
    black_id: str = Field(title="黑名单id")
    black_type: int = Field(title="黑名单类型")


class ArenaSetting(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    user_id: int = Field(primary_key=True, title="玩家QQ")
    jjc_notice: bool = Field(default=True, title="竞技场提醒")
    grand_notice: bool = Field(default=True, title="公主竞技场提醒")


class GrandDefenceCache(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    pcrid: int = Field(primary_key=True, title="玩家ID")
    grand_id: int = Field(title="场次")
    defence: str = Field(title="防守队伍id")
    row: int = Field(primary_key=True, title="防守位置")
    user_id: int = Field(primary_key=True, title="玩家QQ")
    vs_time: int = Field(default=0, title="更新时间")


class CookieCache(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    token: str = Field(primary_key=True, title="token")
    user_id: str = Field(title="user_id")
    time: int = Field(default=int(time.time()), title="时间")


class KcrDelegatedAdmin(DataBase, table=True):
    """会战委派管理员（最多 5 人，仅超级管理员可任命）。超级管理员仅 setting_clanbattle.admin_qq。"""

    __table_args__ = {"keep_existing": True}
    qq_id: int = Field(primary_key=True, title="管理员QQ")
    appointed_at: int = Field(default=0, title="任命时间")
    appointed_by: int = Field(default=0, title="任命人QQ")


class UserAccount(DataBase, table=True):
    """QQ 用户与游戏账号的多对多绑定（含优先级）。"""

    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ", index=True)
    account_id: int = Field(title="账号表ID", index=True)
    viewer_id: int = Field(title="游戏UID", index=True)
    alias: str = Field(default="", title="账号别名")
    sort_order: int = Field(default=0, title="默认优先级")
    is_active: bool = Field(default=True, title="是否启用")


class ChallengeState(DataBase, table=True):
    """每群每 Boss 的挑战进入信号（设计文档第三章）。"""

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    boss: int = Field(primary_key=True, title="Boss编号")
    enter_signal: int = Field(default=0, title="进入信号计数")
    unknown_labels: str = Field(default="[]", title="未知玩家标签JSON")
    last_fighter_num: int = Field(default=0, title="上次API挑战人数")
    updated_at: int = Field(default=0, title="更新时间")


class KnifeBudget(DataBase, table=True):
    """每账号每日出刀点数状态（设计文档第四章）。"""

    __table_args__ = {"keep_existing": True}
    viewer_id: int = Field(primary_key=True, title="游戏UID")
    pcr_date: str = Field(primary_key=True, title="PCR日期")
    used_full: int = Field(default=0, title="已用整刀数")
    avail_comp: int = Field(default=0, title="可用补偿数")
    used_points: float = Field(default=0.0, title="已消耗点数")
    comp_seconds: int = Field(default=0, title="当前补偿剩余秒数(首条镜像)")
    comp_boss: int = Field(default=0, title="补偿对应Boss序号(首条镜像)")
    comp_pool: str = Field(default="[]", title="未出补偿池JSON[{seconds,boss}]")
    updated_at: int = Field(default=0, title="更新时间")


class ClanMergeLineSettings(DataBase, table=True):
    """群级合刀线提醒开关与会战锚点。"""

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="群号")
    reminder_enabled: bool = Field(default=True, title="合刀线提醒开关")
    season_anchor: int = Field(default=0, title="当期会战首日5点时间戳")


class ClanMergeLineBoss(DataBase, table=True):
    """每群每王合刀线阈值。"""

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="群号")
    boss: int = Field(primary_key=True, title="Boss 1-5")
    threshold: int = Field(default=5_000_000_000, title="合刀线HP")
    frozen: bool = Field(default=False, title="是否已锁定20刀样本")
    computed_at: int = Field(default=0, title="计算时间")


class ClanMergeLinePendingSample(DataBase, table=True):
    """未满20刀时的待采样本。"""

    __table_args__ = {"keep_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(index=True, title="群号")
    boss: int = Field(index=True, title="Boss")
    damage: int = Field(title="伤害")
    battle_log_id: int = Field(default=0, title="log_id")
    record_time: int = Field(default=0, title="记录时间")


class ClanMergeLineFrozenSample(DataBase, table=True):
    """锁定后的20刀样本。"""

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="群号")
    boss: int = Field(primary_key=True, title="Boss")
    seq: int = Field(primary_key=True, title="序号1-20")
    damage: int = Field(title="伤害")
    battle_log_id: int = Field(default=0, title="log_id")
    record_time: int = Field(default=0, title="记录时间")
