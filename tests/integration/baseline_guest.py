"""Stage and boot guest preparation under the host capture's exclusive lease."""

from contextlib import contextmanager
from pathlib import Path
import stat
import time

import prepare_vm
from test_account_password import matches

STAGE = '/var/lib/onpc-baseline-preparation'
UNIT = '/etc/systemd/system/onpc-baseline-preparation.service'
LINK = '/etc/systemd/system/multi-user.target.wants/onpc-baseline-preparation.service'
SERVICE = f'''[Unit]
Description=Prepare the ONPC test baseline
Wants=network-online.target accounts-daemon.service
After=network-online.target accounts-daemon.service
Before=display-manager.service
ConditionPathExists={STAGE}/password
SuccessAction=poweroff
FailureAction=poweroff

[Service]
Type=oneshot
UMask=0077
WorkingDirectory={STAGE}/checkout
ExecStart=/usr/bin/python3 -B {STAGE}/checkout/tests/integration/baseline_guest_entry.py
TimeoutStartSec=2400
StandardOutput=append:{STAGE}/preparation.log
StandardError=append:{STAGE}/preparation.log
'''


def require(condition, code):
    if not condition:
        from prepare_baseline import CaptureError
        raise CaptureError(code)


@contextmanager
def mounted(guestfs, capture):
    capture.revalidate(off=True)
    g = guestfs.GuestFS(python_return_dict=True)
    try:
        g.set_trace(False)
        g.set_verbose(False)
        g.set_backend('direct')
        g.set_network(False)
        g.add_drive_opts(capture.state['source']['layout']['disk'], format='qcow2')
        g.launch()
        roots = g.inspect_os()
        require(len(roots) == 1 and g.inspect_get_distro(roots[0]) == 'ubuntu'
                and g.inspect_get_major_version(roots[0]) == 26
                and g.inspect_get_minor_version(roots[0]) == 4, 'guest:release')
        mounts = g.inspect_get_mountpoints(roots[0])
        for point in sorted(mounts, key=lambda value: (len(value), value)):
            g.mount(mounts[point], point)
        yield g
        g.sync()
    finally:
        g.close()
    capture.revalidate(off=True)


def directory(g, path):
    if not g.exists(path) and not g.is_symlink(path):
        directory(g, str(Path(path).parent))
        g.mkdir(path)
        g.chmod(0o700, path)
    info = g.lstatns(path)
    require(g.realpath(path) == path and stat.S_ISDIR(info['st_mode'])
            and info['st_uid'] == 0 and not info['st_mode'] & 0o022,
            'guest:preparation-directory')


def write(g, path, content):
    directory(g, str(Path(path).parent))
    if g.exists(path) or g.is_symlink(path):
        info = g.lstatns(path)
        require(g.realpath(path) == path and stat.S_ISREG(info['st_mode'])
                and info['st_uid'] == 0 and info['st_nlink'] == 1,
                'guest:preparation-file')
    g.write(path, content)
    g.chmod(0o600, path)


def prepare(capture, guestfs, password):
    """Operate only on the off, journal-bound source. Never restore a baseline."""
    with mounted(guestfs, capture) as g:
        directory(g, STAGE)
        require(g.lstatns(STAGE)['st_mode'] & 0o077 == 0, 'guest:preparation-private')
        files = set(prepare_vm.SCRIPT_FILES) | set(prepare_vm.REQUIRED_CHECKOUT_ENTRIES)
        files.update({'tests/integration/baseline_guest_entry.py',
                      'tests/integration/test_account_password.py'})
        files.update(str(Path(account.icon_file).relative_to(prepare_vm.CHECKOUT))
                     for account in prepare_vm.IDENTITIES)
        for relative in sorted(files):
            write(g, STAGE + '/checkout/' + relative,
                  (prepare_vm.CHECKOUT / relative).read_bytes())
        for name in ('success',):
            if g.exists(STAGE + '/' + name) or g.is_symlink(STAGE + '/' + name):
                write(g, STAGE + '/' + name, b'')
        write(g, STAGE + '/password', password.encode('ascii'))
        write(g, UNIT, SERVICE.encode('ascii'))
        directory(g, str(Path(LINK).parent))
        if g.exists(LINK) or g.is_symlink(LINK):
            require(g.is_symlink(LINK) and g.readlink(LINK) == UNIT,
                    'guest:preparation-unit')
        else:
            g.ln_s(UNIT, LINK)
    capture.revalidate(off=True)
    source = capture.source
    source.domain.create()
    instance = source.domain.ID()
    require(instance >= 0, 'guest:preparation-start')
    try:
        deadline = time.monotonic() + 2700
        while not source.snapshot()[1]:
            require(source.domain.ID() == instance, 'guest:preparation-instance-changed')
            require(time.monotonic() < deadline, 'guest:preparation-timeout')
            time.sleep(2)
    except BaseException:
        # Only the instance we started may be asked to stop. No force kill.
        if not source.snapshot()[1] and source.domain.ID() == instance:
            source.shutdown(capture.revalidate, requested=False)
        raise
    capture.revalidate(off=True)
    with mounted(guestfs, capture) as g:
        require(g.exists(STAGE + '/success')
                and g.read_file(STAGE + '/success') == b'success\n',
                'guest:preparation-failed; inspect guest preparation.log')
        require(not g.exists(STAGE + '/password'), 'guest:preparation-secret-retained')
        hashes = [line.split(':') for line in g.read_file('/etc/shadow').decode('ascii').splitlines()]
        for account in prepare_vm.IDENTITIES:
            rows = [row for row in hashes if row[0] == account.username]
            require(len(rows) == 1 and len(rows[0]) == 9
                    and matches(password, rows[0][1]), 'guest:prepared-password-mismatch')
        require(g.is_symlink(LINK) and g.readlink(LINK) == UNIT, 'guest:preparation-unit')
        g.rm(LINK)
        g.rm(UNIT)
