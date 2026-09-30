"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import sys

import test_activity
import test_retention
from test_recovery import cleanup
from vm_selection import select, vm_config, VARIABLE, BATCH


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help='one configured VM; omitted: all enabled VMs')
    args = parser.parse_args(argv)
    try:
        _, vms = vm_config.execution(args.vm)
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        os.environ.pop(BATCH, None)
        for vm in vms:
            select(vm.name)
            with test_activity.activity(root):
                status = cleanup(root)
            if status:
                return status
        with test_activity.activity(root, host_only=True):
            if test_activity.retention_path(root).exists():
                # VM recovery finished above. Reconcile the host journal
                # serially under its own ownership lock as well.
                test_retention.Store(test_activity.retention_path(root)).reconcile(lambda: None)
        return 0
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
