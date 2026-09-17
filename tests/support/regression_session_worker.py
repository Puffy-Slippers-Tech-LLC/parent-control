"""Harmless aggregate double for real detached-process lifecycle tests."""

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))

import regression_session
import regression
import regression_process
from regression_process import Control
import test_commands
import test_recovery

# This process exercises session ownership against a temporary checkout. Its
# recovery behavior is covered separately; never dispatch host/VM work here.
test_recovery.before_run = lambda root, argv, **kwargs: 0
test_commands.selections = lambda root, argv: [(argv[0], argv[1:])]

dispatch = test_commands._main


def run(argv, *, detached=False):
    assert detached
    root = Path(sys.argv[1])
    (root / 'started').write_text(argv[0])
    (root / 'arguments').write_text(' '.join(argv))
    if argv[0] == 'traceability':
        # Exercise the actual non-aggregate dispatcher and owned subprocess
        # controller, using a harmless child instead of project tests.
        test_commands.plan = lambda *_: ([[sys.executable, __file__, '--child', str(root)]], False)
        regression.main = lambda root, **kwargs: regression_process.category_run(
            root, 'traceability', argv[1:], pipe=False)
        return dispatch(argv, detached=detached)
    sys.stdout.frame(['[Running] harmless aggregate'])
    return wait(root)


def wait(root):
    print('worker started', flush=True)
    deadline = time.monotonic() + 15
    control = Control()
    with control.installed():
        (root / 'child-ready').touch()
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
    if sys.argv[1] == '--child':
        sys.exit(wait(Path(sys.argv[2])))
    test_commands._main = run
    sys.exit(regression_session.worker(Path(sys.argv[1]), sys.argv[4:],
                                      Path(sys.argv[2]), int(sys.argv[3])))
