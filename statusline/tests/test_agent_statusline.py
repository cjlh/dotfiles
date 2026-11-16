import json
import os
import re
import subprocess
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

SCRIPT = Path(__file__).parents[1] / ".local/bin/agent-statusline"
# Real payloads from Claude Code 2.1.311 and cursor-agent 2026.11.13, with the
# session details replaced
CLAUDE_FIXTURE = Path(__file__).parent / "fixtures/claude-2.1.311.json"
CURSOR_FIXTURE = Path(__file__).parent / "fixtures/cursor-2026.11.13.json"
# SGR colours and OSC 8 hyperlinks
ESCAPES = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;[^\x1b]*\x1b\\")
# Claude Code indents its status line by two columns on each side
CLAUDE_INSET = 4
PULL_REQUEST: dict[str, object] = {
    "number": 1234,
    "url": "https://github.com/example/repo/pull/1234",
}

Payload = dict[str, object]


def claude_payload(
    cwd: Path, *, effort: str | None = "high", context: float | None = 38
) -> Payload:
    payload = cast(Payload, json.loads(CLAUDE_FIXTURE.read_text()))
    payload["cwd"] = str(cwd)
    payload["workspace"] = {
        **cast(Payload, payload["workspace"]),
        "current_dir": str(cwd),
    }
    payload["context_window"] = {
        **cast(Payload, payload["context_window"]),
        "used_percentage": context,
    }
    if effort is None:
        del payload["effort"]
    else:
        payload["effort"] = {"level": effort}
    return payload


def cursor_payload(
    cwd: Path,
    *,
    display_name: str = "Gemini 4 Carbon Medium",
    param_summary: str = "Medium",
    context: float | None = 62,
    width: int = 100,
) -> Payload:
    payload = cast(Payload, json.loads(CURSOR_FIXTURE.read_text()))
    payload["cwd"] = str(cwd)
    payload["render_width_chars"] = width
    payload["workspace"] = {
        **cast(Payload, payload["workspace"]),
        "current_dir": str(cwd),
    }
    payload["model"] = {
        **cast(Payload, payload["model"]),
        "display_name": display_name,
        "param_summary": param_summary,
    }
    payload["context_window"] = {
        **cast(Payload, payload["context_window"]),
        "used_percentage": context,
    }
    return payload


def run(
    host: str, payload: Payload, *, home: Path, columns: int | None = None
) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name != "COLUMNS"} | {
        "HOME": str(home),
        "XDG_CACHE_HOME": str(home / ".cache"),
        # Puts the fake gh first
        "PATH": f"{home / 'bin'}{os.pathsep}{os.environ['PATH']}",
    }
    if columns is not None:
        env["COLUMNS"] = str(columns)
    return subprocess.run(
        [SCRIPT, "--host", host],
        check=False,
        input=json.dumps(payload),
        env=env,
        capture_output=True,
        text=True,
    )


def visible(result: subprocess.CompletedProcess[str]) -> str:
    """Returns the printed line without escape codes, after checking that it is one line."""
    assert result.returncode == 0, result.stderr
    line = ESCAPES.sub("", result.stdout.removesuffix("\n"))
    assert "\n" not in line
    return line


def status_line(payload: Payload, *, home: Path, columns: int) -> str:
    """Returns Claude Code's line, after checking that it fills the space Claude Code gives it."""
    line = visible(run("claude", payload, home=home, columns=columns))
    assert len(line) == max(0, columns - CLAUDE_INSET)
    return line


def cursor_line(payload: Payload, *, home: Path) -> str:
    """Returns Cursor's line, after checking that it fits in the space Cursor gives it."""
    line = visible(run("cursor", payload, home=home))
    assert len(line) <= cast(int, payload["render_width_chars"])
    return line


