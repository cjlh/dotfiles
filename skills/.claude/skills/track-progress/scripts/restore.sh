#!/bin/bash
# SessionStart (compact) hook: after compaction, point Claude back at the
# progress file recorded by record.sh and the rules for maintaining it.

session_id=$(jq -r '.session_id // empty')

[[ "$session_id" =~ ^[A-Za-z0-9_-]+$ ]] || exit 0
state_file="$HOME/.claude/track-progress/$session_id"
[[ -f "$state_file" ]] || exit 0
file_path=$(<"$state_file")
[[ -f "$file_path" ]] || exit 0

skill_file="$HOME/.claude/skills/track-progress/SKILL.md"
cat <<MSG
This session is tracking progress with /track-progress in $file_path.
Before continuing, read $skill_file and $file_path in full, then keep
following those rules for the rest of the task.
MSG
