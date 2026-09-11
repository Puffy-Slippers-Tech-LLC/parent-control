"""Execute the real no-echo probe against explicit guest process fixtures."""

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import termios
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from guest_observations import (BOOT, SERIAL_PASSWORD, VT6_PASSWORD, VT6_GETTY,
                                VT6_GETTY_IDENTITY, VT6_PASSWORD_IDENTITY)


@pytest.mark.parametrize('fault', [None, 'pid', 'exe', 'autologin', 'device', 'stdin',
                                  'pgrp', 'session', 'tty', 'foreground', 'echo',
                                  'echonl', 'canonical', 'starttime',
                                  'inactive', 'active-changed', 'active-read-error',
                                  'unit-replaced', 'boot-changed', 'boot-malformed',
                                  'credentials', 'late-starttime', 'late-exe'])
@pytest.mark.parametrize('terminal', ['serial', 'vt6', 'vt6-getty', 'vt6-getty-raw',
                                     'vt6-getty-identity', 'vt6-password-identity'])
def test_guest_password_probe_refuses_wrong_process_or_echo(fault, capsys, terminal):
    vt = terminal != 'serial'
    getty = terminal.startswith('vt6-getty')
    identity_probe = terminal.endswith('-identity')
    rejected = bool(fault) and (vt or not fault.startswith('active') and fault != 'inactive')
    if not identity_probe and fault in ('unit-replaced', 'boot-changed', 'boot-malformed',
                                       'credentials', 'late-starttime', 'late-exe'):
        rejected = False
    if getty and fault in ('autologin', 'echonl'):
        rejected = False
    device = os.makedev(4, 6 if vt else 64)
    events = []
    counts = {'stat': 0}
    class GuestPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, value):
            return GuestPath(self.value + '/' + value)

        def __eq__(self, other):
            return isinstance(other, GuestPath) and self.value == other.value

        def resolve(self):
            assert self.value == '/proc/42/exe'
            counts['exe'] = counts.get('exe', 0) + 1
            return GuestPath('/usr/bin/sh' if fault == 'exe' or (
                fault == 'late-exe' and identity_probe and counts['exe'] == 3) else
                             '/usr/sbin/agetty' if getty else '/usr/bin/login')

        def read_bytes(self):
            assert self.value == '/proc/42/cmdline'
            return b'/bin/login\0' + (b'-f\0--\0' if fault == 'autologin' else b'--\0') + b'\0' * 18

        def read_text(self):
            if self.value == '/proc/sys/kernel/random/boot_id':
                counts['boot'] = counts.get('boot', 0) + 1
                if fault == 'boot-malformed':
                    return 'private-canary'
                return ('b' if fault == 'boot-changed' and counts['boot'] > 1 else 'a') + (
                    '0000000-0000-0000-0000-000000000001\n')
            if self.value == '/proc/42/status':
                return 'Uid:\t' + ('1000' if fault == 'credentials' else '0') + '\t0\t0\t0\n'
            if self.value == '/sys/class/tty/tty0/active':
                assert vt
                counts['active'] = counts.get('active', 0) + 1
                if fault == 'active-read-error':
                    raise OSError('private-canary')
                return 'tty1\n' if fault == 'inactive' or (
                    fault == 'active-changed' and counts['active'] > 2) else 'tty6\n'
            assert self.value == '/proc/42/stat'
            counts['stat'] += 1
            fields = ['S', '1', '42', '42', str(device), '42', *(['0'] * 46)]
            for name, index in [('pgrp', 2), ('session', 3), ('tty', 4), ('foreground', 5)]:
                if fault == name:
                    fields[index] = '999'
            fields[19] = '987' if (fault == 'starttime' and counts['stat'] > 1 or
                fault == 'late-starttime' and counts['stat'] > 2) else '123'
            return '42 (login with spaces) ' + ' '.join(fields)

        def stat(self):
            assert self.value == '/proc/42/fd/0'
            return SimpleNamespace(st_rdev=0 if fault == 'stdin' else device)

    def command(args, **kwargs):
        counts['command'] = counts.get('command', 0) + 1
        assert args == ['systemctl', 'show', 'getty@tty6.service' if vt else
                        'serial-getty@ttyS0.service', '--property=MainPID', '--value']
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=10)
        return SimpleNamespace(stdout='0' if fault == 'pid' else '99' if
            fault == 'unit-replaced' and counts['command'] > 1 else '42')

    def opened(path, flags):
        assert path == ('/dev/tty6' if vt else '/dev/ttyS0')
        assert flags == os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW
        events.append('open')
        return 77

    def attributes(fd):
        assert fd == 77
        flags = termios.ICANON | (termios.ECHO if getty else 0)
        if terminal == 'vt6-getty-raw':
            # agetty reset_vc(canon=0), AGETTY_RELOAD build: get_logname
            # consumes characters and echoes them without the kernel ECHO bit.
            flags = 0
        if fault == 'echo':
            flags ^= termios.ECHO
        elif fault == 'echonl':
            flags |= termios.ECHONL
        elif fault == 'canonical':
            flags ^= termios.ICANON
        return [0,0,0,flags]

    fake_os = SimpleNamespace(makedev=os.makedev, O_RDONLY=os.O_RDONLY, O_NONBLOCK=os.O_NONBLOCK,
                              O_NOCTTY=os.O_NOCTTY, O_NOFOLLOW=os.O_NOFOLLOW, open=opened,
                              close=lambda fd: events.append(('close', fd)),
                              fstat=lambda fd: SimpleNamespace(st_mode=stat.S_IFCHR,
                                  st_rdev=0 if fault == 'device' else device))
    modules = {'os': fake_os, 'pathlib': SimpleNamespace(Path=GuestPath),
               'subprocess': SimpleNamespace(run=command),
               'time': SimpleNamespace(monotonic=iter([0, 31]).__next__, sleep=lambda _: None),
               'termios': SimpleNamespace(ICANON=termios.ICANON, ECHO=termios.ECHO,
                                         ECHONL=termios.ECHONL, tcgetattr=attributes)}
    with patch.dict(sys.modules, modules):
        program = ((VT6_GETTY_IDENTITY if getty else VT6_PASSWORD_IDENTITY) if identity_probe else
                   VT6_GETTY if getty else VT6_PASSWORD if vt else SERIAL_PASSWORD)
        if rejected:
            with pytest.raises(OSError if fault == 'active-read-error' else AssertionError):
                exec(program, {})
        else:
            exec(program, {})
    output = capsys.readouterr().out
    if identity_probe and not rejected:
        # The independently maintained boot observer must produce the same
        # digest, and exec from getty to login must retain recipient identity.
        with patch.dict(sys.modules, modules):
            exec(BOOT, {})
        boot = capsys.readouterr().out.strip()
        result = json.loads(output)
        assert result == {'probe': terminal, 'boot_sha256': boot,
            'recipient_sha256': hashlib.sha256(json.dumps(
                [boot, 'getty@tty6.service', 42, '123'], separators=(',', ':')).encode()).hexdigest()}
        assert output == json.dumps(result, sort_keys=True) + '\n'
    else:
        assert output == ('' if rejected else
            'vt6-getty-ready\n' if getty else terminal + '-password-safe\n')
    if 'open' in events:
        assert events[-1] == ('close', 77)
