# A watcher that sandbox.sh adds to every sandbox, so that errors logged by the
# config's Python code reach the instance's log (instance.sh log).
#
# kitty sends log_error to macOS's unified log rather than stderr when Launch
# Services starts it, which is how instance.sh starts it. kitty's log_error
# writes through its redirect attribute when one is set, so set one that writes
# to stderr. Errors logged by kitty's C code still go to the unified log.

import sys

from kitty.utils import log_error


def _to_stderr(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


log_error.redirect = _to_stderr