def wait_for(condition: Callable[[], bool], *, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, (
            "timed out waiting for the background lookup"
        )
        time.sleep(0.1)


def git(repo: Path, *args: str) -> None:
    _ = git_stdout(repo, *args)


def git_stdout(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_repo(path: Path, branch: str) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "--initial-branch", branch)
    git(path, "commit", "--allow-empty", "--message", "Initial commit")
    return path


@dataclass(frozen=True)
class FakeGh:
    """A gh on PATH that records its arguments and prints a set list of pull requests."""

    calls: Path
    response: Path

    def respond_with(self, pull_requests: list[dict[str, object]]) -> None:
        _ = self.response.write_text(json.dumps(pull_requests))

    def call_count(self) -> int:
        return len(self.calls.read_text().splitlines()) if self.calls.exists() else 0


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture(autouse=True)
def gh(home: Path) -> FakeGh:
    fake = FakeGh(calls=home / "gh-calls", response=home / "gh-response.json")
    fake.respond_with([])
    script = home / "bin/gh"
    script.parent.mkdir()
    _ = script.write_text(
        f'#!/bin/sh\necho "$*" >> "{fake.calls}"\ncat "{fake.response}"\n'
    )
    script.chmod(0o755)
    return fake


def test_shows_worktree_under_work_with_branch_and_model(home: Path) -> None:
    repo = make_repo(home / "Work/ExampleProject/main", "fix-1234-new-label")

    line = status_line(claude_payload(repo), home=home, columns=100)

    assert line.startswith("ExampleProject/main · fix-1234-new-label  ")
    assert line.endswith("  Opus 5.5 (high) · 38%")


def test_shows_config_repos_without_their_parent_folders(home: Path) -> None:
    repo = make_repo(home / "Documents/Config/dotfiles", "example")
    (repo / "kitty").mkdir()

    line = status_line(claude_payload(repo / "kitty"), home=home, columns=100)

    assert line.startswith("dotfiles/kitty · example  ")


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("Downloads", "~/Downloads"),
        ("Work/app/main/src/app", "app/main/src/app"),
        ("Work/app/main/src/app/commands", "app/main/src/app/commands"),
        (
            "Work/ExampleProject/main/src/feature/stages/utilities",
            "ExampleProject/main/s/f/stages/utilities",
        ),
        ("Documents/a/.config/b/c/d", "~/Documents/a/.c/b/c/d"),
    ],
)
def test_shortens_middle_folders_of_deep_paths(
    home: Path, relative: str, expected: str
) -> None:
    cwd = home / relative
    cwd.mkdir(parents=True)

    line = status_line(claude_payload(cwd), home=home, columns=120)

    assert line.startswith(f"{expected}  ")


def test_shows_paths_outside_home_from_the_root(home: Path) -> None:
    line = status_line(claude_payload(Path("/usr/local/share")), home=home, columns=100)

    assert line.startswith("/usr/local/share  ")


@pytest.mark.parametrize("folder", ["repo", "repo with spaces", "repo\nwith\ttabs"])
def test_shows_commit_when_head_is_detached(home: Path, folder: str) -> None:
    repo = make_repo(home / "Work" / folder / "main", "main")
    commit = git_stdout(repo, "rev-parse", "--short", "HEAD")
    git(repo, "checkout", "--detach")

    line = status_line(claude_payload(repo), home=home, columns=100)

    safe_folder = folder.replace("\n", "�").replace("\t", "�")
    assert line.startswith(f"{safe_folder}/main · @{commit}  ")


@pytest.mark.parametrize("host", ["claude", "cursor"])
@pytest.mark.parametrize("field", ["directory", "model", "effort"])
def test_sanitizes_terminal_controls_before_fitting_the_line(
    home: Path, host: str, field: str
) -> None:
    attack = "unsafe\x1b]52;c;ZXhhbXBsZQ==\x07\n\t\u202e"
    cwd = home / attack if field == "directory" else home
    cwd.mkdir(exist_ok=True)
    for width in (100, 35, 12):
        if host == "claude":
            payload = claude_payload(
                cwd, effort=attack if field == "effort" else "high"
            )
            if field == "model":
                cast(Payload, payload["model"])["display_name"] = attack
            result = run(host, payload, home=home, columns=width + CLAUDE_INSET)
        else:
            payload = cursor_payload(
                cwd,
                display_name=attack if field == "model" else "Example",
                param_summary=attack if field == "effort" else "",
                width=width,
            )
            result = run(host, payload, home=home)
        line = visible(result)
        assert len(line) == width if host == "claude" else len(line) <= width
        assert not any(
            unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp") for char in line
        )
        assert "\x1b]52;" not in result.stdout


