# Custom kitten generated using Claude.
#
# Prototype that names the active tab after the task it is being used for. The
# tab's windows (titles, working directories, running programs, last commands
# and screen text) and the Git repositories they are in are written to a
# context file, which the name-tab script from this repo's scripts package
# names with Apple's on-device model in the background.
#
# While it runs the tab shows a placeholder name, then the generated name, or
# its previous name again when the model finds no clear purpose or fails. A
# status tag such as "[todo]" at the start of the previous name is kept.
#
# Each context file and the model's response are kept in DATA_DIR, as fixtures
# for evaluating the model with name-tab.
#
# Enable with: map ctrl+alt+shift+r kitten name_tab.py

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

from kittens.tui.handler import result_handler
from kitty.constants import clear_handled_signals
from kitty.fast_data_types import add_timer, get_boss, remove_timer
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.tabs import Tab
    from kitty.window import Window

DATA_DIR = os.path.expanduser("~/.local/share/kitty/tab-names")
# Shown with its own icon by tab_bar.py, see STATUS_TAG_ICONS
PLACEHOLDER = "[naming] generating name…"
# Must match STATUS_TAG in tab_bar.py
STATUS_TAG = re.compile(r"\[(\w+)\]\s*")
# Last lines of each window's screen to include
SCREEN_LINES = 40
GIT_TIMEOUT = 2  # seconds per git command
GIT_STATUS_LINES = 20
GIT_LOG_COMMITS = 8
NAME_TAB_TIMEOUT = 120  # seconds, its first run on a machine builds its dependencies

# kitty may be launched from the Dock without Homebrew or ~/.local/bin in PATH,
# and name-tab is run by uv
HELPER_PATH = os.pathsep.join(
    [
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        os.environ.get("PATH", ""),
    ]
)
NAME_TAB = shutil.which("name-tab", path=HELPER_PATH)


def main(args: list[str]) -> None:
    pass


def _git(cwd: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            preexec_fn=clear_handled_signals,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.rstrip() if result.returncode == 0 else None


def _base_branch(root: str) -> str | None:
    """The branch the current one was likely made from."""
    if (
        default := _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    ) is not None:
        return default
    for branch in ("main", "master"):
        if _git(root, "rev-parse", "--verify", "--quiet", branch) is not None:
            return branch
    return None


def _repository_context(root: str) -> list[str]:
    branch = _git(root, "branch", "--show-current") or "(detached)"
    lines = [f"## Git repository {_home_relative(root)}", f"branch: {branch}"]

    status = (_git(root, "status", "--short") or "").splitlines()
    lines.append("status:" if status else "status: clean")
    lines += status[:GIT_STATUS_LINES]
    if len(status) > GIT_STATUS_LINES:
        lines.append(f"... and {len(status) - GIT_STATUS_LINES} more")

    base = _base_branch(root)
    merge_base = _git(root, "merge-base", "HEAD", base) if base else None
    if merge_base and branch not in (base, base.split("/")[-1]):
        if commits := _git(
            root, "log", "--oneline", f"-{GIT_LOG_COMMITS}", f"{merge_base}..HEAD"
        ):
            lines += [f"commits since {base}:", commits]
        if diff_stat := _git(root, "diff", "--stat", merge_base):
            lines += [f"changes since {base}:", diff_stat]
    elif commits := _git(root, "log", "--oneline", f"-{GIT_LOG_COMMITS}"):
        lines += ["recent commits:", commits]

    return lines


def _home_relative(path: str) -> str:
    home = os.path.expanduser("~")
    return (
        "~" + path[len(home) :]
        if path == home or path.startswith(home + os.sep)
        else path
    )


def _screen_text(window: Window) -> str:
    lines = window.as_text().rstrip().splitlines()
    return "\n".join(lines[-SCREEN_LINES:])


def _tab_context(tab: Tab) -> str:
    windows: list[Window] = list(tab)
    lines = ["## Tab"]
    roots: dict[str, None] = {}  # repository roots in window order

    for i, window in enumerate(windows, 1):
        cwd = window.cwd_of_child or ""
        command = " ".join(window.child.foreground_cmdline)
        lines.append(
            f"window {i}: title {window.title!r}, cwd {_home_relative(cwd)}, running: {command}"
        )
        if window.last_cmd_cmdline:
            lines.append(
                f"  last command: {window.last_cmd_cmdline} (exit status {window.last_cmd_exit_status})"
            )
        if cwd and (root := _git(cwd, "rev-parse", "--show-toplevel")):
            roots[root] = None

    for root in roots:
        lines += ["", *_repository_context(root)]

    for i, window in enumerate(windows, 1):
        if text := _screen_text(window):
            lines += ["", f"## Window {i} screen (last lines)", text]

    return "\n".join(lines) + "\n"


def _normalise_title(title: str) -> str:
    # The model is asked for words separated by spaces, but sometimes joins
    # them with underscores or hyphens instead
    title = title.strip()

    if " " not in title:
        title = title.replace("_", " ").replace("-", " ")

    return title


def _generated_title(output_path: str) -> str | None:
    try:
        with open(output_path, encoding="utf-8") as f:
            result = json.loads(f.read())
    except (OSError, ValueError):
        return None

    if "error" in result:
        log_error(f"name_tab.py: {result['error']}: {result.get('message')}")
        return None

    # Without a clear purpose the model gives "none" as the title rather than null
    title = result.get("title")
    if not result.get("has_clear_purpose") or not isinstance(title, str):
        return None
    title = _normalise_title(title)
    return title if title and title.lower() not in ("none", "null") else None


def _run_name_tab(context_path: str, output_path: str, done) -> None:
    """Run name-tab in the background, then call done(exit_code) on kitty's
    main thread, with None if it took longer than NAME_TAB_TIMEOUT seconds."""
    with open(output_path, "w") as output:
        process = subprocess.Popen(
            [NAME_TAB, "--json", context_path],
            env={**os.environ, "PATH": HELPER_PATH},
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.DEVNULL,
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

    timeout_timer = add_timer(on_timeout, NAME_TAB_TIMEOUT, False)
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
    if NAME_TAB is None or tab is None or tab.name == PLACEHOLDER:
        boss.ring_bell_if_allowed()
        return

    previous_name = tab.name
    match = STATUS_TAG.match(previous_name)
    status_tag = match.group(0) if match else ""
    tab_id = tab.id

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        stem = os.path.join(DATA_DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-tab{tab_id}")
        context_path, output_path = f"{stem}.txt", f"{stem}.json"
        with open(context_path, "w", encoding="utf-8") as f:
            f.write(_tab_context(tab))
    except Exception as e:
        log_error(f"name_tab.py: failed to collect context: {e}")
        boss.ring_bell_if_allowed()
        return

    tab.set_title(PLACEHOLDER)

    def done(exit_code: int | None) -> None:
        tab = boss.tab_for_id(tab_id)
        # Keep names given while the model was running
        if tab is None or tab.name != PLACEHOLDER:
            return
        if exit_code != 0:
            log_error(f"name_tab.py: name-tab failed with exit code {exit_code}")
        title = _generated_title(output_path) if exit_code == 0 else None
        tab.set_title(status_tag + title if title else previous_name)

    try:
        _run_name_tab(context_path, output_path, done)
    except OSError as e:
        log_error(f"name_tab.py: failed to run name-tab: {e}")
        tab.set_title(previous_name)
