#!/bin/bash
# Runs a scripted kitty instance for a sandbox (see sandbox.sh), controllable
# over a private remote control socket inside the sandbox directory. Remote
# control is limited to that socket, the user's own kitty is never touched.
#
# Usage:
#   instance.sh start <sandbox> [kitty binary] [extra kitty args...]
#   instance.sh rc    <sandbox> <kitten @ args...>   e.g. rc <sandbox> launch --title B
#   instance.sh log   <sandbox>                      kitty's stderr, minus known noise
#   instance.sh stop  <sandbox>
#
# The kitty binary defaults to the installed app. The matching kitten binary of
# the same build is used for remote control.
set -uo pipefail

DEFAULT_KITTY=/Applications/kitty.app/Contents/MacOS/kitty
# Harmless messages that are always logged, see SKILL.md
NOISE='font .* was not found|Failed to kill child: Operation not permitted'

if [ $# -lt 2 ]; then
    sed -n '2,15p' "$0" >&2
    exit 1
fi

cmd=$1
dir=$(cd "$2" && pwd) || exit 1
shift 2

socket() { ls -d "$dir"/rc.sock-* 2>/dev/null | head -1; }

case "$cmd" in
    start)
        kitty=${1:-$DEFAULT_KITTY}
        shift || true
        rm -f "$dir"/rc.sock-*
        echo "$kitty" > "$dir/.kitty-binary"
        # Use the login shell, not whatever SHELL this script was started from
        login_shell=$(dscl . -read ~ UserShell | awk '{print $2}')
        # Launch the app bundle in the background with open -g, so the instance
        # does not take keyboard focus from whatever the user is typing in
        app=${kitty%/Contents/MacOS/kitty}
        open -g -n -a "$app" --env "KITTY_CONFIG_DIRECTORY=$dir" --env "SHELL=$login_shell" \
            --stdout "$dir/kitty.log" --stderr "$dir/kitty.log" \
            --args -o allow_remote_control=socket-only -o "listen_on=unix:$dir/rc.sock" "$@"
        for _ in $(seq 50); do
            if [ -n "$(socket)" ]; then
                pgrep -f "listen_on=unix:$dir/rc.sock" | head -1 > "$dir/.pid"
                echo "started pid $(cat "$dir/.pid"), socket $(socket)"
                exit 0
            fi
            sleep 0.2
        done
        echo "kitty did not start, log:" >&2
        cat "$dir/kitty.log" >&2
        exit 1
        ;;
    rc)
        kitten="$(dirname "$(cat "$dir/.kitty-binary")")/kitten"
        exec "$kitten" @ --to "unix:$(socket)" "$@"
        ;;
    log)
        grep -Ev "$NOISE" "$dir/kitty.log"
        ;;
    stop)
        [ -f "$dir/.pid" ] && kill "$(cat "$dir/.pid")" 2>/dev/null
        rm -f "$dir/.pid" "$dir"/rc.sock-*
        ;;
    *)
        echo "Unknown command: $cmd" >&2
        exit 1
        ;;
esac
