from tests._module_loader import load_module

_dpb = load_module("clanbattle/damage_push_batch.py", "kcr_dpb_test")
DamagePushBlock = _dpb.DamagePushBlock
flush_damage_push_batch = _dpb.flush_damage_push_batch
group_blocks_for_merge = _dpb.group_blocks_for_merge
merge_damage_push_blocks = _dpb.merge_damage_push_blocks
merge_window_key = _dpb.merge_window_key


def _block(boss: int, ts: int, headline: str, status: str, n: int, lines=None):
    return DamagePushBlock(
        boss_order=boss,
        create_time=ts,
        headline=headline,
        status_line=status,
        challenger_count=n,
        challenger_lines=lines or [],
    )


def test_merge_window_same_second():
    """API create_time 为秒级 Unix 时间戳，同秒合刀数值相同。"""
    t = 1790582387
    assert merge_window_key(5, t) == merge_window_key(5, t)
    assert merge_window_key(5, t) != merge_window_key(5, t + 1)


def test_merge_two_headlines_one_status():
    t = 1790582387
    blocks = [
        _block(5, t, "line1", "status A", 0),
        _block(5, t, "line2", "status B", 1, ["ch1"]),
    ]
    msg = merge_damage_push_blocks(blocks)
    assert msg.splitlines()[0] == "line1"
    assert msg.splitlines()[1] == "line2"
    assert "status B" in msg
    assert "ch1" in msg
    assert msg.count("status") == 1


def test_flush_splits_boss():
    blocks = [
        _block(5, 1000, "a", "s5", 0),
        _block(3, 1000, "b", "s3", 0),
    ]
    msgs = flush_damage_push_batch(blocks, group_id=1)
    assert len(msgs) == 2


def test_challenging_header_boss_in_fight_annotation():
    block = DamagePushBlock(
        boss_order=3,
        create_time=1,
        headline="h",
        status_line="s",
        challenger_count=4,
        challenger_lines=["a", "b", "c", "d"],
        boss_enter_signal=1,
    )
    msg = merge_damage_push_blocks([block])
    assert "目前有4人正在挑战（Boss内1人）：" in msg


def test_merge_line_suffix_at_then_threshold_on_separate_lines():
    t = 1790582387
    suffix = "[CQ:at,qq=111]\n合刀线：3.5e"
    block = DamagePushBlock(
        boss_order=1,
        create_time=t,
        headline="h",
        status_line="s",
        challenger_count=2,
        challenger_lines=["a"],
        merge_line_prefix="[合刀提醒1-余2.0e-2人]",
        merge_line_suffix=suffix,
    )
    msg = merge_damage_push_blocks([block])
    lines = msg.splitlines()
    assert lines[0] == "[合刀提醒1-余2.0e-2人]"
    assert lines[-2] == "[CQ:at,qq=111]"
    assert lines[-1] == "合刀线：3.5e"


def test_group_keeps_order():
    t = 1790582387
    groups = group_blocks_for_merge(
        [
            _block(5, t, "a", "s", 0),
            _block(5, t, "b", "s2", 0),
            _block(5, t + 2, "c", "s3", 0),
        ]
    )
    assert len(groups) == 2
    assert len(groups[0]) == 2
    assert len(groups[1]) == 1
