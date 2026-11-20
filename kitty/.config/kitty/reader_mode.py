# Custom kitten generated using Claude.
#
# Centre terminal content in a fixed-width column using side padding.
# Programs see the narrower terminal width and wrap their output to fit.
# Stacked windows share the width; the tab bar aligns when no other windows
# are visible. Narrow windows keep their configured padding.
#
# Run as a kitten with an optional column count, and load as a watcher to
# maintain alignment as windows change.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kittens.tui.handler import result_handler
from kitty.fast_data_types import (
    add_timer,
    cell_size_for_window,
    get_options,
    pt_to_px,
    viewport_for_window,
)
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.tabs import Tab, TabManager
    from kitty.window import Window

DEFAULT_COLUMNS = 120
# Save the column count in a user variable so it survives session restoration.
COLUMNS_VAR = "reader_mode"
# Track which windows need their original padding restored.
PADDED_ATTR = "_reader_mode_padded"
STACK_LAYOUT = "stack"
# Skip layout updates for redraws that only animate the tab bar.
DRAW_ONLY_ATTR = "tab_bar_draw_only"
# Leave room for point-to-pixel rounding so it cannot cost a text column.
SLACK_PX = 2


def main(args: list[str]) -> None:
    pass


def _columns(window: Window | None) -> int | None:
    try:
        return int(window.user_vars[COLUMNS_VAR]) if window is not None else None
    except (KeyError, ValueError):
        return None


def _side_padding_pt(window: Window, columns: int) -> float | None:
    """Calculate side padding in points, or None to use the configured padding."""
    os_window_id = window.os_window_id
    cell_width = cell_size_for_window(os_window_id)[0]
    g = window.geometry
    # The width available for the text and the padding, including the leftover
    # space from the width not being a multiple of the cell width
    available = (
        g.right
        - g.left
        + window.effective_padding("left")
        + window.effective_padding("right")
        + g.compensatory.left
        + g.compensatory.right
    )
    side = (available - columns * cell_width - SLACK_PX) // 2
    configured = get_options().window_padding_width
    if side <= max(
        pt_to_px(configured.left, os_window_id),
        pt_to_px(configured.right, os_window_id),
    ):
        return None
    return side * 1000 / max(1, pt_to_px(1000, os_window_id))


def _set_side_padding(window: Window, pt: float | None) -> bool:
    """Set side padding and report whether it changed."""
    setattr(window, PADDED_ATTR, pt is not None)
    current = window.padding.left
    if current == pt or (
        current is not None and pt is not None and abs(current - pt) < 0.01
    ):
        return False
    window.patch_edge_width("padding", "left", pt)
    window.patch_edge_width("padding", "right", pt)
    return True


def _centred_columns(tab: Tab | None) -> int | None:
    """Return the reader width when the active window is the only visible window."""
    window = tab.active_window if tab is not None else None
    columns = _columns(window)
    if columns is None or window.padding.left is None:
        return None
    if not tab.has_single_window_visible():
        return None
    # Visible docks also prevent the text column from spanning the tab.
    iter_docks = getattr(tab.windows, "iter_dock_groups", None)
    if iter_docks is not None:
        for group in iter_docks(only_visible=True):
            if any(w is not window for w in group):
                return None
    return columns


def _stack(tab: Tab | None) -> list[Window]:
    """Return stacked windows, excluding docks and overlays."""
    if tab is None or tab.current_layout.name != STACK_LAYOUT:
        return []
    return [
        g.windows[0]
        for g in tab.windows.iter_all_layoutable_groups()
        if g.windows
    ]


def _sync_stack(tab: Tab) -> None:
    """Share reader mode across the stack, preferring the active window's width."""
    stack = _stack(tab)
    active = tab.active_window
    candidates = ([active] if active in stack else []) + stack
    columns = next((c for w in candidates if (c := _columns(w)) is not None), None)
    if columns is not None:
        for window in stack:
            if _columns(window) != columns:
                window.set_user_var(COLUMNS_VAR, str(columns))


def _update_windows(tab: Tab) -> None:
    _sync_stack(tab)
    changed = False
    for window in tab:
        if (columns := _columns(window)) is not None:
            changed |= _set_side_padding(window, _side_padding_pt(window, columns))
        elif getattr(window, PADDED_ATTR, False):
            changed |= _set_side_padding(window, None)
    if changed:
        tab.relayout()


def _update_tab_bar(tm: TabManager) -> None:
    tab_bar = tm.tab_bar
    if tab_bar.is_vertical:
        return
    os_window_id = tm.os_window_id
    margin = configured = pt_to_px(get_options().tab_bar_margin_width, os_window_id)
    if (columns := _centred_columns(tm.active_tab)) is not None:
        tab_bar_region = viewport_for_window(os_window_id)[1]
        cell_width = cell_size_for_window(os_window_id)[0]
        margin = max(configured, (tab_bar_region.width - columns * cell_width) // 2)
    if tab_bar.margin_width != margin:
        tab_bar.margin_width = margin
        tm.layout_tab_bar()
        # Repaint the borders to clear the old tab bar from the margins.
        for tab in tm:
            tab.relayout_borders()


def _update(tm: TabManager) -> None:
    try:
        for tab in tm:
            _update_windows(tab)
        _update_tab_bar(tm)
    except Exception:
        import traceback

        log_error(f"reader_mode: {traceback.format_exc()}")


_pending: set[int] = set()


def _schedule(boss: Boss, os_window_id: int) -> None:
    if os_window_id in _pending:
        return
    _pending.add(os_window_id)

    def callback(timer_id: int | None) -> None:
        _pending.discard(os_window_id)
        if (tm := boss.os_window_map.get(os_window_id)) is not None:
            _update(tm)

    add_timer(callback, 0, False)


@result_handler(no_ui=True)
def handle_result(
    args: list[str], answer: None, target_window_id: int, boss: Boss
) -> None:
    window = boss.window_id_map.get(target_window_id)
    tm = boss.os_window_map.get(window.os_window_id) if window is not None else None
    if tm is None:
        return
    try:
        columns = int(args[1]) if len(args) > 1 else DEFAULT_COLUMNS
    except ValueError:
        log_error(f"reader_mode: not a number of columns: {args[1]}")
        return
    value = None if _columns(window) == columns else str(columns)
    stack = _stack(window.tabref())
    for w in stack if window in stack else [window]:
        w.set_user_var(COLUMNS_VAR, value)
    _update(tm)


def on_resize(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    _schedule(boss, window.os_window_id)


def on_tab_bar_dirty(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # Defer layout updates until kitty has finished processing the current change.
    tm = data.get("tab_manager")
    if tm is not None and not getattr(tm, DRAW_ONLY_ATTR, False):
        _schedule(boss, tm.os_window_id)
