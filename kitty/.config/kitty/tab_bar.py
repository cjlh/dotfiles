# Custom tab bar that displays available disk space, Codex and Claude Code
# usage in the far right corner. Disk space is sampled every redraw interval.
# All providers read JSON caches in ~/.cache/kitty-tab-bar and refresh them
# in the background. Agent usage is refreshed every CCUSAGE_REFRESH_INTERVAL seconds.
# See: https://github.com/kovidgoyal/kitty/discussions/4447

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

from kitty.boss import get_boss
from kitty.fast_data_types import Screen, add_timer, wcswidth
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    as_rgb,
    draw_tab_with_separator,
)

CCUSAGE_REFRESH_INTERVAL = 300  # seconds between ccusage runs
REDRAW_INTERVAL = 30  # seconds between tab bar redraws
CACHE_DIR = os.path.expanduser("~/.cache/kitty-tab-bar")
STATUS_FG = as_rgb(0x656565)

_timer_id = None


class StatusProvider:
    """A status item backed by an atomically refreshed JSON cache."""

    def __init__(self, name: str, icon: str, refresh_interval: int) -> None:
        self.name = name
        self.icon = icon
        self.refresh_interval = refresh_interval
        self.cache_path = os.path.join(CACHE_DIR, f"{name}.json")
        self.worker = None
        self.next_refresh = None
        self.mtime = None
        self.text = ""

    def fetch_data(self):
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

    def _refresh(self) -> None:
        temp_path = None
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            data = self.fetch_data()
            self.format_data(data)  # Validate before replacing a good cache.
            with tempfile.NamedTemporaryFile(
                mode="w", dir=CACHE_DIR, prefix=f".{self.name}-", delete=False
            ) as f:
                temp_path = f.name
                json.dump(data, f, allow_nan=False)
            os.replace(temp_path, self.cache_path)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            pass
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def maybe_refresh(self) -> None:
        if self.worker is not None and self.worker.is_alive():
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
        self.worker = threading.Thread(target=self._refresh, daemon=True)
        self.worker.start()
        add_timer(self._poll_refresh, 0.1, False)

    def _poll_refresh(self, timer_id=None) -> None:
        if self.worker is not None and self.worker.is_alive():
            add_timer(self._poll_refresh, 0.1, False)
        else:
            _mark_tab_bar_dirty()


class DiskProvider(StatusProvider):
    def __init__(self) -> None:
        super().__init__("disk", "⛁", REDRAW_INTERVAL)

    def fetch_data(self):
        if sys.platform == "darwin":
            helper = os.path.join(os.path.dirname(__file__), "disk_available.js")
            result = subprocess.run(
                ["/usr/bin/osascript", "-l", "JavaScript", helper],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=True,
                timeout=5,
            )
            return int(result.stdout.strip())
        if sys.platform.startswith("linux"):
            stats = os.statvfs("/")
            return stats.f_bavail * stats.f_frsize
        raise ValueError("Unsupported disk capacity platform")

    def format_data(self, data) -> str:
        if not isinstance(data, int) or isinstance(data, bool) or data < 0:
            raise ValueError("Invalid available disk capacity")
        return f"{self.icon} {data // 1_000_000_000}G"


class AgentUsageProvider(StatusProvider):
    """Daily usage cost for one ccusage tool (claude, codex, ...)."""

    def __init__(self, tool: str, icon: str, cost_key: str) -> None:
        super().__init__(tool, icon, CCUSAGE_REFRESH_INTERVAL)
        self.cost_key = cost_key

    def fetch_data(self):
        # kitty may be launched from the Dock without Homebrew in PATH.
        env = dict(os.environ)
        env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")
        result = subprocess.run(
            ["bunx", "ccusage", self.name, "daily", "--last", "1", "--offline", "--json"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
            timeout=120,
        )
        return json.loads(result.stdout)

    def format_data(self, data) -> str:
        cost = data["totals"][self.cost_key]
        return f"{self.icon} {cost:,.2f}" if cost > 0 else ""


PROVIDERS = (
    DiskProvider(),
    AgentUsageProvider("codex", "⌬", "costUSD"),
    AgentUsageProvider("claude", "✻", "totalCost"),
)


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
