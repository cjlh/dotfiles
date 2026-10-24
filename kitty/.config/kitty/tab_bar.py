# Custom tab bar that displays available disk space, Codex and Claude Code
# usage in the far right corner. Disk space is sampled every redraw interval.
# All providers read JSON caches in ~/.cache/kitty-tab-bar and refresh them
# concurrently in the background. Agent usage is refreshed every
# CCUSAGE_REFRESH_INTERVAL seconds.
#
# Renamed tabs are marked with an icon, see RENAMED_TAB_ICON_MODE. In
# "apple-foundation-model" mode the icon is chosen by Apple's on-device model
# using tab_icon.swift, which is compiled into the cache directory on first use.
# See: https://github.com/kovidgoyal/kitty/discussions/4447

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from typing import Literal

from kitty.boss import get_boss
from kitty.constants import clear_handled_signals, config_dir
from kitty.fast_data_types import Screen, add_timer, remove_timer, wcswidth
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
CACHE_DIR = os.path.expanduser("~/.cache/kitty-tab-bar")
STATUS_FG = as_rgb(0x656565)
MAX_SHORT_TITLE_LENGTH = 24
TAB_ICON_TIMEOUT = 30  # seconds before choosing a tab icon is abandoned
TAB_ICON_COMPILE_TIMEOUT = 300  # seconds before compiling tab_icon.swift is abandoned

# "dynamic" picks an icon from the hash of the tab's name, "apple-foundation-model"
# has Apple's on-device model pick the icon whose meaning best matches the name,
# using "dynamic" when the model is unavailable or refuses to pick one.
TabIconMode = Literal["dynamic", "fixed", "apple-foundation-model"]

RENAMED_TAB_ICON_MODE: TabIconMode = "apple-foundation-model"

# Alternatives: ✎, ★, ✦, ⚐
RENAMED_TAB_FIXED_ICON = "⚑"

# Shown while the model is picking an icon
RENAMED_TAB_LOADING_ICON = "◌"

# Ids and meanings are what the model picks from, the icons themselves mean
# little to it. Changing them re-picks the icons of every renamed tab.
RENAMED_TAB_DYNAMIC_ICONS = {
    "umbrella": ("☂", "protection, cover, fallback, rain"),
    "ascending-node": ("☊", "orbits, astronomy, connections, networking"),
    "skull": ("☠", "danger, killing processes, debugging crashes, destructive work"),
    "cross": ("☩", "religion, crossroads, medical, merging"),
    "moon": ("⏾", "sleep, night, background or idle work, scheduled jobs"),
    "chess-bishop": ("♝", "strategy, planning, diagonal thinking"),
    "chess-knight": ("♞", "tactics, games, unusual moves"),
    "spade": ("♠", "digging, gardening, cards"),
    "club": ("♣", "groups, clubs, organisations, cards"),
    "heart": ("♥", "personal, health, favourites, love"),
    "diamond": ("♦", "money, finance, value, gems"),
    "music-notes": ("♬", "music, audio, sound"),
    "crossed-swords": ("⚔", "conflict, competition, fixing merge conflicts, battles"),
    "pick": ("⛏", "mining, digging into data, excavation, crypto"),
    "shield": ("⛨", "security, auth, defence, permissions"),
    "shrine": ("⛩", "Japan, travel, gateways, entry points"),
    "gear": ("⛭", "settings, config, tooling, infrastructure, builds"),
    "mountain": ("⛰", "big projects, goals, outdoors, hiking"),
    "beach-umbrella": ("⛱", "holiday, leisure, side projects, downtime"),
    "skier": ("⛷", "speed, sport, winter, going downhill"),
    "flag": ("⚑", "milestones, releases, feature flags, markers"),
    "pencil": ("✎", "writing, editing, notes, docs, drafts"),
    "star": ("★", "important, favourites, highlights, ratings"),
    "sparkle": ("✦", "AI, new things, magic, ideas"),
    "up-triangle": ("⏶", "deploys, uploads, growth, upgrades"),
    "airplane": ("✈", "travel, shipping, flights, remote"),
}

