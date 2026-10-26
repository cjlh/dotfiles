# Custom kitten generated using Claude.
#
# Shows the windows of a tab in the stack layout in a bar above them, like the
# tabs of an i3 tabbed container or, with VERTICAL, the titles of a stacked one.
#
# The bar is a tab dock (kitty >= 0.50.0) at the top edge. It is created when a
# tab with more than one window switches to the stack layout and closed when it
# switches away. As docks are placed in creation order, a bar created after a
# left/right dock (see dock_window.py) only spans the stack and not that dock.
# Does nothing on versions of kitty without docks.
#
# Enable with: watcher stack_bar.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import kitty.types
from kitty.fast_data_types import (
    add_timer,
    get_boss,
    get_options,
    truncate_point_for_length,
    wcswidth,
)
from kitty.launch import launch, parse_launch_args
from kitty.tab_bar import draw_attributed_string

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.tabs import Tab
    from kitty.window import Window

# False: one row with the windows side by side (i3 tabbed)
# True: one row per window, stacked above each other (i3 stacked)
VERTICAL = False

STACK_LAYOUT = "stack"
# Marks bar windows, so that bars restored from a saved session are recognised
BAR_VAR = "stack_bar"
# The bar only shows what is drawn into it, so it runs a program that does nothing
BAR_COMMAND = ("sleep", "2147483647")

# Rounded pills matching the tab_title_template in tab_bar.conf
LEFT_CAP, RIGHT_CAP = "", ""
TITLE_FG = (255, 255, 255)
ACTIVE_BG = ACTIVE_CAP = (101, 101, 101)
INACTIVE_BG, INACTIVE_CAP = (68, 68, 68), (68, 68, 70)
MAX_TITLE_LENGTH = 24

SUPPORTS_DOCKS = hasattr(kitty.types, "DockSpec")

# Set on a tab manager by tab_bar.py while its tab bar is only being redrawn,
# such as to animate a spinner, with no bars to update. Must match there.
DRAW_ONLY_ATTR = "tab_bar_draw_only"

_pending = False
_bar_ids: set[int] = set()
_closing_ids: set[int] = set()


def _schedule() -> None:
    # Coalesce bursts of events into a single update on the next loop tick.
    # This also avoids creating or closing windows in the middle of a relayout.
    global _pending
    if SUPPORTS_DOCKS and not _pending:
        _pending = True
        add_timer(_update_all, 0, False)


def _update_all(timer_id: int | None) -> None:
    global _pending
    _pending = False
    boss = get_boss()
    # Forget windows that no longer exist
    _bar_ids.intersection_update(boss.window_id_map)
    _closing_ids.intersection_update(boss.window_id_map)
    for tab in tuple(boss.all_tabs):
        _update_tab(boss, tab)


def _is_bar(window: Window) -> bool:
    return window.id in _bar_ids or bool(window.user_vars.get(BAR_VAR))


def _update_tab(boss: Boss, tab: Tab) -> None:
    live_docks = [
        g for g in tab.windows.tab_docks if not any(w.id in _closing_ids for w in g)
    ]
    bars = [w for g in live_docks for w in g if _is_bar(w)]
    wanted = tab.current_layout.name == STACK_LAYOUT and len(tab.windows.groups) > 1
    # The bar must be the innermost tab dock to only span the stack, so it is
    # recreated if another dock was added after it
    misplaced = bool(bars) and bars[-1] not in live_docks[-1]
    if bars and (not wanted or misplaced or len(bars) > 1):
        for bar in bars:
            _closing_ids.add(bar.id)
            boss.mark_window_for_close(bar)
        bars = []
    if wanted and not bars:
        if (bar := _create_bar(boss, tab)) is not None:
            bars = [bar]
    if bars:
        _resize_bar(tab, bars[0])
        _draw(boss, tab, bars[0])


def _bar_rows(tab: Tab) -> int:
    return len(tab.windows.groups) if VERTICAL else 1


def _create_bar(boss: Boss, tab: Tab) -> Window | None:
    spec = parse_launch_args(
        [
            "--type=tab-dock",
            "--dock-edge=top",
            f"--dock-size={_bar_rows(tab)}",
            "--dock-skip-focus",
            "--keep-focus",
            f"--var={BAR_VAR}=1",
            *BAR_COMMAND,
        ]
    )
    bar = launch(boss, spec.opts, spec.args, target_tab=tab, force_target_tab=True)
    if bar is not None:
        _bar_ids.add(bar.id)
        # The borders were computed while the bar was being created, before it
        # could be recognised as a bar, so recompute them to drop its border
        tab.relayout_borders()
    return bar


def _resize_bar(tab: Tab, bar: Window) -> None:
    # A vertical bar grows and shrinks with the stack. Docks have no API to be
    # resized, so swap in a resized copy of the dock spec and relayout.
    group = tab.windows.group_for_window(bar)
    rows = _bar_rows(tab)
    if group is not None and group.dock is not None and group.dock.size != rows:
        group.dock = group.dock._replace(size=rows)
        tab.relayout()


