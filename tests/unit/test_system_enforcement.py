"""Host-only witness regressions; never execute the installed guest test here."""

import errno
import hashlib
import io
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
@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_launch_witness_requires_identity_payload_and_exit(monkeypatch, allowed, raw, code, variant):
    commands = Mock(last_returncode=code)
    commands.run.return_value = raw
    monkeypatch.setattr(enforcement.guest, 'commands', commands)
    enforcement.observe_launch(1234, allowed, variant=variant)
    assert json.loads(commands.run.call_args.kwargs['input']) == {'uid': 1234, 'variant': variant}
    assert commands.run.call_args.kwargs['timeout'] == 30
    for bad_raw, bad_code in ((raw, 1), (raw + b'extra', code), (raw.replace(enforcement.IDENTITY, b''), code)):
        commands.run.return_value = bad_raw
        commands.last_returncode = bad_code
        with pytest.raises(enforcement.guest.GuestError, match='enforcement:expected-'):
            enforcement.observe_launch(1234, allowed, variant=variant)


def policy_rig(monkeypatch, variant='command'):
    target, _, desktop_id = enforcement.native_paths(variant)
    original = json.dumps({'apps': {}, 'parent_control_enabled': False,
                           'daily_time_limit_minutes': 45})
    state = {'current': original, 'saved': [], 'toggles': []}
    records, launches, rules = [], [], []
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'sha', Mock(return_value='a' * 64))

    def call(uid, method, signature='()', args=()):
        assert uid == 1003
        if method == 'ListApplications':
            return [[[desktop_id, '', '', '', [str(target)], []]]]
        if method == 'GetPreferences':
            return [original if args[0] == 1002 else state['current']]
        if method == 'SetParentControl':
            assert signature == '(ubu)' and args[0] == 1001
            saved = json.loads(state['current'])
            saved['parent_control_enabled'] = args[1]
            saved['daily_time_limit_minutes'] = args[2]
            state['current'] = json.dumps(saved)
            state['toggles'].append(args[1:])
            return [state['current']]
        assert method == 'SetPreferences' and args[0] == 1001
        saved = json.loads(args[1])
        # Match the public broker contract: preference saves cannot toggle.
        saved['parent_control_enabled'] = json.loads(state['current'])['parent_control_enabled']
        state['current'] = json.dumps(saved)
        state['saved'].append(saved)
        return [state['current']]

    monkeypatch.setattr(enforcement, 'call', call)
    def launch(uid, allowed, **kwargs):
        assert kwargs == {'variant': variant}
        launches.append((uid, allowed))

    def record_rules(stage, uid, blocked, record, **kwargs):
        assert kwargs == {'variant': variant}
        rules.append((stage, blocked))

    monkeypatch.setattr(enforcement, 'observe_launch', launch)
    monkeypatch.setattr(enforcement, 'record_rules', record_rules)
    return original, state, records, launches, rules


@pytest.mark.parametrize('variant', ['command', 'whitespace'])
def test_native_scenario_checks_other_user_at_each_transition_and_restores(monkeypatch, variant):
    target, _, desktop_id = enforcement.native_paths(variant)
    original, state, records, launches, rules = policy_rig(monkeypatch, variant)
    enforcement.native_policy_transition({'child': 1001, 'other': 1002, 'parent': 1003},
                                        lambda *item: records.append(item), variant=variant)
    assert launches == [(1001, True), (1002, True), (1001, False), (1002, True),
                        (1001, True), (1002, True), (1001, False), (1002, True),
                        (1001, True), (1002, True)] * 2
    assert rules == [('allowed', False), ('hard', True), ('restored', False),
                     ('soft', True), ('soft-restored', False),
                     ('enabled-allowed', False), ('enabled-hard', True),
                     ('enabled-restored', False), ('enabled-soft', True),
                     ('enabled-soft-restored', False)]
    assert [item['parent_control_enabled'] for item in state['saved']] == [False] * 5 + [True] * 5 + [False]
    assert state['toggles'] == [(True, 45), (False, 45)]
    assert [item['apps'].get(desktop_id, {}).get('state')
            for item in state['saved']] == [None, 'permanent', None, 'conditional', None] * 2 + [None]
    assert all(item['apps'][desktop_id]['targets'] == [str(target)]
               for item in state['saved'] if item['apps'])
    assert (f'onpc.native.{variant}.fixture.sha256', 'a' * 64) in records
    assert (f'onpc.native.{variant}.soft.child', 'denied') in records
    assert (f'onpc.native.{variant}.soft.other', 'allowed') in records
    assert (f'onpc.native.{variant}.enabled-soft.child', 'denied') in records
    assert (f'onpc.native.{variant}.enabled-soft.other', 'allowed') in records
    assert state['current'] == original
    assert records[-1] == (f'onpc.native.{variant}.policy-restoration', 'passed')


@pytest.mark.parametrize('restoration_fails', [False, True])
@pytest.mark.parametrize('denial_state', ['permanent', 'conditional'])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('variant', ['command', 'whitespace'])
def test_failed_denial_stops_expansion_and_preserves_failure(
        monkeypatch, restoration_fails, denial_state, enabled, variant):
    _, _, desktop_id = enforcement.native_paths(variant)
    original, state, records, _, rules = policy_rig(monkeypatch, variant)
    ordinary_call = enforcement.call
    failed = False

    def launch(uid, allowed, **kwargs):
        assert kwargs == {'variant': variant}
        nonlocal failed
        current = json.loads(state['current'])
        if (not allowed and current['parent_control_enabled'] is enabled and
                current['apps'][desktop_id]['state'] == denial_state):
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
                                            lambda *item: records.append(item), variant=variant)
    prefix = 'enabled-' if enabled else ''
    assert rules[-1] == (prefix + ('hard' if denial_state == 'permanent' else 'soft'), True)
    assert (f'onpc.native.{variant}.{prefix}soft-restored.child', 'allowed') not in records
    assert records[-1] == (f'onpc.native.{variant}.policy-restoration', 'failed' if restoration_fails else 'passed')
    assert (state['current'] == original) != restoration_fails


