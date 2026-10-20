# Custom tab bar that displays available disk space, Codex and Claude Code
# usage in the far right corner. Disk space is sampled every redraw interval.
# Each cost is read from a cache file which is refreshed in the background
# by running ccusage at most once every REFRESH_INTERVAL seconds.
# See: https://github.com/kovidgoyal/kitty/discussions/4447

import json
import os
import subprocess
import sys
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

REFRESH_INTERVAL = 300  # seconds between ccusage runs
REDRAW_INTERVAL = 30  # seconds between tab bar redraws
STATUS_FG = as_rgb(0x656565)

_timer_id = None


class DiskSpace:
    """Cached available capacity of the startup filesystem."""

    def __init__(self) -> None:
        self.text = ""
        self.worker = None
        self.next_refresh = 0.0

    def _refresh(self) -> None:
        try:
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
                available = int(result.stdout.strip())
            elif sys.platform.startswith("linux"):
                stats = os.statvfs("/")
                available = stats.f_bavail * stats.f_frsize
            else:
                self.text = ""
                return

            self.text = f"⛁ {available // 1_000_000_000}G" if available >= 0 else ""
        except (OSError, ValueError, subprocess.SubprocessError):
            self.text = ""

    def maybe_refresh(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        if time.monotonic() < self.next_refresh:
            return

        self.next_refresh = time.monotonic() + REDRAW_INTERVAL
        self.worker = threading.Thread(target=self._refresh, daemon=True)
        self.worker.start()
        # Check completion on kitty's UI thread so the first result appears
        # promptly, without touching the UI from the background worker.
        add_timer(self._poll_refresh, 0.1, False)

    def _poll_refresh(self, timer_id=None) -> None:
        if self.worker is not None and self.worker.is_alive():
            add_timer(self._poll_refresh, 0.1, False)
        else:
            _mark_tab_bar_dirty()


class UsageSource:
    """Daily usage cost for one ccusage tool (claude, codex, ...)."""

    def __init__(self, tool: str, icon: str, cost_key: str) -> None:
        self.icon = icon
        self.cost_key = cost_key
        self.cache_path = os.path.expanduser(f"~/.cache/daily-usage-{tool}.json")

        # Write to a temp file and rename so a redraw never reads partial JSON.
        self.refresh_command = (
            # kitty may be launched from the Dock, where PATH lacks Homebrew (bunx).
            'PATH="/opt/homebrew/bin:$PATH"; '
            f'bunx ccusage {tool} daily --last 1 --offline --json > "{self.cache_path}.tmp" '
            f'&& mv "{self.cache_path}.tmp" "{self.cache_path}"'
        )

        self.proc = None
        self.mtime = None
        self.text = ""

    def usage_text(self) -> str:
        try:
            mtime = os.path.getmtime(self.cache_path)
        except OSError:
            return ""

        if mtime != self.mtime:
            self.mtime = mtime

            try:
                with open(self.cache_path) as f:
                    cost = json.load(f)["totals"][self.cost_key]

                self.text = ""

                if cost > 0:
                    self.text = f"{self.icon} {cost:,.2f}"
            except (OSError, ValueError, KeyError, TypeError):
                self.text = ""

        return self.text

    def maybe_refresh(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return

        try:
            if time.time() - os.path.getmtime(self.cache_path) < REFRESH_INTERVAL:
                return
        except OSError:
            pass

        self.proc = subprocess.Popen(
            ["/bin/sh", "-c", self.refresh_command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


SOURCES = (
    UsageSource("codex", "⌬", "costUSD"),
    UsageSource("claude", "✻", "totalCost"),
)
DISK_SPACE = DiskSpace()


def _maybe_refresh() -> None:
    DISK_SPACE.maybe_refresh()
    for source in SOURCES:
        source.maybe_refresh()


def _tick(timer_id=None) -> None:
    _maybe_refresh()
    _mark_tab_bar_dirty()


def _mark_tab_bar_dirty() -> None:
    tm = get_boss().active_tab_manager

    if tm is not None:
        tm.mark_tab_bar_dirty()


def _draw_right_status(screen: Screen) -> None:
    parts = [DISK_SPACE.text, *(s.usage_text() for s in SOURCES)]
    text = " ".join(t for t in parts if t)

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
