from tests._module_loader import load_module

_mod = load_module("clanbattle/challenging_count_text.py", "kcr_chal_count_test")
format_challenging_count_line = _mod.format_challenging_count_line


def test_challenging_count_plain_when_in_boss_ge_queue():
    assert format_challenging_count_line(4, 4) == "目前有4人正在挑战："
    assert format_challenging_count_line(3, 5) == "目前有3人正在挑战："


def test_challenging_count_plain_when_in_boss_zero():
    assert format_challenging_count_line(4, 0) == "目前有4人正在挑战："


def test_challenging_count_annotated_when_in_boss_lt_queue():
    assert (
        format_challenging_count_line(4, 1)
        == "目前有4人正在挑战（Boss内1人）："
    )