@pytest.mark.parametrize('fault', ['screen-time-mismatch', 'hard-substitution',
                                 'rules-missing', 'other-launch-denied', 'other-policy-changed'])
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('variant', ['command', 'whitespace'])
def test_soft_policy_faults_fail_and_restore(monkeypatch, fault, enabled, variant):
    _, _, desktop_id = enforcement.native_paths(variant)
    original, state, records, launches, rules = policy_rig(monkeypatch, variant)
    ordinary_call, ordinary_rules = enforcement.call, enforcement.record_rules

    def soft_active():
        current = json.loads(state['current'])
        return (current['parent_control_enabled'] is enabled and
                current['apps'].get(desktop_id, {}).get('state') == 'conditional')

    def call(uid, method, signature='()', args=()):
        reply = ordinary_call(uid, method, signature, args)
        if method == 'GetPreferences' and soft_active():
            saved = json.loads(reply[0])
            if args == (1001,) and fault == 'screen-time-mismatch':
                saved['parent_control_enabled'] = not enabled
            elif args == (1001,) and fault == 'hard-substitution':
                saved['apps'][desktop_id]['state'] = 'permanent'
            elif args == (1002,) and fault == 'other-policy-changed':
                saved['apps'] = json.loads(state['current'])['apps']
            return [json.dumps(saved)]
        return reply

    def record_rules(stage, uid, blocked, record, **kwargs):
        ordinary_rules(stage, uid, blocked, record, **kwargs)
        if stage == ('enabled-soft' if enabled else 'soft') and fault == 'rules-missing':
            raise enforcement.guest.GuestError('enforcement:rule-state')

    def launch(uid, allowed, **kwargs):
        launches.append((uid, allowed))
        if soft_active() and uid == 1002 and fault == 'other-launch-denied':
            raise enforcement.guest.GuestError('enforcement:expected-allow')

    monkeypatch.setattr(enforcement, 'call', call)
    monkeypatch.setattr(enforcement, 'record_rules', record_rules)
    monkeypatch.setattr(enforcement, 'observe_launch', launch)
    expected = {'screen-time-mismatch': 'policy-readback', 'hard-substitution': 'policy-readback',
                'rules-missing': 'rule-state', 'other-launch-denied': 'expected-allow',
                'other-policy-changed': 'other-preferences-changed'}[fault]
    with pytest.raises(enforcement.guest.GuestError, match=expected):
        enforcement.native_policy_transition({'child': 1001, 'other': 1002, 'parent': 1003},
                                            lambda *item: records.append(item), variant=variant)
    assert state['current'] == original
    assert records[-1] == (f'onpc.native.{variant}.policy-restoration', 'passed')
    assert ('enabled-soft-restored' if enabled else 'soft-restored', False) not in rules
    if fault in ('screen-time-mismatch', 'hard-substitution', 'rules-missing'):
        assert launches[-6:] == [(1001, True), (1002, True), (1001, False), (1002, True),
                                (1001, True), (1002, True)]


@pytest.mark.parametrize('fault', ['rejected', 'reply-lost', 'not-applied',
                                 'limit-changed', 'apps-changed'])
def test_screen_time_enable_failure_stops_launches_and_restores(monkeypatch, fault):
    original, state, records, launches, rules = policy_rig(monkeypatch)
    ordinary_call = enforcement.call

    def call(uid, method, signature='()', args=()):
        if method == 'SetParentControl' and args[1] is True:
            if fault == 'rejected':
                raise enforcement.guest.GuestError('enable-rejected')
            reply = ordinary_call(uid, method, signature, args)
            if fault == 'reply-lost':
                raise enforcement.guest.GuestError('enable-reply-lost')
            saved = json.loads(state['current'])
            if fault == 'not-applied':
                saved['parent_control_enabled'] = False
            elif fault == 'limit-changed':
                saved['daily_time_limit_minutes'] += 1
            elif fault == 'apps-changed':
                saved['apps'] = {'unexpected': {}}
            state['current'] = json.dumps(saved)
            return reply
        return ordinary_call(uid, method, signature, args)

    monkeypatch.setattr(enforcement, 'call', call)
    expected = 'enable-' if fault in ('rejected', 'reply-lost') else 'screen-time-readback'
    with pytest.raises(enforcement.guest.GuestError, match=expected):
        enforcement.native_policy_transition({'child': 1001, 'other': 1002, 'parent': 1003},
                                            lambda *item: records.append(item))
    assert len(launches) == 10
    assert rules[-1] == ('soft-restored', False)
    assert state['toggles'][-1] == (False, 45)
    assert state['current'] == original
    assert records[-1] == ('onpc.native.command.policy-restoration', 'passed')


@pytest.mark.parametrize('original_failure', [False, True])
@pytest.mark.parametrize('fault', ['disable-rejected', 'disable-not-applied',
                                 'preferences-rejected', 'other-changed'])
