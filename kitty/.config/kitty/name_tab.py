# Custom kitten generated using Claude.
#
# Prototype that names the active tab after the task it is being used for. A
# snapshot of the tab's windows (titles, working directories, running programs,
# last commands and screen text) is named in the background by the namer script
# from this repo's scripts package, which adds the state of the Git
# repositories they are in. A decision model, d1-2B, decides whether it shows
# what the tab is being used for; only then does Apple's on-device model name
# it, and d1-2B pick an icon for the name.
#
# While it runs the tab keeps its name, with a spinner drawn by tab_bar.py in
# place of its icon. It is then renamed with the generated name and icon, unless
# the models find no clear purpose or fail, or the tab was renamed meanwhile. A
# status tag such as "[todo]" at the start of the previous name is kept. If the
# tab isn't renamed, or no icon was picked with its name, tab_bar.py picks its
# icon anew.
#
# Each context given to the models, their response (with d1-2B's probability
# that the tab has a purpose) and any errors from namer are kept in DATA_DIR,
# as fixtures for evaluating the models with 'namer eval'.
#
# Enable with: map ctrl+alt+shift+r kitten name_tab.py

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING

from kittens.tui.handler import result_handler
from kitty.constants import clear_handled_signals
from kitty.fast_data_types import add_timer, get_boss, remove_timer, wakeup_main_loop
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.window import Window

DATA_DIR = os.path.expanduser("~/.local/share/kitty/tab-names")
# Set on tabs while their name is generated, to the name they had then, so
# that tab_bar.py draws a spinner for them. Must match NAMING_ATTR there.
NAMING_ATTR = "name_tab_previous_name"
# Set on tabs to have tab_bar.py pick their icon anew, or to the name they were
# given and the icon picked with it. Must match REPICK_ICON_ATTR there.
REPICK_ICON_ATTR = "tab_bar_repick_icon"
# Must match STATUS_TAG in tab_bar.py
STATUS_TAG = re.compile(r"\[(\w+)\]\s*")
# Last lines of each window's screen to include
SCREEN_LINES = 40
# seconds; its first run on a machine installs the models' libraries and
# downloads d1-2B (1.35 GB)
NAMER_TIMEOUT = 600

# kitty may be launched from the Dock without Homebrew or ~/.local/bin in PATH,
# and namer is run by uv
HELPER_PATH = os.pathsep.join(
    [
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        os.environ.get("PATH", ""),
    ]
)
NAMER = shutil.which("namer", path=HELPER_PATH)


def main(args: list[str]) -> None:
    pass


def _screen_text(window: Window) -> str:
    lines = window.as_text().rstrip().splitlines()
    return "\n".join(lines[-SCREEN_LINES:])


def _window_snapshot(window: Window) -> dict:
    """What namer is given about a window, see 'namer tab --help'."""
    # The program the shell started is the oldest process in the foreground,
    # kitty otherwise takes the newest, such as a language server started by an
    # editor or agent
    oldest = min(window.child.foreground_processes, key=lambda p: p["pid"], default=None)
    command = (oldest and oldest["cmdline"]) or window.child.cmdline
    return {
        "title": window.title,
        "cwd": window.get_cwd_of_child(oldest=True) or "",
        "command": " ".join(command),
        "last_command": window.last_cmd_cmdline or None,
        "last_exit_status": window.last_cmd_exit_status,
        "screen": _screen_text(window),
    }


