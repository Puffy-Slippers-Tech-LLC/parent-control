"""Build and prepare an online app snapshot through guarded standalone dispatch."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

import test_activity
import test_launcher
import test_retention
import test_source
from dev_privileges import check
from regression_process import Control
from test_recovery import cleanup
from vm_selection import select, arguments as vm_arguments, vm_config, SELECTOR_HELP, confirm_queue, BATCH
from vm_queue import preparation
from vm_pool import check_queue, reservation


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help=SELECTOR_HELP)
    parser.add_argument('--y', action='store_true',
                        help='proceed without confirmation for authorized automation and agent sessions')
    parser.add_argument('--release-notes-upgrade', action='store_true',
                        help='prepare the genuine prior/current upgrade for child release notes')
    parser.add_argument('--overwrite', nargs='?', const='true', default='true',
                        choices=('true', 'false'),
                        help='rebuild the current source before installing and replacing '
                             'a matching online version snapshot (default: true); false keeps '
                             'an existing version snapshot without building, or creates it if missing')
    return parser.parse_args(argv)


def confirm_preparation(args):
    warning = (f'\033[31mprepare-appsnapshot: prepare the current app snapshot on {args.vm} '
          f'(online, overwrite={args.overwrite}). '
          'Preparation may restore the baseline, install the app and replace the version snapshot. '
          'Preparation leaves an owned running guest.\033[0m')
    return confirm_queue(args, 'prepare-appsnapshot', warning, prompt=input)


def build_artifacts(root, package_format, control, environment, *, label='prepare-appsnapshot',
                    release_notes_upgrade=False):
    """Build once in the caller's active retained session, using owned transport."""
    target = vm_config.selected().require_build_target()
    if target.package_format != package_format:
        raise ValueError('configured build target does not match baseline package format')
    if release_notes_upgrade:
        from test_commands import prepare_qualification_artifacts
        from test_storage import named_input
        status = prepare_qualification_artifacts(root, 'system', ['check_e2e_kiosk_whats_new'],
            run=lambda command: control.run(command, cwd=root, env=environment))
        return str(named_input(upgrade_source=True)), status
    directory = test_retention.allocate(tempfile.mkdtemp,
        prefix='onpc-test-artifacts-')
    print(label + ': artifacts=' + directory, flush=True)
    status = control.run(['/usr/bin/python3', '-B',
        str(root / 'tools/build_test_artifacts.py'), '--output', directory,
        '--package-format', package_format, '--build-target', target.name,
        '--architecture', target.architecture], cwd=root, env=environment)
    return directory, status


def main(argv=None, *, _worker=False):
    args = arguments(argv)
    try:
        concurrency, vms = vm_config.execution(args.vm)
        check_queue(vms)
        args.vm = ','.join(vm.name for vm in vms)
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        if not _worker and not confirm_preparation(args):
            print('prepare-appsnapshot: cancelled; no app snapshot was prepared.')
            return 0
        root = Path(__file__).resolve().parents[1]
        helper = '/usr/local/libexec/onpc-test-runner'
        test_source.finish_admission()
        recipe_args = ['--release-notes-upgrade'] if args.release_notes_upgrade else []
        if not _worker:
            check(helper)
            _, status = preparation(root, 'prepare-appsnapshot', args, concurrency, vms)
            return status
        os.environ.pop(BATCH, None)
        select(args.vm)
        with Control().installed() as control, reservation(args.vm, stopped=control.stopped), \
                test_activity.activity(root, named_vm=True), \
                test_source.reader(root, stopped=control.stopped.is_set):
            check(helper)
            environment = test_launcher.environment(root)
            if 'ONPC_WORKFLOW_DIRECTORY' in os.environ:
                environment['ONPC_WORKFLOW_DIRECTORY'] = os.environ['ONPC_WORKFLOW_DIRECTORY']
            if args.overwrite == 'true':
                cleanup(root)
                if control.stopped.is_set():
                    return 130
            status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                helper, 'appsnapshot', '--probe',
                '--overwrite', args.overwrite, *recipe_args, *vm_arguments()], cwd=root, env=environment)
            if status == 6:
                cleanup(root)
                if control.stopped.is_set():
                    return 130
                status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                    helper, 'appsnapshot', '--probe',
                    '--overwrite', args.overwrite, *recipe_args, *vm_arguments()], cwd=root, env=environment)
            if status == 4:
                return control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                    helper, 'appsnapshot', '--resume', '--overwrite', args.overwrite, *recipe_args, *vm_arguments()],
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
            for attempt in range(3):
                with test_retention.Store(test_activity.retention_path(root)).session() as run:
                    directory, status = build_artifacts(root, package_format, control, environment,
                        release_notes_upgrade=args.release_notes_upgrade)
                    if status:
                        return status
                    status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
                        '--retention-run=' + run, '--unattended', 'appsnapshot',
                        '--overwrite', args.overwrite, '--artifacts', directory, *recipe_args, *vm_arguments()],
                        cwd=root, env=environment, cooperative=True)
                if status != 7:
                    break
                if control.stopped.is_set():
                    return 130
                if attempt < 2:
                    print('prepare-appsnapshot: checkout version changed during package preparation; '
                          'rebuilding the current app package.', flush=True)
            if status:
                return status
            return control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
                'appsnapshot', '--resume', '--overwrite', args.overwrite, *recipe_args, *vm_arguments()], cwd=root, env=environment)
    except (ValueError, OSError) as error:
        print('\033[31mprepare-appsnapshot: ' + str(error) + '\033[0m', file=sys.stderr)
        return 2
