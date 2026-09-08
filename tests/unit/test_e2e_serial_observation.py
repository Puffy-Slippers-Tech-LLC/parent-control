"""Execute the real no-echo probe against explicit guest process fixtures."""

import os
from pathlib import Path
import stat
import sys
import termios
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from guest_observations import SERIAL_PASSWORD
sys.path.pop(0)


@pytest.mark.parametrize('fault', [None, 'pid', 'exe', 'autologin', 'device', 'stdin',
                                  'pgrp', 'session', 'tty', 'foreground', 'echo',
                                  'echonl', 'canonical', 'starttime'])
def test_guest_password_probe_refuses_wrong_process_or_echo(fault, capsys):
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
            return GuestPath('/usr/bin/sh' if fault == 'exe' else '/usr/bin/login')

        def read_bytes(self):
            assert self.value == '/proc/42/cmdline'
            return b'/bin/login\0' + (b'-f\0--\0' if fault == 'autologin' else b'--\0') + b'\0' * 18

        def read_text(self):
            assert self.value == '/proc/42/stat'
            counts['stat'] += 1
            fields = ['S', '1', '42', '42', str(os.makedev(4,64)), '42', *(['0'] * 46)]
            for name, index in [('pgrp', 2), ('session', 3), ('tty', 4), ('foreground', 5)]:
                if fault == name:
                    fields[index] = '999'
            fields[19] = '987' if fault == 'starttime' and counts['stat'] > 1 else '123'
            return '42 (login with spaces) ' + ' '.join(fields)

        def stat(self):
            assert self.value == '/proc/42/fd/0'
            return SimpleNamespace(st_rdev=0 if fault == 'stdin' else os.makedev(4,64))

    def command(args, **kwargs):
        assert args == ['systemctl', 'show', 'serial-getty@ttyS0.service', '--property=MainPID', '--value']
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=10)
        return SimpleNamespace(stdout='0' if fault == 'pid' else '42')

    def opened(path, flags):
        assert path == '/dev/ttyS0'
        assert flags == os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW
        events.append('open')
        return 77

    def attributes(fd):
        assert fd == 77
        flags = termios.ICANON
        if fault == 'echo':
            flags |= termios.ECHO
        elif fault == 'echonl':
            flags |= termios.ECHONL
        elif fault == 'canonical':
            flags = 0
        return [0,0,0,flags]

    fake_os = SimpleNamespace(makedev=os.makedev, O_RDONLY=os.O_RDONLY, O_NONBLOCK=os.O_NONBLOCK,
                              O_NOCTTY=os.O_NOCTTY, O_NOFOLLOW=os.O_NOFOLLOW, open=opened,
                              close=lambda fd: events.append(('close', fd)),
                              fstat=lambda fd: SimpleNamespace(st_mode=stat.S_IFCHR,
                                  st_rdev=0 if fault == 'device' else os.makedev(4,64)))
    modules = {'os': fake_os, 'pathlib': SimpleNamespace(Path=GuestPath),
               'subprocess': SimpleNamespace(run=command),
               'termios': SimpleNamespace(ICANON=termios.ICANON, ECHO=termios.ECHO,
                                         ECHONL=termios.ECHONL, tcgetattr=attributes)}
    with patch.dict(sys.modules, modules):
        if fault:
            with pytest.raises(AssertionError):
                exec(SERIAL_PASSWORD, {})
        else:
            exec(SERIAL_PASSWORD, {})
    assert capsys.readouterr().out == ('' if fault else 'serial-password-safe\n')
    if 'open' in events:
        assert events[-1] == ('close', 77)
