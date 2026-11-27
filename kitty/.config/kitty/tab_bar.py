# Custom tab bar with status indicators, automatic tab icons, and stack markers.
# Configure status providers and appearance in tab_bar.toml.

import colorsys
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from dataclasses import dataclass
from typing import Literal

from kitty.boss import get_boss
from kitty.constants import clear_handled_signals, config_dir, kitty_exe
from kitty.fast_data_types import (
    Screen,
    add_timer,
    get_options,
    remove_timer,
    wakeup_main_loop,
    wcswidth,
)
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    apply_title_template,
    as_rgb,
    draw_tab_with_separator,
    truncate_line,
)
from kitty.rgb import to_color
from kitty.utils import color_as_int, log_error

CONFIG_PATH = os.path.join(config_dir, "tab_bar.toml")
PROVIDER_NAME = re.compile(r"[A-Za-z0-9_-]+")
# Default command-provider settings.
COMMAND_REFRESH_INTERVAL = 180  # seconds between runs of its command
COMMAND_TIMEOUT = 60  # seconds before a run of its command is killed
# Show weekly usage once it reaches this percentage.
WEEKLY_USAGE_THRESHOLD = 0
DISK_TIMEOUT = 5  # seconds before a disk query is abandoned
DISK_POLL_INTERVAL = 0.01  # seconds between checks for a finished disk query
REDRAW_INTERVAL = 30  # seconds between tab bar redraws
LOADED_AT = time.monotonic()
# Allow test instances to use separate caches.
CACHE_DIR = os.environ.get("KITTY_TAB_BAR_CACHE_DIR") or os.path.expanduser(
    "~/.cache/kitty-tab-bar"
)
STATUS_FG = as_rgb(0x656565)
MAX_SHORT_TITLE_LENGTH = 24
# Keep full titles for these programs. Match the command name because Claude
# Code's executable filename contains its version instead of its name.
FULL_TITLE_PROGRAMS = frozenset({"claude", "codex"})
# Allow time for model downloads on the first run (seconds).
NAMER_TIMEOUT = 600

# kitty may be launched from the Dock without Homebrew or ~/.local/bin in PATH.
HELPER_PATH = os.pathsep.join(
    [
        os.path.dirname(kitty_exe()),  # so that "kitty" is the running one
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        os.environ.get("PATH", ""),
    ]
)
NAMER = shutil.which("namer", path=HELPER_PATH)

TabIconMode = Literal["dynamic", "fixed"]

RENAMED_TAB_ICON_MODE: TabIconMode = (
    "dynamic" if NAMER and shutil.which("uv", path=HELPER_PATH) else "fixed"
)

RENAMED_TAB_FIXED_ICON = "⚑"

# Tags that replace a renamed tab's icon, matched case-insensitively
STATUS_TAG_ICONS = {
    "todo": "☐",
    "done": "☑",
    "failed": "☒",
}
STATUS_TAG = re.compile(r"\[(\w+)\]\s*")

# Strip SGR formatting before measuring title width.
SGR_ESCAPE = re.compile(r"\x1b\[[0-9:;]*m")

# The previous tab name, saved while automatic naming is in progress.
NAMING_ATTR = "name_tab_previous_name"

# True requests a fresh icon; a (name, icon) pair supplies one directly.
REPICK_ICON_ATTR = "tab_bar_repick_icon"

# Store each tab's TabIcon on the tab so it survives config reloads.
TAB_ICON_ATTR = "tab_bar_icon"

# Icons for program states in priority order, matching the tab colour priority.
# Keys are a state, or "blocked:<kind>" for why a program is blocked. None
# shows the working spinner.
PROGRAM_STATE_ICONS = {
    "blocked:permission": "⊘",
    "blocked:question": "◌",
    "blocked:auth": "⊛",
    "blocked": "⊝",
    "error": "⊗",
    "working": None,
    "done": "⊙",
}

