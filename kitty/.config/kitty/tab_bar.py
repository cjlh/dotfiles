# Custom tab bar that displays available disk space, Codex and Claude Code
# usage in the far right corner. Disk space is sampled every redraw interval.
# All providers read JSON caches in ~/.cache/kitty-tab-bar and refresh them
# concurrently in the background. Agent usage is refreshed every
# CCUSAGE_REFRESH_INTERVAL seconds.
#
# Renamed tabs are marked with an icon, see RENAMED_TAB_ICON_MODE. In "dynamic"
# mode the icon is picked by the pick-icon script from this repo's scripts
# package, which is run in the background whenever a tab is renamed, see
# PickedIcons. If it fails the tab shows RENAMED_TAB_FIXED_ICON until renamed.
# Names starting with a status tag, such as "[done] some task", show the
# status's icon in place of the tag instead, see STATUS_TAG_ICONS.
#
# While name_tab.py generates a tab's name, or pick-icon picks its icon, the icon
# is replaced by a spinner, which a timer animates only while some tab is
# waiting. Redraws that change nothing but what is drawn, such as the spinner's,
# set DRAW_ONLY_ATTR so that watchers can skip their work, see
# _mark_tab_bar_dirty.
#
# kitty runs this file again when its config is reloaded, see _shared. It draws
# with the copy loaded by the previous reload though, as it only forgets that
# copy after applying the reloaded config, so edits here take two reloads.
# See: https://github.com/kovidgoyal/kitty/discussions/4447

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Literal

from kitty.boss import get_boss
from kitty.constants import clear_handled_signals
from kitty.fast_data_types import (
    Screen,
    add_timer,
    remove_timer,
    wakeup_main_loop,
    wcswidth,
)
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    as_rgb,
    draw_tab_with_separator,
)
from kitty.utils import log_error

CCUSAGE_REFRESH_INTERVAL = 300  # seconds between ccusage runs
CCUSAGE_TIMEOUT = 120  # seconds before a ccusage run is killed
DISK_TIMEOUT = 5  # seconds before a disk query is abandoned
DISK_POLL_INTERVAL = 0.01  # seconds between checks for a finished disk query
REDRAW_INTERVAL = 30  # seconds between tab bar redraws
# When this copy of the module was loaded, see _shared
LOADED_AT = time.monotonic()
CACHE_DIR = os.path.expanduser("~/.cache/kitty-tab-bar")
STATUS_FG = as_rgb(0x656565)
MAX_SHORT_TITLE_LENGTH = 24
PICK_ICON_TIMEOUT = 120  # seconds, its first run on a machine builds its dependencies

# kitty may be launched from the Dock without Homebrew or ~/.local/bin in PATH.
HELPER_PATH = os.pathsep.join(
    [
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        os.environ.get("PATH", ""),
    ]
)
PICK_ICON = shutil.which("pick-icon", path=HELPER_PATH)

TabIconMode = Literal["dynamic", "fixed"]

# "dynamic" has the pick-icon script pick an icon to suit the tab's name, which
# needs both it and uv to be present
RENAMED_TAB_ICON_MODE: TabIconMode = (
    "dynamic" if PICK_ICON and shutil.which("uv", path=HELPER_PATH) else "fixed"
)

# Alternatives: ✎, ★, ✦, ⚐
RENAMED_TAB_FIXED_ICON = "⚑"

# Tags that replace a renamed tab's icon, matched case-insensitively
STATUS_TAG_ICONS = {
    "todo": "☐",
    "done": "☑",
    "failed": "☒",
}
STATUS_TAG = re.compile(r"\[(\w+)\]\s*")

# Set on tabs by name_tab.py while it generates their name, must match there
NAMING_ATTR = "name_tab_previous_name"

# Set on tabs by name_tab.py to have their icon picked anew, rather than taken
# from pick-icon's cache, must match there
REPICK_ICON_ATTR = "tab_bar_repick_icon"

