"""Host-only checks of the scenario read-only capability and output boundary."""

import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT
import guest_observations
import installation_observations
from observation_transport import ReadOnlyObservations
from private_artifacts import EvidenceError


@pytest.fixture
def observer():
    transport = Mock(config={'run': 'a' * 32, 'domain_id': 7})
    return ReadOnlyObservations(transport), transport


def test_customer_reboot_requires_fresh_agreeing_boot_observation(observer):
    reader, transport = observer
    transport.call.side_effect = [b'a'*64 + b'\n', b'b'*64 + b'\n']
    before = reader.read('boot')['boot_sha256']
    transport.wait_boot_change.return_value = b'b'*64 + b'\n'
    assert reader.wait_boot_change(before) == {
        'previous_boot_sha256': 'a'*64, 'boot_sha256': 'b'*64, 'boot_changed': True}
    transport.wait_boot_change.assert_called_once_with(before, on_diagnostic=None)
    assert transport.call.call_count == 2
    transport.reboot.assert_not_called()
    transport.copy.assert_not_called()


@pytest.mark.parametrize('fault', ['unobserved', 'wrong-before', 'unchanged', 'second-reboot',
    'malformed', 'before-ownership', 'after-ownership', 'configuration', 'transport',
    'interrupt', 'final-read'])
def test_failed_reboot_observation_latches_all_reads_and_retries(observer, fault, capsys):
    reader, transport = observer
    transport.call.return_value = b'a'*64 + b'\n'
    if fault != 'unobserved':
        reader.read('boot')
    transport.reset_mock()
    transport.call.return_value = b'b'*64 + b'\n'
    transport.wait_boot_change.return_value = b'b'*64 + b'\n'
    before = 'c'*64 if fault == 'wrong-before' else 'a'*64
    private = RuntimeError('private-canary')
    if fault == 'unchanged':
        transport.wait_boot_change.return_value = b'a'*64 + b'\n'
    elif fault == 'second-reboot':
        transport.call.return_value = b'c'*64 + b'\n'
    elif fault == 'malformed':
        transport.wait_boot_change.return_value = b'private-canary'
    elif fault in ('before-ownership', 'after-ownership'):
        transport.guard.side_effect = ([private] if fault == 'before-ownership'
                                       else [None, private])
    elif fault == 'configuration':
        transport.config['domain_id'] = 8
    elif fault in ('transport', 'interrupt'):
        transport.wait_boot_change.side_effect = (KeyboardInterrupt('private-canary')
                                                  if fault == 'interrupt' else private)
    elif fault == 'final-read':
        transport.call.side_effect = private
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else EvidenceError) as caught:
        reader.wait_boot_change(before)
    assert 'private-canary' not in str(caught.value) + capsys.readouterr().err
    calls = list(transport.mock_calls)
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.wait_boot_change(before)
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('greeter')
    assert transport.mock_calls == calls
    if fault in ('unobserved', 'wrong-before', 'before-ownership', 'configuration'):
        transport.wait_boot_change.assert_not_called()


def test_customer_reboot_uses_real_readiness_loop_and_revalidates_final_boot(monkeypatch):
    from contextlib import nullcontext
    from vm_transport import Transport
    import vm_transport
    events = Mock()
    monkeypatch.setattr(vm_transport, 'readiness_events', lambda: nullcontext(events))
    commands = Mock(last_returncode=0)
    responses = iter([(0, b'a'*64 + b'\n'), (0, b'a'*64 + b'\n'),
                      (255, b'private-canary'), (0, b'b'*64 + b'\n'),
                      (0, b'b'*64 + b'\n')])
    def output(*args, **kwargs):
        commands.last_returncode, raw = next(responses)
        return raw
    commands.run.side_effect = output
    config = {'directory': '/tmp/onpc-reboot-test', 'hostname': 'example.invalid',
              'run': 'a'*32, 'domain_uuid': '00000000-0000-0000-0000-000000000001'}
    transport = Transport(config, commands, guard=Mock())
    reader = ReadOnlyObservations(transport)
    before = reader.read('boot')['boot_sha256']
    reports = []
    assert reader.wait_boot_change(before, on_diagnostic=reports.append)['boot_sha256'] == 'b'*64
    assert reports == [{'old_boot': 1, 'ssh_unavailable': 1, 'changed_boot': 1,
                        'outcome': 'changed-boot'}]
    assert commands.run.call_count == 5
    assert events.wait.call_count == 2