SPINNER_FRAMES = "⠦⠖⠲⠴"
# Programs that report the working state get their own spinner.
WORKING_SPINNER_FRAMES = "◐◓◑◒"
SPINNER_INTERVAL = 0.12  # seconds

STACK_LAYOUT = "stack"

# Dim status colours on inactive tabs so the active tab stands out.
INACTIVE_TAB_SATURATION = 0.6
INACTIVE_TAB_LIGHTNESS = 0.75

# Marks redraws that don't change tab or window state, such as spinner frames.
# Watchers can skip layout updates while this flag is set.
DRAW_ONLY_ATTR = "tab_bar_draw_only"


@dataclass(frozen=True)
class StackIndicator:
    inactive: str = "▫"
    active: str = "▪"
    separator: str = ""

    def render(self, count: int, active: int) -> str:
        return self.separator.join(
            self.active if i == active else self.inactive for i in range(count)
        )


@dataclass(frozen=True)
class TabColors:
    blocked: int = 0xDE7500
    error: int = 0xC90A0A


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log_error(f"tab_bar.py: failed to read {CONFIG_PATH}: {e!r}")
        return {}


def _config() -> dict:
    return _shared("config", _load_config)


def _load_stack_indicator() -> StackIndicator:
    try:
        tabs = _config().get("tabs", {})
        if not isinstance(tabs, dict):
            raise TypeError("tabs must be a table")
        values = {}
        for field, key in (
            ("inactive", "inactive-stacked-window-indicator"),
            ("active", "active-stacked-window-indicator"),
            ("separator", "stacked-window-indicator-separator"),
        ):
            if key in tabs:
                if not isinstance(tabs[key], str):
                    raise TypeError(f"{key} must be a string")
                values[field] = tabs[key]
        return StackIndicator(**values)
    except (TypeError, ValueError) as e:
        log_error(f"tab_bar.py: invalid tabs settings in {CONFIG_PATH}: {e!r}")
        return StackIndicator()


def _stack_indicator() -> StackIndicator:
    return _shared("stack_indicator", _load_stack_indicator)


def _load_tab_colors() -> TabColors:
    try:
        tabs = _config().get("tabs", {})
        if not isinstance(tabs, dict):
            raise TypeError("tabs must be a table")
        values = {}
        for field, key in (
            ("blocked", "blocked-tab-color"),
            ("error", "error-tab-color"),
        ):
            if key in tabs:
                if not isinstance(tabs[key], str):
                    raise TypeError(f"{key} must be a string")
                values[field] = color_as_int(to_color(tabs[key], validate=True))
        return TabColors(**values)
    except (TypeError, ValueError) as e:
        log_error(f"tab_bar.py: invalid tabs settings in {CONFIG_PATH}: {e!r}")
        return TabColors()


def _tab_colors() -> TabColors:
    return _shared("tab_colors", _load_tab_colors)


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
        self.data = None
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
                    self.data = json.load(f)
                self.mtime = mtime
            # Formatted on every draw, as it may depend on the time.
            self.text = self.format_data(self.data)
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


class CommandProvider(StatusProvider):
    """Run a command for JSON data; subclasses control how it is displayed."""

    def __init__(
        self,
        name: str,
        command: list[str],
        icon: str = "",
        interval: int = COMMAND_REFRESH_INTERVAL,
        timeout: int = COMMAND_TIMEOUT,
    ) -> None:
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(arg, str) for arg in command)
        ):
            raise ValueError("command must be a list of strings")
        if not isinstance(icon, str):
            raise ValueError("icon must be a string")
        for seconds in (interval, timeout):
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
                raise ValueError("interval and timeout must be numbers")
            if seconds <= 0:
                raise ValueError("interval and timeout must be positive")
        super().__init__(name, icon, interval)
        self.command = command
        self.timeout = timeout

    def start_fetch(self, output_path: str, done) -> None:
        env = {**os.environ, "PATH": HELPER_PATH}
        _run_monitored(
            self.command,
            output_path,
            self.timeout,
            lambda exit_code: done(exit_code == 0),
            env,
            config_dir,
        )

    def format_data(self, data) -> str:
        if data is None:
            return ""
        text = self.format_text(data)
        return f"{self.icon} {text}".lstrip() if text else ""

    def format_text(self, data) -> str:
        raise NotImplementedError


