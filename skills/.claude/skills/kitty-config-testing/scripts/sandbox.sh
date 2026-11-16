#!/bin/bash
# Creates a throwaway kitty config directory that loads the real config, so a
# change can be tried without touching ~/.config/kitty or the running kitty.
#
# Every file of the real config directory is symlinked into the sandbox, except
# kitty.conf, which is a copy of the real kitty.conf followed by the given extra
# config lines. It is copied rather than included because kitty resolves the
# relative paths of includes from the directory of the file they are in, so an
# included real kitty.conf would include the real watchers.conf and other files
# rather than the sandbox's. watchers.conf is also a copy, with the
# sandbox_log.py watcher added. To try a changed copy of any other file (such as
# a watcher or an included .conf file), replace its symlink in the sandbox with
# the copy.
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

# Send errors logged by the config's Python code to instance.sh log. kitty.conf
# includes ./watchers.conf, which resolves to the sandbox's copy.
rm -f "$dir/watchers.conf"
if [ -e "$real/watchers.conf" ]; then
    cat "$(readlink -f "$real/watchers.conf")" > "$dir/watchers.conf"
fi
echo "watcher $(cd "$(dirname "$0")" && pwd)/sandbox_log.py" >> "$dir/watchers.conf"

{
    cat "$(readlink -f "$real/kitty.conf")"
    echo
    echo "# Added by sandbox.sh"
    for line in "$@"; do
        echo "$line"
    done
} > "$dir/kitty.conf"

echo "$dir"