@pytest.mark.parametrize('name,program,timeout,result,raw', [
    ('boot', guest_observations.BOOT, 20, {'boot_sha256': 'a' * 64}, b'a' * 64 + b'\n'),
    ('package-absent', installation_observations.ABSENT, 30,
     {'product_package_absent': True, 'core_payload_absent': True,
      'product_reboot_required': False}, b'package-absent\n'),
    ('install-refused', installation_observations.REFUSED, 30,
     {'product_package_absent': True, 'core_payload_absent': True,
      'product_reboot_required': False, 'install_process_absent': True},
     b'install-refused-safe\n'),
    ('package-installed', installation_observations.INSTALLED, 90,
     {'package_sha256': 'a' * 64, 'installed_identity_verified': True,
      'product_reboot_required': True},
     (json.dumps({'package_sha256': 'a' * 64, 'installed_identity_verified': True,
                  'product_reboot_required': True}, sort_keys=True) + '\n').encode()),
    ('installed-layout', installation_observations.INSTALLED_LAYOUT, 90,
     {'installed_files': 12, 'inventory_sha256': 'a' * 64,
      'installed_layout_verified': True},
     (json.dumps({'installed_files': 12, 'inventory_sha256': 'a' * 64,
                  'installed_layout_verified': True}, sort_keys=True) + '\n').encode()),
    ('assets', guest_observations.ASSETS, 120, {'files': 3, 'sha256': 'a' * 64},
     (json.dumps({'files': 3, 'sha256': 'a' * 64}, sort_keys=True) + '\n').encode()),
    ('greeter', guest_observations.GREETER, 110,
     {'active_graphical_greeter': True, 'unexpected_user_session': False}, b'greeter-ready\n'),
    ('parent-session', guest_observations.PARENT_SESSION, 110,
     {'fixture_role': 'parent', 'active_local_graphical_session': True,
      'unexpected_user_session': False}, b'parent-session-ready\n'),
    ('serial-password', guest_observations.SERIAL_PASSWORD, 20,
     {'serial_login_process_verified': True,
      'terminal_echo_disabled': True}, b'serial-password-safe\n'),
    ('install-password', installation_observations.SUDO_PASSWORD, 20,
     {'sudo_install_process_verified': True,
      'terminal_echo_disabled': True}, b'install-password-safe\n'),
    ('reboot-password', installation_observations.REBOOT_PASSWORD, 20,
     {'sudo_reboot_process_verified': True,
      'terminal_echo_disabled': True}, b'reboot-password-safe\n'),
    ('sudo-implementation', installation_observations.SUDO_IMPLEMENTATION, 30,
     {'implementation': 'sudo-rs', 'package_version': '0.2.13-0ubuntu1.2',
      'executable': '/usr/lib/cargo/bin/sudo'},
     (json.dumps({'implementation': 'sudo-rs', 'package_version': '0.2.13-0ubuntu1.2',
                  'executable': '/usr/lib/cargo/bin/sudo'}, sort_keys=True) + '\n').encode()),
    ('serial-session', guest_observations.SERIAL_SESSION, 110,
     {'fixture_role': 'parent', 'active_local_serial_session': True,
      'unexpected_user_session': False}, b'serial-session-ready\n'),
])
def test_fixed_probe_checks_ownership_before_and_after_output(observer, name, program, timeout, result, raw):
    reader, transport = observer
    events = []
    transport.guard.side_effect = lambda _: events.append('guard')
    def call(*args, **kwargs):
        events.append('call')
        return raw
    transport.call.side_effect = call
    assert reader.read(name) == result
    assert events == ['guard', 'call', 'guard']
    transport.call.assert_called_once_with(['/usr/bin/python3', '-c', program], timeout=timeout)
    transport.reboot.assert_not_called()
    transport.copy.assert_not_called()