# Set on renamed tabs to their TabIcon in "dynamic" mode
TAB_ICON_ATTR = "tab_bar_icon"

# Shown in place of the icon of tabs being named or waiting for their icon,
# one frame per interval
SPINNER_FRAMES = "⠦⠖⠲⠴"
SPINNER_INTERVAL = 0.12  # seconds

# Set on a tab manager while its tab bar is marked dirty only to be redrawn,
# with nothing about its tabs or windows changed. on_tab_bar_dirty is called
# synchronously, so watchers that only care about changes return early while it
# is set. Must match tab_sessions.py and stack_bar.py, and any new watcher with
# an on_tab_bar_dirty handler should check it too.
DRAW_ONLY_ATTR = "tab_bar_draw_only"


def _statvfs_capacity(path: str) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def _foundation_disk_capacity_query():
    """Build a Finder-style available capacity query (including storage macOS
    can reclaim) by calling Foundation directly through ctypes."""
    import ctypes

    objc = ctypes.CDLL("/usr/lib/libobjc.dylib")
    foundation = ctypes.CDLL(
        "/System/Library/Frameworks/Foundation.framework/Foundation"
    )
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_autoreleasePoolPush.restype = ctypes.c_void_p
    objc.objc_autoreleasePoolPop.argtypes = [ctypes.c_void_p]

    def objc_method(selector: bytes, restype, *argtypes):
        """objc_msgSend cast to the signature of one Objective-C method."""
        send = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(
            ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        )
        sel = objc.sel_registerName(selector)
        return lambda receiver, *args: send(receiver, sel, *args)

    ns_string = objc.objc_getClass(b"NSString")
    ns_url = objc.objc_getClass(b"NSURL")
    string_with_utf8 = objc_method(
        b"stringWithUTF8String:", ctypes.c_void_p, ctypes.c_char_p
    )
    file_url_with_path = objc_method(
        b"fileURLWithPath:", ctypes.c_void_p, ctypes.c_void_p
    )
    get_resource_value = objc_method(
        b"getResourceValue:forKey:error:",
        ctypes.c_bool,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    long_long_value = objc_method(b"longLongValue", ctypes.c_longlong)
    important_capacity_key = ctypes.c_void_p.in_dll(
        foundation, "NSURLVolumeAvailableCapacityForImportantUsageKey"
    ).value
    if not (ns_string and ns_url and important_capacity_key):
        raise OSError("Unable to resolve Foundation symbols")

    def available_disk_capacity() -> int:
        pool = objc.objc_autoreleasePoolPush()
        try:
            url = file_url_with_path(
                ns_url, string_with_utf8(ns_string, b"/System/Volumes/Data")
            )
            capacity = ctypes.c_void_p()
            if not url or not get_resource_value(
                url, ctypes.byref(capacity), important_capacity_key, None
            ):
                raise OSError("Unable to read available disk capacity")
            return long_long_value(capacity)
        finally:
            objc.objc_autoreleasePoolPop(pool)

    return available_disk_capacity


if sys.platform == "darwin":
    try:
        _available_disk_capacity = _foundation_disk_capacity_query()
    except (OSError, AttributeError, ValueError):
        # Keep the tab bar working if the Foundation bridge cannot be set up,
        # at the cost of showing free blocks rather than Finder's figure.
        def _available_disk_capacity() -> int:
            return _statvfs_capacity("/System/Volumes/Data")

else:

    def _available_disk_capacity() -> int:
        return _statvfs_capacity("/")


class StatusProvider:
    """A status item backed by an atomically refreshed JSON cache."""

    def __init__(self, name: str, icon: str, refresh_interval: int) -> None:
        self.name = name
        self.icon = icon
        self.refresh_interval = refresh_interval
        self.cache_path = os.path.join(CACHE_DIR, f"{name}.json")
        self.refreshing = False
        self.next_refresh = None
        self.mtime = None
        self.text = ""

    def start_fetch(self, output_path: str, done) -> None:
        """Start writing JSON data to output_path without blocking, then call
        done(succeeded) on kitty's main thread once finished."""
        raise NotImplementedError

    def format_data(self, data) -> str:
        raise NotImplementedError

    def status_text(self) -> str:
        try:
            mtime = os.stat(self.cache_path).st_mtime_ns
            if mtime != self.mtime:
                with open(self.cache_path) as f:
                    data = json.load(f)
                self.text = self.format_data(data)
                self.mtime = mtime
        except (OSError, ValueError, KeyError, TypeError):
            # Keep the last successful value if a cache becomes unreadable.
            pass
        return self.text

    def maybe_refresh(self) -> None:
        if self.refreshing:
            return

        now = time.monotonic()
        if self.next_refresh is None:
            try:
                age = time.time() - os.path.getmtime(self.cache_path)
            except OSError:
                age = self.refresh_interval
            self.next_refresh = now + max(0, self.refresh_interval - age)

        # Allow a little timer jitter so a tick doesn't miss its refresh slot.
        if now + 0.1 < self.next_refresh:
            return

        self.next_refresh = now + self.refresh_interval
        temp_path = None
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, prefix=f".{self.name}-")
            os.close(fd)
            self.refreshing = True
            self.start_fetch(
                temp_path, lambda succeeded: self._finish_refresh(temp_path, succeeded)
            )
        except (OSError, subprocess.SubprocessError):
            self.refreshing = False
            _unlink(temp_path)

    def _finish_refresh(self, temp_path: str, succeeded: bool) -> None:
        self.refreshing = False
        try:
            if succeeded:
                with open(temp_path) as f:
                    self.format_data(
                        json.load(f)
                    )  # Validate before replacing a good cache.
                os.replace(temp_path, self.cache_path)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        finally:
            _unlink(temp_path)
        _mark_tab_bar_dirty()


