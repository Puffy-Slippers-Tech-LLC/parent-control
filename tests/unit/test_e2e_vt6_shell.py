"""Execute the fixed shell-lineage probe; never confuse lineage with readiness."""

import hashlib
import errno
import json
import os
import stat
import sys
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from guest_observations import VT6_SHELL_IDENTITY


def test_linux_foreground_ioctl_requires_the_observers_controlling_terminal():
    master, slave = os.openpty()
    try:
        with pytest.raises(OSError) as error:
            os.tcgetpgrp(slave)
        assert error.value.errno == errno.ENOTTY
    finally:
        os.close(slave)
        os.close(master)


@pytest.mark.parametrize('fault', [None, 'leader', 'leader-replaced', 'children',
    'child-self', 'child-invalid', 'children-replaced', 'shell-child', 'shell-args',
    'shell-parent', 'shell-pgrp', 'shell-session', 'shell-tty', 'shell-foreground',
    'login-pgrp', 'login-session', 'login-tty', 'login-foreground',
    'shell-older', 'shell-start-replaced', 'login-start-replaced',
    'shell-state', 'login-state', 'short-stat', 'start-zero', 'start-malformed',
    'login-exe', 'shell-exe', 'late-login-exe', 'late-shell-exe',
    'login-uid', 'shell-uid', 'late-shell-uid', 'fixture-root',
    'binary-mode', 'binary-owner', 'binary-group', 'binary-type',
    'stdin', 'stdout', 'stderr', 'fd-type', 'terminal-type', 'terminal-device',
    'late-shell-foreground', 'boot', 'boot-malformed', 'active',
    'late-active', 'read-error', 'open-error'])