def test_restoration_failures_fail_success_or_preserve_original(monkeypatch, fault, original_failure):
    original, state, records, _, _ = policy_rig(monkeypatch)
    ordinary_call = enforcement.call
    restoring = False
    preference_restore_attempted = False

    def call(uid, method, signature='()', args=()):
        nonlocal restoring, preference_restore_attempted
        if method == 'SetParentControl' and args[1] is False:
            restoring = True
            if fault == 'disable-rejected':
                raise enforcement.guest.GuestError('disable-rejected')
            if fault == 'disable-not-applied':
                return [state['current']]
        if restoring and method == 'SetPreferences':
            preference_restore_attempted = True
            assert args[1] == original
            if fault == 'preferences-rejected':
                raise enforcement.guest.GuestError('preferences-rejected')
        reply = ordinary_call(uid, method, signature, args)
        if restoring and method == 'GetPreferences' and args == (1002,) and fault == 'other-changed':
            saved = json.loads(reply[0])
            saved['parent_control_enabled'] = True
            return [json.dumps(saved)]
        return reply

    def launch(uid, allowed, **kwargs):
        if original_failure and json.loads(state['current'])['parent_control_enabled'] and not allowed:
            raise enforcement.guest.GuestError('original-launch-failure')

    monkeypatch.setattr(enforcement, 'call', call)
    monkeypatch.setattr(enforcement, 'observe_launch', launch)
    expected = ('original-launch-failure' if original_failure else {
        'disable-rejected': 'disable-rejected', 'disable-not-applied': 'policy-restore-mismatch',
        'preferences-rejected': 'preferences-rejected', 'other-changed': 'other-preferences-changed'}[fault])
    with pytest.raises(enforcement.guest.GuestError, match=expected):
        enforcement.native_policy_transition({'child': 1001, 'other': 1002, 'parent': 1003},
                                            lambda *item: records.append(item))
    assert preference_restore_attempted
    assert records[-1] == ('onpc.native.command.policy-restoration', 'failed')
    if fault in ('disable-rejected', 'disable-not-applied'):
        saved = json.loads(state['current'])
        assert saved['apps'] == {} and saved['parent_control_enabled'] is True


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
    assert (private / 'native-command-hard-compiled.txt').read_bytes() == compiled.read_bytes()


@pytest.mark.parametrize('number', [errno.EPERM, errno.EACCES, errno.ENOENT, errno.ENOEXEC])
@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_only_permission_errors_can_be_denial_witnesses(monkeypatch, capsys, number, variant):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement, 'drop_identity', Mock())
    monkeypatch.setattr(enforcement.os, 'execv', Mock(side_effect=OSError(number, 'private detail')))
    if number in (errno.EPERM, errno.EACCES):
        assert enforcement.launch_as(1001, variant) == 77
        assert capsys.readouterr().out.encode() == enforcement.IDENTITY + enforcement.DENIED
    else:
        with pytest.raises(enforcement.guest.GuestError, match='enforcement:exec-failed'):
            enforcement.launch_as(1001, variant)
        assert capsys.readouterr().out.encode() == enforcement.IDENTITY


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'retention'])
def test_provision_keeps_fixture_executable_through_private_umask(monkeypatch, tmp_path, variant):
    from oh_no_parent_control import catalog
    from oh_no_parent_control.core import UserAccount

    payload = tmp_path / 'payload'
    source = payload / 'fixtures/native/onpc-test-application'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'deterministic fixture bytes')
    _, _, desktop_id = enforcement.native_paths(variant)
    target = tmp_path / 'command' / ('native fixture' if variant == 'whitespace' else 'fixture')
    desktop = tmp_path / desktop_id
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.guest, 'PAYLOAD', payload)
    prefix = {'command': '', 'whitespace': 'SPACE_', 'retention': 'RETENTION_'}[variant]
    monkeypatch.setattr(enforcement, prefix + 'TARGET', target)
    monkeypatch.setattr(enforcement, prefix + 'DESKTOP', desktop)
    accounts = iter((SimpleNamespace(pw_uid=1001), SimpleNamespace(pw_uid=1002),
                     SimpleNamespace(pw_uid=1003)))
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', lambda name: next(accounts))
    old_umask = os.umask(0o077)
    try:
        assert enforcement.provision_native(variant) == {'child': 1001, 'other': 1002, 'parent': 1003}
    finally:
        os.umask(old_umask)
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o755
    assert target.parent.stat().st_mode & 0o777 == 0o755
    assert desktop.stat().st_mode & 0o777 == 0o644
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', (tmp_path,))
    monkeypatch.setattr(catalog.pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=1001, pw_dir=str(tmp_path / 'home')))
    apps = catalog.list_apps(UserAccount(1001, 'child', 'child', False, False, True))
    assert [app['targets'] for app in apps if app['id'] == desktop_id] == [(str(target),)]
    with pytest.raises(enforcement.guest.GuestError, match='fixture-collision'):
        enforcement.provision_native(variant)
    assert target.read_bytes() == source.read_bytes()


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_launch_request_dispatches_fixed_variant(monkeypatch, variant):
    launch = Mock(return_value=77)
    monkeypatch.setattr(enforcement, 'launch_as', launch)
    monkeypatch.setattr(enforcement.sys, 'stdin', io.StringIO(json.dumps({'uid': 1001, 'variant': variant})))
    assert enforcement.main() == 77
    launch.assert_called_once_with(1001, variant)


