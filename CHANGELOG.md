# 更新日志

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

### Added

- **Phase 2** `clanbattle/handlers/`：会战 QQ 指令按域拆分（9 个 handler 模块）
- **Phase 3** `util/display/`、`util/image/`；`webui/session.py`、`webui/permissions.py`、`webui/helpers.py`
- **Phase 4** `webui/routes/`：Web API 按 auth / panel / member / admin_ops 拆分
- **Phase 5** 用户文档导航补全；`docs/` 正式文档改为中文文件名
- **Phase 6** `LICENSE`（MIT）；[`docs/优化报告.md`](docs/优化报告.md) 开源优化总报告
- **Phase 1** `devtools/`：预览 PNG 脚本、`fixtures/api/` 脱敏样本、`docs/user/部署要点.md`
- `docs/developer/安全检查清单.md` 开源前敏感信息检查
- `docs/` 文档体系（用户 / 开发者 / 设计 / 部署）
- `docs/user/自动报刀帮助.qq.txt` 与 `scripts/sync_help_text.py` 帮助文本同步
- `pytest` 统一测试入口、`tests/` 无 Hoshino 依赖用例、GitHub Actions CI
- `scripts/run_checks.py`、`scripts/check_docs.py` 本地与 CI 检查
- `docs/developer/重构计划.md` 会战重构路线图
- `CONTRIBUTING.md`、`pyproject.toml`、扩展 `.gitignore`

### Changed

- `clanbattle/__init__.py` 从 ~1488 行精简至 ~60 行（仅 Service + 启动）
- `webui/api.py` 从 ~1285 行精简至 ~119 行（仅 app 装配 + 启动）
- QQ【自动报刀帮助】正文改由 `clanbattle/user_help.py` 提供（生成文件）
- `knife_budget/record_report.py` 排序键兼容无 `id` 字段的测试桩
- 文档内部链接与脚本路径适配中文文件名

### Removed

- 仓库内真实凭据样例（账号 JSON、含密码配置等；本地需自行恢复）

### Fixed

- `record_report` 去重排序在测试桩 `SimpleNamespace` 上因缺少 `id` 字段报错

## [2.0.0] - 历史

- KCR 2.0：刀型四态、1 秒监控、Web 面板、预约/申请语义更新等（详见 `docs/backup/blueprint/`）
