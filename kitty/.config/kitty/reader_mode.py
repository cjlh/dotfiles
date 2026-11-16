# Custom kitten generated using Claude.
#
# Toggles a reader mode for the current window, which keeps its text to a
# column of a fixed width in the middle, by padding the window at the sides.
# Programs see a terminal of that width, so they wrap and lay out to it.
#
# In the stack layout, reader mode applies to all the windows in the stack:
# toggling it in one toggles it in all of them, and windows opened in or moved
# to the stack take it on from the others.
#
# While the window is the only one visible in the active tab (or the active
# window of the stack layout), the tab bar and the bar of stack_bar.py are
# kept to the same column.
#
# The watcher keeps the column centred when the OS window is resized, the font
# size changes, or windows are opened, closed or moved. Windows narrower than
# the column keep their configured padding.
#
# Enable with:
#   map ctrl+alt+shift+c kitten reader_mode.py [columns]
#   watcher reader_mode.py

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
# The columns of a window in reader mode are kept in a user var, so that they
# are saved with sessions, along with the padding
COLUMNS_VAR = "reader_mode"
# Set on windows padded by this module, to restore their padding when reader
# mode is turned off
PADDED_ATTR = "_reader_mode_padded"
# Must match stack_bar.py
STACK_LAYOUT = "stack"
STACK_BAR_VAR = "stack_bar"
DRAW_ONLY_ATTR = "tab_bar_draw_only"
# Spare pixels left over when padding, so that rounding the padding when it is
# converted from pts to pixels never loses a column
SLACK_PX = 2


def main(args: list[str]) -> None:
    pass


def _columns(window: Window | None) -> int | None:
    try:
        return int(window.user_vars[COLUMNS_VAR]) if window is not None else None
    except (KeyError, ValueError):
        return None


def _is_stack_bar(window: Window) -> bool:
    return bool(window.user_vars.get(STACK_BAR_VAR))


def _side_padding_pt(window: Window, columns: int) -> float | None:
    "The padding in pts for each side of window to fit columns, or None for the configured padding"
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
    "Set the left and right padding of window, returning whether it changed"
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
    "The columns of the active window of tab when it is in reader mode and the only window visible"
    window = tab.active_window if tab is not None else None
    columns = _columns(window)
    if columns is None or window.padding.left is None:
        return None
    if not tab.has_single_window_visible():
        return None
    # Docks (kitty >= 0.50.0) other than the stack bar, such as from dock_window.py
    iter_docks = getattr(tab.windows, "iter_dock_groups", None)
    if iter_docks is not None:
        for group in iter_docks(only_visible=True):
            if any(w is not window and not _is_stack_bar(w) for w in group):
                return None
    return columns


def _stack(tab: Tab | None) -> list[Window]:
    "The windows in the stack, when tab is in the stack layout, without docks and overlays"
    if tab is None or tab.current_layout.name != STACK_LAYOUT:
        return []
    return [
        g.windows[0]
        for g in tab.windows.iter_all_layoutable_groups()
        if g.windows and not _is_stack_bar(g.windows[0])
    ]


def _sync_stack(tab: Tab) -> None:
    "When any window in the stack is in reader mode, put all of them in it, preferring the active one's columns"
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
    bars = []
    for window in tab:
        if _is_stack_bar(window):
            bars.append(window)
        elif (columns := _columns(window)) is not None:
            changed |= _set_side_padding(window, _side_padding_pt(window, columns))
        elif getattr(window, PADDED_ATTR, False):
            changed |= _set_side_padding(window, None)
    # The stack bar follows the active window, once it has been padded. Its
    # padding is always managed here, as it may be restored from a session.
    bar_columns = _centred_columns(tab)
    for window in bars:
        pt = _side_padding_pt(window, bar_columns) if bar_columns is not None else None
        changed |= _set_side_padding(window, pt)
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
        # The tab bar's margins are painted over with the borders of the tabs,
        # without this the tab bar stays drawn where it was in them
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
    if tm is None or _is_stack_bar(window):
        return
    try:
        columns = int(args[1]) if len(args) > 1 else DEFAULT_COLUMNS
    except ValueError:
        log_error(f"reader_mode: not a number of columns: {args[1]}")
        return
    # Toggle off, unless switching to a different width
    value = None if _columns(window) == columns else str(columns)
    stack = _stack(window.tabref())
    for w in stack if window in stack else [window]:
        w.set_user_var(COLUMNS_VAR, value)
    _update(tm)


def on_resize(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # The OS window was resized, the font size changed, or a window was opened,
    # closed or moved here from another OS window
    _schedule(boss, window.os_window_id)


def on_tab_bar_dirty(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    # Another tab or window was focused, the layout changed, windows were
    # opened or closed, or the config was reloaded, which resets the tab bar
    # margin. Called synchronously, so defer the work.
    tm = data.get("tab_manager")
    if tm is not None and not getattr(tm, DRAW_ONLY_ATTR, False):
        _schedule(boss, tm.os_window_id)
