"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import sys

import test_activity
import test_retention
from test_recovery import cleanup


def main(argv=None):
    argparse.ArgumentParser(description=__doc__, allow_abbrev=False).parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        with test_activity.activity(root):
            status = cleanup(root)
        if status:
            return status
        with test_activity.activity(root, host_only=True):
            if test_activity.retention_path(root).exists():
                # VM recovery and its cleanup gate passed above. Repeating that
                # gate under host ownership would contend with this very lock.
                test_retention.Store(test_activity.retention_path(root)).reconcile(lambda: None)
        return 0
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
