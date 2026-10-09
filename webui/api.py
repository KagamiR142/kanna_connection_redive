import asyncio
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from nonebot import logger, on_startup
from starlette.responses import FileResponse

from ..clanbattle_setting import get_clanbattle_settings
from ..setting import WebSetting
from .admin_api import router as admin_router
from .routes import register_routes
from .web_admin_routes import router as web_admin_router

app = FastAPI()
app.include_router(admin_router)

origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3141",
    "http://yourhost:3141",
    # 局域网部署地址（前端 5173）
    f"http://{WebSetting.web_host.value}:{WebSetting.web_port.value}",
    # 兼容使用默认 3141 生产端口的部署
    f"http://{WebSetting.web_host.value}:3141",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _kcr_web_access_log(request: Request, call_next):
    from ..util.kcr_logging import web_log

    t0 = time.time()
    response = await call_next(request)
    ms = int((time.time() - t0) * 1000)
    web_log().info(
        "{} {} status={} ms={}",
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response


api_router = APIRouter(prefix=WebSetting.api_base.value)
register_routes(api_router)
api_router.include_router(web_admin_router)
app.include_router(api_router)

_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


def _mount_vue_panel_static() -> None:
    """生产：同端口托管 web/dist（无需 Nginx）。须先在开发机 npm run build 后拷贝 dist。"""
    if not (_WEB_DIST / "index.html").is_file():
        logger.warning(
            "Vue 面板未挂载：缺少 {}，仅提供 API（/kanna_dependency）",
            _WEB_DIST / "index.html",
        )
        return
    assets_dir = _WEB_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="kcr-web-assets")

    @app.get("/", include_in_schema=False)
    async def _web_panel_index():
        return FileResponse(_WEB_DIST / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def _web_panel_favicon():
        fav = _WEB_DIST / "favicon.ico"
        if fav.is_file():
            return FileResponse(fav)
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    logger.info(
        f"Vue 面板已挂载 dist={_WEB_DIST}（路由使用 hash，访问 http://host:port/#/login）"
    )


_mount_vue_panel_static()


@on_startup
async def kanna_web():
    # on_startup 钩子在 nonebot 主事件循环内执行，此刻记录的 loop 就是游戏 client 所属 loop。
    from . import session as web_session

    web_session.main_event_loop = asyncio.get_running_loop()
    cfg = get_clanbattle_settings()
    web = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": cfg.api_host, "port": cfg.api_port},
    )
    web.start()
    from ..util.kcr_logging import web_log

    web_log().info(
        "KCR Web API started host={} port={} base={}",
        cfg.api_host,
        cfg.api_port,
        WebSetting.api_base.value,
    )
