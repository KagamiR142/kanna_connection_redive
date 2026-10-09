#!/usr/bin/env python3
"""修复 docs 内仅文件名（无目录前缀）的英文链接。"""
from __future__ import annotations

from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS = MODULE_ROOT / "docs"

BARE = {
    "game-rules.md": "游戏规则.md",
    "platform.md": "平台需求.md",
    "challenge-queue.md": "挑战队列.md",
    "knife-budget.md": "刀型预算.md",
    "monitor-and-status.md": "监控与状态图.md",
    "report-images.md": "战报图.md",
    "webui.md": "网页端.md",
    "architecture.md": "架构.md",
    "permissions.md": "权限模型.md",
    "api-reference.md": "API参考.md",
    "refactor-plan.md": "重构计划.md",
    "data-paths.md": "数据目录.md",
    "security-checklist.md": "安全检查清单.md",
    "quick-start.md": "快速上手.md",
    "clanbattle.md": "自动报刀.md",
    "account-binding.md": "账号绑定.md",
    "deployment.md": "部署要点.md",
    "installation.md": "安装指南.md",
    "commands/clanbattle.md": "commands/会战指令.md",
}


def main() -> None:
    for md in DOCS.rglob("*.md"):
        if "backup" in md.parts:
            continue
        text = md.read_text(encoding="utf-8")
        orig = text
        for old, new in sorted(BARE.items(), key=lambda x: -len(x[0])):
            text = text.replace(f"]({old})", f"]({new})")
            text = text.replace(f"](../{old})", f"](../{new})")
            text = text.replace(f"](../../{old})", f"](../../{new})")
        if text != orig:
            md.write_text(text, encoding="utf-8", newline="\n")
            print(f"fixed: {md.relative_to(MODULE_ROOT)}")

    # 代码与测试中的帮助源路径
    for rel in (
        "scripts/sync_help_text.py",
        "tests/test_user_help.py",
    ):
        p = MODULE_ROOT / rel
        t = p.read_text(encoding="utf-8")
        t2 = t.replace("clanbattle-help.qq.txt", "自动报刀帮助.qq.txt")
        if t2 != t:
            p.write_text(t2, encoding="utf-8", newline="\n")
            print(f"fixed: {rel}")

    # 部署要点中 devtools 链接应保持 README.md
    dep = DOCS / "user" / "部署要点.md"
    if dep.is_file():
        t = dep.read_text(encoding="utf-8")
        t = t.replace("../../devtools/说明.md", "../../devtools/README.md")
        dep.write_text(t, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
