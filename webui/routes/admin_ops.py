from fastapi import Depends, HTTPException, status

from ...clanbattle.status_cache import notify_display_data_changed
from ...database.dal import CookieCache, pcr_sqla
from ..ops_log import append_ops_log
from ..services.monitor_web_service import start_monitor_web, stop_monitor_web
from ..state import report_time
from ..util import *
from ..web_model import CorrectDaoInfo, MonitorActionForm, MonitorAccountOption
from nonebot import logger


def register(router) -> None:
    @router.post("/correct_dao")
    async def correct_dao_record(
        correct: CorrectDaoInfo, token: CookieCache = Depends(verify_cookie)
    ):
        user_id = int(token.user_id)
        # 只能操作本人所属的群，防止改请求体里的 group_id 去改别的群的出刀记录
        await ensure_group_access(user_id, int(correct.group_id))
        from ...rbac import require_admin_plus_http

        require_admin_plus_http(user_id)
        if await pcr_sqla.correct_dao(
            correct.dao_id,
            0 if correct.type == "完整刀" else 1 if correct.type == "尾刀" else 0.5,
            correct.group_id,
        ):
            report_time[token.token] = 0
            return "修改成功"
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "请检查你输入了正确的出刀编号")

    @router.delete("/{group_id}/notice/{notice_id}")
    async def admin_delete_notice_row(
        group_id: int,
        notice_id: int,
        token: CookieCache = Depends(verify_group_access),
    ):
        user_id = int(token.user_id)
        await require_web_ops_admin(user_id, group_id)
        if not await pcr_sqla.delete_notice_by_id(notice_id, group_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "记录不存在")
        await notify_display_data_changed(int(group_id), "web_notice_delete")
        append_ops_log(
            "notice",
            f"删除队列项 id={notice_id}",
            group_id=group_id,
            user_id=user_id,
        )
        logger.info("Web 管理员删除通知: group={} id={}", group_id, notice_id)
        return {"ok": True}

    @router.get("/{group_id}/monitor/accounts")
    async def monitor_list_accounts(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        """列出当前管理员绑定的游戏凭证，供 Web 开启出刀监控（仅管理员可调 /monitor）。"""
        user_id = int(token.user_id)
        await require_web_ops_admin(user_id, group_id)
        accounts = await pcr_sqla.query_account(user_id)
        if not accounts:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "还没绑定角色账号，请先在网页端仪表盘绑定，"
                "或在QQ上对机器人发送【绑定账号帮助】完成绑定后再开启",
            )
        return [
            MonitorAccountOption(
                account_id=acc.id,
                name=acc.name or "未命名",
                platform=acc.platform,
                viewer_id=acc.viewer_id,
                group_id=int(acc.group_id or 0),
            ).dict()
            for acc in accounts
            if acc.id is not None
        ]

    @router.post("/{group_id}/monitor")
    async def monitor_switch(
        group_id: int,
        form: MonitorActionForm,
        token: CookieCache = Depends(verify_group_access),
    ):
        """Web 出刀监控开关：仅管理员及以上（与蓝图一致，普通成员不可操作）。"""
        user_id = int(token.user_id)
        await require_web_ops_admin(user_id, group_id)

        if form.action == "off":
            return await stop_monitor_web(group_id, user_id)
        if form.action == "on":
            if form.account_id is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "请选择用于监控的游戏账号"
                )
            return await start_monitor_web(group_id, user_id, int(form.account_id))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知 action: {form.action}")
