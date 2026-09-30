"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import sys

import test_activity
from test_recovery import cleanup, cleanup_host
from vm_selection import select, vm_config, BATCH


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--vm', help='one configured VM; omitted: all enabled VMs')
    scope.add_argument('--host-only', action='store_true', help='host retention only; no VM access')
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        if args.host_only:
            return cleanup_host(root)
        _, vms = vm_config.execution(args.vm)
        os.environ.pop(BATCH, None)
        for vm in vms:
            select(vm.name)
            with test_activity.activity(root):
                status = cleanup(root)
            if status:
                return status
        return cleanup_host(root)
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
