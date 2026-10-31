"""Opt-in extension isolation, shared by the CLI and owned VM tests.

Never included in product packages. Tests call apply(transport) on their own
guarded transport; the CLI uses test-vm's existing maintenance transport.
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys

LAUNCHER = Path(__file__).with_name('development_broker.py')
TIMEOUT = 600

# Executed only through the existing identity-checked guest transport. Input is
# the checkout launcher, not a host path opened by a privileged dispatcher.
GUEST_PROGRAM = r'''
import os
import hashlib
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

if os.geteuid() != 0:
    raise SystemExit('disable-extension: guest root required')
root = Path('/usr/lib/oh-no-parent-control')
if not (root / 'broker/oh_no_parent_control/extension_manager.py').is_file():
    raise SystemExit('disable-extension: installed product required')
launcher = sys.stdin.buffer.read(65537)
if not launcher or len(launcher) > 65536:
    raise SystemExit('disable-extension: invalid launcher input')
compile(launcher, 'development_broker.py', 'exec')

def directory(path):
    for parent in reversed((path, *path.parents)):
        if not parent.exists() and not parent.is_symlink():
            parent.mkdir(mode=0o755)
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise SystemExit('disable-extension: unsafe guest directory')

def install(path, contents):
    # Preserve unknown files, links and previous differing versions. Completed
    # deployments are reusable; snapshot recovery owns incomplete/failed state.
    directory(path.parent)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                info.st_nlink != 1 or info.st_mode & 0o022 or path.read_bytes() != contents):
            raise SystemExit('disable-extension: guest file collision; restore the snapshot')
    else:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())

destination = Path('/var/lib/oh-no-parent-control-development/development_broker.py')
unit = 'oh-no-parent-control-broker.service'
dropin = Path('/etc/systemd/system') / (unit + '.d') / '90-development-disable-extension.conf'
override = ('[Service]\nExecStart=\nExecStart=/usr/bin/python3 -IB ' + str(destination) +
            ' --disable-child-extension-recovery\n').encode()
install(destination, launcher)
# Fedora retains trusted-language enforcement. Admit only these exact root-owned
# bytes through the existing file backend, never a permissive execution rule.
digest = hashlib.sha256(launcher).hexdigest()
trust = Path('/etc/fapolicyd/trust.d/oh-no-parent-control-development.trust')
install(trust, (str(destination) + ' ' + str(len(launcher)) + ' ' + digest + '\n').encode())
if shutil.which('restorecon'):
    subprocess.run(['restorecon', str(destination), str(trust)], check=True, timeout=30)
subprocess.run(['/usr/sbin/fapolicyd-cli', '--update'], check=True, timeout=180,
               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
# Reuse the package's exact, concurrency-safe file-backend snapshot reader.
# Each read is bounded in its own process; unrelated trust records stay private.
probe = """
import runpy,sys
api = runpy.run_path('/usr/libexec/oh-no-parent-control-package-activation')
expected = {(sys.argv[1], sys.argv[2], sys.argv[3])}
try:
    print(api['read_child_trust'](expected) == expected)
except api['ChildTrustBusy']:
    raise SystemExit(75)
"""
deadline = time.monotonic() + 120
while True:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SystemExit('disable-extension: launcher trust readiness timed out')
    result = subprocess.run(['/usr/bin/python3', '-IB', '-c', probe,
        str(destination), str(len(launcher)), digest], capture_output=True,
        text=True, timeout=min(10, remaining))
    if result.returncode == 0 and result.stdout.strip() == 'True':
        break
    if result.returncode not in (0, 75) or (result.returncode == 0 and result.stdout.strip() != 'False'):
        raise SystemExit('disable-extension: launcher trust verification failed')
    time.sleep(min(0.5, max(0, deadline - time.monotonic())))
install(dropin, override)
subprocess.run(['systemctl', '--no-ask-password', 'daemon-reload'], check=True, timeout=30)
subprocess.run(['systemctl', '--no-ask-password', 'restart', unit], check=True, timeout=200)
subprocess.run(['systemctl', '--no-ask-password', 'is-active', '--quiet', unit], check=True, timeout=10)
pid = int(subprocess.check_output(['systemctl', 'show', '--property=MainPID', '--value', unit], timeout=10))
command = Path('/proc') / str(pid) / 'cmdline'
if command.read_bytes().split(b'\0')[:-1] != [b'/usr/bin/python3', b'-IB',
        str(destination).encode(), b'--disable-child-extension-recovery']:
    raise SystemExit('disable-extension: development launcher is not running')

# Use installed account classification and the normal per-account disable path.
# Never clear the global switch, change policy, grants or usage, or target admins.
sys.path[:0] = [str(root), str(root / 'broker')]
from gi.repository import Gio
from common.oh_no_parent_control_ui.diagnostic_events import configure_console
from oh_no_parent_control import config
from oh_no_parent_control.adapters import AccountsService
from oh_no_parent_control.core import Broker
from oh_no_parent_control.extension_manager import ExtensionManager
configure_console()
configuration = config.load('/etc/oh-no-parent-control/config.json')
accounts = AccountsService(Gio.bus_get_sync(Gio.BusType.SYSTEM, None))
manager = ExtensionManager()
count = 0
for user in accounts.list_users():
    if Broker._eligible(configuration, user):
        manager.set_enabled(user.uid, False)
        count += 1
print('DEVELOPMENT ONLY: recovery suppressed; child extensions disabled; accounts=' + str(count), flush=True)
'''


def command():
    return ['/usr/bin/python3', '-B', '-c', GUEST_PROGRAM]


def apply(transport):
    """Modify this test's current guest without acquiring or restoring another VM.

    Requires the caller's guarded VM transport and live lease. Restarting the
    broker and disabling extensions are explicit engineering setup actions.
    Ordinary attempt cleanup restores the snapshot, also after a failure.
    """
    from watch_activity import operation
    if transport.lease is None:
        raise ValueError('disable-extension: an owned VM transport is required')
    with operation('Disabling child extensions and recovery for this VM attempt'):
        transport.lease.guard()
        return transport.call(command(), input=LAUNCHER.read_bytes(), timeout=TIMEOUT)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
        epilog='Requires an owned running app-snapshot maintenance VM. '
               'Never boots, restores or adopts a VM.')
    parser.add_argument('--vm', required=True, help='one registered VM name or ID')
    args = parser.parse_args(argv)
    try:
        if os.geteuid() == 0:
            raise ValueError('invoke as an unprivileged administrator')
        from vm_selection import vm_config
        from vm_pool import reservation
        from test_storage import scratch_descriptors
        configured = vm_config.load(args.vm)
        root = Path(__file__).resolve().parents[1]
        with reservation(configured.name):
            status = subprocess.run([
                str(root / 'tools/test-vm'), '--vm', configured.name, 'exec',
                '--timeout', str(TIMEOUT), '--input-file', str(LAUNCHER), '--', *command(),
            ], cwd=root, pass_fds=scratch_descriptors(), check=False).returncode
        if status:
            print('disable-extension: deployment failed; retain diagnostics and use normal '
                  'VM recovery before testing', file=sys.stderr)
        return status if status >= 0 else 128 - status
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as error:
        print('disable-extension: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
