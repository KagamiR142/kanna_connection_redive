"""Web 运维操作日志（内存 + 持久化 jsonl，供管理运维页查询）。"""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from loguru import logger

from ..basedata import FilePath

_MAX = 500
_LOG: Deque[Dict[str, Any]] = deque(maxlen=_MAX)
_LOG_PATH = FilePath.data.value / "web_ops_log.jsonl"


def _append_file(entry: Dict[str, Any]) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("WebOps 持久化失败: {}", e)


def append_ops_log(
    kind: str,
    message: str,
    *,
    group_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    entry = {
        "time": int(time.time()),
        "kind": kind,
        "message": message,
        "group_id": group_id,
        "user_id": user_id,
    }
    _LOG.appendleft(entry)
    _append_file(entry)
    logger.info(
        "WebOps kind={} group={} user={} msg={}",
        kind,
        group_id,
        user_id,
        message,
    )


def list_ops_logs(group_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
    rows = list(_LOG)
    if not rows and _LOG_PATH.is_file():
        try:
            lines = _LOG_PATH.read_text(encoding="utf-8").splitlines()
            for line in lines[-limit:]:
                rows.append(json.loads(line))
            rows.reverse()
        except Exception as e:
            logger.warning("WebOps 读取持久化日志失败: {}", e)
    if group_id is not None:
        gid = int(group_id)
        rows = [r for r in rows if r.get("group_id") in (None, gid)]
    return rows[:limit]
