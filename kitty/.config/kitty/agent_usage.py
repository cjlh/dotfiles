# Helper script generated using Claude.
#
# Prints how much of a coding agent's subscription limits have been used, for
# tab_bar.py, which runs it in the background with kitty's own Python:
#
#   kitty +launch agent_usage.py claude|codex
#
# The output is JSON, with each window's reset time in seconds since the epoch,
# or null when unknown:
#
#   {"session": {"percent": 27.0, "resets_at": 1794595800.4},
#    "weekly": {"percent": 6.0, "resets_at": 1794826800.4}}
#
# Neither tool documents a way to read its limits, so both are read the way the
# tool's own usage screen does, see _claude_usage and _codex_usage. If a tool
# answers with something else than expected, null is printed instead. If it
# can't be asked at all, e.g. when offline or logged out, the exit code is 1.

import json
import os
import selectors
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

TIMEOUT = 20  # seconds to wait for a tool's servers to answer
CLAUDE_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")
CLAUDE_KEYCHAIN_SERVICE = "Claude Code-credentials"
# Windows no longer than this many minutes are session limits, others weekly
CODEX_MAX_SESSION_WINDOW = 24 * 60


def _claude_access_token() -> str:
    # Claude Code keeps its credentials in the keychain on macOS, and in a
    # file elsewhere
    if sys.platform == "darwin":
        credentials = subprocess.run(
            ["security", "find-generic-password", "-s", CLAUDE_KEYCHAIN_SERVICE, "-w"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=True,
        ).stdout
    else:
        with open(CLAUDE_CREDENTIALS_PATH) as f:
            credentials = f.read()
    return json.loads(credentials)["claudeAiOauth"]["accessToken"]


def _claude_window(window) -> dict:
    if window is None:  # nothing has been used
        return {"percent": 0, "resets_at": None}
    resets_at = window["resets_at"]
    if resets_at is not None:
        resets_at = datetime.fromisoformat(resets_at).timestamp()
    return {"percent": float(window["utilization"]), "resets_at": resets_at}


def _claude_usage() -> dict:
    """Usage from the endpoint behind Claude Code's /usage screen, using the
    access token of its login. Only Claude Code refreshes the token, as doing
    so here could log it out, so this fails once the token expires, until
    Claude Code is next used."""
    request = urllib.request.Request(
        CLAUDE_USAGE_URL,
        headers={
            "Authorization": f"Bearer {_claude_access_token()}",
            "anthropic-beta": "oauth-2025-04-20",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        usage = json.load(response)
    return {
        "session": _claude_window(usage["five_hour"]),
        "weekly": _claude_window(usage["seven_day"]),
    }


def _codex_rate_limits() -> dict:
    """Ask a Codex app server, started for the purpose, for the rate limits
    of the logged in account."""
    requests = (
        {
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "kitty-tab-bar", "version": "1.0.0"}},
        },
        {"method": "initialized"},
        {"id": 2, "method": "account/rateLimits/read"},
    )
    server = subprocess.Popen(
        ["codex", "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        server.stdin.write(
            "".join(
                json.dumps({"jsonrpc": "2.0", **r}) + "\n" for r in requests
            ).encode()
        )
        # The server exits when its stdin is closed, so that is left to kill()
        server.stdin.flush()

        selector = selectors.DefaultSelector()
        selector.register(server.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + TIMEOUT
        buffer = b""
        while selector.select(max(0, deadline - time.monotonic())):
            chunk = os.read(server.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                message = json.loads(line)
                if isinstance(message, dict) and message.get("id") == 2:
                    return message["result"]
        raise TimeoutError("No rate limits from the Codex app server")
    finally:
        server.kill()
        server.wait()


def _codex_usage() -> dict:
    limits = _codex_rate_limits()["rateLimits"]
    usage = {
        "session": {"percent": 0, "resets_at": None},
        "weekly": {"percent": 0, "resets_at": None},
    }
    # Which of the two is the session limit depends on the plan
    for window in (limits["primary"], limits["secondary"]):
        if window is None:
            continue
        is_session = window["windowDurationMins"] <= CODEX_MAX_SESSION_WINDOW
        usage["session" if is_session else "weekly"] = {
            "percent": float(window["usedPercent"]),
            "resets_at": window["resetsAt"],
        }
    return usage


def main(tool: str) -> int:
    fetch = {"claude": _claude_usage, "codex": _codex_usage}[tool]
    try:
        usage = fetch()
    except (KeyError, TypeError, ValueError):
        usage = None  # The tool's answer has changed shape
    except (OSError, subprocess.SubprocessError):
        return 1
    json.dump(usage, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
