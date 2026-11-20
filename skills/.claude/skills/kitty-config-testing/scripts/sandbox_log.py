# Route Python config errors to the sandbox instance log.
#
# Launch Services sends kitty errors to macOS's unified log. Redirect Python
# errors to stderr so instance.sh can capture them. C errors still use the
# unified log.

import sys

from kitty.utils import log_error


def _to_stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


log_error.redirect = _to_stderr
