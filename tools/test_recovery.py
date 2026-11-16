"""Recover actual VM resources before the public test launcher executes."""

import test_activity


def cleanup_host(root):
    """Explicitly retire recorded host output under its checkout owner."""
    import test_retention
    with test_activity.activity(root, host_only=True):
        path = test_activity.retention_path(root)
        if path.exists():
            test_retention.Store(path).reconcile(lambda: None, completed_guard=lambda paths: None)
    return 0


def before_run(root, argv, *, categories=None):
    # Help/collection and owned aggregate children must remain read-only here.
    from test_commands import host_only_request, is_inspection
    if not argv or is_inspection(argv):
        return 0
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    if host_only_request(argv):
        return 0  # The execution owner rotates its output independently.
    return cleanup(root)


def cleanup(root):
    """Reconcile recorded leftovers under the caller's checkout activity lock."""
    if not test_activity.descriptors():
        raise ValueError('retention: checkout activity ownership required')
    # Run only recorded recovery, serially before test scheduling. Do not
    # generate regression fixtures or reports while trying to remove leftovers.
    from regression_process import category_run
    def guard():
        import regression_process
        import threading
        print('Automatic recovery: checking the recorded VM and retained evidence.',
              flush=True)
        from vm_selection import arguments
        previous = regression_process.session_stop
        try:
            # This owned recovery may be restoring a snapshot. A parent STOP
            # waits for it; it must not interrupt restoration and then retry it.
            regression_process.session_stop = threading.Event()
            status = category_run(root, 'system', ['check_test_recovery', *arguments()], pipe=False)
        finally:
            regression_process.session_stop = previous
        if status:
            raise ValueError(f'retention: automatic recovery failed (status={status}); '
                             'see diagnostics above; previous evidence preserved')
    guard()
    print('Automatic recovery: VM resources are ready.', flush=True)
    return 0
