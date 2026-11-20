# Custom kitten generated using Claude.
#
# Marks a program's status as seen when it reports it in the window the user is
# looking at. Programs such as Claude Code and Codex report whether they are
# working, waiting on the user, done or failed with OSC 7501, and kitty keeps
# "done" and "error" until the user has seen them. kitty only counts them as
# seen when the window gains focus though, so a program that finishes while the
# user watches it would stay "done", and tab_bar.py would colour its tab as
# soon as the user left it.
#
# Requires kitty >= 0.50.0, does nothing on older versions.
#
# Enable with: watcher program_status_seen.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kitty.fast_data_types import add_timer, current_focused_os_window_id

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.window import Window


def _is_seen(boss: Boss, window: Window) -> bool:
    # While kitty is in the background, its active window is that of the OS
    # window focused last, which the user can't see
    return (
        not window.destroyed
        and window.os_window_id == current_focused_os_window_id()
        and window is boss.active_window
    )


def on_program_status_change(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # kitty calls this while it parses the program's output, so mark the
    # status as seen afterwards
    def mark_seen(timer_id: int | None = None) -> None:
        if _is_seen(boss, window):
            window.program_status_seen_by_user()

    add_timer(mark_seen, 0, False)
