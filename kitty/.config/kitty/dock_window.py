# Custom kitten generated using Claude.
#
# Dock the current window on the left and open a stack on the right.
# Restore the dock as a normal window when the last stacked window closes.
# Also allow docks to be resized by dragging their borders.
#
# Requires kitty >= 0.50.0. Load as both a kitten and a watcher.

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import kitty.types
from kittens.tui.handler import result_handler
from kitty.fast_data_types import (
    BOTTOM_EDGE,
    LEFT_EDGE,
    RIGHT_EDGE,
    TOP_EDGE,
    add_timer,
)
from kitty.launch import launch, parse_launch_args
from kitty.utils import log_error

if TYPE_CHECKING:
    from kitty.boss import Boss
    from kitty.tabs import Tab
    from kitty.types import DockSpec
    from kitty.window import Window
    from kitty.window_list import WindowGroup

DOCK_EDGE = "left"
DOCK_SIZE = "50%"
STACK_LAYOUT = "stack"
# Fallback when the tab has no saved layout.
DEFAULT_LAYOUT = "splits"
# Store the previous layout on the tab: the kitten and watcher load separately.
PREVIOUS_LAYOUT_ATTR = "_dock_window_previous_layout"
MIN_DOCK_PERCENT, MAX_DOCK_PERCENT = 5, 95
MIN_DOCK_CELLS = 2

SUPPORTS_DOCKS = hasattr(kitty.types, "DockSpec")


def main(args: list[str]) -> None:
    pass


def _move_window(tab: Tab, window: Window, dock: DockSpec | None = None) -> None:
    """Move a window into or out of a dock without triggering a layout update."""
    tab.remove_window(window, destroy=False, do_post_removal_update=False)
    tab._take_ownership_of_window(window)
    tab.current_layout.add_window(tab.windows, window, dock=dock)


@result_handler(no_ui=True)
def handle_result(
    args: list[str], answer: None, target_window_id: int, boss: Boss
) -> None:
    window = boss.window_id_map.get(target_window_id)
    tab = window.tabref() if window is not None else None
    group = (
        tab.windows.group_for_window(window)
        if SUPPORTS_DOCKS and tab is not None
        else None
    )
    # Moving a window with overlays or docks would leave those windows behind.
    if group is None or group.dock is not None or len(group.windows) > 1 or group.docks:
        boss.ring_bell_if_allowed()
        return

    # Create a normal window first; kitty closes docks when none remain.
    spec = parse_launch_args(["--cwd=oldest"])
    if (
        new_window := launch(
            boss, spec.opts, spec.args, target_tab=tab, force_target_tab=True
        )
    ) is None:
        return
    setattr(tab, PREVIOUS_LAYOUT_ATTR, tab.current_layout.name)
    _move_window(tab, window, kitty.types.parse_dock_spec(DOCK_EDGE, DOCK_SIZE))
    tab.goto_layout(STACK_LAYOUT)
    # goto_layout() does nothing when the tab already uses the stack layout
    tab.relayout()
    tab.set_active_window(new_window)


def _undock_if_last_normal_window(tab: Tab, window: Window) -> None:
    """Undock a window before closing the tab's last normal window."""
    wl = tab.windows
    group = wl.group_for_window(window)
    if (
        group is None
        or group.dock is not None
        or len(group.windows) > 1
        or len(wl.groups) > 1
    ):
        return
    dock = next(
        (
            g
            for g in wl.tab_docks
            if g.dock is not None and g.dock.focusable and len(g.windows) == 1
        ),
        None,
    )
    if dock is None:
        return
    # Move the dock now so it survives removal. Defer relayout until kitty finishes.
    _move_window(tab, dock.windows[0])
    layout = getattr(tab, PREVIOUS_LAYOUT_ATTR, DEFAULT_LAYOUT)

    def restore_layout(timer_id: int | None) -> None:
        if tab.windows.groups:
            tab.goto_layout(layout)

    add_timer(restore_layout, 0, False)


def _resizable_dock(tab: Tab, window_id: int) -> WindowGroup | None:
    """Find a resizable tab dock for this window ID."""
    # Layout object IDs can refer to dividers rather than windows.
    if (window := tab.windows.id_map.get(window_id)) is None:
        return None
    group = tab.windows.group_for_window(window)
    if (
        group is not None
        and group in tab.windows.tab_docks
        and group.dock is not None
        and group.dock.focusable
    ):
        return group
    return None


