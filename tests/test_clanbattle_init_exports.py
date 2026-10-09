"""clanbattle 包须向 webui/captcha 再导出 registry 符号。"""
from __future__ import annotations

from pathlib import Path

INIT = Path(__file__).resolve().parents[1] / "clanbattle" / "__init__.py"


def test_clanbattle_init_reexports_registry_symbols() -> None:
    text = INIT.read_text(encoding="utf-8")
    assert "from .registry import" in text
    for name in ("clanbattle_info", "clanbattle_pool", "notice_update_time"):
        assert name in text
