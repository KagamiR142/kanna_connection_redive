#!/usr/bin/env python3
"""扫描仓库内疑似 QQ/群号（8～11 位），排除 HP/时间戳等常见误报。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    "node_modules",
    "web/dist",
    "devtools/output",
    "docs/backup",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
SKIP_GLOBS = ("*.png", "*.jpg", "*.woff", "*.woff2", "*.db", "*.pyc")
# 占位 QQ / 群号示例
ALLOW = {
    "100000001",
    "100000002",
    "100000003",
    "100000004",
    "100000005",
    "100000006",
    "100000007",
    "100000008",
    "100000009",
    "1000000001",
}
PATTERN = re.compile(r"\b([1-9]\d{7,10})\b")


def should_skip(path: Path) -> bool:
    rel = path.relative_to(MODULE_ROOT)
    if rel.parts[:2] == ("docs", "backup"):
        return True
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".dll", ".csv"}:
        return True
    if path.name in ("basedata.py",):
        return True
    if rel.parts[0] in ("resource", "jjckiller", "knife_budget"):
        return True
    if rel.parts[:2] == ("tests",) or rel.parts[0] == "tests":
        return True
    return False


def scan() -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    for path in MODULE_ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        if path.name in SKIP_GLOBS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in PATTERN.finditer(line):
                num = m.group(1)
                if num in ALLOW:
                    continue
                # 常见误报：Unix 时间戳（1.6e9～1.9e9）、10 位以上 HP
                n = int(num)
                if 1_600_000_000 <= n <= 2_000_000_000:
                    continue
                if n >= 100_000_000 and n % 10_000_000 == 0:
                    continue
                if "enemy_id" in line or "max_hp" in line or "current_hp" in line:
                    continue
                if "BossValue" in line or "battle_log_id" in line or "RES-VER" in line:
                    continue
                if "PLATFORM-OS-VERSION" in line or "Random(" in line:
                    continue
                if "servertime" in line or ("create_time" in line and len(num) >= 10):
                    continue
                if num.startswith("202") and len(num) == 8:
                    continue
                hits.append((str(path.relative_to(MODULE_ROOT)), i, num, line.strip()[:120]))
    return hits


def main() -> int:
    hits = scan()
    if not hits:
        print("scan_sensitive_numbers: 未发现需人工复核的 8～11 位数字（已排除 backup/ 与常见误报）")
        return 0
    print("scan_sensitive_numbers: 以下条目请人工确认是否为真实 QQ/群号：")
    for path, line_no, num, snippet in hits[:80]:
        print(f"  {path}:{line_no}  {num}  {snippet}")
    if len(hits) > 80:
        print(f"  ... 另有 {len(hits) - 80} 处")
    return 1


if __name__ == "__main__":
    sys.exit(main())
