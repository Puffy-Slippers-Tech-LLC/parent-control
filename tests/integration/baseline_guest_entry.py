"""Private guest entry point staged only by the host baseline controller."""

import os
from pathlib import Path
import stat
import subprocess
import sys
import time

import prepare_vm

ROOT = Path('/var/lib/onpc-baseline-preparation')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')


def prepare_native(os_id='ubuntu'):
    """Let the packaged daemon initialize its database after offline reconciliation.

    This runs in a separate, fresh boot after package updates and the final
    backend configuration. No fixture or test attempt may initialize this state.
    """
    runner = prepare_vm.Runner()
    # Movable source modules have already been retired before this boot.
    cli = {'ubuntu': '/usr/sbin/fapolicyd-cli', 'fedora': '/usr/bin/fapolicyd-cli'}[os_id]
    vendor = {'ubuntu': 'debdb', 'fedora': 'rpmdb'}[os_id]
    runner.run([cli, '--check-config'])
    runner.run(['systemctl', 'enable', 'fapolicyd.service'])
    try:
        runner.run(['systemctl', 'start', 'fapolicyd.service'], timeout=180)
    except subprocess.SubprocessError as error:
        # This root-private preparation log is the diagnosis owner after the
        # one-shot powers off. Preserve the native failure, even if the extra
        # read-only journal query itself fails.
        print('baseline: [native:service-start-failed]', flush=True)
        if getattr(error, 'stderr', None):
            print(error.stderr, file=sys.stderr, flush=True)
        try:
            journal = runner.run(['journalctl', '--boot', '--unit=fapolicyd.service',
                                  '--no-pager', '--lines=80'], check=False)
            print(journal.stdout, flush=True)
        except (OSError, subprocess.SubprocessError):
            print('baseline: [native:journal-unavailable]', flush=True)
        raise
    enabled = runner.run(['systemctl', 'is-enabled', 'fapolicyd.service'])
    if enabled.stdout.strip() != 'enabled':
        raise ValueError('baseline:native-not-ready')
    # This packaged Type=forking daemon exits its parent before loading trust.
    # An old readable database can precede native initialization. Require the
    # public status handshake in the same bounded wait before the fresh dump;
    # never repair or create database files.
    deadline = time.monotonic() + 180
    last_status_error = None
    ready = False
    rows = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        active = runner.run(['systemctl', 'is-active', 'fapolicyd.service'], timeout=min(30, remaining))
        if active.stdout.strip() != 'active':
            raise ValueError('baseline:native-not-ready')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            database = runner.run([cli, '--dump-db'], timeout=min(30, remaining))
        except subprocess.CalledProcessError as error:
            if 'mdb_env_open failed, error 2 ' not in (error.stderr or ''):
                raise
            database = subprocess.CompletedProcess([cli, '--dump-db'], 0, stdout='')
        rows = [line.split() for line in database.stdout.splitlines() if line.strip()]
        remaining = deadline - time.monotonic()
        if any(row[0] == vendor for row in rows) and remaining > 0:
            try:
                runner.run([cli, '--check-status'], timeout=min(60, remaining))
            except subprocess.TimeoutExpired as error:
                if last_status_error is None or time.monotonic() < deadline:
                    raise
                # A final deadline-clipped request can outlive the remaining
                # native polling window. Diagnose it without retrying it.
                print(last_status_error.stdout, flush=True)
                last_status_error = error
                break
            except subprocess.CalledProcessError as error:
                if (error.returncode != 1 or error.stderr not in (None, '')
                        or error.stdout not in ("Can't find fapolicyd: timed out waiting for report",
                                                "Can't find fapolicyd: timed out waiting for report\n")):
                    raise
                last_status_error = error
            else:
                ready = time.monotonic() < deadline
                break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(1, remaining))
    if not ready:
        print(f'baseline: [native:inspection] enabled=1 active=1 '
              f'database_rows={len(rows)} vendor_rows={sum(row[0] == vendor for row in rows)}', flush=True)
        print('baseline: [native:readiness-timeout]', flush=True)
        if last_status_error is not None:
            try:
                journal = runner.run(['journalctl', '--boot', '--unit=fapolicyd.service',
                                      '--no-pager', '--lines=80'], check=False, timeout=30)
                print(journal.stdout, flush=True)
            except (OSError, subprocess.SubprocessError):
                print('baseline: [native:journal-unavailable]', flush=True)
            raise last_status_error
        raise ValueError('baseline:native-readiness-timeout')
    database = runner.run([cli, '--dump-db'], timeout=120)
    rows = [line.split() for line in database.stdout.splitlines() if line.strip()]
    vendor_rows = sum(row[0] == vendor for row in rows)
    print(f'baseline: [native:inspection] enabled=1 active=1 '
          f'database_rows={len(rows)} vendor_rows={vendor_rows}', flush=True)
    if not vendor_rows:
        raise ValueError('baseline:native-not-ready')