@pytest.mark.parametrize('fault', ['version', 'executable', 'implementation', 'extra', 'duplicate', 'trailing'])
def test_sudo_identity_output_rejects_private_and_noncanonical_data(observer, fault, capsys):
    reader, transport = observer
    data = {'implementation': 'sudo-rs', 'package_version': '0.2.13-0ubuntu1.2',
            'executable': '/usr/lib/cargo/bin/sudo'}
    if fault in ('version', 'executable', 'implementation'):
        data['package_version' if fault == 'version' else fault] = 'private-canary'
    elif fault == 'extra':
        data['private-canary'] = True
    raw = json.dumps(data, sort_keys=True) + '\n'
    if fault == 'duplicate':
        raw = raw.replace('{', '{"implementation": "private-canary", ', 1)
    if fault == 'trailing':
        raw += 'private-canary'
    transport.call.return_value = raw.encode()
    with pytest.raises(EvidenceError):
        reader.read('sudo-implementation')
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('sudo-implementation')
    assert 'private-canary' not in capsys.readouterr().err


@pytest.mark.parametrize('stage', installation_observations.SUDO_PASSWORD_STAGES)
def test_sudo_condition_is_collected_before_terminal_refusal(observer, stage, capsys):
    reader, transport = observer
    transport.call.return_value = ('install-password-rejected:' + stage + '\n').encode()
    with pytest.raises(EvidenceError, match='probe-failed'):
        reader.read('install-password')
    assert capsys.readouterr().err.splitlines() == [
        'e2e:install-password-rejected:' + stage, 'e2e:observation-rejected']
    assert transport.guard.call_count == 2
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('install-password')
    assert transport.call.call_count == 1


@pytest.mark.parametrize('raw', [
    b'install-password-rejected:private-secret-canary\n',
    b'install-password-rejected:sudo-command\nprivate-secret-canary',
    b'install-password-rejected:sudo-command',
    b'install-password-rejected:sudo-command\r\n',
    b'install-password-rejected:sudo-command\ninstall-password-safe\n',
])
def test_sudo_diagnostic_accepts_only_exact_fixed_conditions(observer, raw, capsys):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('install-password')
    assert capsys.readouterr().err == 'e2e:observation-rejected\n'


@pytest.mark.parametrize('action', ['install', 'reboot'])
def test_sudo_diagnostic_is_not_published_after_ownership_loss(observer, action, capsys):
    reader, transport = observer
    transport.call.return_value = (action + '-password-rejected:sudo-command\n').encode()
    transport.guard.side_effect = [None, RuntimeError('private-secret-canary')]
    with pytest.raises(EvidenceError, match='probe-failed'):
        reader.read(action + '-password')
    assert capsys.readouterr().err == 'e2e:observation-rejected\n'


@pytest.mark.parametrize('write_fails', [False, True])
@pytest.mark.parametrize('action', ['install', 'reboot'])
def test_sudo_refusal_checkpoint_precedes_failure_and_cannot_enable_retry(observer, write_fails, action):
    _, transport = observer
    events = []
    def save(condition):
        events.append(condition)
        if write_fails:
            raise OSError('private-secret-canary')
    reader = ReadOnlyObservations(transport, on_diagnostic=save)
    transport.call.return_value = (action + '-password-rejected:terminal-echo\n').encode()
    with pytest.raises(EvidenceError, match='probe-failed'):
        reader.read(action + '-password')
    assert events == ['terminal-echo']
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read(action + '-password')
    assert transport.call.call_count == 1