@pytest.fixture
def retention_tree(monkeypatch, tmp_path):
    target = tmp_path / 'retention/native-fixture'
    desktop = tmp_path / enforcement.RETENTION_DESKTOP_ID
    source = tmp_path / 'payload/fixtures/native/onpc-test-application'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'deterministic fixture')
    monkeypatch.setattr(enforcement, 'RETENTION_TARGET', target)
    monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'PAYLOAD', tmp_path / 'payload')
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', Mock(side_effect=[
        SimpleNamespace(pw_uid=uid) for uid in (1001, 1002, 1003)]))
    accounts = enforcement.provision_native('retention')
    return SimpleNamespace(target=target, desktop=desktop, source=source, accounts=accounts)


@pytest.mark.parametrize('fault', [None, 'still-listed', 'lost-before-save', 'lost-after-save',
                                 'source-lost', 'compiled-lost', 'child-allowed', 'other-denied',
                                 'other-preferences', 'removal-failed', 'restore-failed'])
def test_missing_launcher_retains_rules_through_public_save_and_isolation(
        monkeypatch, tmp_path, retention_tree, fault):
    from oh_no_parent_control import catalog
    from oh_no_parent_control.core import UserAccount
    from oh_no_parent_control.execution_policy import FapolicydPolicy
    from oh_no_parent_control.preferences import default_preferences
    from test_core import make_broker

    tree = retention_tree
    real_rules, real_sha = enforcement.record_rules, enforcement.guest.sha
    original, state, records, _, _ = policy_rig(monkeypatch, 'retention')
    monkeypatch.setattr(enforcement.guest, 'sha', real_sha)
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', (tmp_path,))
    monkeypatch.setattr(catalog.pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=1001, pw_dir=str(tmp_path / 'home')))
    user = UserAccount(1001, 'child', 'child', False, False, True)
    broker = make_broker(application_catalog=catalog.list_apps)
    files = (tmp_path / 'source.rules', tmp_path / 'compiled.rules')
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(enforcement, 'RULES', files[0])
    monkeypatch.setattr(enforcement, 'COMPILED_RULES', files[1])
    monkeypatch.setattr(enforcement.guest, 'commands', Mock(directory=private))
    ordinary_call = enforcement.call
    launches, missing_saves = [], []

    def call(uid, method, signature='()', args=()):
        missing = not tree.desktop.exists()
        if method == 'ListApplications' and not (missing and fault == 'still-listed'):
            return [[[app['id'], app['name'], '', '', list(app['targets']), []]
                     for app in catalog.list_apps(user)]]
        if method == 'GetPreferences' and missing:
            if args == (1002,) and fault == 'other-preferences':
                return ['changed']
            if args == (1001,) and (
                    (fault == 'lost-before-save' and not missing_saves) or
                    (fault == 'lost-after-save' and len(missing_saves) == 1)):
                return [original]
        if method == 'SetPreferences':
            if fault == 'restore-failed' and len(launches) == 20:
                raise enforcement.guest.GuestError('restore-failed')
            # Real broker save resolves the real temporary desktop catalog.
            requested = json.loads(args[1])
            saved = broker.set_preferences(uid, args[0], {**default_preferences(), **requested})
            requested['apps'] = saved['apps']
            args = (args[0], json.dumps(requested))
            if missing:
                missing_saves.append(saved['apps'])
            entry = saved['apps'].get(enforcement.RETENTION_DESKTOP_ID)
            rendered = FapolicydPolicy.render({1001: tuple(entry['targets'])} if entry else {})
            for index, path in enumerate(files):
                lost = missing and fault == ('source-lost', 'compiled-lost')[index]
                path.write_text('# lost\n' if lost else rendered)
        return ordinary_call(uid, method, signature, args)

    def launch(uid, allowed, variant):
        assert variant == 'retention'
        assert tree.target.read_bytes() == tree.source.read_bytes()
        saved = json.loads(state['current'])
        blocked = bool(saved['apps'])
        assert allowed == (uid == 1002 or not blocked)
        launches.append((saved['parent_control_enabled'], blocked, uid, allowed))
        if not tree.desktop.exists() and ((fault == 'child-allowed' and uid == 1001) or
                                          (fault == 'other-denied' and uid == 1002)):
            raise enforcement.guest.GuestError('launch-fault')

    monkeypatch.setattr(enforcement, 'call', call)
    monkeypatch.setattr(enforcement, 'record_rules', real_rules)
    monkeypatch.setattr(enforcement, 'observe_launch', launch)
    if fault == 'removal-failed':
        monkeypatch.setattr(enforcement, 'remove_retention_launcher',
                            Mock(side_effect=enforcement.guest.GuestError('removal-failed')))
    if fault:
        with pytest.raises(enforcement.guest.GuestError):
            enforcement.native_policy_transition(tree.accounts, lambda *item: records.append(item), 'retention')
    else:
        enforcement.native_policy_transition(tree.accounts, lambda *item: records.append(item), 'retention')
        assert len(launches) == 20
        assert ('onpc.native.retention.missing.catalog', 'absent') in records
        assert ('onpc.native.retention.missing.saved-policy', 'retained') in records
        assert missing_saves[0][enforcement.RETENTION_DESKTOP_ID]['targets'] == [str(tree.target)]
        assert not tree.desktop.exists()
        for enabled in (False, True):
            assert (enabled, True, 1001, False) in launches
            assert (enabled, True, 1002, True) in launches
        assert state['toggles'] == [(True, 45), (False, 45)]
    if fault in ('still-listed', 'lost-before-save', 'lost-after-save', 'source-lost',
                 'compiled-lost', 'removal-failed'):
        assert launches == [(False, False, 1001, True), (False, False, 1002, True)]
    assert records[-1] == ('onpc.native.retention.policy-restoration',
                           'failed' if fault in ('other-preferences', 'restore-failed') else 'passed')
    if fault != 'restore-failed':
        assert state['current'] == original


