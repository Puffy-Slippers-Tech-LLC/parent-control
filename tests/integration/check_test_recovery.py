#!/usr/bin/python3
"""Reconcile idle aggregate storage and the identity-recorded test VM only."""

import hashlib
import os
from pathlib import Path
import runpy
import sys

import check_graphical_recovery

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import test_retention


def reconcile_vm(root):
    guard = runpy.run_path(str(root / 'tools/onpc-test-runner'))['retention_guard']
    try:
        guard(root)
    except ValueError as error:
        if str(error) != 'retention: VM recovery is unfinished; preserve evidence':
            raise
        print('Recovering the previous recorded VM attempt before starting tests.', flush=True)
        if check_graphical_recovery.main(graphics_type=None):
            raise ValueError('retention: recorded VM cleanup failed; evidence preserved')
        guard(root)


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0 or Path.cwd() != ROOT:
        raise ValueError('retention: invalid recovery invocation')
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0:
        raise ValueError('retention: authenticated caller required')
    from test_storage import privileged_state
    store = test_retention.Store(privileged_state(uid))
    store.reconcile(lambda: reconcile_vm(ROOT))
    # Rotate eligible completed evidence before the aggregate's RAM admission.
    with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
        with store.locked(fd, 'writer.lock'):
            state = store.read(fd)
            if state is not None and state['finished']:
                store.prune(fd, state, keep=2)
    print('Test recovery: VM and privileged storage are ready.', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        sys.exit('Test recovery failed: ' + detail)
