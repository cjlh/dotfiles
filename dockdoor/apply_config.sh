#! /usr/bin/env bash

cd "$(dirname "$BASH_SOURCE")"

config="com.ethanbills.DockDoor.plist"

if [ ! -f "$config" ]; then
    echo "Config file not found: $config"
    exit 1
fi

# Pretty print as JSON for sanity check
plutil -convert json -o - "$config" | jq

read -p "Apply config (y/n)? " choice

case "$choice" in
    y|Y ) ;;
    * ) echo "Cancelled" && exit 1;;
esac

# Kill and apply
osascript -e 'quit app "DockDoor"'
defaults import com.ethanbills.DockDoor "$config"
open -a DockDoor

echo "Done!"
