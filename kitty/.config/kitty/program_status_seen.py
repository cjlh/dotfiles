# Custom kitten generated using Claude.
#
# Clear completion and error statuses reported while the user is watching.
# kitty normally clears them when the window gains focus, so a task that
# finishes in an already-focused window can otherwise keep its status.
#
# Requires kitty >= 0.50.0.
# Enable with: watcher program_status_seen.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kitty.fast_data_types import add_timer, current_focused_os_window_id

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.window import Window


def _is_seen(boss: Boss, window: Window) -> bool:
    # kitty retains an active window even when the application is in the background.
    return (
        not window.destroyed
        and window.os_window_id == current_focused_os_window_id()
        and window is boss.active_window
    )


def on_program_status_change(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # Wait until kitty has finished parsing the output before clearing the status.
    def mark_seen(timer_id: int | None = None) -> None:
        if _is_seen(boss, window):
            window.program_status_seen_by_user()

    add_timer(mark_seen, 0, False)
