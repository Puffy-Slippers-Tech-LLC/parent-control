"""Host-only witness regressions; never execute the installed guest test here."""

import errno
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_enforcement as enforcement
sys.path.pop(0)


@pytest.mark.parametrize(('allowed', 'raw', 'code'), [
    (True, enforcement.IDENTITY + enforcement.READY, 0),
    (False, enforcement.IDENTITY + enforcement.DENIED, 77),
])
def test_launch_witness_requires_identity_payload_and_exit(monkeypatch, allowed, raw, code):
    commands = Mock(last_returncode=code)
    commands.run.return_value = raw
    monkeypatch.setattr(enforcement.guest, 'commands', commands)
    enforcement.observe_launch(1234, allowed)
    assert json.loads(commands.run.call_args.kwargs['input']) == {'uid': 1234}
    assert commands.run.call_args.kwargs['timeout'] == 30
    for bad_raw, bad_code in ((raw, 1), (raw + b'extra', code), (raw.replace(enforcement.IDENTITY, b''), code)):
        commands.run.return_value = bad_raw
        commands.last_returncode = bad_code
        with pytest.raises(enforcement.guest.GuestError, match='enforcement:expected-'):
            enforcement.observe_launch(1234, allowed)


def policy_rig(monkeypatch):
    original = json.dumps({'apps': {}, 'parent_control_enabled': False})
    state = {'current': original}
    records, launches, rules = [], [], []
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'sha', Mock(return_value='a' * 64))

    def call(uid, method, signature='()', args=()):
        assert uid == 1003
        if method == 'ListApplications':
            return [[[enforcement.DESKTOP_ID, '', '', '', [str(enforcement.TARGET)], []]]]
        if method == 'GetPreferences':
            return [original if args[0] == 1002 else state['current']]
        assert method == 'SetPreferences' and args[0] == 1001
        state['current'] = args[1]
        return [args[1]]

    monkeypatch.setattr(enforcement, 'call', call)
    monkeypatch.setattr(enforcement, 'observe_launch', lambda uid, allowed: launches.append((uid, allowed)))
    monkeypatch.setattr(enforcement, 'record_rules', lambda stage, uid, blocked, record: rules.append((stage, blocked)))
    return original, state, records, launches, rules


def test_native_scenario_checks_other_user_at_each_transition_and_restores(monkeypatch):
    original, state, records, launches, rules = policy_rig(monkeypatch)
    enforcement.native_policy_transition({'child': 1001, 'other': 1002, 'parent': 1003},
                                        lambda *item: records.append(item))
    assert launches == [(1001, True), (1002, True), (1001, False), (1002, True),
                        (1001, True), (1002, True)]
    assert rules == [('allowed', False), ('hard', True), ('restored', False)]
    assert state['current'] == original
    assert records[-1] == ('onpc.native.policy-restoration', 'passed')


@pytest.mark.parametrize('restoration_fails', [False, True])
def test_failed_denial_stops_expansion_and_preserves_failure(monkeypatch, restoration_fails):
    original, state, records, _, rules = policy_rig(monkeypatch)
    ordinary_call = enforcement.call
    failed = False

    def launch(uid, allowed):
        nonlocal failed
        if not allowed:
            failed = True
            raise enforcement.guest.GuestError('original-denial-failure')

    def call(uid, method, signature='()', args=()):
        if failed and restoration_fails and method == 'SetPreferences':
            raise enforcement.guest.GuestError('restore-failed')
        return ordinary_call(uid, method, signature, args)

    monkeypatch.setattr(enforcement, 'observe_launch', launch)
    monkeypatch.setattr(enforcement, 'call', call)
    with pytest.raises(enforcement.guest.GuestError, match='original-denial-failure'):
        enforcement.native_policy_transition({'child': 1001, 'other': 1002, 'parent': 1003},
                                            lambda *item: records.append(item))
    assert rules == [('allowed', False), ('hard', True)]
    assert records[-1] == ('onpc.native.policy-restoration', 'failed' if restoration_fails else 'passed')
    assert (state['current'] == original) != restoration_fails


@pytest.mark.parametrize('blocked', [False, True])
def test_rule_evidence_requires_both_source_and_compiled_state(monkeypatch, tmp_path, blocked):
    source, compiled = tmp_path / 'source', tmp_path / 'compiled'
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(enforcement, 'RULES', source)
    monkeypatch.setattr(enforcement, 'COMPILED_RULES', compiled)
    monkeypatch.setattr(enforcement.guest, 'commands', Mock(directory=private))
    line = f'deny_syslog perm=execute uid=1001 : path={enforcement.TARGET}\n'
    for path in (source, compiled):
        path.write_text(line if blocked else '# empty policy\n')
    record = Mock()
    enforcement.record_rules('hard', 1001, blocked, record)
    assert record.call_count == 2
    compiled.write_text('# empty policy\n' if blocked else line)
    with pytest.raises(enforcement.guest.GuestError, match='rule-state'):
        enforcement.record_rules('hard', 1001, blocked, record)
    assert (private / 'native-hard-compiled.txt').read_bytes() == compiled.read_bytes()


@pytest.mark.parametrize('number', [errno.EPERM, errno.EACCES, errno.ENOENT, errno.ENOEXEC])
def test_only_permission_errors_can_be_denial_witnesses(monkeypatch, capsys, number):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement, 'drop_identity', Mock())
    monkeypatch.setattr(enforcement.os, 'execv', Mock(side_effect=OSError(number, 'private detail')))
    if number in (errno.EPERM, errno.EACCES):
        assert enforcement.launch_as(1001) == 77
        assert capsys.readouterr().out.encode() == enforcement.IDENTITY + enforcement.DENIED
    else:
        with pytest.raises(enforcement.guest.GuestError, match='enforcement:exec-failed'):
            enforcement.launch_as(1001)
        assert capsys.readouterr().out.encode() == enforcement.IDENTITY


def test_provision_keeps_fixture_executable_through_private_umask(monkeypatch, tmp_path):
    payload = tmp_path / 'payload'
    source = payload / 'fixtures/native/onpc-test-application'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'deterministic fixture bytes')
    target, desktop = tmp_path / 'command/fixture', tmp_path / 'command.desktop'
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.guest, 'PAYLOAD', payload)
    monkeypatch.setattr(enforcement, 'TARGET', target)
    monkeypatch.setattr(enforcement, 'DESKTOP', desktop)
    accounts = iter((SimpleNamespace(pw_uid=1001), SimpleNamespace(pw_uid=1002),
                     SimpleNamespace(pw_uid=1003)))
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', lambda name: next(accounts))
    old_umask = os.umask(0o077)
    try:
        assert enforcement.provision_native() == {'child': 1001, 'other': 1002, 'parent': 1003}
    finally:
        os.umask(old_umask)
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o755
    assert target.parent.stat().st_mode & 0o777 == 0o755
    assert desktop.stat().st_mode & 0o777 == 0o644
    with pytest.raises(enforcement.guest.GuestError, match='fixture-collision'):
        enforcement.provision_native()
    assert target.read_bytes() == source.read_bytes()
