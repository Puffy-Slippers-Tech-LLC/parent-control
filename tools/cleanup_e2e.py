"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import sys

import test_activity
import test_retention
from test_recovery import cleanup, cleanup_host
from vm_selection import select, vm_config, BATCH


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--vm', help='configured VM name or ID; omitted: all enabled VMs')
    scope.add_argument('--host-only', action='store_true', help='host retention only; no VM access')
    parser.add_argument('--discard-completed', action='store_true',
                        help='explicitly remove all completed execution-retention results; not workflow/session logs')
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        if args.host_only:
            if args.discard_completed:
                with test_activity.activity(root, host_only=True):
                    test_retention.Store(test_activity.retention_path(root)).discard_completed(lambda paths: None)
            return cleanup_host(root)
        _, vms = vm_config.execution(args.vm)
        os.environ.pop(BATCH, None)
        for vm in vms:
            select(vm.name)
            with test_activity.activity(root):
                if args.discard_completed:
                    from regression_process import category_run
                    from vm_selection import arguments
                    status = category_run(root, 'integration',
                        ['check_retained_runs_cleanup', *arguments()], pipe=False)
                    if status:
                        return status
                    test_retention.Store(test_activity.retention_path(root)).discard_completed(lambda paths: None)
                status = cleanup(root)
            if status:
                return status
        return cleanup_host(root)
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
