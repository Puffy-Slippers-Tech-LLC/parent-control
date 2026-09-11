"""Advisory prompt timing evidence cannot become an input proof."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from guest_observations import VT6_LOGIN_DIAGNOSTIC
from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError


@pytest.mark.parametrize('executable', ['login', 'agetty', 'private-canary'])
@pytest.mark.parametrize('config', ['LOGIN_TIMEOUT 60\n', '# LOGIN_TIMEOUT 2\n',
                                   'LOGIN_TIMEOUT private-canary\n',
                                   'LOGIN_TIMEOUT 60\nLOGIN_TIMEOUT 90\n'])
def test_actual_diagnostic_exports_only_selected_recipient_and_numeric_configuration(capsys, executable, config):
    class GuestPath:
        def __init__(self, value):
            self.value = value
        def __truediv__(self, part):
            return GuestPath(self.value + '/' + part)
        def __hash__(self):
            return hash(self.value)
        def __eq__(self, other):
            return self.value == other.value
        def resolve(self):
            assert self.value == '/proc/42/exe'
            return GuestPath('/usr/sbin/agetty' if executable == 'agetty' else '/usr/bin/' + executable)
        def read_text(self):
            if self.value == '/proc/42/stat':
                return '42 (private-canary) ' + ' '.join(['0'] * 19 + ['123'])
            return {'/sys/class/tty/tty0/active': 'tty6\n', '/etc/login.defs': config,
                    '/proc/sys/kernel/random/boot_id': 'a0000000-0000-0000-0000-000000000001\n'}[self.value]
    def run(args, **kwargs):
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=10)
        if args == ['/usr/bin/login', '--version']:
            return SimpleNamespace(stdout='login from util-linux 2.41.3\n')
        assert args == ['systemctl', 'show', 'getty@tty6.service', '--property=MainPID', '--value']
        return SimpleNamespace(stdout='42\n')
    with patch('pathlib.Path', GuestPath), patch('subprocess.run', run):
        if 'private-canary' in config or config.count('LOGIN_TIMEOUT') > 1:
            with pytest.raises(AssertionError):
                exec(VT6_LOGIN_DIAGNOSTIC, {})
            assert not capsys.readouterr().out
            return
        exec(VT6_LOGIN_DIAGNOSTIC, {})
    raw = capsys.readouterr().out
    result = json.loads(raw)
    assert 'private-canary' not in raw
    assert result['executable'] == ('other' if executable == 'private-canary' else executable)
    assert result['login_timeout_seconds'] == 60
    boot = hashlib.sha256(b'a0000000-0000-0000-0000-000000000001\n').hexdigest()
    assert result['recipient_sha256'] == hashlib.sha256(
        json.dumps([boot, 'getty@tty6.service', 42, '123'], separators=(',', ':')).encode()).hexdigest()


@pytest.mark.parametrize('fault', [None, 'private-field', 'private-exe', 'bool-timeout',
                                  'duplicate', 'transport', 'late-owner'])
def test_diagnostic_parser_is_private_guarded_and_cannot_advance_recipient(fault, capsys):
    transport = Mock(config={'run': 'fixture'})
    reader = ReadOnlyObservations(transport)
    transport.call.return_value = b'c' * 64 + b'\n'
    reader.read('boot')
    transport.call.return_value = (json.dumps({'probe': 'vt6-getty-identity',
        'boot_sha256': 'c' * 64, 'recipient_sha256': 'a' * 64}, sort_keys=True) + '\n').encode()
    reader.read('vt6-getty-identity')
    transport.reset_mock()
    result = {'executable': 'agetty', 'login_timeout_seconds': 60,
              'timeout_source': 'login.defs', 'login_version': '2.41.3',
              'recipient_sha256': 'b' * 64}
    if fault == 'private-field':
        result['private-canary'] = 'private-canary'
    if fault == 'private-exe':
        result['executable'] = 'private-canary'
    if fault == 'bool-timeout':
        result['login_timeout_seconds'] = True
    raw = (json.dumps(result, sort_keys=True) + '\n').encode()
    if fault == 'duplicate':
        raw = raw.replace(b'{', b'{"executable":"private-canary",')
    transport.call.return_value = raw
    if fault == 'transport':
        transport.call.side_effect = RuntimeError('private-canary')
    if fault == 'late-owner':
        transport.guard.side_effect = [None, RuntimeError('private-canary')]
    if fault:
        with pytest.raises(EvidenceError):
            reader.read('vt6-login-diagnostic')
        with pytest.raises(EvidenceError, match='previous-failure'):
            reader.read('vt6-getty-identity')
    else:
        accepted = reader.read('vt6-login-diagnostic')
        assert accepted == {k: v for k, v in result.items() if k != 'recipient_sha256'} | {
            'matches_pinned_recipient': False}
        transport.call.assert_called_once_with(['/usr/bin/python3', '-c', VT6_LOGIN_DIAGNOSTIC], timeout=30)
        assert transport.guard.call_count == 2
    assert reader._vt6_recipient_stage == 1 and reader._vt6_recipient == ('c' * 64, 'a' * 64)
    assert 'private-canary' not in capsys.readouterr().err


@pytest.mark.parametrize('same_recipient', [False, True])
def test_diagnostic_compares_digest_with_recipient_pinned_by_real_reader(same_recipient):
    transport = Mock(config={'run': 'fixture'})
    reader = ReadOnlyObservations(transport)
    transport.call.return_value = b'c' * 64 + b'\n'
    reader.read('boot')
    transport.call.return_value = (json.dumps({'probe': 'vt6-getty-identity',
        'boot_sha256': 'c' * 64, 'recipient_sha256': 'a' * 64}, sort_keys=True) + '\n').encode()
    reader.read('vt6-getty-identity')
    transport.call.return_value = (json.dumps({'executable': 'login', 'login_timeout_seconds': 60,
        'timeout_source': 'login.defs', 'login_version': '2.41.3',
        'recipient_sha256': ('a' if same_recipient else 'b') * 64}, sort_keys=True) + '\n').encode()
    assert reader.read('vt6-login-diagnostic')['matches_pinned_recipient'] is same_recipient
    assert reader._vt6_recipient_stage == 1
