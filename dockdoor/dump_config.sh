#! /usr/bin/env bash

cd "$(dirname "$BASH_SOURCE")"

tmp="/tmp/com.ethanbills.DockDoor.plist"
out="com.ethanbills.DockDoor.plist"

# Export app preferences as plist
defaults export com.ethanbills.DockDoor "$tmp"

# Convert binary plist to XML
plutil -convert xml1 "$tmp"

# Remove sensitive keys

blacklist=(
  persistedWindowOrder                # private window-title history
  launched                            # runtime state
  lastKnownScreenRecordingPermission  # derived from the actual permission grant
  SUHasLaunchedBefore                 # Sparkle updater bookkeeping
  SULastCheckTime                     # Sparkle updater bookkeeping
  filteredCalendarIdentifiers         # EventKit calendar IDs
  folderWidgetSortOrders              # keyed by folder paths on disk
  folderWidgetSortReversed            # keyed by folder paths on disk
  lockedDockScreenIdentifier          # machine-specific display UUID
  pinnedScreenIdentifier              # machine-specific display UUID
  fullscreenAppBlacklist              # bundle IDs of excluded apps
)

for key in "${blacklist[@]}"; do
  plutil -remove "$key" "$tmp" 2>/dev/null
done

# Pretty print as JSON for sanity check
plutil -convert json -o - "$tmp" | jq

mv "$tmp" "$out"

echo "Written to $out"
