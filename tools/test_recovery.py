"""Automatic idle-run reconciliation for the public test launcher."""

import test_activity
import test_retention


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
            test_retention.Store(path).reconcile(lambda: None, completed_guard=lambda paths: None)
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
        store.reconcile(guard, completed_guard=lambda paths: None)
    else:
        guard()
    print('Automatic recovery: ready; evidence retained within storage limits.', flush=True)
    return 0
