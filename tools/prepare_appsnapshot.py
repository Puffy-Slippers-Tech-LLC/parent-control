"""Unprivileged build and guarded dispatch for standalone app preparation."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

import test_activity
import test_launcher
import test_retention
from dev_privileges import check
from regression_process import Control
from test_recovery import cleanup


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--overwrite', nargs='?', const='true', default='true',
                        choices=('true', 'false'),
                        help='rebuild the current source before installing and replacing '
                             'a matching version snapshot (default: true)')
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        helper = '/usr/local/libexec/onpc-test-runner'
        with test_activity.activity(root), Control().installed() as control:
            check(helper)
            environment = test_launcher.environment(root)
            if args.overwrite == 'false':
                status = control.run(['/usr/bin/pkexec', '--disable-internal-agent',
                                      helper, 'appsnapshot', '--probe'],
                                     cwd=root, env=environment)
                if status != 3:  # 3 means absent; every other failure is terminal.
                    return status
            cleanup(root)
            if control.stopped.is_set():
                return 130
            with test_retention.Store(root / 'artifacts/test-retention').session() as run:
                directory = test_retention.allocate(tempfile.mkdtemp,
                    prefix='onpc-test-artifacts-', dir='/tmp')
                print('prepare-appsnapshot: artifacts=' + directory, flush=True)
                status = control.run(['/usr/bin/python3', '-B',
                    str(root / 'tools/build_test_artifacts.py'), '--output', directory],
                    cwd=root, env=environment)
                if status:
                    return status
                return control.run(['/usr/bin/pkexec', '--disable-internal-agent', helper,
                    '--retention-run=' + run, '--unattended', 'appsnapshot',
                    '--overwrite', args.overwrite, '--artifacts', directory],
                    cwd=root, env=environment, cooperative=True)
    except (ValueError, OSError) as error:
        print('prepare-appsnapshot: ' + str(error), file=sys.stderr)
        return 2
