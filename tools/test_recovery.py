"""Automatic idle-run reconciliation for the public test launcher."""

import os

import test_activity
import test_retention


def before_run(root, argv, *, categories=None):
    # Help/collection and owned aggregate children must remain read-only here.
    if not argv or argv[0].startswith('-') or '--list' in argv or '--help' in argv:
        return 0
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    store = test_retention.Store(root / 'artifacts/test-retention')
    pending = False
    if store.path.exists():
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with store.locked(fd, 'writer.lock'):
                state = store.read(fd)
                pending = ('recovery-required' in os.listdir(fd) or
                           bool(state and not state['finished']))
    vm = any(kind in ('all', 'all-verify', 'system', 'e2e', 'integration')
             for kind in (categories or [argv[0]]))
    if pending and not vm and argv[0] in ('host', 'host-builds'):
        raise ValueError('retention: unfinished run requires VM recovery; host will not touch the VM; '
                         'use tools/run-tests integration check_test_recovery first')
    if not pending and not vm:
        return 0
    return cleanup(root)


def cleanup(root):
    """Reconcile recorded leftovers under the caller's checkout activity lock."""
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    store = test_retention.Store(root / 'artifacts/test-retention')
    # This runs only recovery plus its mandatory cleanup-safety prerequisite;
    # it does not rerun a product category or create another detached session.
    from regression_process import category_run
    def guard():
        print('Automatic recovery: checking cleanup safety, the recorded VM and retained evidence.',
              flush=True)
        status = category_run(root, 'integration', ['check_test_recovery'], pipe=False)
        if status:
            raise ValueError(f'retention: automatic recovery failed (status={status}); '
                             'see diagnostics above; previous evidence preserved')
    if store.path.exists():
        store.reconcile(guard)
    else:
        guard()
    print('Automatic recovery: ready; previous evidence preserved.', flush=True)
    return 0
