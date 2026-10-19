#!/bin/bash
# PostToolUse hook: remember which progress file this session is tracking, so
# restore.sh can point Claude back at it after compaction.

input=$(cat)
session_id=$(jq -r '.session_id // empty' <<<"$input")
file_path=$(jq -r '.tool_input.file_path // empty' <<<"$input")

[[ "$session_id" =~ ^[A-Za-z0-9_-]+$ ]] || exit 0
[[ -f "$file_path" ]] || exit 0
[[ "$(head -n 1 "$file_path")" == "<!-- track-progress -->" ]] || exit 0

state_dir="$HOME/.claude/track-progress"
mkdir -p "$state_dir"
printf '%s\n' "$file_path" >"$state_dir/$session_id"
