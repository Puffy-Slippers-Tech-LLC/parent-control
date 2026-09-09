"""Run the actual sudo proof with bounded guest process and terminal fixtures."""

import io
import os
import select
from pathlib import Path
import stat
import sys
import termios
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from installation_observations import SUDO_PASSWORD


@pytest.mark.parametrize('fault,stage', [
    (None, None), ('fixture', 'fixture-identity'), ('leader', 'getty-leader'),
    ('getty-session', 'getty-session'), ('getty-tty', 'getty-terminal'),
    ('getty-foreground', 'getty-terminal'), ('getty-exe', 'getty-initial-exe-mismatch'),
    ('getty-uid', 'getty-initial-credentials'), ('getty-owner', 'getty-initial-file-owner'),
    ('getty-writable', 'getty-initial-file-writable'),
    ('getty-changed-exe', 'getty-continuity-exe-mismatch'),
    ('no-child', 'getty-child'), ('many-children', 'getty-child'),
    ('child-self', 'getty-child'), ('child-read-error', 'getty-child'),
    ('parent-ancestry', 'parent-ancestry'), ('parent-pgrp', 'parent-session'),
    ('foreground', 'foreground-distinct'), ('session', 'foreground-session'),
    ('tty', 'foreground-session'), ('parent-session', 'parent-session'),
    ('parent-tty', 'parent-terminal'), ('parent-foreground', 'parent-foreground'),
    ('exe', 'sudo-executable'), ('shell', 'parent-executable'),
    ('sudo-uid', 'sudo-credentials'), ('parent-uid', 'parent-credentials'),
    ('command', 'sudo-command'), ('cached-auth', 'sudo-command'),
    ('old-prompt', 'sudo-command'), ('literal-prompt-escape', 'sudo-command'),
    ('stdin', 'sudo-stdin'), ('echo', 'terminal-echo-enabled-other'),
    ('echonl', None),
    ('echo-both', 'terminal-echo-enabled-other'),
    ('echo-stopped', 'terminal-echo-enabled-stopped'),
    ('echo-traced', 'terminal-echo-enabled-stopped'),
    ('echo-running', 'terminal-echo-enabled-running'),
    ('echo-drain', 'terminal-echo-enabled-terminal-drain'),
    ('echo-read', 'terminal-echo-enabled-terminal-read'),
    ('echo-poll', 'terminal-echo-enabled-poll'),
    ('echo-futex', 'terminal-echo-enabled-futex'),
    ('echo-woken', 'terminal-echo-enabled-wait-woken'),
    ('echo-wait-error', 'terminal-echo-enabled-unavailable-syscall-other-queue-empty'),
    ('echo-zero', 'terminal-echo-enabled-zero'),
    ('echo-syscall-running', 'terminal-echo-enabled-other-syscall-running-queue-empty'),
    ('echo-syscall-outside', 'terminal-echo-enabled-other-syscall-outside-queue-empty'),
    ('echo-syscall-drain', 'terminal-echo-enabled-other-syscall-ioctl-drain-queue-pending'),
    ('echo-syscall-flush', 'terminal-echo-enabled-other-syscall-ioctl-drain-queue-empty'),
    ('echo-syscall-other-tty', 'terminal-echo-enabled-other-syscall-ioctl-queue-empty'),
    ('echo-syscall-error', 'terminal-echo-enabled-other-syscall-unavailable-queue-empty'),
    ('echo-syscall-malformed', 'terminal-echo-enabled-other-syscall-unavailable-queue-empty'),
    ('echo-syscall-bad-fd', 'terminal-echo-enabled-other-syscall-unavailable-queue-empty'),
    ('echo-syscall-bad-request', 'terminal-echo-enabled-other-syscall-unavailable-queue-empty'),
    ('echo-syscall-compat', 'terminal-echo-enabled-other-syscall-unsupported-queue-empty'),
    ('echo-syscall-arch', 'terminal-echo-enabled-other-syscall-unsupported-queue-empty'),
    ('echo-syscall-header-error', 'terminal-echo-enabled-other-syscall-unavailable-queue-empty'),
    ('echo-queue-error', 'terminal-echo-enabled-other-syscall-other-queue-unavailable'),
    ('echo-queue-negative', 'terminal-echo-enabled-other-syscall-other-queue-unavailable'),
    ('echo-diagnostic-error-continuity', 'process-continuity'),
    ('echo-state-error', 'terminal-echo-enabled-unavailable'),
    ('echo-changed-command', 'sudo-command'),
    ('echo-changed-starttime', 'process-continuity'),
    ('parent-stdin', 'parent-stdin'), ('regular-stdin', 'sudo-stdin'),
    ('regular-parent-stdin', 'parent-stdin'),
    ('device', 'terminal-device'), ('regular-device', 'terminal-device'),
    ('binary-owner', 'sudo-binary'), ('binary-writable', 'sudo-binary'),
    ('starttime', 'process-continuity'), ('changed-command', 'sudo-command'),
    ('command-read-error', 'sudo-command'), ('open-error', 'terminal-open'),
    ('termios-error', 'terminal-attributes'), ('getty-error', 'getty-leader'),
    ('changed-child', 'process-continuity'), ('getty-starttime', 'process-continuity'),
    ('parent-starttime', 'process-continuity'), ('changed-ancestry', 'process-continuity'),
    ('getty-stat-error', 'getty-session'),
] + [('echo-syscall-' + call, 'terminal-echo-enabled-other-syscall-' + detail + '-queue-empty')
     for call, detail in (('read', 'read'), ('write', 'write'), ('poll', 'poll'),
                         ('ppoll', 'poll'), ('futex', 'futex'), ('ioctl', 'ioctl'))]
  + [(phase + ':' + fault, 'getty-' + phase + '-' + stage)
     for phase in ('initial', 'recipient', 'continuity')
     for fault, stage in (
         ('stat-error', 'file-stat'), ('file-type', 'file-type'),
         ('file-owner', 'file-owner'), ('file-group', 'file-owner'),
         ('file-writable', 'file-writable'), ('resolve-error', 'exe-resolve'),
         ('exe-mismatch', 'exe-mismatch'), ('credentials', 'credentials'))])