class TextProvider(CommandProvider):
    """Shows the text printed by its command as is."""

    def format_text(self, data) -> str:
        text = data["text"]
        if not isinstance(text, str):
            raise TypeError("Invalid text")
        return text


class UsageProvider(CommandProvider):
    """Display session and weekly usage as percentages of subscription limits."""

    def __init__(
        self, *args, weekly_threshold: float = WEEKLY_USAGE_THRESHOLD, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        if not isinstance(weekly_threshold, (int, float)):
            raise ValueError("weekly_threshold must be a number")
        self.weekly_threshold = weekly_threshold

    def format_text(self, data) -> str:
        now = time.time()
        session = self._used_percent(data["session"], now)
        weekly = self._used_percent(data["weekly"], now)
        text = f"{session}"
        if weekly >= self.weekly_threshold:
            text += f"/{weekly}"
        remaining = self._session_time_left(data["session"], now)
        if remaining:
            text += f" ({remaining})"
        return text

    @staticmethod
    def _session_time_left(window, now: float) -> str:
        """Time until the session resets, rounded up to the minute, once less
        than half the window remains."""
        resets_at = window["resets_at"]
        length = window.get("window")  # missing from caches of older versions
        if resets_at is None or length is None:
            return ""
        left = resets_at - now
        if left <= 0 or left >= length / 2:
            return ""
        hours, minutes = divmod(math.ceil(left / 60), 60)
        return f"{hours}h{minutes:02}" if hours else f"{minutes}m"

    @staticmethod
    def _used_percent(window, now: float) -> int:
        # Cached usage may outlive a limit reset. Treat it as zero after reset.
        resets_at = window["resets_at"]
        if resets_at is not None and resets_at <= now:
            return 0
        return round(window["percent"])


BUILTIN_PROVIDERS = {"disk": DiskProvider}
COMMAND_PROVIDERS = {"text": TextProvider, "usage": UsageProvider}


def _create_provider(spec) -> StatusProvider:
    spec = dict(spec)
    name = spec.pop("name")
    if not isinstance(name, str) or not PROVIDER_NAME.fullmatch(name):
        raise ValueError(f"invalid name {name!r}")
    if "command" not in spec and name in BUILTIN_PROVIDERS:
        if spec:
            raise ValueError(f"{name} takes no {', '.join(spec)}")
        return BUILTIN_PROVIDERS[name]()
    format = spec.pop("format", "text")
    if format not in COMMAND_PROVIDERS:
        raise ValueError(f"unknown format {format!r}")
    # Raises TypeError on missing and unknown keys.
    return COMMAND_PROVIDERS[format](name, **spec)


def _load_providers() -> tuple[StatusProvider, ...]:
    """Load providers, using disk space by default and skipping invalid entries."""
    path = CONFIG_PATH
    if not os.path.exists(path):
        return (DiskProvider(),)
    try:
        specs = _config().get("provider", [{"name": "disk"}])
        if not isinstance(specs, list):
            raise TypeError("provider must be an array of tables")
    except (OSError, ValueError, KeyError, TypeError) as e:
        log_error(f"tab_bar.py: failed to read {path}: {e!r}")
        return (DiskProvider(),)

    providers = {}
    for spec in specs:
        try:
            provider = _create_provider(spec)
            if provider.name in providers:
                raise ValueError("listed twice")
        except (KeyError, TypeError, ValueError) as e:
            name = spec.get("name") if isinstance(spec, dict) else spec
            log_error(f"tab_bar.py: skipping provider {name!r} of {path}: {e!r}")
        else:
            providers[provider.name] = provider
    return tuple(providers.values())


@dataclass
class TabIcon:
    """An icon request tied to a particular tab name."""

    name: str
    refresh: bool = False  # picked anew rather than from namer's cache
    is_loading: bool = True
    icon: str | None = None  # None once loaded if namer failed


class PickedIcons:
    """Batch icon requests into one background namer process at a time.

    Forget old names when tabs are renamed, so reusing a name gets a fresh icon.
    """

    def __init__(self) -> None:
        self.queue = []  # (tab id, TabIcon) waiting for the next run, oldest first
        self.forget = set()  # names for namer to forget in the next run
        self.running = False

    def icon(self, tab) -> str:
        tab_icon = getattr(tab, TAB_ICON_ATTR, None)
        refresh = getattr(tab, REPICK_ICON_ATTR, False)

        if tab_icon is None or tab_icon.name != tab.name or refresh:
            if tab_icon is not None and tab_icon.name != tab.name:
                self.forget.add(tab_icon.name)
            if refresh:
                delattr(tab, REPICK_ICON_ATTR)
            if isinstance(refresh, tuple):
                name, icon = refresh
                # Only single cell icons, anything else would break the layout.
                if name == tab.name and wcswidth(icon) == 1:
                    tab_icon = TabIcon(tab.name, is_loading=False, icon=icon)
                    setattr(tab, TAB_ICON_ATTR, tab_icon)
                    if self.forget:
                        add_timer(self._run, 0, False)
                    return icon
                # A status tag can hide the icon across several renames.
                refresh = False
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
        if not self.queue and not self.forget:
            return

        # namer refreshes every name in a run or none of them.
        refresh = bool(self.queue) and self.queue[0][1].refresh
        picking = [
            tab_icon for _, tab_icon in self.queue if tab_icon.refresh == refresh
        ]
        self.queue = [item for item in self.queue if item[1].refresh != refresh]
        names = list(dict.fromkeys(tab_icon.name for tab_icon in picking))
        forget, self.forget = sorted(self.forget), set()
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
            icons = None
            try:
                if exit_code == 0:
                    with open(temp_path, encoding="utf-8") as f:
                        lines = f.read().splitlines()
                    # Only single cell icons, anything else would break the layout.
                    if len(lines) == len(names) and all(
                        wcswidth(line) == 1 for line in lines
                    ):
                        icons = dict(zip(names, lines))
                if icons is None:
                    log_error(f"tab_bar.py: namer failed with exit code {exit_code}")
            except OSError:
                pass
            finally:
                _unlink(temp_path)
            finish(icons or {})

        try:
            fd, temp_path = tempfile.mkstemp(prefix="kitty-namer-")
            os.close(fd)
            _run_monitored(
                [
                    NAMER,
                    "icon",
                    *(["--refresh"] if refresh else []),
                    *(f"--forget={name}" for name in forget),
                    "--",
                    *names,
                ],
                temp_path,
                NAMER_TIMEOUT,
                done,
                {**os.environ, "PATH": HELPER_PATH},
            )
        except (OSError, subprocess.SubprocessError):
            _unlink(temp_path)
            finish({})


def _shared(name: str, create, retire=None):
    """Share state across module copies without duplicating timers or refreshes.

    kitty reloads this module before it stops drawing with the previous copy,
    so code edits take two config reloads to appear. State lives on the boss,
    which survives reloads. Older callbacks get the newest object. When supplied,
    retire(old, new) stops old timers or hands pending work to the replacement.
    """
    boss = get_boss()
    attr = f"tab_bar_shared_{name}"
    shared = getattr(boss, attr, None)  # (load time of its copy, object)

    if shared is not None and shared[0] >= LOADED_AT:
        return shared[1]

    # Accept state from modules loaded before the timestamped storage format.
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
    """Use elapsed time to keep spinners in sync, regardless of redraw frequency."""

    def __init__(self) -> None:
        self.timer_id = None

    def frame(self, frames: str = SPINNER_FRAMES) -> str:
        if self.timer_id is None:
            self._schedule()
        index = int(time.monotonic() / SPINNER_INTERVAL) % len(frames)
        return frames[index]

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
        if tab_managers:
            self._schedule()
            _mark_tab_bar_dirty(*tab_managers)


def _hand_over_icons(old: PickedIcons, new: PickedIcons) -> None:
    # Leave any running request to finish; transfer only pending work.
    new.queue, old.queue = getattr(old, "queue", []), []
    new.forget, old.forget = getattr(old, "forget", set()), set()
    if new.queue or new.forget:
        add_timer(new._run, 0, False)


def _picked_icons() -> PickedIcons:
    return _shared("tab_icons", PickedIcons, _hand_over_icons)


def _spinner() -> Spinner:
    return _shared(
        "spinner",
        Spinner,
        lambda old, new: _remove_timer(getattr(old, "timer_id", None)),
    )


def _providers() -> tuple[StatusProvider, ...]:
    return _shared("providers", _load_providers)


def _run_monitored(
    args, output_path: str, timeout: int, done, env=None, cwd=None
) -> None:
    """Run args in the background with stdout written to output_path, then
    call done(exit_code) on kitty's main thread, with None if it took longer
    than timeout seconds."""
    with open(output_path, "w") as output:
        process = subprocess.Popen(
            args,
            env=env,
            cwd=cwd,
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


def _right_status_text() -> str:
    return " ".join(t for t in (p.status_text() for p in _providers()) if t)


def _draw_right_status(screen: Screen, for_layout: bool) -> None:
    text = _right_status_text()

    if not text:
        return

    # Kitty first measures the tabs to decide how much room each title gets.
    # During that step, leave just one space before the status text. Pushing
    # it to the right edge would make Kitty think the last tab needs all the
    # remaining room, so other tab titles would stay shortened unnecessarily.
    if for_layout:
        padding = 1
    else:
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


def _shows_full_title(tab) -> bool:
    """Whether the active window of tab is running one of FULL_TITLE_PROGRAMS."""
    window = tab.active_window

    if window is None:
        return False

    try:
        processes = window.child.foreground_processes
    except Exception:
        return False

    return any(
        p["cmdline"] and os.path.basename(p["cmdline"][0]) in FULL_TITLE_PROGRAMS
        for p in processes
    )


def _renamed_tab_icon(tab) -> str:
    if RENAMED_TAB_ICON_MODE == "fixed":
        return RENAMED_TAB_FIXED_ICON

    return _picked_icons().icon(tab)


def _is_naming(tab) -> bool:
    return getattr(tab, NAMING_ATTR, None) is not None


def _program_states(tab) -> set[str]:
    """Collect program states reported through OSC 7501.

    Blocked states with a kind also appear as "blocked:<kind>". Working and
    blocked states persist until the program changes them; completion and
    error states persist until the user sees the window.
    """
    states = set()
    # kitty < 0.50.0 has no program_status
    for w in tab:
        for record in getattr(w, "program_status", ()):
            states.add(record.state.value)
            if (kind := getattr(record, "kind", None)) is not None:
                states.add(f"{record.state.value}:{kind.value}")
    return states


def _is_working(tab) -> bool:
    return "working" in _program_states(tab)


def _is_waiting(tab) -> bool:
    tab_icon = getattr(tab, TAB_ICON_ATTR, None)
    return (
        _is_naming(tab)
        or (tab_icon is not None and tab_icon.is_loading)
        or _is_working(tab)
    )


def _status_icon(tab) -> str | None:
    """An icon for the most urgent program state, or a spinner while busy."""
    states = _program_states(tab)

    for state, icon in PROGRAM_STATE_ICONS.items():
        # Naming a tab ranks alongside working, with the usual spinner.
        if icon is None and _is_naming(tab):
            return _spinner().frame()
        if state in states:
            return icon or _spinner().frame(WORKING_SPINNER_FRAMES)
    return None


def _tab_title(tab: TabBarData) -> str:
    # Tabs renamed with set_tab_title keep their full name, marked with an icon.
    t = get_boss().tab_for_id(tab.tab_id)
    status_icon = _status_icon(t) if t is not None else None

    if t is not None and t.name:
        match = STATUS_TAG.match(t.name)

        if match and (icon := STATUS_TAG_ICONS.get(match.group(1).lower())):
            return f"{status_icon or icon} {t.name[match.end() :]}".rstrip()
        return f"{status_icon or _renamed_tab_icon(t)} {tab.title}"

    short = (
        tab.title if t is not None and _shows_full_title(t) else _short_title(tab.title)
    )
    return f"{status_icon} {short}" if status_icon else short


def _stack_suffix(tab: TabBarData) -> str:
    """Markers for normal window groups in a stack, including the active one."""
    t = get_boss().tab_for_id(tab.tab_id)

    # Groups are the normal windows with their overlays, without docks
    if t is None or t.current_layout.name != STACK_LAYOUT or len(t.windows.groups) < 2:
        return ""

    active = t.windows.active_group_idx
    markers = _stack_indicator().render(len(t.windows.groups), active)
    return " " + markers if markers else ""


def _attention_color(tab: TabBarData) -> int | None:
    """Choose a tab colour, prioritising blocked programs, then errors.

    Completed programs and bells use the theme's active border colour.
    Return None when the tab needs no attention.
    """
    t = get_boss().tab_for_id(tab.tab_id)
    states = _program_states(t) if t is not None else set()

    if "blocked" in states:
        return _tab_colors().blocked
    if "error" in states:
        return _tab_colors().error
    color = get_options().active_border_color
    # active_border_color can be "none"
    if ("done" in states or tab.needs_attention) and color is not None:
        return color_as_int(color)
    return None


def _dimmed(color: int) -> int:
    r, g, b = (((color >> shift) & 0xFF) / 255 for shift in (16, 8, 0))
    h, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(
        h,
        lightness * INACTIVE_TAB_LIGHTNESS,
        saturation * INACTIVE_TAB_SATURATION,
    )
    return (round(r * 255) << 16) | (round(g * 255) << 8) | round(b * 255)


def _attention_colors(tab: TabBarData) -> TabBarData:
    """Override theme colours when a tab needs attention, dimming inactive tabs."""
    c = _attention_color(tab)

    if c is None:
        return tab

    dimmed = _dimmed(c)
    return tab._replace(
        active_fg=c, active_bg=c, inactive_fg=dimmed, inactive_bg=dimmed
    )


def _fit_title(
    draw_data: DrawData,
    tab: TabBarData,
    index: int,
    max_tab_length: int,
    suffix: str = "",
) -> TabBarData:
    """Shorten the title while preserving the suffix and tab decorations.

    kitty's own truncation can cut these off.
    """
    template = apply_title_template(draw_data, tab._replace(title=""), index)
    room = (
        max_tab_length
        - wcswidth(SGR_ESCAPE.sub("", template))
        - draw_data.leading_spaces
        - min(max_tab_length - 1, draw_data.trailing_spaces)
        - wcswidth(suffix)
    )

    # Without room for a character and the ellipsis, leave it to kitty
    if room >= 2 and wcswidth(tab.title) > room:
        tab = tab._replace(title=truncate_line(tab.title, room))

    return tab._replace(title=tab.title + suffix)


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

    tab = _attention_colors(tab._replace(title=_tab_title(tab)))

    # Kitty leaves an extra unused cell per tab, which accumulates at status area. Let
    # the last tab use this space.
    if is_last and not extra_data.for_layout:
        text = _right_status_text()
        room = screen.columns - before - (wcswidth(text) + 1 if text else 0)
        max_title_length = max(max_title_length, room)

    tab = _fit_title(draw_data, tab, index, max_title_length, _stack_suffix(tab))

    end = draw_tab_with_separator(
        draw_data, screen, tab, before, max_title_length, index, is_last, extra_data
    )

    if is_last:
        _draw_right_status(screen, extra_data.for_layout)

    return end