@pytest.mark.parametrize('raw', [b'install-password-safe\n',
    b'reboot-password-safe\nprivate-secret-canary', b'reboot-password-rejected:private-secret-canary\n',
    b'reboot-password-rejected:sudo-command\nreboot-password-safe\n'])
def test_reboot_proof_rejects_other_purpose_and_private_or_mixed_output(observer, raw, capsys):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('reboot-password')
    assert capsys.readouterr().err == 'e2e:observation-rejected\n'
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('reboot-password')


@pytest.mark.parametrize('phase', ['initial', 'recipient', 'continuity'])
@pytest.mark.parametrize('field,value', [
    (field, value) for field, values in installation_observations.LOGIN_RESOLUTION_FIELDS.items()
    for value in values
])
def test_resolution_diagnostic_fields_are_checkpointed_but_never_authorize_input(
        observer, phase, field, value, capsys):
    _, transport = observer
    fields = {key: values[0] for key, values in installation_observations.LOGIN_RESOLUTION_FIELDS.items()}
    fields[field] = value
    condition = 'getty-' + phase + '-exe-resolve' + ''.join(
        '-' + key + '-' + item for key, item in fields.items())
    events = []
    reader = ReadOnlyObservations(transport, on_diagnostic=events.append)
    transport.call.return_value = ('install-password-rejected:' + condition + '\n').encode()
    with pytest.raises(EvidenceError, match='probe-failed'):
        reader.read('install-password')
    assert events == [condition]
    assert capsys.readouterr().err.splitlines() == [
        'e2e:install-password-rejected:' + condition, 'e2e:observation-rejected']
    transport.call.return_value = b'install-password-safe\n'
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('install-password')
    assert transport.call.call_count == 1


@pytest.mark.parametrize('fault', ['private', 'extra', 'missing', 'reordered', 'newline', 'phase'])
def test_resolution_diagnostic_rejects_noncanonical_and_private_fields(observer, fault, capsys):
    reader, transport = observer
    fields = [key + '-' + values[0]
              for key, values in installation_observations.LOGIN_RESOLUTION_FIELDS.items()]
    if fault == 'private':
        fields[0] = 'error-private-secret-canary'
    elif fault == 'extra':
        fields.append('private-secret-canary')
    elif fault == 'missing':
        fields.pop()
    elif fault == 'reordered':
        fields.reverse()
    condition = ('getty-' + ('private-secret-canary' if fault == 'phase' else 'initial')
                 + '-exe-resolve-' + '-'.join(fields))
    transport.call.return_value = ('install-password-rejected:' + condition
                                  + ('\nprivate-secret-canary' if fault == 'newline' else '') + '\n').encode()
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('install-password')
    assert capsys.readouterr().err == 'e2e:observation-rejected\n'


@pytest.mark.parametrize('raw', [b'', b'A' * 64 + b'\n', b'a' * 63 + b'\n',
                                b'a' * 64, b'a' * 64 + b'\nprivate-canary'])
def test_boot_identity_rejects_malformed_or_private_output(observer, raw):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('boot')
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('boot')


def test_boot_probe_hashes_actual_kernel_identity(capsys):
    import hashlib
    exec(guest_observations.BOOT, {})
    actual = (Path('/proc/sys/kernel/random/boot_id').read_text()).encode()
    assert capsys.readouterr().out == hashlib.sha256(actual).hexdigest() + '\n'


