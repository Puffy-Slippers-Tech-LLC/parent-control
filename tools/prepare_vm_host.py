"""Fixed setup controller: baseline, current app snapshot, then off baseline.

The authenticated setup caller builds packages without privilege in a separate
process. Its host activity/retention session stays alive until consumption ends.
All VM stages execute in this process beneath one exclusive controller lease.
"""
from contextlib import contextmanager
import argparse
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests/integration'))

import prepare_baseline as baseline
import vm_config
from watch_activity import operation


def build_worker(package_format, result_fd):
    """Private unprivileged worker; the pipe carries one allocated path only."""
    import test_activity
    import test_launcher
    import test_retention
    from regression_process import Control
    from prepare_appsnapshot import build_artifacts
    baseline.require(os.geteuid() != 0, 'build:unprivileged-caller-required')
    with test_activity.activity(ROOT, named_vm=True):
        with test_retention.Store(test_activity.retention_path(ROOT)).session(), Control().installed() as control:
            path, status = build_artifacts(ROOT, package_format, control,
                test_launcher.environment(ROOT), label='prepare-vm')
            if status:
                return status
            with os.fdopen(result_fd, 'w') as result:
                result.write(path + '\n')
            # Keep ownership/retention through privileged snapshot consumption.
            sys.stdin.buffer.read(1)
    return 0


@contextmanager
def built_artifacts(package_format, caller):
    reader, writer = os.pipe()
    process = None
    try:
        environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                       'HOME': caller.pw_dir, 'PYTHONDONTWRITEBYTECODE': '1',
                       vm_config.VARIABLE: vm_config.selected().name}
        process = subprocess.Popen(['/usr/bin/python3', '-IB', str(Path(__file__).resolve()),
            '--build-package-format', package_format, '--result-fd', str(writer)],
            cwd=ROOT, env=environment, stdin=subprocess.PIPE, pass_fds=(writer,),
            user=caller.pw_uid, group=caller.pw_gid,
            extra_groups=os.getgrouplist(caller.pw_name, caller.pw_gid))
        os.close(writer)
        writer = None
        with os.fdopen(reader) as result:
            reader = None
            path = result.readline(8192).rstrip('\n')
        baseline.require(path and len(path) < 8191, 'build:artifacts-unavailable')
        sys.path.insert(0, str(ROOT / 'tests/e2e'))
        from runner import validate_artifact_path
        validate_artifact_path(Path(path))
        yield Path(path)
    finally:
        if reader is not None:
            os.close(reader)
        if writer is not None:
            os.close(writer)
        if process is not None:
            process.stdin.close()
            status = process.wait()
            baseline.require(status == 0, 'build:failed')


def prepare(mode, assume_yes, vm, caller):
    import libvirt
    import test_retention
    from test_storage import privileged_state
    from vm_backup import lease, idle, read_json, verify_bootstrap
    commands = baseline.Commands()
    baseline.start_event_dispatch(libvirt)
    with operation('Preparing baseline, app snapshot and final powered-off VM'):
        with lease(vm, commands):
            options = ['--mode', mode, *(['--y'] if assume_yes else []), '--vm', vm.name]
            # Snapshot-free disaster archives contain the already prepared guest.
            # Reconcile it through the maintained manual implementation before
            # auto mode restores/updates its newly accepted baseline.
            journal = vm.baseline_directory / 'restore-vms.json'
            if mode == 'auto' and not os.path.lexists(vm.baseline_directory / 'phase.json') and os.path.lexists(journal):
                restored = read_json(journal)
                baseline.require(restored.get('phase') == 'complete', 'state:interrupted-vm-restore')
                source = baseline.LibvirtSource(libvirt)
                try:
                    verify_bootstrap(source, libvirt, vm, commands, restored)
                finally:
                    source.close()
                status = baseline.main(['--mode', 'manual', *(['--y'] if assume_yes else []),
                                        '--vm', vm.name])
                if status:
                    return status
            status = baseline.main(options)
            if status:
                return status
            sys.path.insert(0, str(ROOT / 'tests/e2e'))
            import system_runner
            import prepare_snapshot
            source = baseline.LibvirtSource(libvirt)
            try:
                capture = baseline.Capture(source, commands, None)
                capture.directory_identity = capture.private_directory()
                capture.state = capture.read_state()
                capture.revalidate(off=True)
                capture.verify_snapshot()
                package_format = system_runner.package_format(capture.state['guest'])
                with built_artifacts(package_format, caller) as artifacts:
                    with test_retention.Store(privileged_state(caller.pw_uid)).session(
                            guard=lambda: idle(vm)):
                        # This is the implementation used by prepare-appsnapshot.
                        # Its normal online cleanup restores the off baseline.
                        status = prepare_snapshot.prepare(artifacts, source.uuid,
                                                          overwrite=True, mode='online')
                        if status:
                            return status
                idle(vm)
                capture.revalidate(off=True)
                capture.verify_snapshot()
                source.restore_baseline(capture.state['source']['layout'], source.baseline())
                capture.revalidate(off=True)
                capture.verify_snapshot(boundary='restoration')
                return 0
            finally:
                source.close()


def main(argv=None):
    argv, vm = vm_config.extract(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--mode', required=True, choices=('auto', 'manual'))
    parser.add_argument('--y', action='store_true')
    args = parser.parse_args(argv)
    try:
        uid = int(os.environ.get('PKEXEC_UID', '0'))
        baseline.require(os.geteuid() == os.getegid() == 0 and uid > 0,
                         'guard:root; use tools/prepare-vm')
        return prepare(args.mode, args.y, vm, pwd.getpwuid(uid))
    except (Exception, KeyboardInterrupt) as error:
        category = str(error) if isinstance(error, (baseline.CaptureError, ValueError)) else type(error).__name__
        print('prepare-vm: ' + category + '; preserve controller state and retry.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if sys.argv[1:2] == ['--build-package-format']:
        parser = argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument('--build-package-format', required=True, choices=('deb', 'rpm'))
        parser.add_argument('--result-fd', required=True, type=int)
        args = parser.parse_args()
        sys.exit(build_worker(args.build_package_format, args.result_fd))
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    sys.exit(main())