def test_shows_when_a_rebase_is_in_progress(home: Path) -> None:
    repo = make_repo(home / "Work/repo/main", "main")
    git(repo, "commit", "--allow-empty", "--message", "Second commit")
    git(repo, "checkout", "--quiet", "-b", "feature", "HEAD~1")
    _ = (repo / "file").write_text("feature\n")
    git(repo, "add", "file")
    git(repo, "commit", "--message", "Feature")
    git(repo, "checkout", "--quiet", "main")
    _ = (repo / "file").write_text("main\n")
    git(repo, "add", "file")
    git(repo, "commit", "--message", "Conflicting change")
    git(repo, "checkout", "--quiet", "feature")
    with pytest.raises(subprocess.CalledProcessError):
        git(repo, "rebase", "main")
    commit = git_stdout(repo, "rev-parse", "--short", "HEAD")

    line = status_line(claude_payload(repo), home=home, columns=100)

    assert line.startswith(f"repo/main · @{commit} (rebasing)  ")


def test_shows_branch_of_repo_without_commits(home: Path) -> None:
    repo = home / "Work/repo/main"
    repo.mkdir(parents=True)
    git(repo, "init", "--initial-branch", "first")

    line = status_line(claude_payload(repo), home=home, columns=100)

    assert line.startswith("repo/main · first  ")


def test_leaves_out_effort_and_context_when_claude_does(home: Path) -> None:
    line = status_line(
        claude_payload(home, effort=None, context=None), home=home, columns=60
    )

    assert line.endswith("  Opus 5.5")


@pytest.mark.parametrize(
    ("percent", "sgr"),
    [
        (0, "38;5;244"),
        (50, "38;5;244"),
        (60, "38;5;137"),
        (75, "38;5;173"),
        (82, "38;5;208"),
        (90, "38;5;208"),
        (91, "38;5;167"),
        (100, "38;5;167"),
    ],
)
def test_colours_context_use_by_how_full_it_is(
    home: Path, percent: int, sgr: str
) -> None:
    result = run("claude", claude_payload(home, context=percent), home=home, columns=80)

    assert result.stdout.rstrip("\n").endswith(f"\x1b[{sgr}m{percent}%\x1b[0m")


@pytest.mark.parametrize(
    ("width", "expected_left", "expected_right"),
    [
        (
            90,
            "ExampleProject/main · fix-1234-new-label-in-glossary",
            "Opus 5.5 (high) · 62%",
        ),
        (70, "ExampleProject/main · fix-1234-new-label-in-glossary", "Opus 5.5 · 62%"),
        (60, "ExampleProject/main · fix-1234-new-label-in…  ", "Opus 5.5 · 62%"),
        (45, "…/main · fix-1234-new-label-…  ", "Opus 5.5 · 62%"),
        (30, "…/main  ", "Opus 5.5 · 62%"),
        (20, "…/m…  ", "Opus 5.5 · 62%"),
        (16, "  ", "Opus 5.5 · 62%"),
        (10, "", "Opus 5.5 …"),
    ],
)
def test_drops_parts_in_order_as_the_terminal_narrows(
    home: Path, width: int, expected_left: str, expected_right: str
) -> None:
    repo = make_repo(
        home / "Work/ExampleProject/main", "fix-1234-new-label-in-glossary"
    )

    line = status_line(
        claude_payload(repo, context=62), home=home, columns=width + CLAUDE_INSET
    )

    assert line.startswith(expected_left)
    assert line.endswith(expected_right)


def test_fits_every_width_on_one_line(home: Path) -> None:
    repo = make_repo(
        home / "Work/ExampleProject/main", "fix-1234-new-label-in-glossary"
    )
    payload = claude_payload(repo / "src" / "feature" / "stages", context=62)
    (repo / "src" / "feature" / "stages").mkdir(parents=True)

    for columns in range(1, 151):
        _ = status_line(payload, home=home, columns=columns)


