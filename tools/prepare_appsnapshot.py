"""Build and prepare an online app snapshot through guarded standalone dispatch."""
import argparse
from contextlib import contextmanager
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
from vm_queue import preparation, prepare_hosts, require_host_queue
from vm_pool import binding, check_queue, reservation


def ensure_snap_prepared(root, control, environment):
    """Refresh the selected outdated or Snap-incomplete baseline under its reservation.

    Run before acquiring checkout activity: maintained preparation owns that
    activity and keeps all baseline/snapshot/VM ownership checks itself.
    """
    if not vm_config.snap_tests_enabled():
        return 0
    helper = '/usr/local/libexec/onpc-test-runner'
    with test_source.reader(root, stopped=control.stopped.is_set):
        status = control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
            helper, 'appsnapshot', '--probe', '--overwrite', 'true', *vm_arguments()],
            cwd=root, env=environment)
    if status != 8:
        return 0 if status in (3, 5, 6) else status
    with test_activity.activity(root, named_vm=True), \
            test_source.reader(root, stopped=control.stopped.is_set):
        status = cleanup(root)
    if status:
        return status
    print('VM readiness: baseline preparation required; automatically refreshing '
          'the selected baseline and app snapshots before resuming tests.', flush=True)
    status = control.run([str(root / 'tools/prepare-vm'), *vm_arguments(), '--mode', 'auto', '--y'],
                         cwd=root, env=environment, wait_on_cancel=True)
    print('VM readiness: ' + (f'automatic preparation failed (status {status}); see preparation output above.'
          if status else 'automatic preparation completed; resuming tests.'), flush=True)
    return status


@contextmanager
def snap_ready_reservation(root, name, control):
    with reservation(name, stopped=control.stopped):
        status = ensure_snap_prepared(root, control, test_launcher.environment(root))
        if status:
            raise ValueError(f'Snap baseline readiness failed (status {status})')
        yield


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vm', help=SELECTOR_HELP)
    parser.add_argument('--y', action='store_true',
                        help='proceed without confirmation for authorized automation and agent sessions')
    parser.add_argument('--queue-host', help=argparse.SUPPRESS)
    parser.add_argument('--release-notes-upgrade', action='store_true',
                        help='prepare the genuine prior/current upgrade for child release notes')
    parser.add_argument('--overwrite', nargs='?', const='true', default='true',
                        choices=('true', 'false'),
                        help='rebuild the current source before installing and replacing '
                             'a matching online version snapshot (default: true); false keeps '
                             'an existing version snapshot without building, or creates it if missing')
    return vm_config.parse_vm_arguments(parser, argv)


def confirm_preparation(args):
    warning = (f'\033[31mprepare-appsnapshot: prepare the current app snapshot on {args.vm} '
          f'(online, overwrite={args.overwrite}). '
          'Preparation may restore the baseline, install the app and replace the version snapshot. '
          'Guests are left running for maintenance when the selected VMs fit on their host. '
          'When the selection exceeds host capacity, preparation returns owned guests to the powered-off baseline.\033[0m')
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


def main(argv=None, *, _worker=False, _snapshot_only=False, _expected=None, _control=None):
    args = arguments(argv)
    try:
        concurrency, vms = vm_config.execution(args.vm)
        if _expected is not None and tuple(_expected) != vms:
            raise ValueError('selected VM registry changed before preparation')
        check_queue(vms)
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        root = Path(__file__).resolve().parents[1]
        from host_dispatch import tool_host
        owner = tool_host(root).name
        require_host_queue(args.queue_host, owner, args.vm, vms)
        args.vm = ','.join(vm.name for vm in vms)
        if not _worker and not confirm_preparation(args):
            print('prepare-appsnapshot: cancelled; no app snapshot was prepared.')
            return 0
        helper = '/usr/local/libexec/onpc-test-runner'
        test_source.finish_admission()
        recipe_args = ['--release-notes-upgrade'] if args.release_notes_upgrade else []
        if not _worker:
            if any(vm.host.name != owner for vm in vms):
                if binding() is not None:
                    raise ValueError('vm-pool: check in before dispatching preparation to another host')

                def run_local(options, control, targets):
                    return main(options, _expected=targets, _control=control)

                return prepare_hosts(root, 'prepare-appsnapshot',
                                     ['--overwrite', args.overwrite, *recipe_args], vms, owner, run_local)
            check(helper)
            _, status = preparation(root, 'prepare-appsnapshot', args, concurrency, vms, control=_control)
            return status
        os.environ.pop(BATCH, None)
        select(args.vm)
        with Control().installed() as control, snap_ready_reservation(root, args.vm, control), \
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
                if _snapshot_only:
                    status = cleanup(root)
                    if not status:
                        print('prepare-appsnapshot: reusing the existing online snapshot.', flush=True)
                    return status
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
            if status or _snapshot_only:
                return status
            return control.run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
                'appsnapshot', '--resume', '--overwrite', args.overwrite, *recipe_args, *vm_arguments()], cwd=root, env=environment)
    except (ValueError, OSError) as error:
        print('\033[31mprepare-appsnapshot: ' + str(error) + '\033[0m', file=sys.stderr)
        return 2