def update_system(os_id='ubuntu'):
    """Update packages within the supported guest release using APT or DNF5."""
    environment = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'NEEDRESTART_MODE': 'a'}
    commands = (
        ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'],
        ['apt-get', '-o', 'DPkg::Lock::Timeout=300',
         '-o', 'Dpkg::Options::=--force-confdef', '-o', 'Dpkg::Options::=--force-confold',
         '-y', 'dist-upgrade'],
        ['apt-get', 'check'],
    )
    if os_id == 'fedora':
        commands = (['dnf5', '--refresh', '-y', 'upgrade'], ['dnf5', 'check'])
    elif os_id != 'ubuntu':
        raise ValueError('baseline:unsupported-os')
    for command in commands:
        print('baseline: updating ' + os_id + ': ' + command[-1], flush=True)
        subprocess.run(command, check=True, timeout=3600, env=environment,
                       stdin=subprocess.DEVNULL)
    prepare_vm.guest_tools.verify_installed(os_id, runner=prepare_vm.Runner(), root=Path('/'))


def main(argv=None):
    args, _ = prepare_vm.vm_config.extract(sys.argv[1:] if argv is None else argv)
    root = ROOT
    print('baseline: [stage:entry]', flush=True)
    if os.geteuid() != 0 or prepare_vm.CHECKOUT != root / 'checkout':
        print('baseline: [guard:entry-context]', flush=True)
        return 1
    if args == ['--prepare-native']:
        os_id, _ = prepare_vm.release_identity(prepare_vm._read_os_release(Path('/etc/os-release')))
        prepare_vm.guest_tools.verify_installed(os_id, runner=prepare_vm.Runner(), root=Path('/'))
        try:
            prepare_native(os_id)
        except subprocess.SubprocessError as error:
            if getattr(error, 'stdout', None):
                print(error.stdout, flush=True)
            if getattr(error, 'stderr', None):
                print(error.stderr, file=sys.stderr, flush=True)
            raise
        print('baseline: [native:ready]', flush=True)
        (root / 'success').write_text('success\n')
        return 0
    if args == ['--verify-reboot']:
        previous = (root / 'reboot-required').read_text().strip()
        if not previous or previous == BOOT_ID.read_text().strip():
            return 1
        os_id, _ = prepare_vm.release_identity(prepare_vm._read_os_release(Path('/etc/os-release')))
        prepare_vm.guest_tools.verify_installed(os_id, runner=prepare_vm.Runner(), root=Path('/'))
        (root / 'reboot-required').unlink()
        (root / 'success').write_text('success\n')
        return 0
    if args:
        print('baseline: [guard:entry-arguments]', flush=True)
        return 1
    mode = (root / 'mode').read_text()
    if mode not in ('auto', 'manual'):
        print('baseline: [guard:entry-mode]', flush=True)
        return 1
    fd = os.open(root / 'password', os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, encoding='ascii') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            print('baseline: [guard:entry-secret-file]', flush=True)
            return 1
        password = stream.read(257)
    (root / 'password').unlink()
    os.chdir(prepare_vm.CHECKOUT)
    result = prepare_vm.main(password)
    password = ''
    if result == 0:
        if mode == 'auto':
            os_id, _ = prepare_vm.release_identity(prepare_vm._read_os_release(Path('/etc/os-release')))
            update_system(os_id)
            # A full power cycle after Fedora updates avoids depending on an
            # optional needs-restarting plugin. Manual mode performs no update.
            if os_id == 'fedora' or Path('/run/reboot-required').exists():
                (root / 'reboot-required').write_text(BOOT_ID.read_text())
                return 0
        (root / 'success').write_text('success\n')
    return result


if __name__ == '__main__':
    sys.exit(main())
