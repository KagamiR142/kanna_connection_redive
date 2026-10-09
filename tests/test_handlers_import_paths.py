"""clanbattle/handlers 相对 import 层级回归（须用 ... 引用模块根包）。"""
from __future__ import annotations

import ast
from pathlib import Path

HANDLERS_DIR = Path(__file__).resolve().parents[1] / "clanbattle" / "handlers"

# 位于 kanna_connection_redive 根下的包，handlers 内须 from ...pkg
ROOT_PACKAGES = frozenset(
    {
        "basedata",
        "challenge",
        "client",
        "database",
        "knife_budget",
        "member",
        "rbac",
        "setting",
        "util",
        "webui",
    }
)


def _bad_root_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        top = node.module.split(".", 1)[0]
        if top not in ROOT_PACKAGES:
            continue
        if node.level == 2:
            bad.append(f"{path.name}:{node.lineno} from ..{node.module}")
    return bad


def test_handlers_do_not_use_double_dot_for_root_packages() -> None:
    violations: list[str] = []
    for py in sorted(HANDLERS_DIR.glob("*.py")):
        if py.name == "__init__.py":
            continue
        violations.extend(_bad_root_imports(py))
    assert not violations, "handlers root imports must use ...:\n" + "\n".join(violations)
