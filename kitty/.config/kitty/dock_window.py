# Custom kitten generated using Claude.
#
# Turns the active window into a dock at the left of the tab and opens a new
# window next to it in the stack layout, so that the docked window stays visible
# while the windows on the right are leafed through. Pairs with stack_bar.py.
#
# When the last window next to the dock is closed, the docked window becomes a
# normal window again and the tab goes back to its previous layout, instead of
# kitty closing the dock, and with it the whole tab.
#
# Docks at the edges of a tab can also be resized by dragging their border with
# the mouse, which kitty does not support itself.
#
# Requires kitty >= 0.50.0 for docked windows, does nothing on older versions.
# kitty has no action for docking an existing window, so this moves the window
# using the same internals kitty uses to move windows between tabs.
#
# Enable with:
#   map cmd+shift+d kitten dock_window.py
#   watcher dock_window.py

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
# Restored when undocking in a tab that was not docked by this kitten
DEFAULT_LAYOUT = "splits"
# The kitten and the watcher are separate instances of this module, so the
# layout to restore when undocking is kept on the tab itself
PREVIOUS_LAYOUT_ATTR = "_dock_window_previous_layout"
# Limits when resizing docks with the mouse
MIN_DOCK_PERCENT, MAX_DOCK_PERCENT = 5, 95
MIN_DOCK_CELLS = 2

SUPPORTS_DOCKS = hasattr(kitty.types, "DockSpec")


def main(args: list[str]) -> None:
    pass


def _move_window(tab: Tab, window: Window, dock: DockSpec | None = None) -> None:
    "Move window into a new dock of tab, or out of one when dock is None, without relayouting"
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
    # Also refuse windows that are already docked or cannot simply be moved, as
    # they have overlays (such as the hints kitten) or docks of their own
    if group is None or group.dock is not None or len(group.windows) > 1 or group.docks:
        boss.ring_bell_if_allowed()
        return

    # Open the new window first so that the tab always has a normal window,
    # otherwise kitty would close its docks
    spec = parse_launch_args(["--cwd=current"])
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
    "Turn a docked window back into a normal one when window is the last normal window of tab"
    wl = tab.windows
    group = wl.group_for_window(window)
    if (
        group is None
        or group.dock is not None
        or len(group.windows) > 1
        or len(wl.groups) > 1
    ):
        return
    # Not focusable docks, such as the stack bar, are left to be closed
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
    # This runs while window is being destroyed, so nothing here may relayout,
    # that happens once kitty has finished removing window
    _move_window(tab, dock.windows[0])
    layout = getattr(tab, PREVIOUS_LAYOUT_ATTR, DEFAULT_LAYOUT)

    def restore_layout(timer_id: int | None) -> None:
        if tab.windows.groups:
            tab.goto_layout(layout)

    add_timer(restore_layout, 0, False)


def _resizable_dock(tab: Tab, window_id: int) -> WindowGroup | None:
    "The tab dock of the window, if it is one that can be resized with the mouse"
    # Layouts also resize things that are not windows, such as the dividers of
    # the splits layout, with ids that are not window ids
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
    "Grow the dock by cells, or shrink it when negative, returning the cells applied"
    from kitty.layout.base import lgd

    spec = group.dock
    if spec.size_is_percent:
        # Scale the percentage, so that the dock keeps its proportion of the tab
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
    # Layouts only know how to resize their own windows, so when the border of a
    # dock is grabbed, point the drag at the dock instead
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
                # Docks at the left or right resize sideways, the others up and down
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
            # Never get in the way of kitty removing the window
            log_error(
                f"dock_window.py: failed to undock before removing a window:\n{traceback.format_exc()}"
            )
        original(self, window, *args, **kwargs)

    return remove_window


def _patch(cls: type, name: str, make_wrapper: Callable[[Any], Any]) -> None:
    "Wrap a method of a kitty class, once even if this watcher is loaded again"
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