def test_fails_without_terminal_width_from_claude(home: Path) -> None:
    result = run("claude", claude_payload(home), home=home)

    assert result.returncode != 0
    assert "COLUMNS" in result.stderr


def test_never_looks_up_pull_requests_for_claude(home: Path, gh: FakeGh) -> None:
    gh.respond_with([PULL_REQUEST])
    repo = make_repo(home / "Work/repo/main", "feature")

    line = status_line(claude_payload(repo), home=home, columns=100)
    time.sleep(1)

    assert line.startswith("repo/main · feature  ")
    assert gh.call_count() == 0


@pytest.mark.parametrize(
    ("display_name", "param_summary", "expected"),
    [
        ("Gemini 4 Carbon Medium", "Medium", "~ · Gemini 4 Carbon (medium) · 62%"),
        ("Grok 4.7  Low Fast\u200b\u200b", "Low Fast", "~ · Grok 4.7 (low fast) · 62%"),
        ("Composer 2.5", "", "~ · Composer 2.5 · 62%"),
    ],
)
def test_shows_cursor_models_with_their_settings_apart(
    home: Path, display_name: str, param_summary: str, expected: str
) -> None:
    payload = cursor_payload(
        home, display_name=display_name, param_summary=param_summary
    )

    line = cursor_line(payload, home=home)

    assert line == expected


def test_shows_open_pull_request_for_cursor_once_looked_up(
    home: Path, gh: FakeGh
) -> None:
    gh.respond_with([PULL_REQUEST])
    repo = make_repo(home / "Work/repo/main", "feature")
    payload = cursor_payload(repo)

    first = cursor_line(payload, home=home)
    wait_for(lambda: "#1234" in cursor_line(payload, home=home))
    result = run("cursor", payload, home=home)

    assert first == "repo/main · feature · Gemini 4 Carbon (medium) · 62%"
    assert (
        visible(result)
        == "repo/main · feature · #1234 · Gemini 4 Carbon (medium) · 62%"
    )
    assert f"\x1b]8;;{PULL_REQUEST['url']}\x1b\\" in result.stdout
    assert (
        gh.calls.read_text()
        == "pr list --head feature --state open --json number,url --limit 1\n"
    )


def test_looks_up_pull_request_once_per_minute(home: Path, gh: FakeGh) -> None:
    repo = make_repo(home / "Work/repo/main", "feature")
    payload = cursor_payload(repo)

    for _ in range(5):
        _ = cursor_line(payload, home=home)
    wait_for(lambda: gh.call_count() > 0)
    time.sleep(1)

    assert gh.call_count() == 1


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (
            100,
            "ExampleProject/main · fix-1234-new-label-in-glossary · #1234 · Gemini 4 Carbon (medium) · 62%",
        ),
        (
            85,
            "ExampleProject/main · fix-1234-new-label-in-glossary · #1234 · Gemini 4 Carbon · 62%",
        ),
        (70, "ExampleProject/main · fix-1234-new-la… · #1234 · Gemini 4 Carbon · 62%"),
        (55, "…/main · fix-1234-new-… · #1234 · Gemini 4 Carbon · 62%"),
        (45, "…/main · fix-1234-ne… · Gemini 4 Carbon · 62%"),
        (24, "Gemini 4 Carbon · 62%"),
    ],
)
def test_keeps_cursor_line_left_aligned_and_drops_pull_request_last(
    home: Path, gh: FakeGh, width: int, expected: str
) -> None:
    gh.respond_with([PULL_REQUEST])
    repo = make_repo(
        home / "Work/ExampleProject/main", "fix-1234-new-label-in-glossary"
    )
    _ = cursor_line(cursor_payload(repo), home=home)
    wait_for(lambda: "#1234" in cursor_line(cursor_payload(repo), home=home))

    line = cursor_line(cursor_payload(repo, width=width), home=home)

    assert line == expected
