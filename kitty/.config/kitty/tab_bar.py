# Custom tab bar that displays Codex and Claude Code usage in the far
# right corner.
# Each cost is read from a cache file which is refreshed in the background
# by running ccusage at most once every REFRESH_INTERVAL seconds.
# See: https://github.com/kovidgoyal/kitty/discussions/4447

import json
import os
import subprocess
import time

from kitty.boss import get_boss
from kitty.fast_data_types import Screen, add_timer
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

                self.text = f"{self.icon} {max(0, cost):,.2f}"
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


def _maybe_refresh() -> None:
    for source in SOURCES:
        source.maybe_refresh()


def _tick(timer_id=None) -> None:
    _maybe_refresh()

    tm = get_boss().active_tab_manager

    if tm is not None:
        tm.mark_tab_bar_dirty()


def _draw_right_status(screen: Screen) -> None:
    text = " ".join(t for t in (s.usage_text() for s in SOURCES) if t)

    if not text:
        return

    padding = screen.columns - screen.cursor.x - len(text)

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
