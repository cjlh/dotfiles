# Custom kitten generated using Claude.
#
# Lists the icons namer picks from, for the active tab's icon to be chosen from
# them, keeping its name. namer caches the choice for the tab's name, so that it
# is kept until the tab is renamed or its icon picked anew. Tabs that haven't
# been renamed have no icon, and are refused with a bell, as are tabs being
# named.
#
# Enable with: map ctrl+alt+shift+o kitten choose_tab_icon.py

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING

from kittens.tui.handler import result_handler
from kitty.constants import clear_handled_signals
from kitty.fast_data_types import get_boss, wakeup_main_loop
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss

# Set on tabs to the name they were given and the icon chosen for it. Must match
# REPICK_ICON_ATTR in tab_bar.py.
REPICK_ICON_ATTR = "tab_bar_repick_icon"
# The icon tab_bar.py shows for a tab. Must match TAB_ICON_ATTR there.
TAB_ICON_ATTR = "tab_bar_icon"
# Set on tabs while name_tab.py names them. Must match NAMING_ATTR there.
NAMING_ATTR = "name_tab_previous_name"

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


def _run_namer(args: list[str], done) -> None:
    """Run namer with args in the background, then call done(output) on
    kitty's main thread, with None if it failed."""
    fd, output_path = tempfile.mkstemp(prefix="kitty-choose-tab-icon-")
    with os.fdopen(fd, "w") as output:
        process = subprocess.Popen(
            [NAMER, *args],
            env={**os.environ, "PATH": HELPER_PATH},
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.DEVNULL,
            preexec_fn=clear_handled_signals,
        )

    # kitty reaps every child process itself, so let it report the exit on
    # its main thread instead of waiting on the process.
    def on_exit(exit_status: int, err=None) -> None:
        try:
            with open(output_path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = None
        finally:
            os.unlink(output_path)
        done(text if os.waitstatus_to_exitcode(exit_status) == 0 else None)

    get_boss().monitor_pid(process.pid, on_exit)


@result_handler(no_ui=True)
def handle_result(
    args: list[str], answer: None, target_window_id: int, boss: Boss
) -> None:
    window = boss.window_id_map.get(target_window_id)
    tab = window.tabref() if window is not None else None
    if NAMER is None or tab is None or not tab.name or hasattr(tab, NAMING_ATTR):
        boss.ring_bell_if_allowed()
        return

    tab_id, name = tab.id, tab.name

    def listed(output: str | None) -> None:
        try:
            icons = {
                str(icon_id): (str(icon), str(meaning))
                for icon_id, (icon, meaning) in json.loads(output).items()
            }
        except (TypeError, ValueError, AttributeError) as e:
            log_error(f"choose_tab_icon.py: namer listed no icons: {e!r}")
            boss.ring_bell_if_allowed()
            return

        tab = boss.tab_for_id(tab_id)
        if tab is None or tab.name != name:
            return
        current = getattr(getattr(tab, TAB_ICON_ATTR, None), "icon", None)

        def chosen(icon_id: str | None) -> None:
            tab = boss.tab_for_id(tab_id)
            # Keep names given while choosing
            if icon_id not in icons or tab is None or tab.name != name:
                return
            setattr(tab, REPICK_ICON_ATTR, (name, icons[icon_id][0]))
            tab.mark_tab_bar_dirty()
            # This runs after kitty has drawn for the current loop iteration,
            # and marking the tab bar dirty does not wake it to draw again
            wakeup_main_loop()
            _run_namer(
                ["set-icon", "--", name, icon_id],
                lambda output: (
                    output is None
                    and log_error(
                        f"choose_tab_icon.py: namer failed to cache {icon_id}"
                    )
                ),
            )

        # Each icon by the first of its meanings, to fit as many lines as
        # possible in short windows, as the list can't scroll. The current icon
        # is listed but can't be chosen.
        boss.choose_entry(
            f"Choose the icon for: {name}",
            (
                (None, f"   {icon}  {meaning.split(',')[0]} (current)")
                if icon == current
                else (icon_id, f"{icon}  {meaning.split(',')[0]}")
                for icon_id, (icon, meaning) in icons.items()
            ),
            chosen,
        )

    try:
        _run_namer(["icons"], listed)
    except (OSError, RuntimeError) as e:
        log_error(f"choose_tab_icon.py: failed to run namer: {e}")
        boss.ring_bell_if_allowed()