_timer_id = None


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
        env = dict(os.environ)
        env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")
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


class FoundationModelIcons:
    """Icons for renamed tabs picked by Apple's on-device model. Names are
    looked up one at a time by the tab_icon.swift helper in the background,
    and the picked icon ids cached by name."""

    # Cached for names the model refuses to pick an icon for
    REFUSED = ""

    def __init__(self) -> None:
        self.source_path = os.path.join(config_dir, "tab_icon.swift")
        self.binary_path = os.path.join(CACHE_DIR, "tab-icon")
        self.cache_path = os.path.join(CACHE_DIR, "tab-icons.json")
        self.available = sys.platform == "darwin"
        self.compiled = False
        self.busy = False
        self.version = None
        self.icons = None  # name -> icon id, loaded on first use
        self.queue = []  # names waiting for an icon, oldest first
        self.current = None  # name being looked up
        self.failed = set()  # names whose lookup failed in this kitty

    def icon(self, name: str) -> str | None:
        """The icon for name, the loading icon while one is being picked, or
        None if the model can't pick one."""
        icons = self._load()
        if not self.available or name in self.failed:
            return None
        if name in icons:
            entry = RENAMED_TAB_DYNAMIC_ICONS.get(icons[name])
            return entry[0] if entry else None
        if name not in self.queue and name != self.current:
            self.queue.append(name)
            # Start the lookup after drawing rather than in the middle of it.
            add_timer(self._next, 0, False)
        return RENAMED_TAB_LOADING_ICON

    def _load(self) -> dict[str, str]:
        if self.icons is None:
            self.icons = {}
            try:
                with open(self.source_path, "rb") as f:
                    source = f.read()
            except OSError:
                self.available = False
                return self.icons
            # Changing the icons or the helper's prompt invalidates the cache.
            icons_json = json.dumps(RENAMED_TAB_DYNAMIC_ICONS).encode()
            self.version = zlib.crc32(source + icons_json)
            self.icons = self._read_cache()
        return self.icons

    def _read_cache(self) -> dict[str, str]:
        try:
            with open(self.cache_path) as f:
                data = json.load(f)
            if data["version"] == self.version:
                return {str(k): str(v) for k, v in data["icons"].items()}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
        return {}

    def _store(self, name: str, icon_id: str) -> None:
        # Merge with icons picked by other kitty instances since loading.
        self.icons = {**self._read_cache(), **self.icons, name: icon_id}
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, prefix=".tab-icons-")
            with os.fdopen(fd, "w") as f:
                json.dump({"version": self.version, "icons": self.icons}, f)
            os.replace(temp_path, self.cache_path)
        except OSError:
            _unlink(temp_path)

    def _disable(self, reason: str) -> None:
        log_error(f"tab_bar.py: {reason}, using dynamic tab icons instead")
        self.available = False
        self.queue.clear()
        _mark_tab_bar_dirty()

    def _next(self, timer_id=None) -> None:
        if self.busy or not self.available:
            return
        if not self.compiled:
            self._compile()
            return

        # Skip names that were renamed again before their turn.
        names = {tab.name for tab in get_boss().all_tabs}
        while self.queue:
            name = self.queue.pop(0)
            if name in names and name not in self.icons and name not in self.failed:
                self._lookup(name)
                return

    def _compile(self) -> None:
        try:
            if os.path.getmtime(self.binary_path) >= os.path.getmtime(self.source_path):
                self.compiled = True
                self._next()
                return
        except OSError:
            pass

        temp_path = None

        def done(exit_code: int | None) -> None:
            self.busy = False
            if exit_code == 0:
                try:
                    os.replace(temp_path, self.binary_path)
                except OSError:
                    pass
                else:
                    self.compiled = True
                    self._next()
                    return
            _unlink(temp_path)
            self._disable("Unable to compile tab_icon.swift")

        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, prefix=".tab-icon-")
            os.close(fd)
            self.busy = True
            # Checking xcode-select first stops xcrun from offering to install
            # the Command Line Tools when they are missing.
            _run_monitored(
                [
                    "/bin/sh",
                    "-c",
                    'xcode-select -p >/dev/null 2>&1 && exec xcrun swiftc -O "$1" -o "$2"',
                    "sh",
                    self.source_path,
                    temp_path,
                ],
                os.devnull,
                TAB_ICON_COMPILE_TIMEOUT,
                done,
            )
        except (OSError, subprocess.SubprocessError):
            self.busy = False
            _unlink(temp_path)
            self._disable("Unable to compile tab_icon.swift")

    def _lookup(self, name: str) -> None:
        request = json.dumps(
            {
                "name": name,
                "icons": [
                    {"id": icon_id, "meaning": meaning}
                    for icon_id, (_, meaning) in RENAMED_TAB_DYNAMIC_ICONS.items()
                ],
            }
        )
        temp_path = None

        def done(exit_code: int | None) -> None:
            self.busy = False
            self.current = None
            try:
                if exit_code == 0:
                    with open(temp_path) as f:
                        icon_id = f.read().strip()
                    if icon_id in RENAMED_TAB_DYNAMIC_ICONS:
                        self._store(name, icon_id)
                    else:
                        self.failed.add(name)
                elif exit_code == 2:
                    self._store(name, self.REFUSED)
                elif exit_code == 3:
                    self._disable("Apple's on-device model is unavailable")
                else:
                    self.failed.add(name)
            except OSError:
                self.failed.add(name)
            finally:
                _unlink(temp_path)
            _mark_tab_bar_dirty()
            self._next()

        try:
            fd, temp_path = tempfile.mkstemp(dir=CACHE_DIR, prefix=".tab-icon-")
            os.close(fd)
            self.busy = True
            self.current = name
            _run_monitored(
                [self.binary_path, request], temp_path, TAB_ICON_TIMEOUT, done
            )
        except (OSError, subprocess.SubprocessError):
            self.busy = False
            self.current = None
            _unlink(temp_path)
            self.failed.add(name)
            _mark_tab_bar_dirty()
            add_timer(self._next, 0, False)


