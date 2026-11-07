# Custom kitten generated using Claude.
#
# Saves kitty's session, including scrollback, whenever kitty quits, so that
# restore_session_after_logout in kitty.conf restores it the next time kitty
# starts. kitty itself only saves it when logging out, restarting or shutting
# down the computer.
#
# It is saved when quitting and when the last OS window is closed by hand, which
# quits kitty without an on_quit event. kitty has no event for that, so this
# wraps the internal Boss.mark_os_window_for_close, which the close button and
# close_os_window end in. Nothing is saved when the last window closes because
# its program exited, as then there is nothing left to restore.
#
# Instances started with a command or --session are not saved, as kitty would
# restore them as extra instances the next time it starts.
#
# Requires kitty >= 0.50.0, does nothing on older versions.
#
# Enable with: watcher save_session_on_quit.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kitty.fast_data_types import IMPERATIVE_CLOSE_REQUESTED
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.window import Window

# Set on the boss once mark_os_window_for_close is wrapped, as kitty loads this
# file again when the config is reloaded
WRAPPED_ATTR = "save_session_on_quit_wrapped"


def _save(boss: Boss) -> None:
    if not hasattr(boss, "save_session_at_logout") or boss.args.args or boss.args.session:
        return
    try:
        boss.save_session_at_logout()
    except Exception as e:
        log_error(f"save_session_on_quit: failed to save the session: {e}")


def on_load(boss: Boss, data: dict[str, Any]) -> None:
    if getattr(boss, WRAPPED_ATTR, False):
        return
    setattr(boss, WRAPPED_ATTR, True)
    mark_for_close = boss.mark_os_window_for_close

    def mark_os_window_for_close(os_window_id: int, *args: Any, **kwargs: Any) -> None:
        try:
            request_type = args[0] if args else kwargs.get("request_type", IMPERATIVE_CLOSE_REQUESTED)
            if request_type == IMPERATIVE_CLOSE_REQUESTED and set(boss.os_window_map) == {os_window_id}:
                _save(boss)
        except Exception as e:
            log_error(f"save_session_on_quit: failed to check the closed OS window: {e}")
        mark_for_close(os_window_id, *args, **kwargs)

    boss.mark_os_window_for_close = mark_os_window_for_close  # type: ignore[method-assign]


def on_quit(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    if data.get("confirmed") and not data.get("aborted"):
        _save(boss)
