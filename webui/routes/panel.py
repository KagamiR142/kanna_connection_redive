import asyncio
import json
import time

import nonebot
from fastapi import Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import Response as FastAPIResponse
from nonebot import logger
from sse_starlette.sse import EventSourceResponse

from ...basedata import NoticeType
from ...clanbattle import clanbattle_info, notice_update_time
from ...clanbattle.base import (
    DEFAULT_RANK_LINES,
    clanbattle_report,
    get_rank_lines_cached,
    is_monitor_running,
)
from ...clanbattle.detail_reports import format_today_guild_detail
from ...clanbattle.reserve_service import list_reserve_for_boss
from ...clanbattle.status_cache import (
    get_cached_status_png_bytes,
    is_monitor_active,
    notify_display_data_changed,
)
from ...clanbattle.status_service import get_group_status_png
from ...database.dal import SLDao, pcr_sqla
from ...database.models import CookieCache
from ...util.auto_boss import clan_boss_info
from ...util.tools import anywhere_send, daoflag2str
from .. import helpers
from ..services.panel_service import build_panel_payload
from ..services.stats_service import build_daily_stats, list_battle_days
from ..state import dashboard_time, notice_time, report_time
from ..util import *
from ..web_model import *


def register(router) -> None:
    @router.get("/{group_id}/dashboard")
    async def dashboard_info(group_id: int, token: CookieCache = Depends(verify_group_access)):
        now = int(time.time())
        boss_info = clan_boss_info.boss_info
        user_id = int(token.user_id)
        response = DashboardResponse()
        response.boss = [
            BossInfoCounter(
                name=boss_info[i].name,
                id=boss_info[i].boss_id,
            )
            for i in range(5)
        ]
        response.user_id = user_id
        if web_user := await pcr_sqla.web_query_user(user_id):
            response.priority = web_user.priority
        # 本群实际权限等级（群主/群管自动 2 级，bot 主人 3 级），前端据此控制按钮显隐
        response.clan_priority = await effective_group_priority(user_id, group_id)
        # 游戏账号（全局，一个 QQ 一个号、各群同值），仪表盘状态条上的绑定入口用它
        response.account = helpers.account_info(
            await pcr_sqla.query_account_for_group(user_id, group_id)
        )

        if clan_info := clanbattle_info.get(group_id, None):
            response.clan_name = clan_info.clan_name
            response.stage = f"{clan_info.period}面{clan_info.lap_num}周目"
            response.rank = clan_info.rank
            response.name = clan_info.user_id
            # 出刀监控人 QQ：前端据此禁用非监控人的"取消出刀监控"按钮
            response.monitor_user_id = int(getattr(clan_info, "user_id", 0) or 0)
            if clan_info.loop_check:
                response.state = "开启" + (
                    "(高占用)" if now - clan_info.loop_check > 30 else ""
                )
                response.boss = [
                    BossInfoCounter(
                        name=boss_info[i].name,
                        id=boss_info[i].boss_id,
                        fighter=boss.fighter_num,
                        current_hp=boss.current_hp,
                        max_hp=boss.max_hp,
                        lap=boss.lap_num,
                    )
                    for i, boss in enumerate(clan_info.boss)
                ]
        # 出刀监控开启时带上完整公会名单，"今日出刀分布"才能显示 0 刀（未出刀）成员
        members = clan_info.members if clan_info else {}
        if dao_data := await pcr_sqla.get_day_rcords(now, group_id):
            response.dao, response.report = await get_day_dao(dao_data, members)
            # 取今日出刀按时间倒序的最近 20 条，给仪表盘"最近出刀"卡片用
            response.last_dao = build_last_dao(dao_data, 20)
            # 今日伤害排行（Top 10）+ 全员总量，给右栏横向条形图用。
            # 和上面两处共用同一份 dao_data，不额外查库。
            rank_rows, damage_total, score_total = build_day_damage_rank(dao_data, 10)
            response.day_damage_rank = [DayDamageRank(**row) for row in rank_rows]
            response.day_damage_total = damage_total
            response.day_score_total = score_total
        if dao_data := await pcr_sqla.get_day_rcords(now - 3600 * 24, group_id):
            response.yesterday_dao, _ = await get_day_dao(dao_data)

        if subscribes := await pcr_sqla.get_notice(NoticeType.subscribe.value, group_id):
            for subscribe in subscribes:
                response.boss[subscribe.boss - 1].subscribe += 1
        if board_msgs := await pcr_sqla.get_notice(
            NoticeType.board_message.value, group_id
        ):
            for row in board_msgs:
                response.boss[row.boss - 1].subscribe += 1
        if applies := await pcr_sqla.get_notice(NoticeType.apply.value, group_id):
            for apply in applies:
                response.boss[apply.boss - 1].apply += 1
        if trees := await pcr_sqla.get_notice(NoticeType.tree.value, group_id):
            for tree in trees:
                response.boss[tree.boss - 1].tree += 1
        response.day_num = await pcr_sqla.get_clan_day(group_id)
        return response.dict()

    @router.get("/{group_id}/boss_dao")
    async def boss_dao_records(
        group_id: int, boss: int, token: CookieCache = Depends(verify_group_access)
    ):
        """指定 BOSS 本次会战周期内的全部出刀记录，按时间倒序（BOSS 卡片"出刀记录"弹窗用）"""
        if not 1 <= boss <= 5:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "BOSS 编号必须是 1~5")
        # 本次会战 = 最近一次出刀时间的 pcr 日期往前推 5 天（与 get_clan_day 口径一致）
        period = await pcr_sqla.get_all_records(group_id)
        filtered = [r for r in period if r.boss == boss] if period else []
        # build_last_dao 本身就是按时间倒序转换，limit 传记录总数即"全部返回"
        return build_last_dao(filtered, max(len(filtered), 1))

    @router.get("/{group_id}/rank_lines")
    async def get_rank_lines(
        group_id: int,
        ranks: str = None,
        force: bool = False,
        token: CookieCache = Depends(verify_group_access),
    ):
        """查档线：本届会战指定排名的分数线（仅会战期间有效），ranks 为逗号分隔自定义排名

        档线是全服排名数据，游戏侧每半小时才更新一次，但抓一次要打十几次分页请求
        （默认 14 个档位 = 13 个分页，外加「末位二分搜索」十来次）。缓存逻辑统一收在
        clanbattle.base.get_rank_lines_cached 里（QQ 端【查档线】指令走同一条路），
        这里只负责「监控没开时只读缓存」和把结果转成响应。

        抓取的前置条件是「出刀监控在跑」，用 `is_monitor_running` 判 —— **不能**只看
        `clan_info.client`：发过【取消出刀监控】之后 client 仍在，而账号很可能正被群友
        自己登录着，这时抓一次失败会触发重登，直接把人顶下线。监控没开时只读缓存，
        读不到才报错。
        """
        # 解析档位。默认档位和每个自定义档位组合各占一条缓存，互不覆盖。
        if ranks:
            try:
                targets = [int(x.strip()) for x in ranks.split(",") if x.strip()]
            except ValueError:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "ranks 参数格式错误，应为逗号分隔数字，如 500,2000"
                )
            if not targets:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "ranks 不能为空")
        else:
            targets = list(DEFAULT_RANK_LINES)
        ranks_key = ",".join(str(t) for t in sorted(set(targets)))

        clan_info = clanbattle_info.get(group_id)
        if not is_monitor_running(clan_info):
            # 监控没开：只读缓存，不抓。拿不到 clan_battle_id，所以取本群最新一届那条。
            cached = await pcr_sqla.get_latest_rank_line_cache(group_id, ranks_key)
            if cached is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "出刀监控未开启，无法查询档线（开启监控后会自动抓取并缓存）",
                )
            return helpers.rank_line_response(
                json.loads(cached.payload),
                cached=True,
                stale=True,
                monitor_running=False,
                updated_at=int(cached.updated_at),
            )

        # 游戏 client 绑定在 nonebot 主循环，必须投递回去执行（与监控循环排队互斥）。
        # 缓存命中 / 抓取 / 抓失败退回旧缓存，都在 get_rank_lines_cached 内部处理完了。
        result = await call_in_main_loop(get_rank_lines_cached(clan_info, targets, force))
        return helpers.rank_line_response(
            result["data"],
            cached=result["cached"],
            stale=result["stale"],
            monitor_running=True,
            updated_at=result["updated_at"],
        )

    @router.get("/{group_id}/notice")
    async def clan_notice(group_id: int, token: CookieCache = Depends(verify_group_access)):
        user_id = int(token.user_id)
        response = NoticeResponse()
        response.user_id = user_id
        if web_user := await pcr_sqla.web_query_user(user_id):
            response.priority = web_user.priority
        # 本群实际权限等级，前端据此控制通知管理入口（>= 1 才显示）
        response.clan_priority = await effective_group_priority(user_id, group_id)
        # 有没有可用的号（账号是全局的，各群同值）；没有就不让发预约/挂树
        response.has_account = (
            await pcr_sqla.query_account_for_group(user_id, group_id)
        ) is not None
        merged_reserve: list = []
        for boss_ord in range(1, 6):
            merged_reserve.extend(
                await list_reserve_for_boss(group_id, boss_ord)
            )
        if merged_reserve:
            response.subscribe = merged_reserve
        if apply := await pcr_sqla.get_notice(NoticeType.apply.value, group_id):
            response.apply = apply
        if tree := await pcr_sqla.get_notice(NoticeType.tree.value, group_id):
            response.tree = tree
        return response.dict()

    @router.get("/{group_id}/report")
    async def clan_report(group_id: int, token: CookieCache = Depends(verify_group_access)):
        user_id = int(token.user_id)
        response = ReportResponse()
        response.user_id = user_id
        if web_user := await pcr_sqla.web_query_user(user_id):
            response.priority = web_user.priority
        # 本群实际权限等级，前端据此控制修正出刀入口（>= 1 才显示）
        response.clan_priority = await effective_group_priority(user_id, group_id)
        if info := await pcr_sqla.get_all_records(group_id):
            players, all_damage, all_score = clanbattle_report(
                info, await pcr_sqla.get_max_dao(group_id)
            )
            response.all = [
                DaoInfo(
                    name=member[1],
                    damage=member[3],
                    score=member[4],
                    dao=member[2],
                    damage_rate=f"{member[3]/all_damage*100:.2f}%",
                    score_rate=f"{member[4]/all_score*100:.2f}%",
                )
                for member in players
            ]
            response.detail = [
                DaoInfo(
                    name=player.name,
                    damage=player.damage,
                    score=int(
                        clan_boss_info.get_boss_rate(player.lap, player.boss)
                        * player.damage
                    ),
                    type=daoflag2str(player.flag),
                    date=player.time,
                    boss=player.boss,
                    lap=player.lap,
                    dao_id=player.battle_log_id,
                )
                for player in info[::-1]
            ]
        # 当前生效的号。一个 QQ 只有一个全局号，但仍统一走 query_account_for_group
        # （本群优先、回退全局），别写 query_account(user_id)[0]（那是「取第一条」的语义）。
        if pcr_user := await pcr_sqla.query_account_for_group(user_id, group_id):
            response.name = pcr_user.name
            if info := await pcr_sqla.get_player_records(pcr_user.viewer_id, 5, group_id):
                knife = 0
                for dao in info:
                    knife += 1 if dao.flag == 0 else 0.5
                    response.me.append(
                        DaoInfo(
                            dao=knife,
                            damage=dao.damage,
                            score=int(
                                clan_boss_info.get_boss_rate(dao.lap, dao.boss) * dao.damage
                            ),
                            type=daoflag2str(dao.flag),
                            boss=dao.boss,
                            lap=dao.lap,
                            date=dao.time,
                            dao_id=dao.battle_log_id,
                        )
                    )
            response.me = response.me[::-1]
        return response.dict()

    @router.post("/set_notice")
    async def add_notice(
        notice: NoticeCache,
        token: CookieCache = Depends(verify_cookie),
        notice_source: str = Header(default="qq", alias="X-KCR-Notice-Source"),
    ):
        user_id = int(token.user_id)
        # 只能操作本人所属的群，防止改请求体里的 group_id 去别的群发通知
        await ensure_group_access(user_id, int(notice.group_id))

        # 预约 / 挂树 / 申请 / SL 都是「自己的事」，普通成员（0 级）就能做，这里不再卡等级；
        # 只有替别人发通知才算「管理他人的通知」，需要本群 2 级（群主 / 群管自动获得）。
        # user_id 传 0 或不传按「给自己发」处理，避免客户端漏传一个字段就变成替别人发。
        target_id = int(notice.user_id) or user_id
        if target_id != user_id:
            from ...rbac import require_admin_plus_http

            require_admin_plus_http(user_id)
        notice.user_id = target_id

        # 预约/挂树/申请出刀必须先绑定游戏账号（未绑定用户没有出刀身份，不允许发起）。
        # 检查的是「这条通知挂谁头上」，所以替别人发时校验的是对方。
        # 账号绑定是全局的（一个 QQ 一个号），所以这里不分群。
        if notice.notice_type in (
            NoticeType.subscribe.value,
            NoticeType.board_message.value,
            NoticeType.tree.value,
            NoticeType.apply.value,
        ):
            from ...clanbattle.account_service import list_bound_accounts

            has_game_identity = bool(
                await pcr_sqla.query_account_for_group(target_id, int(notice.group_id))
            ) or bool(await list_bound_accounts(target_id))
            if not has_game_identity:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "尚未绑定游戏角色：请在「个人数据」选择公会成员，"
                    "或 QQ 私聊【绑定账号】完成凭证绑定",
                )
        if notice.notice_type == NoticeType.sl.value:
            if not await pcr_sqla.add_sl(
                SLDao(group_id=notice.group_id, user_id=target_id, time=int(time.time()))
            ):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "已经sl过了")
        elif notice.notice_type == NoticeType.board_message.value:
            if not str(notice.text or "").strip():
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "留言必须填写内容"
                )
            await pcr_sqla.add_notice(notice)
        else:
            await pcr_sqla.add_notice(notice)
        await notify_display_data_changed(int(notice.group_id), "web_notice")
        if notice_source.lower() != "web":
            await anywhere_send(
                get_notice_msg(
                    notice.notice_type, target_id, notice.boss, notice.lap, notice.text
                ),
                group_id=notice.group_id,
            )
        else:
            logger.info(
                "Web 静默通知: group={} user={} type={} boss={}",
                notice.group_id,
                target_id,
                notice.notice_type,
                notice.boss,
            )
        return "成功"

    @router.post("/delete_notice")
    async def remove_notice(
        notice: NoticeCache,
        token: CookieCache = Depends(verify_cookie),
        notice_source: str = Header(default="qq", alias="X-KCR-Notice-Source"),
    ):
        user_id = int(token.user_id)
        # 只能操作本人所属的群，防止改请求体里的 group_id 去别的群删通知
        await ensure_group_access(user_id, int(notice.group_id))

        # 取消自己的通知不限等级；取消别人的通知属于「管理他人的通知」，需要本群 2 级。
        # 注意删的是 notice.user_id 名下那一条，不能像以前那样先覆盖成自己 ——
        # 覆盖之后管理员点「取消」只会去删自己那条（通常压根不存在），别人的通知永远删不掉。
        target_id = int(notice.user_id) or user_id
        if target_id != user_id:
            from ...rbac import require_admin_plus_http

            require_admin_plus_http(user_id)
        notice.user_id = target_id

        if notice.notice_type == NoticeType.sl.value:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "那你自己心里清楚")
        elif notice.notice_type in (
            NoticeType.subscribe.value,
            NoticeType.board_message.value,
        ):
            await pcr_sqla.delete_user_reserve(
                int(notice.group_id), int(notice.boss), target_id
            )
        else:
            await pcr_sqla.delete_notice(
                notice.notice_type,
                notice.group_id,
                notice.boss,
                user_id=target_id,
            )
        await notify_display_data_changed(int(notice.group_id), "web_notice")
        if notice_source.lower() != "web":
            await anywhere_send(
                cancel_notice_msg(
                    notice.notice_type, target_id, notice.boss, operator=user_id
                ),
                group_id=notice.group_id,
            )
        else:
            logger.info(
                "Web 静默取消通知: group={} user={} type={} boss={}",
                notice.group_id,
                target_id,
                notice.notice_type,
                notice.boss,
            )
        return "取消成功"

    @router.post("/delete_notice_special")
    async def remove_notice_special(
        notice: SpecialNoticeForm,
        token: CookieCache = Depends(verify_cookie),
        notice_source: str = Header(default="qq", alias="X-KCR-Notice-Source"),
    ):
        user_id = int(token.user_id)
        # 只能操作本人所属的群，防止改请求体里的 group_id 去别的群取消通知
        await ensure_group_access(user_id, int(notice.group_id))
        # 取消自己的通知不限等级；替别人取消属于「管理他人的通知」，需要本群 2 级
        # （群主 / 群管自动获得）。这里用 notice.user_id 去删，才能真的删掉目标那条。
        if user_id != notice.user_id:
            from ...rbac import require_admin_plus_http

            require_admin_plus_http(user_id)
        await pcr_sqla.delete_notice(
            notice.notice_type,
            notice.group_id,
            notice.boss,
            user_id=notice.user_id,
            lap=notice.lap,
        )
        await notify_display_data_changed(int(notice.group_id), "web_notice")
        if notice_source.lower() != "web":
            await anywhere_send(
                cancel_notice_msg(
                    notice.notice_type, notice.user_id, notice.boss, operator=user_id
                ),
                group_id=notice.group_id,
            )
        else:
            logger.info(
                "Web 静默取消通知(special): group={} user={} type={} boss={}",
                notice.group_id,
                notice.user_id,
                notice.notice_type,
                notice.boss,
            )
        return "取消成功"

    @router.get("/{group_id}/renew_dashboard")
    async def renew_dashboard(group_id: int, token: CookieCache = Depends(verify_group_access)):
        async def dashboard_generator():
            dashboard_time[token.token] = int(time.time())
            notice_time[token.token] = int(time.time())
            while True:
                await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
                if clan_info := clanbattle_info.get(group_id, None):
                    # 出刀入库(dao_update_time)或战斗人数变化(fighter_update_time)都推送仪表盘
                    latest = max(
                        clan_info.dao_update_time,
                        getattr(clan_info, "fighter_update_time", 0),
                        getattr(clan_info, "status_image_update_time", 0),
                    )
                    if latest > dashboard_time[token.token]:
                        dashboard_time[token.token] = latest
                        yield json.dumps(await dashboard_info(group_id, token))
                        continue
                if update_time := notice_update_time.get(group_id, 0):
                    if update_time > notice_time[token.token]:
                        notice_time[token.token] = update_time
                        yield json.dumps(await dashboard_info(group_id, token))

        return EventSourceResponse(content=dashboard_generator())

    @router.get("/{group_id}/renew_report")
    async def renew_report(group_id: int, token: CookieCache = Depends(verify_group_access)):
        async def report_generator():
            report_time[token.token] = int(time.time())
            while True:
                await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
                if clan_info := clanbattle_info.get(group_id, None):
                    if clan_info.dao_update_time > report_time[token.token]:
                        yield json.dumps(await clan_report(group_id, token))
                        report_time[token.token] = clan_info.dao_update_time
                if not report_time[token.token]:
                    yield json.dumps(await clan_report(group_id, token))
                    report_time[token.token] = int(time.time())

        return EventSourceResponse(content=report_generator())

    @router.get("/{group_id}/renew_notice")
    async def renew_notice(group_id: int, token: CookieCache = Depends(verify_group_access)):
        async def notice_generator():
            notice_time[token.token] = int(time.time())
            while True:
                await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
                if update_time := notice_update_time.get(group_id, 0):
                    if update_time > notice_time[token.token]:
                        yield json.dumps(await clan_notice(group_id, token))
                        notice_time[token.token] = update_time

        return EventSourceResponse(content=notice_generator())

    @router.get("/{group_id}/panel")
    async def guild_panel(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        return await build_panel_payload(group_id)

    @router.get("/{group_id}/status-image")
    async def guild_status_image(
        group_id: int,
        request: Request,
        token: CookieCache = Depends(verify_group_access),
    ):
        """预渲染 PNG 缓存（与 QQ【状态】一致）。"""
        clan_info = clanbattle_info.get(group_id)
        if not clan_info or not is_monitor_active(clan_info):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "未开启出刀监控，无法查看状态图"
            )
        version = getattr(clan_info, "status_png_version", 0)
        etag = f'W/"{version}"'
        if request.headers.get("if-none-match") == etag and get_cached_status_png_bytes(
            clan_info
        ):
            return Response(status_code=304)
        try:
            bot = nonebot.get_bot()
            png = get_cached_status_png_bytes(clan_info)
            if not png:
                png = await get_group_status_png(bot, clan_info)
        except Exception as e:
            logger.warning("Web 状态图失败 group={}: {}", group_id, e)
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "状态图生成失败，请稍后重试"
            )
        return Response(
            content=png,
            media_type="image/png",
            headers={"ETag": etag, "Cache-Control": "no-cache"},
        )

    @router.get("/{group_id}/panel/stream")
    async def guild_panel_stream(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        """面板 SSE（约 8s 推送一次，与轮询互为备份）。"""

        async def generator():
            while True:
                payload = await build_panel_payload(group_id)
                yield json.dumps(payload, ensure_ascii=False)
                await asyncio.sleep(8)

        return EventSourceResponse(generator())

    @router.get("/{group_id}/battle-days")
    async def guild_battle_days(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        return await list_battle_days(group_id)

    @router.get("/{group_id}/stats/daily")
    async def guild_stats_daily(
        group_id: int,
        date: str,
        token: CookieCache = Depends(verify_group_access),
    ):
        try:
            return await build_daily_stats(group_id, date)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    @router.get("/{group_id}/reports/guild/daily.png")
    async def guild_daily_report_png(
        group_id: int,
        token: CookieCache = Depends(verify_group_access),
    ):
        """今日公会出刀次数统计 PNG（与 QQ【今日出刀】同版式）。"""
        try:
            bot = nonebot.get_bot()
        except Exception:
            bot = None
        payload = await format_today_guild_detail(
            group_id, bot, clan_info=clanbattle_info.get(group_id)
        )
        if isinstance(payload, str):
            raise HTTPException(status.HTTP_404_NOT_FOUND, payload)
        return FastAPIResponse(content=payload, media_type="image/png")

    @router.post("/{group_id}/boss/refresh")
    async def guild_boss_refresh_deprecated(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        """已废弃：监控 1s 自动更新 Boss 镜像，请使用 panel / status-image。"""
        raise HTTPException(
            status.HTTP_410_GONE,
            "手动刷新已取消；请依赖出刀监控自动更新或刷新面板数据",
        )
