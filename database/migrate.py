"""
从 kanna_connection_redive 1.0 迁移数据到 2.0 SQLite。

用法（在 Hoshino 工作目录 `8080/HoshinoBot-master` 下）:
    python -m hoshino.modules.kanna_connection_redive.database.migrate

灰度建议（V2-A）:
  1. 停 bot，备份 `resource/data/data.db`
  2. 在本机对备份库执行 migrate，核对账号/绑定条数
  3. 替换生产库并启动；观察 Web 登录与出刀监控
  4. 回滚：恢复备份 db 即可
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger

from ..basedata import FilePath, NoticeType
from .dal import pcr_sqla
from .models import Account, NoticeCache, UserAccount


async def migrate_v1_accounts(v1_data_dir: Path) -> int:
    account_dir = v1_data_dir / "account"
    if not account_dir.exists():
        logger.warning(f"未找到 1.0 账号目录: {account_dir}")
        return 0
    count = 0
    for file in account_dir.glob("*.json"):
        qq_id = int(file.stem)
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"读取 {file} 失败: {e}")
            continue
        items = raw if isinstance(raw, list) else [raw]
        for idx, item in enumerate(items):
            account = Account(
                user_id=qq_id,
                platform=item.get("platform", 0),
                viewer_id=item.get("viewer_id") or int(item.get("uid", 0) or 0) or None,
                account=str(item.get("account") or item.get("uid", "")),
                password=item.get("password") or item.get("access_key", ""),
                name=item.get("name", ""),
                refresh=item.get("refresh"),
            )
            await pcr_sqla.add_account(qq_id, account.dict(exclude_none=True))
            accounts = await pcr_sqla.query_account(qq_id)
            if accounts and account.viewer_id:
                await pcr_sqla.add_user_account(
                    UserAccount(
                        user_id=qq_id,
                        account_id=accounts[-1].id,
                        viewer_id=account.viewer_id,
                        alias=item.get("alias", f"账号{idx + 1}"),
                        sort_order=idx,
                    )
                )
            count += 1
    return count


async def migrate_v1_notices(v1_clan_dir: Path, group_id: int) -> int:
    """迁移单群的 apply/subscribe JSON（若存在）。"""
    count = 0
    apply_file = v1_clan_dir / "apply.json"
    if apply_file.exists():
        for row in json.loads(apply_file.read_text(encoding="utf-8")):
            await pcr_sqla.add_notice(
                NoticeCache(
                    group_id=group_id,
                    notice_type=NoticeType.apply.value,
                    user_id=int(row["uid"]),
                    boss=int(row["boss"]),
                    text=row.get("text", ""),
                    time=int(row.get("time", 0)),
                )
            )
            count += 1
    return count


async def main() -> None:
    await pcr_sqla.create_all()
    await pcr_sqla.ensure_schema_upgrades()
    v1_backup = Path(__file__).resolve().parents[1].parent / "kanna_connection_redive_v1_backup"
    v1_data = v1_backup / "data"
    if not v1_data.exists():
        v1_data = FilePath.data.value.parent.parent / "kanna_connection_redive_v1_backup" / "data"
    n = await migrate_v1_accounts(v1_data)
    logger.info(f"迁移账号 {n} 条")


if __name__ == "__main__":
    asyncio.run(main())