class DiskProvider(StatusProvider):
    def __init__(self) -> None:
        super().__init__("disk", "⛁", REDRAW_INTERVAL)

    def start_fetch(self, output_path: str, done) -> None:
        succeeded = False
        abandoned = False

        def fetch() -> None:
            nonlocal succeeded
            try:
                capacity = _available_disk_capacity()
                if abandoned:
                    return  # The temp file has already been removed.
                with open(output_path, "w") as f:
                    json.dump(capacity, f)
                succeeded = True
            except (OSError, ValueError):
                pass

        # kitty has no way to hand results from another thread to its main
        # loop, so poll until the (usually few millisecond) query finishes.
        # Give up after DISK_TIMEOUT so a hung query cannot block every later
        # refresh; the daemon thread is left to finish on its own.
        deadline = time.monotonic() + DISK_TIMEOUT

        def poll(timer_id=None) -> None:
            nonlocal abandoned
            if not worker.is_alive():
                done(succeeded)
            elif time.monotonic() < deadline:
                add_timer(poll, DISK_POLL_INTERVAL, False)
            else:
                abandoned = True
                done(False)

        worker = threading.Thread(target=fetch, name="kitty-tab-bar-disk", daemon=True)
        worker.start()
        add_timer(poll, DISK_POLL_INTERVAL, False)

    def format_data(self, data) -> str:
        if not isinstance(data, int) or isinstance(data, bool) or data < 0:
            raise ValueError("Invalid available disk capacity")
        return f"{self.icon} {data // 1_000_000_000}G"


class AgentUsageProvider(StatusProvider):
    """Daily usage cost for one ccusage tool (claude, codex, ...)."""

    def __init__(self, tool: str, icon: str, cost_key: str) -> None:
        super().__init__(tool, icon, CCUSAGE_REFRESH_INTERVAL)
        self.cost_key = cost_key

    def start_fetch(self, output_path: str, done) -> None:
        # kitty may be launched from the Dock without Homebrew in PATH.
        env = {**os.environ, "PATH": HELPER_PATH}
        _run_monitored(
            [
                "bunx",
                "ccusage",
                self.name,
                "daily",
                "--last",
                "1",
                "--offline",
                "--json",
            ],
            output_path,
            CCUSAGE_TIMEOUT,
            lambda exit_code: done(exit_code == 0),
            env,
        )

    def format_data(self, data) -> str:
        cost = data["totals"][self.cost_key]
        return f"{self.icon} {cost:,.2f}" if cost > 0 else ""


