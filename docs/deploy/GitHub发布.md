# GitHub 发布（仅模块、无历史）

开源仓库：**[KagamiR142/kanna_connection_redive](https://github.com/KagamiR142/kanna_connection_redive)**  
仓库根目录 = 本模块全部内容，**不包含**上级 `bot/` 或其它 Hoshino 实例。

## 与本地 bot 仓库的关系

| 位置 | 用途 |
|------|------|
| `…/hoshino/modules/kanna_connection_redive/` | 日常开发与 Hoshino 加载 |
| `workspace2/kanna_connection_redive/`（默认） | **仅用于 push** 的独立 Git 副本，**单次初始提交**，不携带 bot 历史 |

在模块目录执行：

```bash
python scripts/prepare_github_release.py
```

会刷新发布目录并 `git init` + 一条 commit + `origin`（**不自动 push**）。

## README 顶部的 CI 徽章

徽章图片地址在 **仓库创建且 Actions 至少成功跑过一次** 之后才会正常显示；本地 Markdown 预览也常只能看到链接。  
当前 README **未放徽章**；推送后若需要，可在首行自行加回：

```markdown
[![CI](https://github.com/KagamiR142/kanna_connection_redive/actions/workflows/ci.yml/badge.svg)](https://github.com/KagamiR142/kanna_connection_redive/actions/workflows/ci.yml)
```

工作流文件仍在 `.github/workflows/ci.yml`。

## 推送前检查

```bash
python scripts/scan_sensitive_numbers.py
set KCR_TOOLING=1
python -m pytest tests -q
```

确认未 `git add`：`data/`、`setting_clanbattle.json`、日志等（见 `docs/developer/安全检查清单.md`）。

## 首次推送（终审通过后）

```powershell
cd <发布目录>
& "C:\Program Files\GitHub CLI\gh.exe" repo create KagamiR142/kanna_connection_redive --public --source=. --remote=origin --push
```

若远程已存在则：

```powershell
git push -u origin main
```

**不要**从 `workspace2/bot` 根目录 push。