def _short_title(title: str, max_length: int) -> str:
    "Same as tab_title_template in tab_bar.conf: the basename of the first word"
    words = title.split()
    title = (words[0].rsplit("/", 1)[-1] if words else "") or "/"
    if wcswidth(title) > max_length:
        title = title[: truncate_point_for_length(title, max_length)] + "…"
    return title


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _unfaded(
    target: tuple[int, ...], under: tuple[int, ...], alpha: float
) -> tuple[int, ...]:
    """
    The bar never has focus, so kitty always fades its text with
    inactive_text_alpha, blending it with the cell background in linear light.
    Return the text colour that ends up as target once faded over under. Colours
    brighter than the fade allows (such as white) are clamped.
    """
    ans = []
    for t, u in zip(target, under):
        lin = (
            _srgb_to_linear(t / 255) - (1 - alpha) * _srgb_to_linear(u / 255)
        ) / alpha
        ans.append(round(255 * _linear_to_srgb(min(max(lin, 0.0), 1.0))))
    return tuple(ans)


def _sgr(color: tuple[int, ...]) -> str:
    return ";".join(map(str, color))


def _pill(
    title: str, width: int, is_active: bool, default_bg: tuple[int, ...], alpha: float
) -> str:
    "A pill of exactly width cells with the title centred in it"
    bg, cap = (ACTIVE_BG, ACTIVE_CAP) if is_active else (INACTIVE_BG, INACTIVE_CAP)
    # The caps are glyphs drawn over the default background, the title over the pill
    left_cap, right_cap = (
        _sgr(_unfaded(cap, default_bg, alpha)),
        _sgr(_unfaded(bg, default_bg, alpha)),
    )
    fg = _sgr(_unfaded(TITLE_FG, bg, alpha))
    inner = max(width - 2, 0)
    # Keep a cell of space on either side of the title inside the pill
    title = _short_title(title, min(MAX_TITLE_LENGTH, inner - 3)) if inner > 3 else ""
    pad = inner - wcswidth(title)
    return (
        f"\x1b[38;2;{left_cap};49m{LEFT_CAP}"
        f"\x1b[38;2;{fg};48;2;{_sgr(bg)}m{' ' * (pad // 2)}{title}{' ' * (pad - pad // 2)}"
        f"\x1b[38;2;{right_cap};49m{RIGHT_CAP}\x1b[m"
    )


def _draw(boss: Boss, tab: Tab, bar: Window) -> None:
    screen = bar.screen
    active_idx = tab.windows.active_group_idx
    bg = screen.color_profile.default_bg
    default_bg = (bg.red, bg.green, bg.blue)
    alpha = abs(get_options().inactive_text_alpha) or 1.0
    titles = []
    for group in tab.windows.groups:
        window = boss.window_id_map.get(group.active_window_id)
        titles.append(window.title if window else "")
    if not titles:
        return
    screen.cursor_visible = False
    screen.erase_in_display(2, False)
    if VERTICAL:
        # A full width pill per row
        for i, title in enumerate(titles[: screen.lines]):
            screen.cursor.x, screen.cursor.y = 0, i
            draw_attributed_string(
                _pill(title, screen.columns, i == active_idx, default_bg, alpha), screen
            )
    else:
        # Equal width pills, unlike the tab bar, with a one cell gap between them
        available = screen.columns - (len(titles) - 1)
        pills = []
        for i, title in enumerate(titles):
            width = available // len(titles) + (1 if i < available % len(titles) else 0)
            pills.append(_pill(title, width, i == active_idx, default_bg, alpha))
        screen.cursor.x = screen.cursor.y = 0
        draw_attributed_string(" ".join(pills), screen)
    screen.mark_as_dirty()


def _patch_dock_borders() -> None:
    # Docks get a border on their inner edge, which there is no option to turn
    # off for a single dock, so drop the one below the bar. This only covers
    # draw_minimal_borders, which draws the borders of docks this way.
    from kitty.layout.base import Layout

    original = Layout.dock_borders
    if getattr(original, "skips_stack_bar", False):
        return

    def dock_borders(self: Any, *args: Any, **kwargs: Any) -> Any:
        for line in original(self, *args, **kwargs):
            window = get_boss().window_id_map.get(abs(line.window_id))
            if window is None or not _is_bar(window):
                yield line

    dock_borders.skips_stack_bar = True  # type: ignore[attr-defined]
    Layout.dock_borders = dock_borders  # type: ignore[method-assign]


def on_load(boss: Boss, data: dict[str, Any]) -> None:
    if SUPPORTS_DOCKS:
        _patch_dock_borders()
        _schedule()


def on_tab_bar_dirty(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # Layout changes, focus changes and windows being added or removed
    if not getattr(data.get("tab_manager"), DRAW_ONLY_ATTR, False):
        _schedule()


def on_title_change(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    _schedule()


def on_resize(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    _schedule()


def on_close(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    _schedule()
