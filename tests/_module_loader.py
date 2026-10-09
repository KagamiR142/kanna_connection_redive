"""在不加载 clanbattle/__init__.py（依赖 Hoshino）的情况下导入子模块。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PKG = "kanna_connection_redive"


def _ensure_package(name: str, path: Path) -> None:
    if name in sys.modules:
        return
    mod = ModuleType(name)
    mod.__path__ = [str(path)]
    sys.modules[name] = mod


def _ensure_parent_packages(rel_path: str) -> str:
    """注册 kanna_connection_redive.* 包链，供相对 import 使用。"""
    _ensure_package(PKG, ROOT)
    parts = Path(rel_path).parts
    for i in range(len(parts) - 1):
        sub = parts[: i + 1]
        name = PKG + "." + ".".join(sub)
        _ensure_package(name, ROOT.joinpath(*sub))
    if len(parts) > 1:
        return PKG + "." + ".".join(parts[:-1])
    return PKG


def load_module(rel_path: str, module_name: str) -> ModuleType:
    path = ROOT / rel_path
    package = _ensure_parent_packages(rel_path)
    qualname = PKG + "." + Path(rel_path).with_suffix("").as_posix().replace("/", ".")
    spec = importlib.util.spec_from_file_location(
        qualname,
        path,
        submodule_search_locations=[str(path.parent)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = package
    sys.modules[module_name] = mod
    sys.modules[qualname] = mod
    spec.loader.exec_module(mod)
    return mod
