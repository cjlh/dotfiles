# Compact footer

```text
~/project (main) [session] $0.55 • 44.6%/262k                  model • high
```

Run `/toggle-footer` (or `on`, `off`, `toggle`) to show a second row:

```text
↑228k ↓72k ¢99.6% • (provider) • 🔌 2/3 • other extension statuses
```

- Cost and input/output totals include all recorded session usage, including compaction,
  branch summaries, and nested-tool usage. Cost is the recorded dollar estimate, not
  necessarily a subscription charge.
- `¢` is the latest assistant prompt's cache-read percentage, not a session-wide average.
  It is omitted until known.
- Context usage turns warning-coloured at 60%, error-coloured at 80%; unknown context
  after compaction shows `?` rather than a misleading zero.
- The provider appears only when more than one provider is available.
- A reasoning-capable model shows the current thinking level.
- Working indicators remain native to Pi; this extension adds no animation.
- The optional stats row is off on session start and is not persisted.

## Narrow terminals

The path first collapses to its basename, then cost and the optional agent marker are
dropped. Remaining left-side text is ellipsized while preserving the right-aligned
model/thinking label. If the terminal is narrower than that label itself, only its
rightmost columns fit. Rendering uses Pi's ANSI/Unicode-aware column helpers.

## Status integrations

The extension reads Pi's footer status bus; it does not import other extensions.

- `active-agent`, `active_agent`, or `agent`: shown next to the model when space permits.
  These are explicit compatibility keys, not a Pi-standard agent API.
- Status values containing `🔌 N` or `🔌 N/M`: compact MCP badge in the stats row.
- Other statuses: shown on the optional stats row, sorted by key.
- `below-footer:*`: always shown below the metadata rows, sorted by key and split on
  newlines. `BELOW_FOOTER_PREFIX` is exported from `index.ts` for callers.

Status text has terminal sequences/control characters stripped. All rows are clipped to
the terminal width, and below-footer rows have no inset either.

## Testing

Tests use Bun. With Pi installed globally through Bun, run the following from the dotfiles
root to resolve Pi's host-provided dependencies in an isolated directory:

```sh
work=$(mktemp -d)
cp pi/.pi/agent/extensions/compact-footer/index{,.test}.ts "$work/"
ln -s "$HOME/.bun/install/global/node_modules" "$work/node_modules"
bun test "$work/index.test.ts"
tsc --noEmit --skipLibCheck --target es2022 --module preserve \
  --moduleResolution bundler "$work/index.ts"
rm -r "$work"
```

Adjust the dependency directory if Pi was installed by another package manager. Tests
cover unpadded alignment, widths 1–150, Unicode, control stripping, stats commands,
context thresholds, usage totals, non-TUI modes, and subscription cleanup.