@pytest.mark.parametrize('newline_echo', [False, True])
def test_install_password_requires_exact_sudo_fixture_and_no_echo(fault, stage, newline_echo, capsys):
    if stage and stage.startswith('terminal-echo-enabled-') and '-syscall-' not in stage and fault != 'echo-state-error':
        stage += '-syscall-other-queue-empty'
    if stage and '-syscall-' in stage:
        stage += '-echo-' + ('both' if fault == 'echo-both' or newline_echo else 'characters')
    counts = {}
    events = []
    device = os.makedev(4, 64)

    def login_fault(name):
        phase = {1: 'initial', 2: 'recipient', 3: 'continuity'}.get(counts.get('login-stat'))
        return fault == str(phase) + ':' + name

    class GuestPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, value):
            return GuestPath(self.value + '/' + value)

        def __eq__(self, other):
            return isinstance(other, GuestPath) and self.value == other.value

        def open(self, mode):
            assert self.value == '/proc/44/exe' and mode == 'rb'
            if fault == 'echo-syscall-header-error':
                raise OSError('private-canary')
            return io.BytesIO(bytes([127, 69, 76, 70,
                1 if fault == 'echo-syscall-compat' else 2, 1]) + bytes(12) + bytes([62, 0]))

        def resolve(self, strict=False):
            assert strict
            resolved = {'/usr/bin/sudo': '/usr/bin/sudo.ws',
                        '/proc/42/exe': '/usr/bin/login',
                        '/proc/44/exe': '/usr/bin/sudo.ws',
                        '/proc/43/exe': '/usr/bin/bash'}[self.value]
            if self.value == '/proc/42/exe':
                counts['login-exe'] = counts.get('login-exe', 0) + 1
                if login_fault('resolve-error'):
                    raise PermissionError('private-canary')
                if (fault == 'getty-exe' or login_fault('exe-mismatch') or
                        fault == 'getty-changed-exe' and counts['login-exe'] > 2):
                    resolved = '/usr/bin/other'
            if (fault == 'exe' and self.value == '/proc/44/exe' or
                    fault == 'shell' and self.value == '/proc/43/exe'):
                resolved = '/usr/bin/other'
            return GuestPath(resolved)

        def read_bytes(self):
            assert self.value == '/proc/44/cmdline'
            if fault == 'command-read-error':
                raise FileNotFoundError('private-canary')
            counts['cmdline'] = counts.get('cmdline', 0) + 1
            args = [b'/usr/bin/sudo', b'-k', b'-p', b'\nONPC-INSTALL-PASSWORD: ', b'--',
                    b'/usr/bin/apt-get', b'install', b'-y',
                    b'/var/lib/onpc-e2e-assets/package.deb', b'']
            if fault == 'command' or fault in ('changed-command', 'echo-changed-command') and counts['cmdline'] > 1:
                args[-2] = b'/tmp/other.deb'
            if fault == 'cached-auth':
                args.remove(b'-k')
            if fault == 'old-prompt':
                args[3] = b'ONPC-INSTALL-PASSWORD: '
            if fault == 'literal-prompt-escape':
                args[3] = b'\\nONPC-INSTALL-PASSWORD: '
            return b'\0'.join(args)

        def read_text(self):
            pid = int(self.value.split('/')[2])
            assert pid in (42, 43, 44)
            if self.value.endswith('/syscall'):
                assert pid == 44
                events.append('syscall')
                if fault in ('echo-syscall-error', 'echo-diagnostic-error-continuity'):
                    raise PermissionError('private-canary')
                if fault == 'echo-syscall-running':
                    return 'running'
                if fault == 'echo-syscall-outside':
                    return '-1 0x123 0x456'
                if fault == 'echo-syscall-malformed':
                    return 'private-canary'
                if fault in ('echo-syscall-drain', 'echo-syscall-flush', 'echo-syscall-other-tty',
                             'echo-syscall-bad-fd', 'echo-syscall-bad-request'):
                    request = hex(termios.TCSETSF if fault == 'echo-syscall-flush' else termios.TCSETSW)
                    return '16 ' + ('private-canary' if fault == 'echo-syscall-bad-fd' else '0x8') + ' ' + (
                        'private-canary' if fault == 'echo-syscall-bad-request' else request) + ' 0x123 0 0 0 0x456 0x789'
                number = {'echo-syscall-read': 0, 'echo-syscall-write': 1,
                          'echo-syscall-poll': 7, 'echo-syscall-ppoll': 271,
                          'echo-syscall-futex': 202, 'echo-syscall-ioctl': 16}.get(fault, 999)
                return str(number) + ' 0 0 0 0 0 0 0x123 0x456'
            if self.value.endswith('/wchan'):
                assert pid == 44
                if fault == 'echo-wait-error':
                    raise OSError('private-canary')
                return {'echo-zero': '0', 'echo-drain': 'tty_wait_until_sent', 'echo-read': 'n_tty_read',
                        'echo-poll': 'do_poll', 'echo-futex': 'futex_wait_queue',
                        'echo-woken': 'wait_woken'}.get(fault, 'private-canary')
            if self.value == '/proc/42/task/42/children':
                counts['children'] = counts.get('children', 0) + 1
                if fault == 'child-read-error':
                    raise FileNotFoundError('private-canary')
                if fault == 'changed-child' and counts['children'] > 1:
                    return '45'
                return {'no-child': '', 'many-children': '43 45', 'child-self': '42'}.get(fault, '43 ')
            if self.value.endswith('/status'):
                ids = {42: [0]*4, 43: [1001]*4, 44: [1001, 0, 0, 0]}[pid]
                if (fault == {42: 'getty-uid', 43: 'parent-uid', 44: 'sudo-uid'}[pid] or
                        pid == 42 and login_fault('credentials')):
                    ids[0] = 999
                return 'Name:\tprivate-canary\nUid:\t' + '\t'.join(map(str, ids)) + '\n'
            assert self.value.endswith('/stat')
            counts[pid] = counts.get(pid, 0) + 1
            if fault == 'getty-stat-error' and pid == 42:
                raise FileNotFoundError('private-canary')
            fields = ['S', str(pid-1), str(pid), '43', str(device), '44', *(['0'] * 20)]
            fields[19] = '123'
            if pid == 44:
                if fault == 'echo-state-error' and counts[pid] > 2:
                    raise OSError('private-canary')
                fields[0] = {'echo-stopped': 'T', 'echo-traced': 't',
                             'echo-running': 'R'}.get(fault, 'S')
                if fault in ('echo-changed-starttime', 'echo-diagnostic-error-continuity') and counts[pid] > 3:
                    fields[19] = '987'
                for name, index in [('session', 3), ('tty', 4)]:
                    if fault == name:
                        fields[index] = '999'
                if fault == 'starttime' and counts[pid] > 2:
                    fields[19] = '987'
                if fault == 'parent-foreground':
                    fields[1] = '999'
            if pid == 42:
                fields[3:6] = ['42', '0', '-1']
                for name, index in [('getty-session', 3), ('getty-tty', 4), ('getty-foreground', 5)]:
                    if fault == name:
                        fields[index] = '999'
            if pid == 43:
                if fault == 'foreground':
                    fields[5] = '43'
                for name, index in [('parent-session', 3), ('parent-tty', 4),
                                    ('parent-ancestry', 1), ('parent-pgrp', 2)]:
                    if fault == name:
                        fields[index] = '999'
                if fault == 'changed-ancestry' and counts[pid] > 1:
                    fields[1] = '999'
            if fault == {42: 'getty-starttime', 43: 'parent-starttime', 44: 'starttime'}[pid] and counts[pid] > 2:
                fields[19] = '987'
            return str(pid) + ' (private process name) ' + ' '.join(fields)

        def stat(self):
            if self.value == '/proc/44/fd/8':
                return SimpleNamespace(st_mode=stat.S_IFCHR,
                    st_rdev=0 if fault == 'echo-syscall-other-tty' else device)
            if self.value == '/usr/bin/login':
                counts['login-stat'] = counts.get('login-stat', 0) + 1
                if login_fault('stat-error'):
                    raise FileNotFoundError('private-canary')
                kind = stat.S_IFDIR if login_fault('file-type') else stat.S_IFREG
                mode = 0o777 if fault == 'getty-writable' or login_fault('file-writable') else 0o755
                return SimpleNamespace(st_mode=kind | mode,
                    st_uid=1 if fault == 'getty-owner' or login_fault('file-owner') else 0,
                    st_gid=1 if login_fault('file-group') else 0)
            if self.value == '/usr/bin/sudo.ws':
                return SimpleNamespace(st_mode=stat.S_IFREG | (0o777 if fault == 'binary-writable' else 0o755),
                                       st_uid=1 if fault == 'binary-owner' else 0, st_gid=0)
            assert self.value in ('/proc/43/fd/0', '/proc/44/fd/0')
            parent = self.value == '/proc/43/fd/0'
            return SimpleNamespace(
                st_mode=stat.S_IFREG if fault == ('regular-parent-stdin' if parent else 'regular-stdin') else stat.S_IFCHR,
                st_rdev=0 if fault == ('parent-stdin' if parent else 'stdin') else device)

    def command(args, **kwargs):
        assert args == ['systemctl', 'show', 'serial-getty@ttyS0.service', '--property=MainPID', '--value']
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=10)
        if fault == 'getty-error':
            raise RuntimeError('private-canary')
        return SimpleNamespace(stdout='0' if fault == 'leader' else '42')

    def opened(path, flags):
        assert path == '/dev/ttyS0'
        assert flags == os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW
        if fault == 'open-error':
            raise OSError('private-canary')
        events.append('open')
        return 77

    def attributes(fd):
        if fault == 'termios-error':
            raise OSError('private-canary')
        if fault and fault.startswith('echo-'):
            flags = termios.ECHO | (termios.ECHONL if fault == 'echo-both' else 0)
        else:
            flags = {'echo': termios.ECHO, 'echonl': termios.ECHONL}.get(fault, 0)
        return [0, 0, 0, flags | (termios.ECHONL if newline_echo else 0)]

    def ioctl(fd, request, count, mutate):
        assert fd == 77 and request == termios.TIOCOUTQ and mutate is True
        assert count.typecode == 'i' and count.tolist() == [0]
        events.append('queue')
        if fault == 'echo-queue-error':
            raise OSError('private-canary')
        count[0] = -1 if fault == 'echo-queue-negative' else 7 if fault == 'echo-syscall-drain' else 0
        return 0

    fake_os = SimpleNamespace(makedev=os.makedev, O_RDONLY=os.O_RDONLY, O_NONBLOCK=os.O_NONBLOCK,
        O_NOCTTY=os.O_NOCTTY, O_NOFOLLOW=os.O_NOFOLLOW, open=opened,
        uname=lambda: SimpleNamespace(machine='aarch64' if fault == 'echo-syscall-arch' else 'x86_64'),
        close=lambda fd: events.append(('close', fd)), fstat=lambda fd: SimpleNamespace(
            st_mode=stat.S_IFREG if fault == 'regular-device' else stat.S_IFCHR,
            st_rdev=0 if fault == 'device' else device))
    modules = {'os': fake_os, 'pathlib': SimpleNamespace(Path=GuestPath),
        'fcntl': SimpleNamespace(ioctl=ioctl),
        'pwd': SimpleNamespace(getpwnam=lambda name: SimpleNamespace(pw_uid=0 if fault == 'fixture' else 1001)),
        'subprocess': SimpleNamespace(run=command),
        'termios': SimpleNamespace(ECHO=termios.ECHO, ECHONL=termios.ECHONL,
            TIOCOUTQ=termios.TIOCOUTQ, TCSETSW=termios.TCSETSW, TCSETSF=termios.TCSETSF,
            tcgetattr=attributes)}
    with patch.dict(sys.modules, modules):
        exec(SUDO_PASSWORD, {})
    captured = capsys.readouterr()
    assert captured.out == ('install-password-rejected:' + stage + '\n'
                            if stage else 'install-password-safe\n')
    assert not captured.err
    if stage is None:
        assert 'syscall' not in events and 'queue' not in events
    elif stage and '-syscall-' in stage:
        assert 'syscall' in events and 'queue' in events
    if 'open' in events:
        assert events[-1] == ('close', 77)


@pytest.mark.parametrize('canonical', [False, True])
@pytest.mark.parametrize('character_echo', [False, True])
def test_kernel_newline_echo_does_not_echo_password_characters(canonical, character_echo):
    master, slave = os.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        attrs[3] |= termios.ECHONL
        if canonical:
            attrs[3] |= termios.ICANON
        if character_echo:
            attrs[3] |= termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        os.write(master, b'synthetic-password\n')
        echoed = b''
        while select.select([master], [], [], 0.05)[0]:
            echoed += os.read(master, 4096)
        assert (b'synthetic-password' in echoed) == character_echo
        if not character_echo:
            assert echoed in (b'', b'\r\n', b'\n')
    finally:
        os.close(slave)
        os.close(master)
