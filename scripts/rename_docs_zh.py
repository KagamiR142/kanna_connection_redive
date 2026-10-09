#!/usr/bin/env python3
"""将 docs/ 下英文文件名改为中文，并更新仓库内引用（一次性迁移脚本）。"""
from __future__ import annotations

from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS = MODULE_ROOT / "docs"

# 旧相对路径（docs/ 下） -> 新相对路径
RENAMES: dict[str, str] = {
    "README.md": "说明.md",
    "user/README.md": "user/说明.md",
    "user/quick-start.md": "user/快速上手.md",
    "user/deployment.md": "user/部署要点.md",
    "user/clanbattle.md": "user/自动报刀.md",
    "user/webui.md": "user/网页端.md",
    "user/account-binding.md": "user/账号绑定.md",
    "user/clanbattle-help.qq.txt": "user/自动报刀帮助.qq.txt",
    "developer/README.md": "developer/说明.md",
    "developer/architecture.md": "developer/架构.md",
    "developer/api-reference.md": "developer/API参考.md",
    "developer/permissions.md": "developer/权限模型.md",
    "developer/refactor-plan.md": "developer/重构计划.md",
    "developer/security-checklist.md": "developer/安全检查清单.md",
    "developer/data-paths.md": "developer/数据目录.md",
    "developer/commands/clanbattle.md": "developer/commands/会战指令.md",
    "design/README.md": "design/说明.md",
    "design/webui.md": "design/网页端.md",
    "design/report-images.md": "design/战报图.md",
    "design/monitor-and-status.md": "design/监控与状态图.md",
    "design/knife-budget.md": "design/刀型预算.md",
    "design/challenge-queue.md": "design/挑战队列.md",
    "design/platform.md": "design/平台需求.md",
    "design/game-rules.md": "design/游戏规则.md",
    "deploy/installation.md": "deploy/安装指南.md",
    "backup/README.md": "backup/说明.md",
}

# 在文本中替换的链接片段（长路径优先）
LINK_REPLACEMENTS: list[tuple[str, str]] = sorted(
    [
        (old.replace("\\", "/"), new.replace("\\", "/"))
        for old, new in RENAMES.items()
    ],
    key=lambda x: -len(x[0]),
)


def rename_files() -> None:
    for old_rel, new_rel in RENAMES.items():
        src = DOCS / old_rel
        dst = DOCS / new_rel
        if not src.is_file():
            if dst.is_file():
                continue
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        src.rename(dst)
        print(f"rename: {old_rel} -> {new_rel}")


def patch_text(text: str) -> str:
    for old, new in LINK_REPLACEMENTS:
        text = text.replace(old, new)
    # docs/README.md -> docs/说明.md
    text = text.replace("docs/README.md", "docs/说明.md")
    return text


def update_references() -> None:
    skip_dirs = {"backup", "web", "web/dist", "node_modules", ".git", "__pycache__"}
    exts = {".md", ".py", ".yml", ".txt", ".toml"}
    for path in MODULE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            if "docs" not in path.parts or "backup" in path.parts:
                if path.suffix in exts and "docs/backup" not in str(path).replace("\\", "/"):
                    if "docs" not in path.parts:
                        continue
        if path.suffix not in exts:
            continue
        if path.name == "rename_docs_zh.py":
            continue
        raw = path.read_text(encoding="utf-8")
        patched = patch_text(raw)
        if patched != raw:
            path.write_text(patched, encoding="utf-8", newline="\n")
            print(f"patch: {path.relative_to(MODULE_ROOT)}")


def main() -> None:
    rename_files()
    update_references()
    print("done")


if __name__ == "__main__":
    main()