@pytest.fixture
def pattern_tree(monkeypatch, tmp_path):
    target = tmp_path / 'pattern/Versioned-1.AppImage'
    desktop = tmp_path / enforcement.PATTERN_DESKTOP_ID
    payload = tmp_path / 'payload'
    source = payload / 'fixtures/native/onpc-test-application'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'deterministic fixture')
    monkeypatch.setattr(enforcement, 'PATTERN_TARGET', target)
    monkeypatch.setattr(enforcement, 'PATTERN_DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'PAYLOAD', payload)
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', Mock(side_effect=[
        SimpleNamespace(pw_uid=uid) for uid in (1001, 1002, 1003)]))
    old = os.umask(0o077)
    try:
        accounts = enforcement.provision_native('pattern')
    finally:
        os.umask(old)
    return SimpleNamespace(target=target, desktop=desktop, source=source, accounts=accounts)


def test_pattern_fixture_catalog_and_future_creation(monkeypatch, tmp_path, pattern_tree):
    from oh_no_parent_control import catalog
    from oh_no_parent_control.core import UserAccount

    tree = pattern_tree
    unrelated, _, _ = enforcement.native_paths('pattern-unrelated')
    future, _, _ = enforcement.native_paths('pattern-future')
    assert not future.exists()
    assert tree.target.read_bytes() == unrelated.read_bytes() == tree.source.read_bytes()
    assert tree.target.parent.stat().st_mode & 0o777 == 0o755
    assert unrelated.stat().st_mode & 0o777 == 0o755
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', (tmp_path,))
    monkeypatch.setattr(catalog.pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=1001, pw_dir=str(tmp_path / 'home')))
    apps = catalog.list_apps(UserAccount(1001, 'child', 'child', False, False, True))
    assert [app['targets'] for app in apps if app['id'] == enforcement.PATTERN_DESKTOP_ID] == [(str(tree.target),)]
    enforcement.provision_future()
    assert future.read_bytes() == tree.source.read_bytes()
    assert future.stat().st_mode & 0o777 == 0o755
    with pytest.raises(enforcement.guest.GuestError, match='fixture-collision'):
        enforcement.provision_native('pattern')


@pytest.mark.parametrize('fault', [None, 'future-allowed', 'unrelated-denied', 'other-denied',
                                 'rules-changed', 'other-preferences', 'restore-failed', 'creation-failed'])
def test_pattern_scenario_future_after_activation_and_isolation(
        monkeypatch, tmp_path, pattern_tree, fault):
    from oh_no_parent_control.execution_policy import FapolicydPolicy
    from oh_no_parent_control.preferences import default_preferences, validate_preferences

    real_rules, real_sha = enforcement.record_rules, enforcement.guest.sha
    original, state, records, _, _ = policy_rig(monkeypatch, 'pattern')
    monkeypatch.setattr(enforcement.guest, 'sha', real_sha)
    files = (tmp_path / 'source.rules', tmp_path / 'compiled.rules')
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(enforcement, 'RULES', files[0])
    monkeypatch.setattr(enforcement, 'COMPILED_RULES', files[1])
    monkeypatch.setattr(enforcement.guest, 'commands', Mock(directory=private))
    ordinary_call = enforcement.call
    launches = []
    future, _, _ = enforcement.native_paths('pattern-future')
    activated = False

    def call(uid, method, signature='()', args=()):
        if method == 'SetPreferences':
            saved = validate_preferences({**default_preferences(), **json.loads(args[1])})
            entry = saved['apps'].get(enforcement.PATTERN_DESKTOP_ID)
            rendered = FapolicydPolicy.render(
                {1001: tuple(entry['targets'])} if entry else {},
                {1001: tuple(entry['patterns'])} if entry else {})
            for path in files:
                path.write_text(rendered)
            if fault == 'restore-failed' and len(launches) == 58:
                raise enforcement.guest.GuestError('restore-failed')
        if method == 'GetPreferences' and args == (1002,) and activated and fault == 'other-preferences':
            return ['changed']
        return ordinary_call(uid, method, signature, args)

    def rules(stage, uid, blocked, record, variant):
        nonlocal activated
        if stage == 'hard':
            assert not future.exists()
            activated = True
        if stage == 'hard-future' and fault == 'rules-changed':
            files[1].write_text(files[1].read_text() + '# changed\n')
        return real_rules(stage, uid, blocked, record, variant)

    def launch(uid, allowed, variant):
        path, _, _ = enforcement.native_paths(variant)
        assert path.is_file()
        saved = json.loads(state['current'])
        blocked = bool(saved['apps'])
        expected = uid == 1002 or variant == 'pattern-unrelated' or not blocked
        assert allowed == expected
        if variant == 'pattern-future':
            assert activated
        launches.append((saved['parent_control_enabled'], blocked, uid, variant, allowed))
        if activated and ((fault == 'future-allowed' and variant == 'pattern-future' and uid == 1001)
                          or (fault == 'unrelated-denied' and variant == 'pattern-unrelated' and uid == 1001)
                          or (fault == 'other-denied' and variant == 'pattern-future' and uid == 1002)):
            raise enforcement.guest.GuestError('launch-fault')

    monkeypatch.setattr(enforcement, 'call', call)
    monkeypatch.setattr(enforcement, 'record_rules', rules)
    monkeypatch.setattr(enforcement, 'observe_launch', launch)
    if fault == 'creation-failed':
        monkeypatch.setattr(enforcement, 'provision_future',
                            Mock(side_effect=enforcement.guest.GuestError('creation-failed')))
    if fault:
        with pytest.raises(enforcement.guest.GuestError):
            enforcement.native_policy_transition(pattern_tree.accounts, lambda *item: records.append(item), 'pattern')
    else:
        enforcement.native_policy_transition(pattern_tree.accounts, lambda *item: records.append(item), 'pattern')
        assert len(launches) == 58
        assert ('onpc.native.pattern.future.unchanged-rules', 'passed') in records
        for enabled in (False, True):
            assert (enabled, True, 1001, 'pattern-future', False) in launches
            assert (enabled, True, 1001, 'pattern-unrelated', True) in launches
            assert (enabled, True, 1002, 'pattern-future', True) in launches
        assert state['toggles'] == [(True, 45), (False, 45)]
    assert records[-1] == ('onpc.native.pattern.policy-restoration',
                           'failed' if fault in ('other-preferences', 'restore-failed') else 'passed')
    assert state['current'] == original