def _resize_dock(tab: Tab, group: WindowGroup, cells: float) -> float:
    """Resize a dock by a signed cell count and return the amount applied."""
    from kitty.layout.base import lgd

    spec = group.dock
    if spec.size_is_percent:
        area = next(
            (a for g, a in tab.current_layout.tab_dock_placements if g is group), None
        )
        if area is None:
            return 0
        extent, cell = (
            (area.height, lgd.cell_height)
            if spec.is_horizontal
            else (area.width, lgd.cell_width)
        )
        size = min(
            max(spec.size * (extent + cells * cell) / max(extent, 1), MIN_DOCK_PERCENT),
            MAX_DOCK_PERCENT,
        )
    else:
        size = max(spec.size + cells, MIN_DOCK_CELLS)
    if size == spec.size:
        return 0
    group.dock = spec._replace(size=size)
    tab.relayout()
    return cells


def _drag_resize_start(original: Callable[..., bool]) -> Callable[..., bool]:
    # Layouts cannot resize docks themselves, so redirect the drag to the dock.
    def drag_resize_start(
        self: Boss,
        edges: int,
        x: float,
        y: float,
        window_id: int,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        started = original(self, edges, x, y, window_id, *args, **kwargs)
        try:
            if (
                started
                and (w := self.window_id_map.get(window_id))
                and (tab := w.tabref())
                and (group := _resizable_dock(tab, w.id))
            ):
                sideways = not group.dock.is_horizontal
                data = kitty.types.WindowResizeDragData(
                    w.id if sideways and edges & (LEFT_EDGE | RIGHT_EDGE) else None,
                    bool(edges & RIGHT_EDGE),
                    w.id if not sideways and edges & (TOP_EDGE | BOTTOM_EDGE) else None,
                    bool(edges & BOTTOM_EDGE),
                )
                self.drag_resize_of_window = self.drag_resize_of_window._replace(
                    data=data
                )
        except Exception:
            log_error(
                f"dock_window.py: failed to start resizing a dock:\n{traceback.format_exc()}"
            )
        return started

    return drag_resize_start


def _drag_resize_window(original: Callable[..., float]) -> Callable[..., float]:
    def drag_resize_window(
        self: Tab,
        object_id: int,
        increment: float,
        is_horizontal: bool,
        *args: Any,
        **kwargs: Any,
    ) -> float:
        try:
            if (group := _resizable_dock(self, object_id)) is not None:
                return (
                    _resize_dock(self, group, increment)
                    if is_horizontal != group.dock.is_horizontal
                    else 0
                )
        except Exception:
            log_error(
                f"dock_window.py: failed to resize a dock:\n{traceback.format_exc()}"
            )
            return 0
        return original(self, object_id, increment, is_horizontal, *args, **kwargs)

    return drag_resize_window


def _remove_window(original: Callable[..., None]) -> Callable[..., None]:
    # kitty closes the docks of a tab when its last normal window is removed,
    # which happens inside Tab.remove_window() before any watcher is called
    def remove_window(self: Tab, window: Window, *args: Any, **kwargs: Any) -> None:
        try:
            _undock_if_last_normal_window(self, window)
        except Exception:
            # A failed undock must not prevent window removal.
            log_error(
                f"dock_window.py: failed to undock before removing a window:\n{traceback.format_exc()}"
            )
        original(self, window, *args, **kwargs)

    return remove_window


def _patch(cls: type, name: str, make_wrapper: Callable[[Any], Any]) -> None:
    """Wrap a kitty method once, even across watcher reloads."""
    original = getattr(cls, name)
    if getattr(original, "patched_by_dock_window", False):
        return
    wrapper = make_wrapper(original)
    wrapper.patched_by_dock_window = True
    setattr(cls, name, wrapper)


def on_load(boss: Boss, data: dict[str, Any]) -> None:
    if not SUPPORTS_DOCKS:
        return
    from kitty.boss import Boss
    from kitty.tabs import Tab

    _patch(Tab, "remove_window", _remove_window)
    _patch(Boss, "drag_resize_start", _drag_resize_start)
    _patch(Tab, "drag_resize_window", _drag_resize_window)
