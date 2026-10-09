import re
import secrets

from fastapi import Depends, HTTPException, Response, status

from ...clanbattle import clanbattle_info
from ...clanbattle_setting import get_clanbattle_settings
from ...database.dal import pcr_sqla
from ...database.models import CookieCache
from ...rbac import is_admin_plus, is_super_admin, resolve_role
from ..services.guild_membership_service import resolve_group_display_name
from ..util import *
from ..web_model import ChangePasswordForm, HomeResponse, User


def register(router) -> None:
    @router.post("/login")
    async def check_user(user: User, response: Response):
        if web_user := await pcr_sqla.web_check_user(user.account, user.password):
            token = secrets.token_urlsafe(16)
            cfg = get_clanbattle_settings()
            response.set_cookie(
                "token",
                token,
                expires=3600 * 24 * 7,
                httponly=cfg.web_cookie_httponly,
                secure=cfg.web_cookie_secure,
                path="/",
                samesite="lax",
            )
            await pcr_sqla.web_add_cookie(token, web_user.account)
            return {
                "ok": True,
                "is_initial_password": bool(
                    getattr(web_user, "is_initial_password", False)
                ),
            }
        else:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "密码错误")

    @router.post("/logout")
    async def logout_user(response: Response, token: CookieCache = Depends(verify_cookie)):
        # 先清服务端记录，再让浏览器删 cookie。
        # 注意这里是 token.token：CookieCache 的主键字段叫 token，没有 cookie 这个属性，
        # 以前写的 token.cookie 会抛 AttributeError 又被下面的 except 吞掉，
        # 结果「登出」只删了浏览器那侧的 cookie，服务端这条 token 还能继续用满 7 天。
        try:
            await pcr_sqla.web_delete_cookie(token=token.token)
        except Exception as e:
            from nonebot import logger

            logger.warning(f"登出时清理服务端 token 失败: {e}")
        response.delete_cookie("token", path="/", samesite="lax")
        response.delete_cookie("token", path="/kanna_dependency")
        return "ok"

    @router.post("/change_password")
    async def change_password(
        form: ChangePasswordForm, token: CookieCache = Depends(verify_cookie)
    ):
        """修改网页端登录密码（登录后自助操作）

        规则：
          - 必须提供旧密码：光有 cookie 不足以改密，防止借到/偷到浏览器的人直接改走账号
          - 新密码 6~32 位，且不能和旧密码相同
          - 改完清掉 temp 标记，登录接口里「临时密码 7 天过期」就不再适用
          - 其他设备上的登录态全部失效，只把当前这一个补回来，
            免得旧密码已经泄露时旧会话还能继续用

        忘记密码：在 QQ 私聊机器人发送【注册】（尚未改密时会重发初始密码）。
        """
        from nonebot import logger

        account = str(token.user_id)
        new_password = form.new_password.strip()
        if not 8 <= len(new_password) <= 20:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码长度需在 8~20 位之间")
        if not re.fullmatch(r"[A-Za-z0-9]+", new_password):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "新密码只能包含大小写字母和数字"
            )
        if new_password == form.old_password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码不能和旧密码相同")
        if not await pcr_sqla.change_web_password(account, form.old_password, new_password):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "旧密码不正确")

        try:
            await pcr_sqla.web_delete_cookie(user_id=account)
            await pcr_sqla.web_add_cookie(token.token, account)
        except Exception as e:
            # 清不掉旧会话不影响改密本身，记个日志继续返回成功
            logger.warning(f"改密后清理旧登录态失败 account={account}: {e}")
        return "修改成功"

    @router.get("/home")
    async def home_info(token: CookieCache = Depends(verify_cookie)):
        user_id = int(token.user_id)
        response = HomeResponse()
        response.user_id = user_id
        if web_user := await pcr_sqla.web_query_user(user_id):
            response.priority = web_user.priority
            response.is_initial_password = bool(
                getattr(web_user, "is_initial_password", False)
            )
        role = await resolve_role(user_id)
        response.role = role.value
        response.is_super_admin = is_super_admin(user_id)
        response.is_admin = is_admin_plus(user_id)
        response.is_global_admin = is_admin_plus(user_id)

        bindings = await pcr_sqla.query_user_accounts(user_id)
        if bindings:
            response.name = bindings[0].alias or str(bindings[0].viewer_id or "")
            response.has_account = True
        if groups := await pcr_sqla.get_member_group(user_id):
            clan_list = []
            for group in groups:
                item = group.dict()
                item["group_name"] = await resolve_group_display_name(
                    int(group.group_id), item.get("group_name")
                )
                # 每个群单独算权限：群主/群管在本群自动是 2 级（bot 主人是 3 级），
                # 前端据此显示"群主/群管/管理员/成员"标签并控制管理入口
                item["priority"] = await effective_group_priority(user_id, group.group_id)
                # 本群有没有可用的号。账号是**全局**的（一个 QQ 一个号，绑一次所有群通用），
                # 所以这里各群结果必然一致 —— 保留逐群字段只是让前端沿用原逻辑。
                # query_account_for_group 会回退到全局号（group_id = 0），语义仍然成立。
                item["has_account"] = (
                    await pcr_sqla.query_account_for_group(user_id, group.group_id)
                ) is not None
                clan_list.append(item)
            response.clan = clan_list

        # 把「我管理的群」补进列表：群主/群管很可能没发过【绑定本群公会】，
        # 不补的话他们在网页端连自己的群都点不进去，"群主自动 2 级"就只是纸面能力；
        # bot 主人则能看到所有在用的群。候选范围只取「有人在用」的群，是有限集合。
        known = {int(clan["group_id"]) for clan in response.clan}
        candidates: dict = {
            int(g.group_id): g.group_name for g in await pcr_sqla.get_bound_groups()
        }
        for group_id in clanbattle_info:
            candidates.setdefault(int(group_id), "")

        owner = is_bot_owner(user_id)
        for gid, gname in candidates.items():
            if gid in known:
                continue
            if owner or await is_group_manager_in(gid, user_id):
                gdisplay = await resolve_group_display_name(gid, gname)
                response.clan.append(
                    {
                        "group_id": gid,
                        "group_name": gdisplay,
                        "priority": await effective_group_priority(user_id, gid),
                        # 群主/群管可能没在这个群绑过公会，这里同样按群算一次
                        "has_account": (
                            await pcr_sqla.query_account_for_group(user_id, gid)
                        ) is not None,
                    }
                )
        response.can_access_admin = is_admin_plus(user_id)
        return response.dict()
