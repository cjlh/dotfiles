# Custom kitten generated using Claude.
#
# Has tab_bar.py pick the active tab's icon anew, keeping its name, as
# name_tab.py does after naming a tab. Tabs that haven't been renamed have no
# icon, and are refused with a bell.
#
# Enable with: map ctrl+alt+shift+i kitten pick_tab_icon.py

from __future__ import annotations

from typing import TYPE_CHECKING

from kittens.tui.handler import result_handler

if TYPE_CHECKING:
    from kitty.boss import Boss

# Set on tabs to have tab_bar.py pick their icon anew. Must match REPICK_ICON_ATTR there.
REPICK_ICON_ATTR = "tab_bar_repick_icon"


def main(args: list[str]) -> None:
    pass


@result_handler(no_ui=True)
def handle_result(
    args: list[str], answer: None, target_window_id: int, boss: Boss
) -> None:
    window = boss.window_id_map.get(target_window_id)
    tab = window.tabref() if window is not None else None
    if tab is None or not tab.name:
        boss.ring_bell_if_allowed()
        return

    setattr(tab, REPICK_ICON_ATTR, True)
    tab.mark_tab_bar_dirty()
