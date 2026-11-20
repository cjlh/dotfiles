# Dump tab bar text as JSON, one string per OS window.
#
# Force a redraw first: hidden test windows do not render automatically, so
# their existing tab bar text may be stale or empty.
#
# Usage: instance.sh rc <sandbox> kitten /path/to/tab_bar_text.py <output.json>

import json

from kittens.tui.handler import result_handler


def main(args: list[str]) -> None:
    pass


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss) -> None:
    texts = []
    for tm in boss.os_window_map.values():
        tm.update_tab_bar_data()
        texts.append(str(tm.tab_bar.screen.line(0)).rstrip())
    with open(args[-1], 'w') as f:
        json.dump(texts, f, indent=2, ensure_ascii=False)