@dataclass
class TabIcon:
    """The icon of a renamed tab, picked for the name it had then."""

    name: str
    refresh: bool = False  # picked anew rather than from pick-icon's cache
    is_loading: bool = True
    icon: str | None = None  # None once loaded if pick-icon failed


class PickedIcons:
    """Icons for renamed tabs picked by the pick-icon script, kept on each tab
    as a TabIcon. A tab's icon is picked again whenever it is renamed, or when
    name_tab.py asks for it to be. Tabs waiting for an icon are picked together
    in the background, one run at a time."""

    def __init__(self) -> None:
        self.queue = []  # (tab id, TabIcon) waiting for the next run, oldest first
        self.running = False

    def icon(self, tab) -> str:
        tab_icon = getattr(tab, TAB_ICON_ATTR, None)
        refresh = getattr(tab, REPICK_ICON_ATTR, False)

        if tab_icon is None or tab_icon.name != tab.name or refresh:
            if refresh:
                delattr(tab, REPICK_ICON_ATTR)
            tab_icon = TabIcon(tab.name, refresh)
            setattr(tab, TAB_ICON_ATTR, tab_icon)
            self.queue.append((tab.id, tab_icon))
            # Start the run after drawing rather than in the middle of it.
            add_timer(self._run, 0, False)

        if tab_icon.is_loading:
            return _spinner().frame()
        return tab_icon.icon or RENAMED_TAB_FIXED_ICON

    def _run(self, timer_id=None) -> None:
        if self.running:
            return  # The queue is picked once the current run finishes.

        # Skip tabs that were closed or renamed again before their turn.
        boss = get_boss()
        self.queue = [
            (tab_id, tab_icon)
            for tab_id, tab_icon in self.queue
            if getattr(boss.tab_for_id(tab_id), TAB_ICON_ATTR, None) is tab_icon
        ]
        if not self.queue:
            return

        # pick-icon refreshes every name in a run or none of them.
        refresh = self.queue[0][1].refresh
        picking = [tab_icon for _, tab_icon in self.queue if tab_icon.refresh == refresh]
        self.queue = [item for item in self.queue if item[1].refresh != refresh]
        names = list(dict.fromkeys(tab_icon.name for tab_icon in picking))
        self.running = True
        temp_path = None

        def finish(icons: dict[str, str]) -> None:
            for tab_icon in picking:
                tab_icon.icon = icons.get(tab_icon.name)
                tab_icon.is_loading = False
            self.running = False
            _mark_tab_bar_dirty()
            self._run()

        def done(exit_code: int | None) -> None:
            icons = {}
            try:
                if exit_code == 0:
                    with open(temp_path, encoding="utf-8") as f:
                        lines = f.read().splitlines()
                    # Only single cell icons, anything else would break the layout.
                    if len(lines) == len(names) and all(
                        wcswidth(line) == 1 for line in lines
                    ):
                        icons = dict(zip(names, lines))
                if not icons:
                    log_error(
                        f"tab_bar.py: pick-icon failed with exit code {exit_code}"
                    )
            except OSError:
                pass
            finally:
                _unlink(temp_path)
            finish(icons)

        try:
            fd, temp_path = tempfile.mkstemp(prefix="kitty-pick-icon-")
            os.close(fd)
            _run_monitored(
                [PICK_ICON, *(["--refresh"] if refresh else []), "--", *names],
                temp_path,
                PICK_ICON_TIMEOUT,
                done,
                {**os.environ, "PATH": HELPER_PATH},
            )
        except (OSError, subprocess.SubprocessError):
            _unlink(temp_path)
            finish({})


