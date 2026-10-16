# A kitten that dumps kitty's internal window state as JSON, for checking what
# a config change did. Runs inside kitty, so it sees state that `kitten @ ls`
# does not report, such as docks, and the text currently shown in each window.
#
# Usage: instance.sh rc <sandbox> kitten /path/to/inspect_tabs.py <output.json>

import json

from kittens.tui.handler import result_handler

# Only the first lines of each window are included, enough for bars and prompts
MAX_TEXT_LINES = 5


def main(args: list[str]) -> None:
    pass


def _window(w, kind: str) -> dict:
    g = w.geometry
    text = [str(w.screen.line(y)).rstrip() for y in range(min(w.screen.lines, MAX_TEXT_LINES))]
    while text and not text[-1]:
        text.pop()
    return {
        'kind': kind,
        'id': w.id,
        'title': w.title,
        'pid': w.child.pid,
        'geometry': {'left': g.left, 'top': g.top, 'right': g.right, 'bottom': g.bottom},
        'lines': w.screen.lines,
        'columns': w.screen.columns,
        'user_vars': dict(w.user_vars),
        'text': text,
    }


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss) -> None:
    tabs = []
    for tab in boss.all_tabs:
        wl = tab.windows
        windows = [_window(boss.window_id_map[g.active_window_id], 'normal') for g in wl.groups]
        # Docks only exist in kitty >= 0.50.0
        for g in getattr(wl, 'tab_docks', ()):
            windows.extend(_window(w, f'tab-dock:{g.dock.edge}') for w in g)
        for g in wl.groups if hasattr(wl, 'tab_docks') else ():
            for d in g.docks:
                windows.extend(_window(w, f'window-dock:{d.dock.edge}') for w in d)
        tabs.append({
            'id': tab.id,
            'os_window_id': tab.os_window_id,
            'layout': tab.current_layout.name,
            'active_window': tab.active_window.id if tab.active_window else None,
            'windows': windows,
        })
    with open(args[-1], 'w') as f:
        json.dump(tabs, f, indent=2)
