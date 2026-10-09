#!/usr/bin/env python3
"""将本模块复制到独立目录并初始化「无历史」的 Git 仓库（仅用于推送到 GitHub）。"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
SKIP_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
}
SKIP_REL_PREFIXES = (
    "data/",
    "docs/backup/",
    "devtools/output/",
    "log/",
    "logs/",
    "web/node_modules/",
)


def _rel(path: Path) -> str:
    return path.relative_to(MODULE_ROOT).as_posix()


def should_skip(path: Path) -> bool:
    if path == MODULE_ROOT:
        return False
    rel = _rel(path)
    if any(part in SKIP_NAMES for part in path.parts):
        return True
    if any(rel == p.rstrip("/") or rel.startswith(p) for p in SKIP_REL_PREFIXES):
        return True
    if path.suffix in {".pyc", ".log"}:
        return True
    return False


def copy_module(dest: Path) -> None:
    if dest.resolve() == MODULE_ROOT.resolve():
        raise SystemExit("目标目录不能与模块根相同")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for src in MODULE_ROOT.rglob("*"):
        if should_skip(src):
            continue
        rel = src.relative_to(MODULE_ROOT)
        dst = dest / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def init_git(dest: Path, message: str) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=KagamiR142",
            "-c",
            "user.email=KagamiR142@users.noreply.github.com",
            "commit",
            "-m",
            message,
        ],
        cwd=dest,
        check=True,
    )
    remote = "https://github.com/KagamiR142/kanna_connection_redive.git"
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=dest, check=True)


def main() -> int:
    default_dest = MODULE_ROOT.parents[5] / "kanna_connection_redive"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dest",
        type=Path,
        default=default_dest,
        help=f"发布目录（默认 {default_dest})",
    )
    p.add_argument(
        "--no-git",
        action="store_true",
        help="只复制文件，不 git init / commit",
    )
    p.add_argument(
        "--message",
        default="Initial public release of kanna_connection_redive (KCR).",
    )
    args = p.parse_args()
    copy_module(args.dest.resolve())
    print(f"copied -> {args.dest}")
    if not args.no_git:
        init_git(args.dest.resolve(), args.message)
        print("git: main @ single commit, remote origin set (not pushed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
