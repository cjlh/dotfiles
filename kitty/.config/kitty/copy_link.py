"""Copy the link under the mouse to the clipboard.

Handles both OSC 8 hyperlinks (where the URL is not shown on screen) and
plain-text URLs. When there is no link under the mouse, falls back to
extending the selection, which is what right click does by default.

Usage: mouse_map right press ungrabbed kitten copy_link.py
"""

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.clipboard import set_clipboard_string
from kitty.fast_data_types import MOUSE_SELECTION_EXTEND


def main(args: list[str]) -> None:
    pass


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: str, target_window_id: int, boss: Boss) -> None:
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return
    pos = window.current_mouse_position()
    url = None
    if pos is not None:
        x, y = pos['cell_x'], pos['cell_y']
        screen = window.screen
        url = screen.hyperlink_at(x, y)
        if not url:
            screen.detect_url(x, y)
            url = screen.current_url_text()
    if url:
        set_clipboard_string(url)
    else:
        window.mouse_selection(MOUSE_SELECTION_EXTEND)