_foundation_model_icons = FoundationModelIcons()

PROVIDERS = (
    DiskProvider(),
    AgentUsageProvider("codex", "⌬", "costUSD"),
    AgentUsageProvider("claude", "✻", "totalCost"),
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
    for provider in PROVIDERS:
        provider.maybe_refresh()


def _tick(timer_id=None) -> None:
    _maybe_refresh()
    _mark_tab_bar_dirty()


def _mark_tab_bar_dirty() -> None:
    for tm in get_boss().os_window_map.values():
        tm.mark_tab_bar_dirty()


def _draw_right_status(screen: Screen) -> None:
    text = " ".join(t for t in (p.status_text() for p in PROVIDERS) if t)

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


def _renamed_tab_icon(name: str) -> str:
    if RENAMED_TAB_ICON_MODE == "fixed":
        return RENAMED_TAB_FIXED_ICON

    if RENAMED_TAB_ICON_MODE == "apple-foundation-model":
        icon = _foundation_model_icons.icon(name)
        if icon is not None:
            return icon

    # zlib.crc32 gives a consistent int value that we can index with
    icons = list(RENAMED_TAB_DYNAMIC_ICONS.values())
    return icons[zlib.crc32(name.encode()) % len(icons)][0]


def _tab_title(tab: TabBarData) -> str:
    # Tabs renamed with set_tab_title keep their full name, marked with an icon.
    t = get_boss().tab_for_id(tab.tab_id)
    if t is not None and t.name:
        return f"{_renamed_tab_icon(t.name)} {tab.title}"
    return _short_title(tab.title)


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
    global _timer_id

    if _timer_id is None:
        _timer_id = add_timer(_tick, REDRAW_INTERVAL, True)
        _maybe_refresh()

    tab = tab._replace(title=_tab_title(tab))
    end = draw_tab_with_separator(
        draw_data, screen, tab, before, max_title_length, index, is_last, extra_data
    )

    if is_last:
        _draw_right_status(screen)

    return end
