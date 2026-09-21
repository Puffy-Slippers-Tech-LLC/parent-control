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
        # Host journals remain subject to Store.session's identity/recovery
        # checks, but host work never inspects or recovers VM-owned storage.
        return 0
    return cleanup(root)


def cleanup(root):
    """Reconcile recorded leftovers under the caller's checkout activity lock."""
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    store = test_retention.Store(test_activity.retention_path(root))
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
