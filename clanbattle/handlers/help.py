"""自动报刀帮助指令。"""
from __future__ import annotations

from hoshino.typing import CQEvent, HoshinoBot

from ..user_help import HELP_TEXT


def register_help_handlers(sv) -> None:
    @sv.on_rex(r"^\s*自动报刀帮助\s*$")
    async def clanbattle_help(bot: HoshinoBot, ev: CQEvent):
        await bot.send(ev, HELP_TEXT)
