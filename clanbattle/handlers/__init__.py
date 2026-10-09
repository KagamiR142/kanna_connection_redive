"""QQ 指令 handler 注册入口。"""
from __future__ import annotations

from .admin import register_admin_handlers
from .merge_line import register_merge_line_handlers
from .apply import register_apply_handlers
from .help import register_help_handlers
from .monitor import register_monitor_handlers
from .query import register_query_handlers
from .report import register_report_handlers
from .reserve import register_reserve_handlers
from .web_member import register_web_member_handlers


def register_handlers(sv) -> None:
    register_help_handlers(sv)
    register_monitor_handlers(sv)
    register_query_handlers(sv)
    register_reserve_handlers(sv)
    register_apply_handlers(sv)
    register_admin_handlers(sv)
    register_merge_line_handlers(sv)
    register_report_handlers(sv)
    register_web_member_handlers(sv)
