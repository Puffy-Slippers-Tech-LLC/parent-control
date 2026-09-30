"""Private guest entry point staged only by the host baseline controller."""

import os
from pathlib import Path
import stat
import subprocess
import sys

import prepare_vm

ROOT = Path('/var/lib/onpc-baseline-preparation')
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')


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
