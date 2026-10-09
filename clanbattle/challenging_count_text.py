"""挑战者人数标题文案（队列行数 n 与 enter_signal 推算的 Boss 内人数 k）。"""


def format_challenging_count_line(
    queue_line_count: int,
    boss_enter_signal: int,
) -> str:
    n = max(0, int(queue_line_count))
    in_boss = max(0, int(boss_enter_signal or 0))
    if in_boss > 0 and in_boss < n:
        return f"目前有{n}人正在挑战（Boss内{in_boss}人）："
    return f"目前有{n}人正在挑战："
