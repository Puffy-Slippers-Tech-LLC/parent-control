"""Harmless aggregate double for real detached-process lifecycle tests."""

from pathlib import Path
import sys
import time

import regression_session
from regression_process import Control
import test_commands


def run(argv):
    root = Path(sys.argv[1])
    (root / 'started').write_text(argv[0])
    sys.stdout.frame(['[Running] harmless aggregate'])
    print('worker started', flush=True)
    deadline = time.monotonic() + 15
    control = Control()
    while not (root / 'release').exists():
        if control.stopped.is_set():
            print('owned cleanup finished', flush=True)
            return 130
        if time.monotonic() >= deadline:
            return 2
        time.sleep(0.02)
    print('usual final summary', flush=True)
    return 7


if __name__ == '__main__':
    test_commands._main = run
    sys.exit(regression_session.worker(Path(sys.argv[1]), sys.argv[2],
                                      Path(sys.argv[3]), int(sys.argv[4])))
