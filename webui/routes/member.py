from typing import List, Optional

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...basedata import Platform
from ...client import decrypt_access_key, get_access_key
from ...database.dal import Account, CookieCache, RefreshAccount, pcr_sqla
from .. import helpers
from ..services.binding_service import (
    get_binding_view,
    remove_user_binding_slot,
    reorder_user_bindings,
    set_primary_binding,
    upsert_binding_slot,
)
from ..services.clan_accounts_service import fetch_clan_member_options
from ..services.season_records_service import build_season_records
from ..session import call_in_main_loop
from ..util import *
from ..web_model import BindAccountForm


class BindingForm(BaseModel):
    viewer_id: int
    group_id: int
    multi: bool = False


class BindingSortForm(BaseModel):
    viewer_ids: List[int]


def register(router) -> None:
    @router.get("/me/binding")
    async def get_my_binding(
        group_id: Optional[int] = Query(None),
        token: CookieCache = Depends(verify_cookie),
    ):
        user_id = int(token.user_id)
        gid = int(group_id) if group_id else None
        if gid:
            await ensure_group_access(user_id, gid)
        return await get_binding_view(user_id, group_id=gid)

    @router.put("/me/binding")
    async def put_my_binding(
        form: BindingForm, token: CookieCache = Depends(verify_cookie)
    ):
        user_id = int(token.user_id)
        await ensure_group_access(user_id, int(form.group_id))
        try:
            if form.multi:
                await upsert_binding_slot(
                    user_id, int(form.viewer_id), group_id=int(form.group_id)
                )
            else:
                await set_primary_binding(
                    user_id, int(form.viewer_id), group_id=int(form.group_id)
                )
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        return await get_binding_view(user_id, group_id=int(form.group_id))

    @router.put("/me/bindings/sort")
    async def put_my_binding_sort(
        form: BindingSortForm,
        group_id: Optional[int] = Query(None),
        token: CookieCache = Depends(verify_cookie),
    ):
        user_id = int(token.user_id)
        gid = int(group_id) if group_id else None
        if gid:
            await ensure_group_access(user_id, gid)
        try:
            await reorder_user_bindings(user_id, [int(x) for x in form.viewer_ids])
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
        return await get_binding_view(user_id, group_id=gid)

    @router.delete("/me/bindings/{viewer_id}")
    async def delete_my_binding_slot(
        viewer_id: int,
        group_id: Optional[int] = Query(None),
        token: CookieCache = Depends(verify_cookie),
    ):
        user_id = int(token.user_id)
        gid = int(group_id) if group_id else None
        if gid:
            await ensure_group_access(user_id, gid)
        try:
            await remove_user_binding_slot(user_id, int(viewer_id))
        except ValueError as e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
        return await get_binding_view(user_id, group_id=gid)

    @router.get("/me/season-records")
    async def my_season_records(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        return await build_season_records(group_id, int(token.user_id))

    @router.get("/{group_id}/clan-accounts")
    async def clan_accounts(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        try:
            return await fetch_clan_member_options(group_id)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    @router.post("/{group_id}/bind_account")
    async def bind_account(
        group_id: int,
        form: BindAccountForm,
        token: CookieCache = Depends(verify_group_access),
    ):
        """绑定游戏账号（**全局生效**，一个 QQ 只绑一个号）

        和 QQ 私聊【绑定账号】写的是同一行（`Account.group_id = 0`），所以在哪个群
        打开仪表盘都一样，换公会 / 进新群都不需要重新绑定。URL 里的 group_id 现在
        只用来做访问校验（verify_group_access），不再决定这条绑定写到哪。

        权限：绑自己的号属于「自己的事」，0 级即可，不限等级。
        重复绑定 = 覆盖原来那一条。
        """
        user_id = int(token.user_id)
        group_id = int(group_id)
        platform = int(form.platform)

        try:
            if platform == Platform.b_id.value:
                bili_account = form.bili_account.strip()
                bili_password = form.bili_password.strip()
                if not bili_account or not bili_password:
                    raise ValueError("请填写 B站账号和 B站密码")
                # 换 access_key 要连 B站，同样得回主循环
                uid, access_key = await call_in_main_loop(
                    get_access_key(bili_account, bili_password, user_id)
                )
                account = Account(
                    user_id=user_id,
                    group_id=0,
                    platform=Platform.b_id.value,
                    account=str(uid),
                    password=access_key,
                    refresh=bili_account,
                )
                refresh: Optional[RefreshAccount] = RefreshAccount(
                    account=bili_account, password=bili_password
                )
            elif platform == Platform.qu_id.value:
                login_id = form.login_id.strip()
                raw_token = form.token.strip()
                if not login_id or not raw_token:
                    raise ValueError("请填写 login_id 和 token")
                # token 有两种给法：
                #   1) 直接的 access_key
                #   2) 提取器导出的 XML 片段（<string name="...">...</string>）
                # 用「像不像 XML」来判断，而不是像 QQ 指令那样按空格切成两段 ——
                # XML 里有没有空格、粘过来是几段都不确定，按空格切很容易切错，
                # 而且切错了 decrypt_access_key 会直接抛 AttributeError 变成 500。
                password = raw_token
                if raw_token.lstrip().startswith("<"):
                    try:
                        password = decrypt_access_key(raw_token)
                    except Exception:
                        raise ValueError(
                            "token 看起来是提取器导出的 XML，但解析失败，"
                            '请确认复制完整（形如 <string name="...">...</string>）'
                        )
                account = Account(
                    user_id=user_id,
                    group_id=0,
                    platform=Platform.qu_id.value,
                    account=login_id,
                    password=password,
                )
                refresh = None
            elif platform == Platform.tw_id.value:
                short_udid = form.short_udid.strip()
                udid = form.udid.strip()
                if not short_udid or not udid or not form.viewer_id:
                    raise ValueError("请填写 short_udid、udid 和 viewer_id")
                account = Account(
                    user_id=user_id,
                    group_id=0,
                    platform=Platform.tw_id.value,
                    viewer_id=int(form.viewer_id),
                    account=short_udid,
                    password=udid,
                )
                refresh = None
            else:
                raise ValueError("未知的服务器编号")
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

        account = await call_in_main_loop(helpers.login_new_account(account, refresh))
        if account is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "绑定失败，请检查账号信息是否完整正确（密码 / token 可能已过期）",
            )
        return helpers.account_info(account).dict()

    @router.post("/{group_id}/unbind_account")
    async def unbind_account(
        group_id: int, token: CookieCache = Depends(verify_group_access)
    ):
        """解绑当前登录用户绑定的游戏账号（全局，所有群一起生效）

        账号绑定不再按群区分，所以这里删的就是那唯一一条；删掉之后仪表盘会显示
        「未绑定游戏账号」，重新点【绑定游戏账号】或 QQ 私聊【绑定账号】即可。
        """
        user_id = int(token.user_id)
        if not await pcr_sqla.delete_account(user_id, 0):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "还没有绑定过游戏账号，无需解绑",
            )
        return "解绑成功"