@pytest.mark.parametrize('probe,raw', [
    ('install-password', b'serial-password-safe\n'),
    ('install-password', b'install-password-safe\nprivate-secret-canary'),
    ('package-absent', b'package-absent\nprivate-secret-canary'),
    ('package-absent', b'package-installed\n'),
    ('package-installed', b'{}'),
    ('package-installed', b'null'),
    ('package-installed', b'\xff'),
    ('installed-layout', b'{}'),
    ('installed-layout', b'null'),
    *[('installed-layout', (json.dumps(value, sort_keys=True) + '\n').encode())
      for value in [
          {'installed_files': 0, 'inventory_sha256': 'a' * 64,
           'installed_layout_verified': True},
          {'installed_files': 1, 'inventory_sha256': 'A' * 64,
           'installed_layout_verified': True},
          {'installed_files': 1, 'inventory_sha256': 'a' * 64,
           'installed_layout_verified': 1},
          {'installed_files': 1, 'inventory_sha256': 'a' * 64,
           'installed_layout_verified': True, 'private-secret-canary': True},
      ]],
    *[('package-installed', (json.dumps(value, sort_keys=True) + '\n').encode())
      for value in [
          {'package_sha256': 'A' * 64, 'installed_identity_verified': True,
           'product_reboot_required': True},
          {'package_sha256': 'a' * 64, 'installed_identity_verified': 1,
           'product_reboot_required': True},
          {'package_sha256': 'a' * 64, 'installed_identity_verified': True,
           'product_reboot_required': False},
          {'package_sha256': 'a' * 64, 'installed_identity_verified': True,
           'product_reboot_required': True, 'user': 'private-secret-canary'},
      ]],
])
def test_package_observation_rejects_unsafe_or_unproven_output(observer, probe, raw, capsys):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError) as caught:
        reader.read(probe)
    assert 'private-secret-canary' not in str(caught.value)
    assert 'private-secret-canary' not in capsys.readouterr().err
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('boot')
    assert transport.call.call_count == 1


@pytest.mark.parametrize('probe', ['reboot', 'checkpoint', 'restore', 'set-grant', 'install',
                                    'sh -c touch /tmp/secret-canary', '/etc/shadow', '', None, [], {}])
def test_unknown_and_state_writing_requests_never_reach_transport(observer, probe, capsys):
    reader, transport = observer
    with pytest.raises(EvidenceError, match='unknown-probe'):
        reader.read(probe)
    transport.guard.assert_not_called()
    transport.call.assert_not_called()
    assert 'secret-canary' not in capsys.readouterr().err
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('greeter')
    transport.call.assert_not_called()


@pytest.mark.parametrize('method', ['call', 'copy', 'reboot', 'provision', 'reset'])
def test_scenario_capability_has_no_mutation_or_command_entrypoint(observer, method):
    assert not hasattr(observer[0], method)


@pytest.mark.parametrize('boundary', ['before', 'after', 'command', 'interrupt', 'config-before', 'config-after'])
def test_failure_and_identity_replacement_latch_without_exporting_raw_errors(observer, boundary, capsys):
    reader, transport = observer
    transport.call.return_value = b'greeter-ready\n'
    error = RuntimeError('private-secret-canary')
    if boundary in ('before', 'after'):
        transport.guard.side_effect = [error] if boundary == 'before' else [None, error]
    elif boundary == 'command':
        transport.call.side_effect = error
    elif boundary == 'interrupt':
        transport.call.side_effect = KeyboardInterrupt('private-secret-canary')
    elif boundary == 'config-before':
        transport.config['domain_id'] = 8
    else:
        def replaced(*args, **kwargs):
            transport.config['domain_id'] = 8
            return b'greeter-ready\n'
        transport.call.side_effect = replaced
    with pytest.raises(KeyboardInterrupt if boundary == 'interrupt' else EvidenceError) as caught:
        reader.read('greeter')
    assert 'private-secret-canary' not in str(caught.value)
    assert 'private-secret-canary' not in capsys.readouterr().err
    assert transport.call.call_count == (0 if boundary in ('before', 'config-before') else 1)
    count = transport.call.call_count
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('greeter')
    assert transport.call.call_count == count


