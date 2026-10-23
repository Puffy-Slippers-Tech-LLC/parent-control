"""Public UI/command doubles and private files; no live user manager/settings."""
import json
import shlex
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.modules import load_module
from tests.support.paths import ROOT


@pytest.fixture
def ordinary(tmp_path, monkeypatch):
    helper = load_module('private_installed_wellbeing', ROOT / 'tests/integration/system_wellbeing_qualification.py')
    account = SimpleNamespace(pw_uid=1002, pw_gid=1002, pw_dir='/private/home', pw_name=helper.ACCOUNT)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: account if name == helper.ACCOUNT else
                        SimpleNamespace(pw_uid=999))
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'wellbeing_probe.py').write_bytes(b'private-public-client')
    process = tmp_path / 'proc/200'
    process.mkdir(parents=True)
    settings = {'environment': {'DCONF_PROFILE': 'private-profile', 'XDG_CONFIG_HOME': '/private/config'},
                'process_environment': None,
                'service': {'ActiveState': 'active', 'InvocationID': 'b' * 32, 'MainPID': '200'}}
    class Proc:
        def __truediv__(self, name):
            return Proc() if str(name) == '200' else process / name
        def stat(self):
            return SimpleNamespace(st_uid=account.pw_uid)
    real_path = helper.Path
    monkeypatch.setattr(helper, 'Path', lambda value: Proc() if value == '/proc' else real_path(value))
    state = {'ActiveState': 'inactive', 'InvocationID': '0' * 32, 'MainPID': '0'}
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == 'systemctl' and argv[-1] == 'user@1002.service'
        if argv[1] == 'start':
            state.update(ActiveState='active', InvocationID='a' * 32, MainPID='100')
        elif argv[1] == 'stop':
            state.update(ActiveState='inactive', InvocationID='0' * 32, MainPID='0')
        else:
            assert argv[1] == 'show'
        return '\n'.join(key + '=' + value for key, value in state.items())
    monkeypatch.setattr(helper.guest, 'run', run)
    def user(argv, **kwargs):
        calls.append(argv)
        assert argv[:7] == ['/usr/bin/setpriv', '--reuid', '1002', '--regid', '1002', '--init-groups', '/usr/bin/env']
        command = argv[next(index for index, value in enumerate(argv)
                            if value in ('systemctl', '/usr/bin/python3')):]
        if command == ['systemctl', '--user', 'show-environment']:
            return '\n'.join(key + '=' + shlex.quote(value)
                             for key, value in settings['environment'].items()).encode()
        if command[:3] == ['systemctl', '--user', 'set-environment']:
            settings['environment'].update(assignment.split('=', 1) for assignment in command[3:])
            return b''
        if command == ['/usr/bin/python3', '-I', '-']:
            assert kwargs['input'] == b'private-public-client'
            assert all(key + '=' + value in argv for key, value in settings['environment'].items())
            return json.dumps({'original': 'default', 'backup_recorded': True,
                               'suppressed': True, 'restored': True}).encode()
        assert command[:2] == ['systemctl', '--user'] and command[-1] == helper.SERVICE
        service = settings['service']
        if command[2] == 'stop':
            service.update(ActiveState='inactive', MainPID='0')
            return b''
        if command[2] == 'start':
            if service['ActiveState'] == 'inactive':
                service.update(ActiveState='active', InvocationID='c' * 32, MainPID='200')
            actual = settings['process_environment']
            if actual is None:
                actual = settings['environment']
            (process / 'environ').write_bytes(b'\0'.join(
                (key + '=' + value).encode() for key, value in actual.items()) + b'\0')
            return b''
        assert command[2] == 'show'
        return '\n'.join(key + '=' + value for key, value in service.items()).encode()
    monkeypatch.setattr(helper.guest.commands, 'run', user)
    return helper, state, calls, process, settings


def test_existing_settings_overrides_are_never_replaced_with_defaults(ordinary):
    helper, state, calls, process, settings = ordinary
    settings['environment'] = {'DCONF_PROFILE': 'profile with spaces',
        'XDG_CONFIG_HOME': '/private/custom config', 'GSETTINGS_BACKEND': 'keyfile'}
    original = dict(settings['environment'])
    assert helper.qualify()['ordinary_settings_environment_retained'] is True
    assert settings['environment'] == original


