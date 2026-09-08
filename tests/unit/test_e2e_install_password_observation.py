"""Run the actual sudo proof with bounded guest process and terminal fixtures."""

import os
from pathlib import Path
import stat
import sys
import termios
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from installation_observations import SUDO_PASSWORD
sys.path.pop(0)


@pytest.mark.parametrize('fault', [None, 'leader', 'foreground', 'session', 'tty',
    'parent-session', 'parent-tty', 'parent-foreground', 'exe', 'shell', 'sudo-uid',
    'parent-uid', 'command', 'cached-auth', 'stdin', 'echo', 'echonl', 'device',
    'regular-device', 'binary-owner', 'binary-writable', 'starttime', 'changed-command'])
def test_install_password_requires_exact_sudo_fixture_and_no_echo(fault, capsys):
    counts = {}
    events = []
    device = os.makedev(4, 64)

    class GuestPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, value):
            return GuestPath(self.value + '/' + value)

        def __eq__(self, other):
            return isinstance(other, GuestPath) and self.value == other.value

        def resolve(self, strict=False):
            assert strict
            resolved = {'/usr/bin/sudo': '/usr/bin/sudo.ws',
                        '/proc/44/exe': '/usr/bin/sudo.ws',
                        '/proc/43/exe': '/usr/bin/bash'}[self.value]
            if (fault == 'exe' and self.value == '/proc/44/exe' or
                    fault == 'shell' and self.value == '/proc/43/exe'):
                resolved = '/usr/bin/other'
            return GuestPath(resolved)

        def read_bytes(self):
            assert self.value == '/proc/44/cmdline'
            counts['cmdline'] = counts.get('cmdline', 0) + 1
            args = [b'/usr/bin/sudo', b'-k', b'-p', b'ONPC-INSTALL-PASSWORD: ', b'--',
                    b'/usr/bin/apt-get', b'install', b'-y',
                    b'/var/lib/onpc-e2e-assets/package.deb', b'']
            if fault == 'command' or fault == 'changed-command' and counts['cmdline'] > 1:
                args[-2] = b'/tmp/other.deb'
            if fault == 'cached-auth':
                args.remove(b'-k')
            return b'\0'.join(args)

        def read_text(self):
            pid = int(self.value.split('/')[2])
            assert pid in (42, 43, 44)
            if self.value.endswith('/status'):
                ids = [1001, 0, 0, 0] if pid == 44 else [1001]*4
                if fault == ('sudo-uid' if pid == 44 else 'parent-uid'):
                    ids[0] = 999
                return 'Name:\tprivate-canary\nUid:\t' + '\t'.join(map(str, ids)) + '\n'
            assert self.value.endswith('/stat')
            counts[pid] = counts.get(pid, 0) + 1
            fields = ['S', str(pid-1), str(pid), '42', str(device), '44', *(['0'] * 20)]
            fields[19] = '123'
            if pid == 44:
                for name, index in [('session', 3), ('tty', 4)]:
                    if fault == name:
                        fields[index] = '999'
                if fault == 'starttime' and counts[pid] > 2:
                    fields[19] = '987'
            if pid == 42 and fault == 'foreground':
                fields[5] = '42'
            if pid == 43:
                for name, index in [('parent-session', 3), ('parent-tty', 4), ('parent-foreground', 5)]:
                    if fault == name:
                        fields[index] = '999'
            return str(pid) + ' (private process name) ' + ' '.join(fields)

        def stat(self):
            if self.value == '/usr/bin/sudo.ws':
                return SimpleNamespace(st_mode=stat.S_IFREG | (0o777 if fault == 'binary-writable' else 0o755),
                                       st_uid=1 if fault == 'binary-owner' else 0, st_gid=0)
            assert self.value == '/proc/44/fd/0'
            return SimpleNamespace(st_rdev=0 if fault == 'stdin' else device)

    def command(args, **kwargs):
        assert args == ['systemctl', 'show', 'serial-getty@ttyS0.service', '--property=MainPID', '--value']
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=10)
        return SimpleNamespace(stdout='0' if fault == 'leader' else '42')

    def opened(path, flags):
        assert path == '/dev/ttyS0'
        assert flags == os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW
        events.append('open')
        return 77

    fake_os = SimpleNamespace(makedev=os.makedev, O_RDONLY=os.O_RDONLY, O_NONBLOCK=os.O_NONBLOCK,
        O_NOCTTY=os.O_NOCTTY, O_NOFOLLOW=os.O_NOFOLLOW, open=opened,
        close=lambda fd: events.append(('close', fd)), fstat=lambda fd: SimpleNamespace(
            st_mode=stat.S_IFREG if fault == 'regular-device' else stat.S_IFCHR,
            st_rdev=0 if fault == 'device' else device))
    modules = {'os': fake_os, 'pathlib': SimpleNamespace(Path=GuestPath),
        'pwd': SimpleNamespace(getpwnam=lambda name: SimpleNamespace(pw_uid=1001)),
        'subprocess': SimpleNamespace(run=command),
        'termios': SimpleNamespace(ECHO=termios.ECHO, ECHONL=termios.ECHONL,
            tcgetattr=lambda fd: [0, 0, 0, {'echo': termios.ECHO, 'echonl': termios.ECHONL}.get(fault, 0)])}
    with patch.dict(sys.modules, modules):
        if fault:
            with pytest.raises(AssertionError):
                exec(SUDO_PASSWORD, {})
        else:
            exec(SUDO_PASSWORD, {})
    assert capsys.readouterr().out == ('' if fault else 'install-password-safe\n')
    if 'open' in events:
        assert events[-1] == ('close', 77)
