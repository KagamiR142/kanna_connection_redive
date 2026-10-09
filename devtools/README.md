# 开发者工具（devtools）

无需启动 HoshinoBot、**无需游戏账号登录**。预览图会尽量从 Satroki 拉取**当期 Boss 名称与头像**；离线时回退 `resource/data/boss_info.json` 或 `fixtures/api/`。

## 环境

```bash
cd hoshino/modules/kanna_connection_redive
pip install pillow httpx loguru
export KCR_TOOLING=1   # Windows: set KCR_TOOLING=1
```

## 生成预览 PNG

输出目录：`devtools/output/`（已 `.gitignore`，勿提交）

| 命令 | 产物 |
|------|------|
| `python -m devtools.previews.status` | `status_sample*.png` |
| `python -m devtools.previews.boss_query` | `boss_query_1.png` … `5` |
| `python -m devtools.previews.guild_stats` | `guild_stats_today/season.png` |
| `python -m devtools.previews.knife_report` | `knife_report_user_sample.png` |
| `python -m devtools.previews.boss_lap_records` | `boss_lap_records_sample.png`（并写入 `docs/assets/readme/boss_lap_records.png`） |

一键生成全部：

```bash
python -m devtools.previews.status
python -m devtools.previews.boss_query
python -m devtools.previews.guild_stats
python -m devtools.previews.knife_report
python -m devtools.previews.boss_lap_records
```

**README 用图**（写入 `docs/assets/readme/`，样例数据见 `previews/_readme_sample.py`）：

```bash
python -m devtools.previews.readme_assets
```

## API 脱敏样本

见 [`fixtures/api/`](fixtures/api/说明.md)，供 `client/`、`knife_budget` 等二次开发参考。

## 与 `tools/` 的关系

原 `tools/generate_*.py` 已迁移至此；`tools/` 保留兼容入口，将打印迁移提示。

## 检查

```bash
python scripts/run_checks.py
```