def _shared(name: str, create, retire=None):
    """The object called name, created on first use and shared by every copy
    of this module. kitty runs this file again when its config is reloaded, so
    state is kept on the boss, which outlives reloads, to stop each copy from
    adding its own timer and running its own refreshes.

    An object created by an earlier copy runs that copy's code, which may have
    changed since, so it is replaced, after retire(old, new) stops its timers
    and hands over its work. Callbacks of earlier copies that are still running
    get the latest copy's object."""
    boss = get_boss()
    attr = f"tab_bar_shared_{name}"
    shared = getattr(boss, attr, None)  # (load time of its copy, object)

    if shared is not None and shared[0] >= LOADED_AT:
        return shared[1]

    # Copies from before objects were stored with their copy's load time
    # stored them alone, under another name
    if hasattr(boss, legacy_attr := f"tab_bar_{name}"):
        shared = (float("-inf"), getattr(boss, legacy_attr))
        delattr(boss, legacy_attr)

    new = create()
    if shared is not None and retire is not None:
        retire(shared[1], new)
    setattr(boss, attr, (LOADED_AT, new))
    return new


def _remove_timer(timer_id) -> None:
    if timer_id is not None:
        remove_timer(timer_id)


class Spinner:
    """Animates the spinner of tabs that are waiting, see _is_waiting. Frames
    follow the clock rather than a count of redraws, so that redraws for other
    reasons never make it skip ahead and every spinner turns in step."""

    def __init__(self) -> None:
        self.timer_id = None

    def frame(self) -> str:
        if self.timer_id is None:
            self._schedule()
        index = int(time.monotonic() / SPINNER_INTERVAL) % len(SPINNER_FRAMES)
        return SPINNER_FRAMES[index]

    def _schedule(self) -> None:
        # Tick a quarter of the way into the next frame, so that a slightly
        # early or late timer still draws each frame exactly once.
        delay = SPINNER_INTERVAL * 1.25 - time.monotonic() % SPINNER_INTERVAL
        self.timer_id = add_timer(self._tick, delay, False)

    def _tick(self, timer_id=None) -> None:
        self.timer_id = None
        tab_managers = [
            tm
            for tm in get_boss().os_window_map.values()
            if any(_is_waiting(t) for t in tm.tabs)
        ]
        # Stops once no tab is waiting, until frame() is called again.
        if tab_managers:
            self._schedule()
            _mark_tab_bar_dirty(*tab_managers)


def _hand_over_icons(old: PickedIcons, new: PickedIcons) -> None:
    # A run of the old one in progress still finishes, updating its tabs.
    new.queue, old.queue = getattr(old, "queue", []), []
    if new.queue:
        add_timer(new._run, 0, False)


def _picked_icons() -> PickedIcons:
    return _shared("tab_icons", PickedIcons, _hand_over_icons)


def _spinner() -> Spinner:
    return _shared(
        "spinner", Spinner, lambda old, new: _remove_timer(getattr(old, "timer_id", None))
    )


def _providers() -> tuple[StatusProvider, ...]:
    return _shared(
        "providers",
        lambda: (
            DiskProvider(),
            AgentUsageProvider("codex", "⌬", "costUSD"),
            AgentUsageProvider("claude", "✻", "totalCost"),
        ),
    )


