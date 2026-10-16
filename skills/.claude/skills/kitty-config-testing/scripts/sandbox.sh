#!/bin/bash
# Creates a throwaway kitty config directory that loads the real config, so a
# change can be tried without touching ~/.config/kitty or the running kitty.
#
# Every file of the real config directory is symlinked into the sandbox, except
# kitty.conf, which is replaced by one that includes the real kitty.conf followed
# by the given extra config lines. To try a changed copy of a file (such as a
# watcher), replace its symlink in the sandbox with the copy.
#
# Usage: sandbox.sh <dir> [config line...]
# Example: sandbox.sh /tmp/kitty-sandbox 'watcher my_watcher.py' 'map f1 ...'
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <dir> [config line...]" >&2
    exit 1
fi

dir=$1
shift
real=${KITTY_REAL_CONFIG_DIR:-$HOME/.config/kitty}

mkdir -p "$dir"
for f in "$real"/*; do
    name=$(basename "$f")
    [ "$name" = kitty.conf ] || ln -sfn "$(readlink -f "$f")" "$dir/$name"
done

{
    echo "include $(readlink -f "$real/kitty.conf")"
    for line in "$@"; do
        echo "$line"
    done
} > "$dir/kitty.conf"

echo "$dir"