@pytest.mark.parametrize('raw', [b'', b'private-secret-canary', b'{}', b'null', b'[]', b'\xff',
    b'a' * 1025, b'{"files": 1, "files": 2, "sha256": "' + b'a' * 64 + b'"}\n',
    *[(json.dumps(value, sort_keys=True) + '\n').encode() for value in [
        {'files': True, 'sha256': 'a' * 64}, {'files': 0, 'sha256': 'a' * 64},
        {'files': 100001, 'sha256': 'a' * 64}, {'files': 1, 'sha256': 'A' * 64},
        {'files': 1, 'sha256': 'a' * 64, 'user': 'private-secret-canary'},
    ]],
])
def test_malformed_or_private_asset_outputs_are_not_returned(observer, raw, capsys):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError) as caught:
        reader.read('assets')
    assert 'private-secret-canary' not in str(caught.value)
    assert 'private-secret-canary' not in capsys.readouterr().err
    with pytest.raises(EvidenceError, match='previous-failure'):
        reader.read('assets')


@pytest.mark.parametrize('raw', [b'greeter-ready', b'greeter-ready\nprivate-secret-canary',
                               b'{"active_graphical_greeter": false}', 'greeter-ready\n'])
def test_greeter_requires_exact_safe_success(observer, raw):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('greeter')


@pytest.mark.parametrize('raw', [b'parent-session-ready', b'greeter-ready\n',
                               b'parent-session-ready\nprivate-canary', b'parent-session-not-ready\n'])
def test_authentication_requires_exact_safe_success(observer, raw):
    reader, transport = observer
    transport.call.return_value = raw
    with pytest.raises(EvidenceError, match='invalid-output'):
        reader.read('parent-session')


@pytest.mark.parametrize('serial', [False, True])
@pytest.mark.parametrize('fault', [None, 'wrong-user', 'inactive', 'remote', 'tty',
                                  'wrong-service', 'greeter', 'duplicate', 'other-session'])
def test_actual_guest_authentication_probe_rejects_wrong_sessions(fault, capsys, serial):
    from types import SimpleNamespace
    from unittest.mock import patch
    parent = dict(Class='user', Active='yes', Remote='no', Type='wayland',
                  Service='gdm-password', User='1234')
    if serial:
        parent.update(Type='tty', TTY='ttyS0', Service='login')
    fields = {'wrong-user': ('User', '9876'), 'inactive': ('Active', 'no'),
              'remote': ('Remote', 'yes'), 'tty': ('Type', 'tty'),
              'wrong-service': ('Service', 'sshd'), 'greeter': ('Class', 'greeter')}
    if serial:
        fields['tty'] = ('TTY', 'ttyS1')
    if fault in fields:
        key, value = fields[fault]
        parent[key] = value
    sessions = {'parent': parent, 'observer': dict(Class='user', Active='yes', Remote='yes',
                                                 Type='tty', Service='sshd', User='0')}
    if fault in ('duplicate', 'other-session'):
        sessions['extra'] = dict(parent, User='1234' if fault == 'duplicate' else '9876')
    clock = [0]
    def call(args, **kwargs):
        assert kwargs['check'] and 0 < kwargs['timeout'] <= 10
        assert args[:2] in (('loginctl', 'list-sessions'), ('loginctl', 'show-session'))
        output = ('\n'.join(sessions) if args[1] == 'list-sessions' else
                  '\n'.join(key + '=' + value for key, value in sessions[args[2]].items()))
        return SimpleNamespace(stdout=output)
    def account(name):
        assert name == 'onpc-parent-jamie'
        return SimpleNamespace(pw_uid=1234)
    modules = {'subprocess': SimpleNamespace(run=call), 'pwd': SimpleNamespace(getpwnam=account),
               'time': SimpleNamespace(monotonic=lambda: clock[0],
                                       sleep=lambda _: clock.__setitem__(0, 100))}
    with patch.dict(sys.modules, modules):
        if fault:
            with pytest.raises(SystemExit) as caught:
                exec(guest_observations.SERIAL_SESSION if serial else guest_observations.PARENT_SESSION, {})
            assert caught.value.code == 1
        else:
            exec(guest_observations.SERIAL_SESSION if serial else guest_observations.PARENT_SESSION, {})
    prefix = 'serial' if serial else 'parent'
    assert capsys.readouterr().out == prefix + ('-session-not-ready\n' if fault else '-session-ready\n')
