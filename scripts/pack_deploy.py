#!/usr/bin/env python3
"""
将 kanna_connection_redive 模块打包为 zip，用于覆盖部署到服务器。

设计原则：zip 内**不包含**运行时配置与数据库，解压覆盖时不会冲掉服务器上的：
  - resource/data/setting_clanbattle.json
  - resource/data/data.db
  - resource/data/token.json
  - 等（见 EXCLUDE_*）

用法（在模块根目录）:
  scripts\\pack_deploy.bat              # Windows：本地 npm build + 打包（推荐）
  scripts\\pack_deploy.bat --skip-web  # 仅打包 Python/文档，不含 web/dist
  python scripts/pack_deploy.py
  python scripts/pack_deploy.py --with-web-dist   # 附带已构建的 web/dist

服务器部署（无需 npm）:
  1. 停 bot
  2. 备份 resource/data/setting_clanbattle.json 与 resource/data/data.db
  3. 解压到 HoshinoBot-master/hoshino/modules/kanna_connection_redive/（覆盖）
  4. zip 若含 web/dist，会直接覆盖服务器前端静态文件
  5. 启动 bot
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import zipfile
from datetime import datetime
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]

# 整目录跳过（相对模块根）
EXCLUDE_DIR_NAMES = {
    ".git",
    ".github",
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "__pycache__",
    "archive_output",
    "build",
    "data",  # 模块根 legacy 运行时目录（若存在）
    "devtools/output",
    "dist",
    "node_modules",
    "samples",
}

# 相对路径通配（Unix 风格）
EXCLUDE_FILE_PATTERNS = (
    "*.pyc",
    "*.pyo",
    "*.log",
    "resource/data/data.db",
    "resource/data/setting_clanbattle.json",
    "resource/data/token.json",
    "resource/data/rungroup.json",
    "resource/data/homework_cache.json",
    "resource/data/web_ops_log.jsonl",
    "resource/data/boss_info.json",
    "resource/data/temp/*",
    "web/.env",
    "web/.env.*",
    "web/dist-ssr/**",
    "web/vite.config.ts.timestamp-*.mjs",
    "rungroup.json",
    "clanbattlework.json",
    "data.db",
    "token.json",
)


def _rel_posix(path: Path) -> str:
    return path.relative_to(MODULE_ROOT).as_posix()


def _skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIR_NAMES


def _skip_file(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    for pat in EXCLUDE_FILE_PATTERNS:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def iter_files(include_web_dist: bool) -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in os.walk(MODULE_ROOT):
        dirs[:] = [d for d in dirs if not _skip_dir(d)]
        root_path = Path(root)
        for name in files:
            full = root_path / name
            rel = _rel_posix(full)
            if _skip_file(rel):
                continue
            if not include_web_dist and rel.startswith("web/dist/"):
                continue
            out.append(full)
    return sorted(out)


def pack(output: Path, include_web_dist: bool) -> tuple[Path, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    files = iter_files(include_web_dist)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for full in files:
            zf.write(full, _rel_posix(full))
    return output, len(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出 zip 路径（默认 dist/kcr-deploy-YYYYMMDD-HHMMSS.zip）",
    )
    parser.add_argument(
        "--with-web-dist",
        action="store_true",
        help="包含 web/dist（需本地已 npm run build）",
    )
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.output or (MODULE_ROOT / "dist" / f"kcr-deploy-{stamp}.zip")
    path, n = pack(out.resolve(), args.with_web_dist)
    print(f"已打包 {n} 个文件 -> {path}")
    print("未打入 zip（服务器上保留原文件）:")
    for line in (
        "  resource/data/setting_clanbattle.json",
        "  resource/data/data.db",
        "  resource/data/token.json",
        "  resource/data/boss_info.json（若服务器已刷新）",
        "  web/node_modules、__pycache__ 等",
    ):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
