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
from vm_selection import select, choose_vm, arguments as vm_arguments


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help='name or ID in config/test-vm.json; prompts for manual work when omitted')
    parser.add_argument('--y', action='store_true',
                        help='proceed without confirmation; automation and agent sessions must include --vm and --y')
    parser.add_argument('--mode', choices=('online', 'offline'), default='online',
                        help='snapshot after reboot with memory (online, default), '
                             'or after shutdown (offline)')
    parser.add_argument('--overwrite', nargs='?', const='true', default=None,
                        choices=('true', 'false'),
                        help='rebuild the current source before installing and replacing '
                             'a matching version snapshot (default: false online, true offline); false keeps '
                             'an existing version snapshot without building, or creates it if missing')
    args = parser.parse_args(argv)
    if args.y and args.vm is None:
        parser.error('--y requires an explicit --vm NAME; use both for automation and agent sessions')
    if args.overwrite is None:
        args.overwrite = 'false' if args.mode == 'online' else 'true'
    return args


def confirm_preparation(args):
    print(f'prepare-appsnapshot: prepare the current app snapshot on {args.vm} '
          f'(mode={args.mode}, overwrite={args.overwrite}). '
          'Preparation may restore the baseline, install the app and replace the version snapshot. '
          + ('Online mode leaves an owned running guest.' if args.mode == 'online' else
             'Offline mode leaves the guest powered off.'), flush=True)
    if args.y:
        return True
    while True:
        try:
            answer = input('Proceed (y/n)? ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if answer in ('y', 'n'):
            return answer == 'y'
        print('Please enter y to proceed or n to exit.', flush=True)


def main(argv=None):
    args = arguments(argv)
    try:
        if args.vm is None:
            args.vm = choose_vm()
        args.vm = select(args.vm).name
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        if not confirm_preparation(args):
            print('prepare-appsnapshot: cancelled; no app snapshot was prepared.')
            return 0
        root = Path(__file__).resolve().parents[1]
        helper = '/usr/local/libexec/onpc-test-runner'
        with test_activity.activity(root), Control().installed() as control:
            check(helper)
            environment = test_launcher.environment(root)
            if args.overwrite == 'true':
                cleanup(root)
                if control.stopped.is_set():
                    return 130
            status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                helper, 'appsnapshot', '--probe', '--mode', args.mode,
                '--overwrite', args.overwrite, *vm_arguments()], cwd=root, env=environment)
            if status == 4:
                return control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                    helper, 'appsnapshot', '--resume', '--mode', args.mode, *vm_arguments()],
                    cwd=root, env=environment)
            # Missing, expired, differently-mode or explicitly overwritten
            # snapshots select their package backend from baseline provenance.
            if status not in (3, 5):
                return status
            package_format = 'rpm' if status == 5 else 'deb'
            if args.overwrite == 'false':
                cleanup(root)
                if control.stopped.is_set():
                    return 130
            args.overwrite = 'true'
            with test_retention.Store(test_activity.retention_path(root)).session() as run:
                directory = test_retention.allocate(tempfile.mkdtemp,
                    prefix='onpc-test-artifacts-', dir='/tmp')
                print('prepare-appsnapshot: artifacts=' + directory, flush=True)
                status = control.run(['/usr/bin/python3', '-B',
                    str(root / 'tools/build_test_artifacts.py'), '--output', directory,
                    '--package-format', package_format],
                    cwd=root, env=environment)
                if status:
                    return status
                status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
                    '--retention-run=' + run, '--unattended', 'appsnapshot',
                    '--overwrite', args.overwrite, '--artifacts', directory,
                    '--mode', args.mode, *vm_arguments()],
                    cwd=root, env=environment, cooperative=True)
            if status or args.mode == 'offline':
                return status
            return control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
                'appsnapshot', '--resume', '--mode', args.mode, *vm_arguments()], cwd=root, env=environment)
    except (ValueError, OSError) as error:
        print('prepare-appsnapshot: ' + str(error), file=sys.stderr)
        return 2