@pytest.mark.parametrize('fault', ['allow-missing', 'allow-after-deny', 'deny-missing', 'wrong-uid',
                                 'stale', 'future-exact-denial'])
@pytest.mark.parametrize('fault_file', ['source', 'compiled'])
def test_pattern_rule_witness_rejects_bad_allowance_or_guard(
        monkeypatch, tmp_path, pattern_tree, fault, fault_file):
    from oh_no_parent_control.execution_policy import FapolicydPolicy

    target = pattern_tree.target
    pattern = str(target.with_name('Versioned-*.AppImage'))
    files = {'source': tmp_path / 'source.rules', 'compiled': tmp_path / 'compiled.rules'}
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(enforcement, 'RULES', files['source'])
    monkeypatch.setattr(enforcement, 'COMPILED_RULES', files['compiled'])
    monkeypatch.setattr(enforcement.guest, 'commands', Mock(directory=private))
    rendered = FapolicydPolicy.render({1001: (str(target),)}, {1001: (pattern,)})
    for path in files.values():
        path.write_text(rendered)
    enforcement.record_rules('hard', 1001, True, Mock(), 'pattern')
    unrelated, _, _ = enforcement.native_paths('pattern-unrelated')
    allow = f'allow perm=execute uid=1001 : path={unrelated}\n'
    deny = f'deny_syslog perm=execute uid=1001 : dir={target.parent}/\n'
    future, _, _ = enforcement.native_paths('pattern-future')
    changed = {'allow-missing': rendered.replace(allow, ''),
               'allow-after-deny': rendered.replace(allow, '') + allow,
               'deny-missing': rendered.replace(deny, ''),
               'wrong-uid': rendered.replace('uid=1001', 'uid=1002'),
               'future-exact-denial': rendered + f'deny_syslog perm=execute uid=1001 : path={future}\n',
               'stale': rendered.replace(f'deny_syslog perm=execute uid=1001 : path={target}\n', '')}[fault]
    if fault == 'stale':
        files['source'].write_text('# empty\n')
        files['compiled'].write_text('# empty\n')
    files[fault_file].write_text(changed)
    with pytest.raises(enforcement.guest.GuestError, match='rule-state'):
        enforcement.record_rules('fault', 1001, fault != 'stale', Mock(), 'pattern')
    assert (private / f'native-pattern-fault-{fault_file}.txt').read_text() == changed


@pytest.mark.parametrize(('blocked', 'fault'), [(False, 'stale-denial'), (True, 'missing'),
                                             (True, 'wrong-hash'), (True, 'wrong-uid'),
                                             (True, 'path-clause')])
@pytest.mark.parametrize('fault_file', ['source', 'compiled'])
def test_whitespace_rules_require_current_hash_in_both_files(
        monkeypatch, tmp_path, blocked, fault, fault_file):
    from oh_no_parent_control.execution_policy import FapolicydPolicy

    target = tmp_path / 'native fixture'
    target.write_bytes(b'deterministic fixture')
    monkeypatch.setattr(enforcement, 'SPACE_TARGET', target)
    files = {'source': tmp_path / 'source', 'compiled': tmp_path / 'compiled'}
    monkeypatch.setattr(enforcement, 'RULES', files['source'])
    monkeypatch.setattr(enforcement, 'COMPILED_RULES', files['compiled'])
    private = tmp_path / 'private'
    private.mkdir()
    monkeypatch.setattr(enforcement.guest, 'commands', Mock(directory=private))
    rendered = FapolicydPolicy.render({1001: (str(target),)} if blocked else {})
    for path in files.values():
        path.write_text(rendered)
    records = []
    enforcement.record_rules('hard', 1001, blocked, lambda *item: records.append(item), 'whitespace')
    assert len(records) == 2
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    line = f'deny_syslog perm=execute uid=1001 : sha256hash={digest}'
    faulty = {'stale-denial': line, 'missing': '# missing', 'wrong-hash': line.replace(digest, '0' * 64),
              'wrong-uid': line.replace('uid=1001', 'uid=1002'),
              'path-clause': f'deny_syslog perm=execute uid=1001 : path={target}'}[fault]
    # Allow stages must reject a stale denial; deny stages must reject every
    # substitute for the exact current executable hash and selected UID.
    files[fault_file].write_text(faulty + '\n')
    with pytest.raises(enforcement.guest.GuestError, match='rule-state'):
        enforcement.record_rules('hard', 1001, blocked, Mock(), 'whitespace')
    assert (private / f'native-whitespace-hard-{fault_file}.txt').read_bytes() == files[fault_file].read_bytes()


