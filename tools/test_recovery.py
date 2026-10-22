"""Automatic idle-run reconciliation for the public test launcher."""

import test_activity
import test_retention
import os


def _recover_finalized(root, store):
    """Finish source-owned runner captures before startup can retire bytes."""
    if not store.path.exists():
        return False
    with (store.opened() as fd,
          store.locked(fd, 'owner.lock', shared=True, blocking=False),
          store.locked(fd, 'writer.lock', shared=True)):
        state = store.read(fd)
        ready = state is not None and state['finished'] and 'recovery-required' not in os.listdir(fd)
    if not ready:
        return False
    from runner_evidence import recover_pending
    return bool(recover_pending(root, store))


def _reconcile(root, store, guard):
    _recover_finalized(root, store)
    try:
        store.reconcile(guard, completed_guard=lambda paths: None)
    except ValueError:
        # Reconciliation commits the finished owner before capacity retirement.
        # If its required runner closure stopped that retirement, finish it
        # under that same run and retry. Other refusals retain their error.
        if not _recover_finalized(root, store):
            raise
        store.reconcile(guard, completed_guard=lambda paths: None)
    _recover_finalized(root, store)


def before_run(root, argv, *, categories=None):
    # Help/collection and owned aggregate children must remain read-only here.
    from test_commands import host_only_selection, is_inspection
    if not argv or is_inspection(argv):
        return 0
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    if host_only_selection([(kind, []) for kind in (categories or [argv[0]])]):
        return cleanup_host(root)
    return cleanup(root)


def cleanup_host(root):
    """Recover only host evidence, under its independent checkout owner."""
    with test_activity.activity(root, host_only=True):
        path = test_activity.retention_path(root)
        if path.exists():
            _reconcile(root, test_retention.Store(path), lambda: None)
    return 0


def cleanup(root):
    """Reconcile recorded leftovers under the caller's checkout activity lock."""
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    store = test_retention.Store(test_activity.retention_path(root))
    # Run only recorded recovery, serially before test scheduling. Do not
    # generate regression fixtures or reports while trying to remove leftovers.
    from regression_process import category_run
    def guard():
        print('Automatic recovery: checking the recorded VM and retained evidence.',
              flush=True)
        from vm_selection import arguments
        status = category_run(root, 'integration', ['check_test_recovery', *arguments()], pipe=False)
        if status:
            raise ValueError(f'retention: automatic recovery failed (status={status}); '
                             'see diagnostics above; previous evidence preserved')
    if store.path.exists():
        _reconcile(root, store, guard)
    else:
        guard()
    print('Automatic recovery: ready; evidence retained within storage limits.', flush=True)
    return 0
