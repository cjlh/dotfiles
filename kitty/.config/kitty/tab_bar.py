# Custom tab bar that displays available disk space, Codex and Claude Code
# usage in the far right corner. Disk space is sampled every redraw interval.
# All providers read JSON caches in ~/.cache/kitty-tab-bar and refresh them
# concurrently in the background. Agent usage is refreshed every
# CCUSAGE_REFRESH_INTERVAL seconds.
# See: https://github.com/kovidgoyal/kitty/discussions/4447

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

from kitty.boss import get_boss
from kitty.constants import clear_handled_signals
from kitty.fast_data_types import Screen, add_timer, remove_timer, wcswidth
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    as_rgb,
    draw_tab_with_separator,
)

CCUSAGE_REFRESH_INTERVAL = 300  # seconds between ccusage runs
CCUSAGE_TIMEOUT = 120  # seconds before a ccusage run is killed
DISK_TIMEOUT = 5  # seconds before a disk query is abandoned
DISK_POLL_INTERVAL = 0.01  # seconds between checks for a finished disk query
REDRAW_INTERVAL = 30  # seconds between tab bar redraws
CACHE_DIR = os.path.expanduser("~/.cache/kitty-tab-bar")
STATUS_FG = as_rgb(0x656565)

_timer_id = None


def _statvfs_capacity(path: str) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def _foundation_disk_capacity_query():
    """Build a Finder-style available capacity query (including storage macOS
    can reclaim) by calling Foundation directly through ctypes."""
    import ctypes

    objc = ctypes.CDLL("/usr/lib/libobjc.dylib")
    foundation = ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
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
    string_with_utf8 = objc_method(b"stringWithUTF8String:", ctypes.c_void_p, ctypes.c_char_p)
    file_url_with_path = objc_method(b"fileURLWithPath:", ctypes.c_void_p, ctypes.c_void_p)
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
            url = file_url_with_path(ns_url, string_with_utf8(ns_string, b"/System/Volumes/Data"))
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
            self.start_fetch(temp_path, lambda succeeded: self._finish_refresh(temp_path, succeeded))
        except (OSError, subprocess.SubprocessError):
            self.refreshing = False
            _unlink(temp_path)

    def _finish_refresh(self, temp_path: str, succeeded: bool) -> None:
        self.refreshing = False
        try:
            if succeeded:
                with open(temp_path) as f:
                    self.format_data(json.load(f))  # Validate before replacing a good cache.
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
        with open(output_path, "w") as output:
            process = subprocess.Popen(
                ["bunx", "ccusage", self.name, "daily", "--last", "1", "--offline", "--json"],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.DEVNULL,
                preexec_fn=clear_handled_signals,
            )

        finished = False

        def finish(succeeded: bool) -> None:
            nonlocal finished
            if not finished:
                finished = True
                done(succeeded)

        # kitty reaps every child process itself, so let it report the exit on
        # its main thread instead of waiting on the process.
        def on_exit(exit_status: int, err=None) -> None:
            remove_timer(timeout_timer)
            # Stop Popen from waiting on a process kitty has already reaped.
            process.returncode = os.waitstatus_to_exitcode(exit_status)
            finish(exit_status == 0)

        # Also finishes the refresh if the exit is never reported, e.g. when
        # the process exits before kitty starts monitoring it.
        def on_timeout(timer_id=None) -> None:
            try:
                process.kill()
            except OSError:
                pass
            finish(False)

        timeout_timer = add_timer(on_timeout, CCUSAGE_TIMEOUT, False)
        try:
            get_boss().monitor_pid(process.pid, on_exit)
        except RuntimeError:
            # kitty's monitored pid table is full; nothing will report the
            # exit, so give up on this run rather than wait for the timeout.
            remove_timer(timeout_timer)
            on_timeout()

    def format_data(self, data) -> str:
        cost = data["totals"][self.cost_key]
        return f"{self.icon} {cost:,.2f}" if cost > 0 else ""


PROVIDERS = (
    DiskProvider(),
    AgentUsageProvider("codex", "⌬", "costUSD"),
    AgentUsageProvider("claude", "✻", "totalCost"),
)


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

    end = draw_tab_with_separator(
        draw_data, screen, tab, before, max_title_length, index, is_last, extra_data
    )

    if is_last:
        _draw_right_status(screen)

    return end
