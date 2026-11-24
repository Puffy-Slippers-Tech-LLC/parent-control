"""Update boots of a newly installed VM. Staged by the unattended installer."""

import os
from pathlib import Path
import subprocess
import sys

from guest_updates import cleanup_ubuntu_kernels, update_guest

SERVICE = 'onpc-newvm-first-boot.service'
USER = 'edgar'
TIMEZONE = 'America/Los_Angeles'
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
KERNEL_CLEANUP = Path(__file__).with_name('kernel-cleanup')


def run(*args):
    return subprocess.run(args, check=True, stdin=subprocess.DEVNULL, text=True, timeout=120)


def report(witness, attempt):
    with open('/dev/ttyS0', 'w', encoding='ascii') as serial:
        # An existing console prompt may end without a newline.
        serial.write(f'\n{witness} {attempt}\n')


def release():
    # Read again after updates, even if /etc/os-release has just been replaced.
    import shlex

    values = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        key, _, value = line.partition('=')
        if key in ('ID', 'VERSION_ID'):
            values[key] = shlex.split(value)[0]
    return values.get('ID'), values.get('VERSION_ID')


def main(distribution, version, hostname, attempt):
    run('systemctl', 'disable', SERVICE)
    if (release() != (distribution, version) or os.uname().nodename != hostname or
            Path('/etc/localtime').resolve() != Path('/usr/share/zoneinfo') / TIMEZONE):
        raise ValueError('Unexpected installed distribution, release, hostname or timezone')

    if distribution == 'ubuntu' and KERNEL_CLEANUP.exists():
        previous_boot = KERNEL_CLEANUP.read_text()
        if not previous_boot or previous_boot == BOOT_ID.read_text():
            raise ValueError('Kernel cleanup requires a fresh boot')
        cleanup_ubuntu_kernels()
        KERNEL_CLEANUP.unlink()
    else:
        if distribution == 'fedora':
            run('fedora-third-party', 'enable')
        update_guest(distribution, username=USER)
        if release() != (distribution, version):
            raise ValueError('The installed OS release changed during updates')
        if distribution == 'ubuntu':
            KERNEL_CLEANUP.write_text(BOOT_ID.read_text())
            run('systemctl', 'enable', SERVICE)
            report('ONPC-NEWVM-UPDATES-APPLIED', attempt)
            return

    # Finish before display-manager startup. Set and read back the GNOME
    # welcome version as the installed account on its own session bus.
    user = ('runuser', '-u', USER, '--')
    config = '/home/' + USER + '/.config'
    run(*user, 'mkdir', '-p', config)
    run(*user, 'touch', config + '/gnome-initial-setup-done')
    settings = (*user, 'env', 'GIO_USE_VFS=local', 'dbus-run-session', '--', 'gsettings')
    key = ('org.gnome.shell', 'welcome-dialog-last-shown-version')
    version_string = "'4294967295'"
    run(*settings, 'set', *key, version_string)
    result = subprocess.check_output([*settings, 'get', *key], text=True, timeout=120)
    if result.strip() != version_string:
        raise ValueError('GNOME tour suppression could not be verified')

    if distribution == 'ubuntu':
        Path('/var/log/installer/autoinstall-user-data').unlink(missing_ok=True)
    directory = Path(__file__).parent
    (directory / 'guest_updates.py').unlink()
    Path(__file__).unlink()
    directory.rmdir()
    Path('/etc/systemd/system', SERVICE).unlink()
    report('ONPC-NEWVM-UPDATED', attempt)


if __name__ == '__main__':
    main(*sys.argv[1:])