@pytest.fixture
def installed_catalog_tree(monkeypatch, tmp_path):
    # The privileged dispatcher's unprivileged safety phase clears PYTHONPATH.
    # Resolve this fixture's source dependency without relying on host setup.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'broker'))
    from oh_no_parent_control import catalog
    from oh_no_parent_control.core import UserAccount

    accounts = {'child': 1001, 'other': 1002, 'parent': 1003}
    identities = {}
    for role, uid in accounts.items():
        home = tmp_path / role
        home.mkdir(mode=0o700)
        identities[uid] = SimpleNamespace(pw_uid=uid, pw_gid=uid, pw_dir=str(home))
    target = tmp_path / 'native/fixture'
    target.parent.mkdir()
    target.write_bytes(b'fixture')
    target.chmod(0o755)
    system = tmp_path / 'system'
    system.mkdir()
    desktop = system / enforcement.DESKTOP_ID
    desktop.write_text(f'[Desktop Entry]\nType=Application\nName=System\nExec="{target}"\n')
    monkeypatch.setattr(enforcement, 'TARGET', target)
    monkeypatch.setattr(enforcement, 'DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwuid', identities.__getitem__)
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', lambda role: identities[accounts[role]])
    chown = Mock()
    monkeypatch.setattr(enforcement.os, 'chown', chown)
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', (system,))
    monkeypatch.setenv('HOME', identities[1003].pw_dir)
    monkeypatch.setenv('XDG_DATA_HOME', str(Path(identities[1003].pw_dir) / '.local/share'))
    monkeypatch.setenv('PATH', str(Path(identities[1003].pw_dir) / '.local/bin'))
    local_bin, system_bin = tmp_path / 'local-bin', tmp_path / 'system-bin'
    monkeypatch.setattr(enforcement, 'CATALOG_LOCAL_BIN', local_bin)
    monkeypatch.setattr(enforcement, 'CATALOG_SYSTEM_BIN', system_bin)
    monkeypatch.setattr(catalog, 'SYSTEM_EXECUTABLE_DIRS', (local_bin, system_bin))
    calls = []

    def call(uid, method, signature='()', args=()):
        assert (uid, method, signature) == (1003, 'ListApplications', '(u)')
        calls.append(args[0])
        role = next(role for role, value in accounts.items() if value == args[0])
        user = UserAccount(args[0], role, role, False, False, True)
        return [[[app['id'], app['name'], '', '', list(app['targets']), []]
                 for app in catalog.list_apps(user)]]

    monkeypatch.setattr(enforcement, 'call', call)
    return SimpleNamespace(accounts=accounts, identities=identities, target=target,
                           system=system, local_bin=local_bin, system_bin=system_bin,
                           call=call, calls=calls, chown=chown)


def test_catalog_fixture_and_broker_assertions_with_real_discovery(installed_catalog_tree):
    tree = installed_catalog_tree
    old_umask = os.umask(0o077)
    try:
        enforcement.provision_catalog(tree.accounts)
    finally:
        os.umask(old_umask)
    records = []
    enforcement.observe_catalog(tree.accounts, lambda *item: records.append(item))
    assert tree.calls == [1001, 1002, 1001]
    assert records == [(f'onpc.catalog.{stage}', 'passed')
                       for stage in ('child', 'other', 'child-again')]
    assert all(path.stat().st_mode & 0o777 == 0o755
               for path in (tree.target.parent / 'catalog').iterdir())
    for directory in (tree.local_bin, tree.system_bin,
                      tree.target.parent / 'catalog/desktop path'):
        assert directory.stat().st_mode & 0o777 == 0o755
        for path in directory.iterdir():
            assert path.stat().st_mode & 0o777 == 0o755
            assert path.read_bytes() == tree.target.read_bytes()
            assert all(call.args[0] != path for call in tree.chown.call_args_list)
    for role, entry in tree.identities.items():
        home = Path(entry.pw_dir)
        assert home.stat().st_mode & 0o777 == 0o700
        assert (home / '.local/share/applications').stat().st_mode & 0o777 == 0o755
        for path in (home / '.local/share/applications').iterdir():
            assert path.stat().st_mode & 0o777 == 0o644
            tree.chown.assert_any_call(path, role, role)
        for directory in (home / '.local/bin', home / 'bin'):
            if directory.exists():
                assert directory.stat().st_mode & 0o777 == 0o755
                for path in directory.iterdir():
                    assert path.stat().st_mode & 0o777 == 0o755
                    assert path.read_bytes() == tree.target.read_bytes()
                    tree.chown.assert_any_call(path, role, role)
        assert all(call.args[0] != home for call in tree.chown.call_args_list)


@pytest.mark.parametrize('fault', ['parent-only', 'parent-target', 'missing-child',
                                 'duplicate', 'wrong-name', 'stale-child', 'missing-system'])
