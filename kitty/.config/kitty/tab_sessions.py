# Custom kitten generated using Claude.
#
# Saves every tab that has been renamed with set_tab_title to a session file,
# which startup_session in kitty.conf restores when kitty next starts. Tabs keep
# their name, layout, windows and working directories. Programs in
# RESTORED_PROGRAMS that were running in a window are started again, other
# commands are not, as they may not be safe to re-run.
#
# The file is saved shortly after any change to the tab bar and when kitty
# quits. Closing the last OS window does not clear it, so quitting that way
# restores the tabs that were open beforehand.
#
# Enable with: watcher tab_sessions.py

from __future__ import annotations

import json
import os
import shlex
from typing import TYPE_CHECKING, Any

from kitty.config import atomic_save
from kitty.constants import unserialize_launch_flag
from kitty.fast_data_types import add_timer, get_boss
from kitty.session import default_save_as_session_opts
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.tabs import TabManager
    from kitty.window import Window

# Must match startup_session in kitty.conf
SESSION_PATH = os.path.expanduser("~/.local/share/kitty/named-tabs.kitty-session")
# Seconds to wait after a change before saving, so bursts of changes save once
SAVE_DELAY = 1.0
# Foreground programs that are restarted in their window when restoring
RESTORED_PROGRAMS = frozenset({"nvim", "vim", "less", "man", "htop", "btop", "top"})

_pending = False
_quitting = False
# Until this kitty has had a named tab, an existing session file belongs to an
# earlier kitty (e.g. this one was started with a command, which skips
# startup_session) and must not be overwritten.
_seen_named_tabs = False


def _schedule() -> None:
    global _pending
    if not _pending and not _quitting:
        _pending = True
        add_timer(_save_after_delay, SAVE_DELAY, False)


def _save_after_delay(timer_id: int | None) -> None:
    global _pending
    _pending = False
    if not _quitting:
        _save()


def _restorable_program(cmd: list[str] | str) -> bool:
    argv = shlex.split(cmd) if isinstance(cmd, str) else cmd
    return bool(argv) and os.path.basename(argv[0]) in RESTORED_PROGRAMS


def _filter_launch(line: str) -> str:
    """Drop the foreground command from a launch line unless it is safe to re-run."""
    if not line.startswith("launch "):
        return line
    args = shlex.split(line)
    for i, arg in enumerate(args):
        if arg.startswith(unserialize_launch_flag):
            data = json.loads(arg[len(unserialize_launch_flag) :])
            cmd = data.get("cmd_at_shell_startup")
            if cmd is not None and not _restorable_program(cmd):
                del data["cmd_at_shell_startup"]
                args[i] = unserialize_launch_flag + json.dumps(data)
                return shlex.join(args)
    return line


def _serialize_tab_manager(tm: TabManager, windows: frozenset[Window], is_first: bool) -> list[str]:
    opts = default_save_as_session_opts()
    opts.use_foreground_process = True
    lines = tm.serialize_state_as_session(SESSION_PATH, windows, opts, is_first=is_first)
    # kitty indexes focus_tab among all tabs, but only named tabs are saved
    named = [t for t in tm.tabs if t.name]
    lines = [_filter_launch(line) for line in lines if not line.startswith("focus_tab ")]
    if tm.active_tab in named:
        lines += ["", f"focus_tab {named.index(tm.active_tab)}"]
    return lines


def _save() -> None:
    global _seen_named_tabs
    boss = get_boss()
    # Nothing to save while the last OS window closes, keep what it had open
    if not boss.os_window_map:
        return

    windows = frozenset(w for t in boss.all_tabs if t.name for w in t)
    if windows:
        _seen_named_tabs = True
    elif not _seen_named_tabs:
        return

    lines: list[str] = []
    for tm in boss.all_tab_managers:
        lines += _serialize_tab_manager(tm, windows, is_first=not lines)

    try:
        if lines:
            os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
            atomic_save("\n".join(lines).encode(), SESSION_PATH)
        else:
            # Without a session file kitty starts with its usual single tab
            os.unlink(SESSION_PATH)
    except FileNotFoundError:
        pass
    except Exception as e:
        log_error(f"tab_sessions: failed to save {SESSION_PATH}: {e}")


def on_tab_bar_dirty(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # Renames, new and closed tabs, and window title changes (which follow the
    # working directory and running program) all mark the tab bar dirty
    _schedule()


def on_quit(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    global _quitting
    if data.get("confirmed") and not data.get("aborted"):
        _save()
        # Closing the remaining tabs must not overwrite what was just saved
        _quitting = True