def _result(output_path: str) -> dict:
    """namer's output, empty if it printed none."""
    try:
        with open(output_path, encoding="utf-8") as f:
            result = json.load(f)
    except (OSError, ValueError):
        return {}
    return result if isinstance(result, dict) else {}


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _run_namer(args: list[str], output_path: str, log_path: str, done) -> None:
    """Run namer with args in the background, then call done(exit_code) on
    kitty's main thread, with None if it took longer than NAMER_TIMEOUT seconds."""
    with open(output_path, "w") as output, open(log_path, "w") as log:
        process = subprocess.Popen(
            [NAMER, *args],
            env={**os.environ, "PATH": HELPER_PATH},
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=log,
            preexec_fn=clear_handled_signals,
        )

    finished = False

    def finish(exit_code: int | None) -> None:
        nonlocal finished
        if not finished:
            finished = True
            done(exit_code)

    # kitty reaps every child process itself, so let it report the exit on
    # its main thread instead of waiting on the process.
    def on_exit(exit_status: int, err=None) -> None:
        remove_timer(timeout_timer)
        process.returncode = os.waitstatus_to_exitcode(exit_status)
        finish(process.returncode)

    def on_timeout(timer_id=None) -> None:
        try:
            process.kill()
        except OSError:
            pass
        finish(None)

    timeout_timer = add_timer(on_timeout, NAMER_TIMEOUT, False)
    try:
        get_boss().monitor_pid(process.pid, on_exit)
    except RuntimeError:
        remove_timer(timeout_timer)
        on_timeout()


@result_handler(no_ui=True)
def handle_result(
    args: list[str], answer: None, target_window_id: int, boss: Boss
) -> None:
    window = boss.window_id_map.get(target_window_id)
    tab = window.tabref() if window is not None else None
    # Also refuse tabs that are already being named
    if NAMER is None or tab is None or hasattr(tab, NAMING_ATTR):
        boss.ring_bell_if_allowed()
        return

    tab_id = tab.id
    snapshot_path = None

    # Only what kitty knows is collected here, on its main thread, the rest by
    # namer in the background
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        stem = os.path.join(DATA_DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-tab{tab_id}")
        context_path, output_path, log_path = (
            f"{stem}.txt",
            f"{stem}.json",
            f"{stem}.log",
        )
        snapshot = {"windows": [_window_snapshot(w) for w in tab]}
        fd, snapshot_path = tempfile.mkstemp(prefix="kitty-name-tab-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot, f)
    except Exception as e:
        log_error(f"name_tab.py: failed to collect snapshot: {e}")
        if snapshot_path is not None:
            _unlink(snapshot_path)
        boss.ring_bell_if_allowed()
        return

    setattr(tab, NAMING_ATTR, tab.name)
    # Picked once naming finishes, the spinner is shown in its place until then
    setattr(tab, REPICK_ICON_ATTR, True)
    tab.mark_tab_bar_dirty()

    def done(exit_code: int | None) -> None:
        _unlink(snapshot_path)
        tab = boss.tab_for_id(tab_id)
        if tab is None:
            return
        previous_name = getattr(tab, NAMING_ATTR)
        delattr(tab, NAMING_ATTR)

        result = _result(output_path)
        if "error" in result:
            log_error(f"name_tab.py: {result['error']}: {result.get('message')}")
        elif exit_code != 0:
            log_error(
                f"name_tab.py: namer failed with exit code {exit_code}, see {log_path}"
            )

        # namer gives no label when the models find no clear purpose
        label = result.get("label") if exit_code == 0 else None
        # Keep names given while the model was running
        if isinstance(label, str) and label and tab.name == previous_name:
            match = STATUS_TAG.match(previous_name)
            name = (match.group(0) if match else "") + label
            if isinstance(icon := result.get("icon"), str) and icon:
                setattr(tab, REPICK_ICON_ATTR, (name, icon))
            tab.set_title(name)
        else:
            # Stop drawing the spinner
            tab.mark_tab_bar_dirty()
        # This runs after kitty has drawn for the current loop iteration, and
        # marking the tab bar dirty does not wake it to draw again
        wakeup_main_loop()

        # Only keep logs with something in them
        try:
            if os.path.getsize(log_path) == 0:
                os.unlink(log_path)
        except OSError:
            pass

    try:
        _run_namer(
            ["tab", "--save-context", context_path, snapshot_path],
            output_path,
            log_path,
            done,
        )
    except OSError as e:
        log_error(f"name_tab.py: failed to run namer: {e}")
        _unlink(snapshot_path)
        delattr(tab, NAMING_ATTR)
        tab.mark_tab_bar_dirty()
