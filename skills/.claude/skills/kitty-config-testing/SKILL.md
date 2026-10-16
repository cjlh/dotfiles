---
name: kitty-config-testing
description: Test changes to the kitty terminal config in this dotfiles repo (including custom watchers and kittens) in a sandboxed, scriptable kitty instance before applying them, including against kitty nightly builds. Use when changing, debugging or verifying kitty config or kitty Python extensions, or when trying unreleased kitty features. Skill verified against kitty version 0.49.2 and 2026-10-16 nightly.
---

# Testing kitty config changes

The kitty config lives in `kitty/.config/kitty/` in this repo and is linked into
`~/.config/kitty/` with `stow kitty` (per-file symlinks). The user's own kitty is running
from that config while you work, so:

- **Never test against the user's running kitty.** kitty watches its config files and
  reloads them on change, so editing a linked file in the repo changes the user's live
  terminal immediately. Try changes in a sandbox first, and only edit the real files once
  they work.
- Python watchers and kittens are only loaded once per kitty process. A running instance
  never picks up edits to them, so restart test instances after edits.

## Helper scripts

All in `scripts/` next to this file. Use bash for anything that drives kitty (zsh does not
word-split `$VARS`, and errors on globs with no matches).

- `sandbox.sh <dir> [config line...]` creates a throwaway config directory that includes
  the real `kitty.conf`, symlinks every other real config file, and appends the given
  lines (later lines override earlier ones). To try a changed copy of a file, replace its
  symlink in the sandbox with the copy.
- `instance.sh start <sandbox> [kitty binary] [kitty args...]` starts a kitty for the
  sandbox in the background (it does not take focus from the user), with remote control
  limited to a private socket in the sandbox. Then:
  - `instance.sh rc <sandbox> <kitten @ args...>` runs any remote control command, e.g.
    `launch --title B`, `goto-layout stack`, `action previous_window`,
    `send-text --match title:^B$ 'exit\r'` (what ctrl+d does at a prompt),
    `get-text --match id:3`, `ls`.
  - `instance.sh log <sandbox>` shows kitty's stderr minus known noise. Check it after
    every scenario, watcher and kitten errors only show up here.
  - `instance.sh stop <sandbox>`.
- `inspect_tabs.py` is a kitten that runs inside kitty and dumps its real window state as
  JSON: layouts, normal windows, docks, geometry, user vars and the text each window
  shows. Run it with
  `instance.sh rc <sandbox> kitten <path>/inspect_tabs.py <output.json>`. Prefer it over
  `kitten @ ls`, which does not report docks.

## Workflow

1. Read the relevant kitty source for the exact build being tested (see below) rather than
   relying on memory, kitty's internals change often.
2. Write the change into a sandbox (`sandbox.sh`, then edit or replace files).
3. Script the scenarios with `instance.sh` in a bash file kept outside the sandbox,
   asserting on `inspect_tabs.py` output and `instance.sh log`. Cover the edge cases:
   windows opening and closing, the last window closing, layout switches, both the
   installed kitty and a nightly where relevant.
4. For pure rendering code, test it without a running instance by drawing on a real kitty
   `Screen`:

   ```python
   # check.py, run with: kitty +runpy "import runpy; runpy.run_path('check.py')"
   # (use runpy.run_path, exec() of the source breaks comprehension scoping)
   from kitty.fast_data_types import Screen
   screen = Screen(None, 1, 80)  # lines, columns
   # ... call the drawing code with screen ...
   print(str(screen.line(0)), repr(screen.line(0).as_ansi()))
   ```

5. Apply to the repo, link new files with `stow -nv kitty` then `stow -v kitty`, and
   re-run the scenarios against a sandbox of the now-real config.
6. Clean up: stop instances and delete sandboxes and scratch files.

To let the user try a change by hand, launch a normal (focused) instance:
`open -n --env SHELL=<login shell> --env KITTY_CONFIG_DIRECTORY=<sandbox> -a <kitty.app>`.
Get the login shell with `dscl . -read ~ UserShell`, otherwise kitty may pick up the shell
of whatever launched it.

## Verify what kitty actually did

Check the state kitty really ended up in, not a recomputation of it. Recomputing inside a
test kitten can hide bugs where kitty drew something earlier and never updated it. For
example, to see the borders kitty actually sent to the GPU, have a kitten wrap
`kitty.borders.set_borders_rects` once to record the rects per tab, then perform the
actions and read the recorded rects with a second invocation.

## kitty nightly builds

Unreleased features (such as docked windows, kitty >= 0.50.0) need the nightly:

```bash
mkdir -p /tmp/kitty-nightly && cd /tmp/kitty-nightly
gh release download nightly --repo kovidgoyal/kitty --pattern 'kitty-nightly.dmg*' --clobber
# Verify the signature with Kovid's key, in a throwaway keyring
export GNUPGHOME=$(mktemp -d /tmp/kitty-gpg.XXXX)
curl -fsSL https://calibre-ebook.com/signatures/kovid.gpg | gpg --import
gpg --verify kitty-nightly.dmg.sig kitty-nightly.dmg
hdiutil attach -nobrowse -readonly -mountpoint ./mnt kitty-nightly.dmg
ditto mnt/kitty.app ./kitty.app && hdiutil detach mnt
```

The nightly reports the version of the last release, so detect features (e.g.
`hasattr(kitty.types, 'DockSpec')`) instead of checking versions. Python extensions should
do nothing when a feature is missing, as the installed kitty loads the same config.

## Reading kitty's source

The app bundle only contains compiled Python, so read the source from GitHub at the commit
of the build being tested:

```bash
# Commit of the current nightly (the tag object points at the commit)
gh api repos/kovidgoyal/kitty/git/refs/tags/nightly --jq .object.sha \
  | xargs -I{} gh api repos/kovidgoyal/kitty/git/tags/{} --jq .object.sha
# A file at that commit
gh api "repos/kovidgoyal/kitty/contents/kitty/tabs.py?ref=<sha>" --jq .content | base64 -d
```

For a release, use its tag, e.g. `ref=v0.49.2`. Useful starting points: `kitty/boss.py`,
`kitty/tabs.py`, `kitty/window.py`, `kitty/window_list.py`, `kitty/layout/base.py`,
`kitty/launch.py`, `kitty/tab_bar.py`, `kitty/options/definition.py` (all options and
their docs), `docs/changelog.rst`.

## Pitfalls learnt the hard way

- **Watcher events:** most are deferred to the next loop tick, but `on_tab_bar_dirty` is
  called synchronously. Defer work with `add_timer(callback, 0, False)`, and never create
  or close windows in the middle of a relayout.
- **Window removal:** when a shell exits, kitty destroys the window _before_ calling
  `Tab.remove_window()`. Anything that relayouts inside it touches the half-destroyed
  window and crashes kitty.
- **Patching kitty internals** (e.g. wrapping `Tab.remove_window`): pass `*args, **kwargs`
  through, guard against patching twice, and catch and `log_error` (from `kitty.utils`)
  any exception in your code so that kitty's original code always runs.
- **Unfocused windows** have their text faded by `inactive_text_alpha`, blended with the
  cell background in linear light. Cell backgrounds are not faded, so glyph-drawn shapes
  and backgrounds of the same colour stop matching.
- The system `python3` is likely to be older than kitty's bundled Python: no backslashes
  inside f-string expressions in helper scripts run with it.
