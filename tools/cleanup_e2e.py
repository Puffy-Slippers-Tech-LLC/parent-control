"""Standalone entry point for the recovery module used by run-tests."""
import argparse
import os
from pathlib import Path
import sys

import test_activity
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
        if (root / 'artifacts/test-retention-host').exists():
            with test_activity.activity(root, host_only=True):
                return cleanup(root)
        return 0
    except (ValueError, OSError) as error:
        print('cleanup-e2e: ' + str(error), file=sys.stderr)
        return 2
