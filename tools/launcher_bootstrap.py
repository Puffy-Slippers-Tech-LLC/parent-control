"""Stable observer trampoline; workflow and reload policy live elsewhere."""

import os
from pathlib import Path
import sys


enabled = False


class ReloadObserver(BaseException):
    """Unwind terminal and caller contexts before replacing the interpreter."""


def run(entry):
    global enabled
    previous, enabled = enabled, True
    try:
        try:
            return entry()
        except ReloadObserver as request:
            sys.stdout.flush()
            sys.stderr.flush()
            os.execv('/usr/bin/python3', ['/usr/bin/python3', '-IBu',
                     str(Path(__file__).resolve()), *request.args])
    finally:
        enabled = previous


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.modules['launcher_bootstrap'] = sys.modules[__name__]
    from launcher_observer import main
    sys.exit(run(main))
