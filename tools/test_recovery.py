"""Automatic idle-run reconciliation for the public test launcher."""

import test_activity
import test_retention


def before_queue(root, argv):
    """Recover retained claims before a fresh batch takes its activity gate.

    The standalone cleanup owns VM admission and excludes competing queue
    writers before returning claims to pending. A resumed queue instead keeps
    its original ownership and lets its workers recover normally.
    """
    import json
    import os
    from vm_selection import BATCH
    from test_commands import host_only_request, is_inspection
    if (BATCH not in os.environ or '--resume' in argv or is_inspection(argv)
            or host_only_request(argv)):
        return 0
    from test_checkpoint import family_claims_pending
    from regression_process import Control
    import test_launcher
    with Control().installed() as control:
        for name in json.loads(os.environ[BATCH])['vms']:
            if not family_claims_pending(root, name):
                continue
            print(f'Automatic recovery: recovering retained queue claims for {name}.', flush=True)
            status = control.run([str(root / 'tools/cleanup-e2e'), '--vm', name, '--vm-only'],
                                 cwd=root, env=test_launcher.environment(root))
            if status:
                return status
        return 130 if control.stopped.is_set() else 0


def before_run(root, argv, *, categories=None):
    # Help/collection and owned aggregate children must remain read-only here.
    from test_commands import host_only_request, is_inspection
    if not argv or is_inspection(argv):
        return 0
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    if host_only_request(argv):
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
        status = category_run(root, 'system', ['check_test_recovery', *arguments()], pipe=False)
        if status:
            raise ValueError(f'retention: automatic recovery failed (status={status}); '
                             'see diagnostics above; previous evidence preserved')
    if store.path.exists():
        store.reconcile(guard, completed_guard=lambda paths: None)
    else:
        guard()
    print('Automatic recovery: ready; evidence retained within storage limits.', flush=True)
    return 0
