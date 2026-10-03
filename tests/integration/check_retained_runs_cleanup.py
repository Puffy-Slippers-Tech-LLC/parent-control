#!/usr/bin/python3
"""Explicitly discard completed registered results for the selected VM only."""

import os
from pathlib import Path
import runpy
import sys

import check_test_recovery
from check_tmp_storage_cleanup import unused

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import test_retention
from test_storage import privileged_state


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0 or Path.cwd() != ROOT:
        raise ValueError('retention: invalid discard invocation')
    uid = int(os.environ.get('PKEXEC_UID', '0'))
    if uid <= 0:
        raise ValueError('retention: authenticated caller required')
    check_test_recovery.reconcile_vm(ROOT)
    lease = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['retention_lease']
    with lease(ROOT):
        test_retention.Store(privileged_state(uid)).discard_completed(unused)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        sys.exit('Completed result cleanup failed: ' + detail)