def test_ordinary_environment_mismatch_fails_and_stops_only_owned_manager(ordinary):
    helper, state, calls, process, settings = ordinary
    settings['process_environment'] = {'DCONF_PROFILE': 'wrong-target'}
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:settings-target-mismatch'):
        helper.qualify()
    assert state['ActiveState'] == 'inactive'


def test_active_ordinary_manager_is_never_adopted_or_stopped(ordinary):
    helper, state, calls, process, settings = ordinary
    state['ActiveState'] = 'active'
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:manager-already-active'):
        helper.qualify()
    assert [call[1] for call in calls] == ['show']


def test_replaced_ordinary_manager_is_never_stopped(ordinary, monkeypatch):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.commands.run
    def replacement(argv, **options):
        result = run(argv, **options)
        if argv[-3:] == ['/usr/bin/python3', '-I', '-']:
            state['InvocationID'] = 'c' * 32
        return result
    monkeypatch.setattr(helper.guest.commands, 'run', replacement)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:manager-replaced'):
        helper.qualify()
    assert not any(call[:2] == ['systemctl', 'stop'] for call in calls)


@pytest.mark.parametrize('started', [False, True])
def test_failed_manager_start_cleans_only_a_new_recorded_invocation(ordinary, monkeypatch, started):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.run

    def failed_start(argv, **options):
        if argv[:2] == ['systemctl', 'start']:
            if started:
                run(argv, **options)
            raise helper.guest.GuestError('wellbeing-test:start-failed')
        return run(argv, **options)

    monkeypatch.setattr(helper.guest, 'run', failed_start)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-test:start-failed'):
        helper.qualify()
    assert state['ActiveState'] == 'inactive'
    assert any(call[:2] == ['systemctl', 'stop'] for call in calls) is started


@pytest.mark.parametrize('field,value,owned', [
    ('MainPID', '0', True), ('MainPID', 'invalid', True),
    ('InvocationID', 'invalid', False), ('InvocationID', '0' * 32, False),
])
def test_invalid_manager_readiness_stops_only_a_valid_new_invocation(ordinary, monkeypatch, field, value, owned):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.run

    def invalid_start(argv, **options):
        result = run(argv, **options)
        if argv[:2] == ['systemctl', 'start']:
            state[field] = value
        return result

    monkeypatch.setattr(helper.guest, 'run', invalid_start)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:manager-identity'):
        helper.qualify()
    assert any(call[:2] == ['systemctl', 'stop'] for call in calls) is owned


def test_owned_manager_state_change_during_failure_does_not_prevent_cleanup(ordinary, monkeypatch):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.commands.run

    def failed_probe(argv, **options):
        result = run(argv, **options)
        if argv[-3:] == ['/usr/bin/python3', '-I', '-']:
            state.update(ActiveState='failed', MainPID='0')
            raise helper.guest.GuestError('wellbeing-test:probe-failed')
        return result

    monkeypatch.setattr(helper.guest.commands, 'run', failed_probe)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-test:probe-failed'):
        helper.qualify()
    assert state['ActiveState'] == 'inactive'
    assert any(call[:2] == ['systemctl', 'stop'] for call in calls)


def test_replaced_service_is_never_stopped_or_given_new_environment(ordinary, monkeypatch):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.commands.run
    shown = 0

    def replacement(argv, **options):
        nonlocal shown
        if argv[-3:] == ['show', '--property=ActiveState,InvocationID,MainPID', helper.SERVICE]:
            shown += 1
            if shown == 2:
                settings['service']['InvocationID'] = 'd' * 32
        return run(argv, **options)

    monkeypatch.setattr(helper.guest.commands, 'run', replacement)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:service-replaced'):
        helper.qualify()
    assert not any('stop' in call and call[-1] == helper.SERVICE for call in calls)
    assert not any('set-environment' in call for call in calls)
    assert state['ActiveState'] == 'inactive'