def test_catalog_assertions_reject_scope_and_target_faults(monkeypatch, installed_catalog_tree, fault):
    tree = installed_catalog_tree
    enforcement.provision_catalog(tree.accounts)

    def call(uid, method, signature='()', args=()):
        reply = tree.call(uid, method, signature, args)
        rows = reply[0]
        shared = next(row for row in rows if row[0] == enforcement.CATALOG_PREFIX + 'Shared.desktop')
        if fault == 'parent-only':
            rows.append([enforcement.CATALOG_PREFIX + 'ParentOnly.desktop', '', '', '', [], []])
        elif fault == 'parent-target':
            shared[4] = [str(tree.target.parent / 'catalog/parent-Shared')]
        elif fault == 'missing-child':
            rows[:] = [row for row in rows if row[0] != enforcement.CATALOG_PREFIX + 'ChildOnly.desktop']
        elif fault == 'duplicate':
            rows.append(shared)
        elif fault == 'wrong-name':
            shared[1] = 'wrong scope'
        elif fault == 'stale-child' and args == (1002,):
            return tree.call(uid, method, signature, (1001,))
        elif fault == 'missing-system':
            rows[:] = [row for row in rows if row[0] != enforcement.DESKTOP_ID]
        return reply

    monkeypatch.setattr(enforcement, 'call', call)
    records = []
    with pytest.raises(enforcement.guest.GuestError, match='catalog:'):
        enforcement.observe_catalog(tree.accounts, lambda *item: records.append(item))
    assert records == ([('onpc.catalog.child', 'passed')] if fault == 'stale-child' else [])


@pytest.mark.parametrize('fault', ['parent', 'lower-priority', 'missing', 'stale-child',
                                 'parent-only-visible'])
def test_catalog_assertions_reject_relative_lookup_faults(monkeypatch, installed_catalog_tree, fault):
    tree = installed_catalog_tree
    enforcement.provision_catalog(tree.accounts)

    def call(uid, method, signature='()', args=()):
        reply = tree.call(uid, method, signature, args)
        rows = reply[0]
        relative = next(row for row in rows if row[0] == enforcement.CATALOG_PREFIX + 'Relative.desktop')
        if fault == 'parent':
            relative[4] = [str(Path(tree.identities[1003].pw_dir) / '.local/bin' / enforcement.CATALOG_COMMAND)]
        elif fault == 'lower-priority':
            relative[4] = [str(Path(tree.identities[1001].pw_dir) / 'bin' / enforcement.CATALOG_COMMAND)]
        elif fault == 'missing':
            rows.remove(relative)
        elif fault == 'stale-child' and args == (1002,):
            relative[4] = [str(Path(tree.identities[1001].pw_dir) / '.local/bin' / enforcement.CATALOG_COMMAND)]
        elif fault == 'parent-only-visible':
            rows.append([enforcement.CATALOG_PREFIX + 'RelativeUnavailable.desktop',
                         'ONPC system RelativeUnavailable', '', '',
                         [str(Path(tree.identities[1003].pw_dir) / '.local/bin' /
                              enforcement.CATALOG_PARENT_COMMAND)], []])
        return reply

    monkeypatch.setattr(enforcement, 'call', call)
    records = []
    with pytest.raises(enforcement.guest.GuestError, match='catalog:'):
        enforcement.observe_catalog(tree.accounts, lambda *item: records.append(item))
    assert records == ([('onpc.catalog.child', 'passed')] if fault == 'stale-child' else [])


@pytest.mark.parametrize('scope', ['child', 'system'])
def test_catalog_provision_preserves_existing_binary_directory(installed_catalog_tree, scope):
    tree = installed_catalog_tree
    home = Path(tree.identities[1001].pw_dir)
    directory = home / '.local/bin' if scope == 'child' else tree.system_bin
    directory.mkdir(parents=True, mode=0o700)
    sentinel = directory / 'unrelated-command'
    sentinel.write_bytes(b'preserved')
    sentinel.chmod(0o700)
    enforcement.provision_catalog(tree.accounts)
    assert directory.stat().st_mode & 0o777 == 0o700
    assert sentinel.read_bytes() == b'preserved'
    assert sentinel.stat().st_mode & 0o777 == 0o700
    assert all(call.args[0] not in (directory, sentinel) for call in tree.chown.call_args_list)


@pytest.mark.parametrize('fault', ['missing-path', 'relative-path', 'missing-path-target',
                                 'missing-preferred', 'nonexecutable-preferred',
                                 'missing-fallback', 'administrator-path'])
def test_catalog_assertions_reject_path_and_system_lookup_faults(
        monkeypatch, installed_catalog_tree, fault):
    from oh_no_parent_control import catalog

    tree = installed_catalog_tree
    enforcement.provision_catalog(tree.accounts)
    if fault in ('missing-path', 'relative-path'):
        desktop = tree.system / (enforcement.CATALOG_PREFIX + 'DesktopPath.desktop')
        lines = desktop.read_text().splitlines()
        lines = [line for line in lines if not line.startswith('Path=')]
        if fault == 'relative-path':
            lines.append('Path=desktop path')
        desktop.write_text('\n'.join(lines) + '\n')
    elif fault == 'missing-path-target':
        (tree.target.parent / 'catalog/desktop path' / enforcement.CATALOG_COMMAND).unlink()
    elif fault in ('missing-preferred', 'nonexecutable-preferred'):
        target = tree.local_bin / enforcement.CATALOG_SYSTEM_COMMAND
        if fault == 'missing-preferred':
            target.unlink()
        else:
            target.chmod(0o644)
    elif fault == 'missing-fallback':
        (tree.system_bin / enforcement.CATALOG_FALLBACK_COMMAND).unlink()
    else:
        # Simulate the broken resolver inheriting the administrator search path.
        monkeypatch.setattr(catalog, 'SYSTEM_EXECUTABLE_DIRS',
                            (Path(tree.identities[1003].pw_dir) / '.local/bin',))
    records = []
    with pytest.raises(enforcement.guest.GuestError, match='catalog:'):
        enforcement.observe_catalog(tree.accounts, lambda *item: records.append(item))
    assert records == []
