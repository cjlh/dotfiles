---
name: track-progress
description: Track progress for the current task in a markdown file using a fixed status convention. This skill should only be invoked if explicitly requested by the user.
argument-hint: [directory or file path]
disable-model-invocation: false
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "$HOME/.claude/skills/track-progress/scripts/record.sh"
  SessionStart:
    - matcher: "compact"
      hooks:
        - type: command
          command: "$HOME/.claude/skills/track-progress/scripts/restore.sh"
---

Track progress for the current task in a markdown file.

## Where the file lives

- If `$ARGUMENTS` ends in `.md`, use that file.
- Otherwise, the target directory is `$ARGUMENTS` if given, else `_progress/` at the repo
  root (or the current directory if not in a git repo). Create it if missing.
- If no `.md` file was given, check the target directory for existing `NN-*.md` files. If
  one clearly matches the current task, resume it; if unsure, ask.
- New files are named `<NN>-<task-slug>.md`, where `NN` is the highest existing prefix
  plus one, zero-padded to two digits (starting at `01`), and `<task-slug>` is a short
  kebab-case name, e.g. `flaky-auth-timeouts`.
- Never stage or commit `_progress/` or anything in it. Don't add it to `.gitignore` or
  `.git/info/exclude` either; it should stay visible in `git status`.

## Starting or resuming

- If the file already exists, read it in full before doing anything else. Treat `[✗]`
  items as ruled out and don't retry them unless there's new evidence. Pick up from
  In-progress; if that's empty, move the next Todo item into it.
- The first line of the file must be exactly `<!-- track-progress -->`. Hooks use it to
  find the file again after compaction. Add it if an existing file is missing it.
- If it doesn't exist, create it with the marker line, a one-line **Goal**, then these
  sections in order: `## In-progress`, `## Todo`, `## Done`, `## Out of scope`, `## Key`.
  Populate Todo with your initial plan.
- `## Key` is always the last section, copied verbatim from the example below so the file
  makes sense on its own. Add it if an existing file is missing it, and never put items
  under it.
- If useful, add a short paragraph of context about the overall task below the Goal.

## Status markers

| Symbol | Meaning              | Lives under  |
| ------ | -------------------- | ------------ |
| `[ ]`  | Not started          | Todo         |
| `[◐]`  | Currently trying     | In-progress  |
| `[✓]`  | Tried, worked        | Done         |
| `[✗]`  | Tried, didn't work   | Done         |
| `[↻]`  | Parked, will revisit | Out of scope |
| `[-]`  | Dropped, won't do    | Out of scope |

## Rules

- "Done" means concluded, not necessarily successful. Failed attempts stay under Done with
  `[✗]`.
- When an item's status changes, move the line to the matching section and update its
  marker. Don't duplicate it.
- Add a short reason after any `[✗]`, `[↻]`, or `[-]` item, separated by an em dash (`—`).
  Include evidence where useful (error message, file, commit, PR).
- Update the file whenever an attempt concludes, before switching approach, and when new
  ideas come up. Don't batch updates to the end.
- Keep only what's actively being worked on under In-progress.
- Never write secrets, tokens, or credentials into the file.

## Example

```markdown
<!-- track-progress -->
**Goal:** Stop intermittent auth timeouts in the API client

## In-progress
- [◐] Swap the retry logic to exponential backoff

## Todo
- [ ] Add integration test for timeout path

## Done
- [✓] Reproduce the failure locally
- [✗] Increase connection pool size — no change in error rate

## Out of scope
- [↻] Refactor client into its own module — after the fix ships

## Key
- `[ ]` not yet started
- `[◐]` in-progress
- `[✓]` completed successfully
- `[✗]` completed unsuccessfully
- `[↻]` parked to revisit later
- `[-]` dropped without plans to revisit
```