def test_vt6_shell_follows_only_pinned_login_child(fault, capsys):
    device = os.makedev(4, 6)
    counts = Counter()
    events = []
    boot = 'a0000000-0000-0000-0000-000000000001\n'

    class GuestPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, value):
            return GuestPath(self.value + '/' + value)

        def __eq__(self, other):
            return isinstance(other, GuestPath) and self.value == other.value

        def read_text(self):
            value = self.value
            counts[value] += 1
            if fault == 'read-error':
                raise OSError('private-canary')
            if value == '/sys/class/tty/tty0/active':
                return 'tty1\n' if fault == 'active' or (
                    fault == 'late-active' and counts[value] > 3) else 'tty6\n'
            if value == '/proc/sys/kernel/random/boot_id':
                return 'private-canary' if fault == 'boot-malformed' else (
                    boot.replace('a', 'b') if fault == 'boot' and counts[value] > 1 else boot)
            if value == '/proc/42/task/42/children':
                return {'children': '43 44', 'child-self': '42',
                        'child-invalid': '0'}.get(fault, '44' if fault == 'children-replaced'
                            and counts[value] > 1 else '43')
            if value == '/proc/43/task/43/children':
                return '44' if fault == 'shell-child' else ''
            assert value in ('/proc/42/stat', '/proc/43/stat', '/proc/42/status', '/proc/43/status')
            shell = value.startswith('/proc/43/')
            role = 'shell' if shell else 'login'
            if value.endswith('/status'):
                uid = 1000 if shell else 0
                wrong = fault == role + '-uid' or (fault == 'late-shell-uid' and shell and counts[value] > 1)
                return 'Uid:\t' + '\t'.join(map(str, [999 if wrong else uid, uid, uid, uid])) + '\n'
            fields = (['S', '42', '43', '43', str(device), '43'] if shell else
                      ['S', '1', '42', '42', '0', '-1']) + ['0'] * 46
            fields[19] = '124' if shell else '123'
            for name, index in [('parent', 1), ('pgrp', 2), ('session', 3),
                                ('tty', 4), ('foreground', 5)]:
                if fault == role + '-' + name:
                    fields[index] = '999'
            if fault == 'late-shell-foreground' and shell and counts[value] > 2:
                fields[5] = '999'
            if fault == role + '-state':
                fields[0] = 'Z'
            if fault == 'shell-older' and shell:
                fields[19] = '122'
            if fault == role + '-start-replaced' and counts[value] > 2:
                fields[19] = '999'
            if fault in ('start-zero', 'start-malformed'):
                fields[19] = '0' if fault == 'start-zero' else 'private-canary'
            if fault == 'short-stat':
                fields = fields[:10]
            return ('43' if shell else '42') + ' (process with spaces) ' + ' '.join(fields)

        def read_bytes(self):
            assert self.value == '/proc/43/cmdline'
            return b'bash\0-c\0read value\0' if fault == 'shell-args' else b'-bash\0'

        def resolve(self, *, strict):
            assert strict and self.value in ('/proc/42/exe', '/proc/43/exe')
            counts[self.value] += 1
            role = 'login' if '/42/' in self.value else 'shell'
            wrong = fault == role + '-exe' or (fault == 'late-' + role + '-exe' and counts[self.value] > 1)
            return GuestPath('/usr/bin/other' if wrong else
                             '/usr/bin/login' if role == 'login' else '/usr/bin/bash')

        def stat(self):
            if self.value in ('/usr/bin/login', '/usr/bin/bash'):
                return SimpleNamespace(st_mode=(stat.S_IFDIR if fault == 'binary-type' else stat.S_IFREG)
                                       | (0o777 if fault == 'binary-mode' else 0o755),
                                       st_uid=int(fault == 'binary-owner'),
                                       st_gid=int(fault == 'binary-group'))
            assert self.value in ('/proc/43/fd/0', '/proc/43/fd/1', '/proc/43/fd/2')
            wrong = fault == {'0': 'stdin', '1': 'stdout', '2': 'stderr'}[self.value[-1]]
            return SimpleNamespace(st_mode=stat.S_IFREG if fault == 'fd-type' else stat.S_IFCHR,
                                   st_rdev=0 if wrong else device)

    def command(args, **kwargs):
        assert args == ['systemctl', 'show', 'getty@tty6.service', '--property=MainPID', '--value']
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=10)
        counts['command'] += 1
        return SimpleNamespace(stdout='0' if fault == 'leader' else '99' if
            fault == 'leader-replaced' and counts['command'] > 1 else '42')

    def opened(path, flags):
        assert path == '/dev/tty6'
        assert flags == os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW
        if fault == 'open-error':
            raise OSError('private-canary')
        events.append('open')
        return 77

    def foreground(fd):
        assert fd == 77
        # SSH observes a terminal outside its own session. The kernel refuses
        # this ioctl even for an otherwise valid descriptor; do not fake success.
        raise OSError(errno.ENOTTY, 'observer does not own controlling terminal')

    fake_os = SimpleNamespace(makedev=os.makedev, O_RDONLY=os.O_RDONLY, O_NONBLOCK=os.O_NONBLOCK,
        O_NOCTTY=os.O_NOCTTY, O_NOFOLLOW=os.O_NOFOLLOW, open=opened, tcgetpgrp=foreground,
        close=lambda fd: events.append(('close', fd)),
        fstat=lambda fd: SimpleNamespace(st_mode=stat.S_IFREG if fault == 'terminal-type' else stat.S_IFCHR,
                                        st_rdev=0 if fault == 'terminal-device' else device))
    def fixture(name):
        assert name == 'onpc-parent-jamie'
        return SimpleNamespace(pw_uid=0 if fault == 'fixture-root' else 1000)

    with patch.dict(sys.modules, {'os': fake_os, 'pathlib': SimpleNamespace(Path=GuestPath),
            'subprocess': SimpleNamespace(run=command), 'pwd': SimpleNamespace(getpwnam=fixture)}):
        if fault:
            with pytest.raises((AssertionError, OSError)):
                exec(VT6_SHELL_IDENTITY, {})
        else:
            exec(VT6_SHELL_IDENTITY, {})
    output = capsys.readouterr()
    assert not output.err
    if fault:
        assert output.out == ''
    else:
        digest = hashlib.sha256(boot.encode()).hexdigest()
        expected = {'probe': 'vt6-shell-identity', 'boot_sha256': digest,
            'recipient_sha256': hashlib.sha256(json.dumps(
                [digest, 'getty@tty6.service', 42, '123'], separators=(',', ':')).encode()).hexdigest(),
            'shell_sha256': hashlib.sha256(json.dumps(
                [digest, 'getty@tty6.service', 42, '123', 43, '124'],
                separators=(',', ':')).encode()).hexdigest()}
        assert output.out == json.dumps(expected, sort_keys=True) + '\n'
        assert 'ready' not in output.out
    if 'open' in events:
        assert events == ['open', ('close', 77)]
