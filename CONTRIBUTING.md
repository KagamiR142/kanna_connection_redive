# 贡献指南

感谢参与 KCR（kanna_connection_redive）会战模块的开发。

## 范围

本仓库核心维护：

- `clanbattle/` — 自动报刀
- `knife_budget/`、`challenge/` — 刀型与队列
- `webui/`、`web/` — 会战 Web 面板
- `database/` — 会战相关持久化

`fendao_test`、`jjckiller`、`support_query` 可随仓库发布，但大型重构不在当前主线内。

## 开发环境

1. 将本模块置于 HoshinoBot：`hoshino/modules/kanna_connection_redive/`
2. 复制 `resource/data/setting_clanbattle.example.json` → `setting_clanbattle.json`
3. 安装开发依赖：

```bash
pip install pytest ruff
# 或
pip install -e ".[dev]"
```

## 本地检查（提交前）

在模块根目录执行：

```bash
python scripts/run_checks.py
```

测试与脚本会自动设置 `KCR_TOOLING=1`，无需完整填写 `setting_clanbattle.json`。

等价于：

```bash
python scripts/sync_help_text.py --check
python scripts/check_docs.py
pytest
ruff check scripts tests conftest.py
```

## 预览 PNG（无需 Bot）

```bash
python -m devtools.previews.status      # Boss 名/头像在线拉取
python -m devtools.previews.boss_query
```

输出在 `devtools/output/`（已 gitignore）。详见 [devtools/说明.md](devtools/说明.md)。

## 修改 QQ 帮助文案

1. 编辑 `docs/user/自动报刀帮助.qq.txt`（每行一条，以 `【` 开头）
2. 运行 `python scripts/sync_help_text.py`
3. 同步更新 `docs/user/自动报刀.md`（用户可读版，表格格式）

**不要** 手改 `clanbattle/user_help.py`（文件头有生成标记）。

## 修改指令行为

1. 更新 `clanbattle/command_parser.py` 或对应 service
2. 更新 `clanbattle/response_messages.py` 文案
3. 更新 `docs/developer/commands/会战指令.md` 规格
4. 补充或修改 `clanbattle/test_*.py` / `tests/`

## 提交规范

- 一个 PR 只做一类改动（文档 / 重构 / 功能 / 修复）
- 重构 PR **不改变** 对外行为；附 `pytest` 通过截图或 CI 链接
- 不提交 `setting_clanbattle.json`、`data/` 下运行时文件

## 文档

- 用户帮助 → `docs/user/`
- 指令规格 → `docs/developer/commands/`
- 设计说明 → `docs/design/`
- 重构计划 → `docs/developer/重构计划.md`