def _run_monitored(args, output_path: str, timeout: int, done, env=None) -> None:
    """Run args in the background with stdout written to output_path, then
    call done(exit_code) on kitty's main thread, with None if it took longer
    than timeout seconds."""
    with open(output_path, "w") as output:
        process = subprocess.Popen(
            args,
            env=env,
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
        # Stop Popen from waiting on a process kitty has already reaped.
        process.returncode = os.waitstatus_to_exitcode(exit_status)
        finish(process.returncode)

    # Also finishes if the exit is never reported, e.g. when the process
    # exits before kitty starts monitoring it.
    def on_timeout(timer_id=None) -> None:
        try:
            process.kill()
        except OSError:
            pass
        finish(None)

    timeout_timer = add_timer(on_timeout, timeout, False)
    try:
        get_boss().monitor_pid(process.pid, on_exit)
    except RuntimeError:
        # kitty's monitored pid table is full; nothing will report the
        # exit, so give up on this run rather than wait for the timeout.
        remove_timer(timeout_timer)
        on_timeout()


def _unlink(path) -> None:
    if path is not None:
        try:
            os.unlink(path)
        except OSError:
            pass


def _maybe_refresh() -> None:
    for provider in _providers():
        provider.maybe_refresh()


def _start_timer() -> int:
    _maybe_refresh()
    return add_timer(_tick, REDRAW_INTERVAL, True)


def _tick(timer_id=None) -> None:
    _maybe_refresh()
    _mark_tab_bar_dirty()


def _mark_tab_bar_dirty(*tab_managers) -> None:
    """Redraw the tab bars of tab_managers, or of every OS window when none are
    given, telling watchers that nothing changed."""
    for tm in tab_managers or get_boss().os_window_map.values():
        setattr(tm, DRAW_ONLY_ATTR, True)
        try:
            tm.mark_tab_bar_dirty()
        finally:
            setattr(tm, DRAW_ONLY_ATTR, False)
    # Marking dirty does not wake kitty's main loop, which only redraws when
    # something else happens, such as input. Timers run outside it, so without
    # this the redraw waits for the next keypress or program output.
    wakeup_main_loop()


def _draw_right_status(screen: Screen) -> None:
    text = " ".join(t for t in (p.status_text() for p in _providers()) if t)

    if not text:
        return

    padding = screen.columns - screen.cursor.x - wcswidth(text)

    if padding < 1:
        return

    screen.cursor.bg = 0
    screen.cursor.fg = STATUS_FG
    screen.draw(" " * padding + text)


def _short_title(title: str) -> str:
    """The last path component of the first word of a window title."""
    words = title.split()
    short = (words[0].rsplit("/", 1)[-1] if words else "") or "/"

    if len(short) > MAX_SHORT_TITLE_LENGTH:
        short = short[:MAX_SHORT_TITLE_LENGTH] + "…"

    return short


def _renamed_tab_icon(tab) -> str:
    if RENAMED_TAB_ICON_MODE == "fixed":
        return RENAMED_TAB_FIXED_ICON

    return _picked_icons().icon(tab)


def _is_naming(tab) -> bool:
    return getattr(tab, NAMING_ATTR, None) is not None


def _is_waiting(tab) -> bool:
    """Whether tab shows a spinner, while being named or waiting for its icon."""
    tab_icon = getattr(tab, TAB_ICON_ATTR, None)
    return _is_naming(tab) or (tab_icon is not None and tab_icon.is_loading)


def _tab_title(tab: TabBarData) -> str:
    # Tabs renamed with set_tab_title keep their full name, marked with an icon.
    t = get_boss().tab_for_id(tab.tab_id)
    spinner = _spinner().frame() if t is not None and _is_naming(t) else None

    if t is not None and t.name:
        match = STATUS_TAG.match(t.name)

        if match and (icon := STATUS_TAG_ICONS.get(match.group(1).lower())):
            return f"{spinner or icon} {t.name[match.end() :]}".rstrip()
        return f"{spinner or _renamed_tab_icon(t)} {tab.title}"

    short = _short_title(tab.title)
    return f"{spinner} {short}" if spinner else short


def draw_tab(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_title_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
) -> int:
    _shared("timer", _start_timer, lambda old, new: _remove_timer(old))

    tab = tab._replace(title=_tab_title(tab))

    end = draw_tab_with_separator(
        draw_data, screen, tab, before, max_title_length, index, is_last, extra_data
    )

    if is_last:
        _draw_right_status(screen)

    return end
