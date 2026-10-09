from hoshino import Service

from .api import *

sv = Service(
    name="环奈网页端管理",
    visible=False,
    enable_on_default=True,
)

# 「面板」「网页端登录」指令已迁移至 clanbattle 模块（群聊/私聊均可，严格整句匹配）
