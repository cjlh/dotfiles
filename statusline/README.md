# Agent status line

`agent-statusline` prints one status line for coding agent TUIs. In Claude Code, it looks
like this:

```text
ExampleProject/main · fix-1234-new-label                          Opus 5.5 (high) · 62%
```

In Cursor (`cursor-agent`), the right side follows the left side instead (see
[Cursor](#cursor) for why), and the line also shows the open pull request:

```text
ExampleProject/main · fix-1234-new-label · #1234 · Gemini 4 Carbon (medium) · 62%
```

- The left side shows the working directory, the git branch and, in Cursor, the branch's
  open pull request. They are in mid-gray, so they don't stand out.
  - Folders under `~/Work` and `~/Documents/Config` show without that prefix.
  - Paths with more than five folders show only the first letter of the middle folders.
  - A detached HEAD shows as `@<commit>`, with `(rebasing)` during a rebase.
  - The pull request number links to the pull request, in terminals that support OSC 8
    hyperlinks.
- The right side shows the model, its reasoning effort, and how much of the context
  window is used.
  - The model is in the light gray that Claude Code uses for its own hints.
  - The effort and the percentage are in the same mid-gray as the left side. The
    percentage fades through orange to red as the context fills, staying gray up
    to half full, reaching orange at 82% and a soft red at 91%.
  - For Cursor, the effort is the summary of the model's settings, such as `(high fast)`.
- The line never wraps. In Claude Code, it fills the space that Claude Code gives it.
  Both agents indent the line by two columns on each side. When the line does not fit,
  parts are dropped in this order:
  1. The reasoning effort.
  2. The end of the branch name, down to 12 columns.
  3. The directory, down to its last folder.
  4. The pull request.

  Below that, the line is cut from the left, and the right side is kept whole while it
  fits.

## Pull requests

Claude Code shows an open pull request as a badge in its own footer, so the status line
leaves it out. A custom status line replaces Cursor's whole footer, so the status line
shows the pull request for Cursor.

The script looks up the pull request with `gh pr list --head <branch>`, which takes about a
second. So it caches the result for each repo and branch for 60 seconds, in
`~/.cache/agent-statusline`. When the cache is stale, the status line shows the cached
result, and refreshes the cache in a background process. A new pull request shows up within
about a minute. Errors from the background process go to
`~/.cache/agent-statusline/refresh.log`.

## Set-up

Stow the package. The script needs `uv` on `PATH`, and `gh` signed in for pull requests:

```sh
stow statusline
```

### Claude Code

Add this to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "~/.local/bin/agent-statusline --host claude",
  "refreshInterval": 1
}
```

Claude Code does not re-run the command when the terminal is resized. `refreshInterval`
re-runs it every second, so the line follows the new width. Each run takes about 50 ms,
mostly for uv to start.

Claude Code passes the terminal width in `COLUMNS`. The script fails if `COLUMNS` is not
set, which leaves the status line blank. Run `claude --debug` to see the error.

### Cursor

Add this to `~/.cursor/cli-config.json`:

```json
"statusLine": {
  "type": "command",
  "command": "~/.local/bin/agent-statusline --host cursor",
  "updateIntervalMs": 1000
}
```

Cursor runs the command without a shell, so the command can't use pipes or variables.
Cursor rewrites `cli-config.json` itself, so edit it while no `cursor-agent` is running.

Cursor re-runs the command when the session changes, such as when tokens stream in, at most
once per `updateIntervalMs`. It does not re-run it when the terminal is resized, and it has
no setting to re-run it on a timer. A right-aligned line would be out of place after every
resize until the next message, so in Cursor the right side follows the left side. If the
terminal gets narrower than the line, the line wraps until Cursor next re-runs the command.

Cursor does not document the status line payload. The fields used here are from the
cursor-agent 2026.11.13 code, and from its built-in skill at
`~/.cursor/skills-cursor/statusline/SKILL.md`.

## Testing

The tests run the script as a black box, against real git repos in a temporary home
folder. A fake `gh` stands in for GitHub. The fixtures are real Claude Code and Cursor
payloads, with the session details replaced. Run these from this folder:

```sh
uv run --no-project --python 3.12 --with pytest pytest tests
uvx ruff format --line-length 120 .local/bin/agent-statusline tests
uvx ruff check --line-length 120 .local/bin/agent-statusline tests
```

basedpyright skips files without a `.py` extension, so type-check a copy of the script:

```sh
cp .local/bin/agent-statusline /tmp/agent_statusline.py
uv run --no-project --python 3.12 --with pytest --with basedpyright \
  basedpyright /tmp/agent_statusline.py tests
```
