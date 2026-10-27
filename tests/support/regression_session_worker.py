"""Harmless aggregate double for real detached-process lifecycle tests."""

from pathlib import Path
from contextlib import nullcontext
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))

import regression_session
import regression
import regression_process
from regression_process import Control
import test_commands
import test_recovery
import vm_recording
import vm_pool

# This process exercises session ownership against a temporary checkout. Its
# host recovery may be enabled explicitly; never dispatch tests or VM work here.
if not (Path(sys.argv[1]) / 'recover-host').exists():
    test_recovery.before_run = lambda root, argv, **kwargs: 0
test_commands.selections = lambda root, argv: [(argv[0], argv[1:])]
# Keep real checkpoint bookkeeping, but do not discover installed-test histories
# in this empty synthetic checkout. This double never executes those histories.
test_commands.execution_selections = lambda root, selections: selections
# This harmless process tests detached ownership only. The separate recording
# UI tests exercise the real private compositor, encoder and publication.
vm_recording.recording = lambda *args, **kwargs: nullcontext(None)
vm_pool.selected_reservation = lambda **kwargs: nullcontext()

dispatch = test_commands._main


def run(argv, *, detached=False, checkpoint=None):
    assert detached
    if '--resume-area-only' in argv:
        assert checkpoint.retry_area == 'authorization'
    root = Path(sys.argv[1])
    (root / 'started').write_text(argv[0])
    # Readers use existence as readiness; publish only after the write closes.
    arguments = root / 'arguments.tmp'
    arguments.write_text(' '.join(argv))
    arguments.replace(root / 'arguments')
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
