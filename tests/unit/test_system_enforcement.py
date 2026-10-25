"""Trust-fixture writes refuse substituted paths before changing policy."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_enforcement as enforcement
from tests.support.baseline_native import native as baseline_native
from tests.support.installed_catalog import installed_catalog_tree


@pytest.mark.parametrize('fault', ['file', 'symlink', 'unsafe-parent'])
def test_future_trust_refuses_foreign_file_or_parent_before_mutation(monkeypatch, tmp_path, fault):
    target = tmp_path / 'Versioned-2.AppImage'
    target.write_bytes(b'future fixture')
    trust = tmp_path / 'trust.d/future.trust'
    trust.parent.mkdir()
    monkeypatch.setattr(enforcement, 'FUTURE_TRUST', trust)
    monkeypatch.setattr(enforcement, 'native_paths', lambda variant: (target, None, None))
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'sha', lambda path: 'a' * 64)
    native_lstat = type(trust).lstat
    monkeypatch.setattr(type(trust), 'lstat', lambda path: (
        SimpleNamespace(st_mode=0o40777 if fault == 'unsafe-parent' else 0o40755, st_uid=0)
        if path in trust.parents else native_lstat(path)))
    if fault == 'file':
        trust.write_text('foreign')
    elif fault == 'symlink':
        trust.symlink_to(tmp_path / 'missing')
    run = Mock()
    monkeypatch.setattr(enforcement.guest, 'run', run)
    with pytest.raises(enforcement.guest.GuestError, match=(
            'unsafe-trust-parent' if fault == 'unsafe-parent' else 'future-trust-collision')):
        enforcement.trust_future()
    run.assert_not_called()


def policy_rig(monkeypatch, variant='command'):
    target, _, desktop_id = enforcement.native_paths(variant)
    # Cases that restore real hashing must still use an owned fixture binary.
    monkeypatch.setattr(enforcement, 'FAPOLICYD', target)
    original = json.dumps({'apps': {}, 'parent_control_enabled': False,
                           'daily_time_limit_minutes': 45})
    state = {'current': original, 'saved': [], 'toggles': []}
    records, launches, rules = [], [], []
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'sha', Mock(return_value='a' * 64))
    monkeypatch.setattr(enforcement.guest, 'run', Mock(return_value='1.3.3-1build1'))

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


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'retention'])
def test_provision_keeps_fixture_executable_through_private_umask(monkeypatch, tmp_path, variant):
    from oh_no_parent_control import catalog
    from oh_no_parent_control.core import UserAccount

    payload = tmp_path / 'payload'
    source = payload / 'fixtures/mechanical/onpc-test-application'
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
    identities = dict(zip(('onpc-child-riley', 'onpc-child-jordan', 'onpc-parent-jamie'),
                          (SimpleNamespace(pw_uid=uid) for uid in (1001, 1002, 1003))))
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', identities.__getitem__)
    baseline_native(target, desktop, source, root=tmp_path, monkeypatch=monkeypatch)
    old_umask = os.umask(0o077)
    try:
        assert enforcement.provision_native(variant) == {'child': 1001, 'other': 1002, 'parent': 1003}
    finally:
        os.umask(old_umask)
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o755
    assert target.parent.stat().st_mode & 0o777 == 0o755
    assert desktop.stat().st_mode & 0o777 == 0o644
    before = target.stat()
    enforcement.provision_native(variant)
    assert target.stat() == before
    monkeypatch.setattr(catalog, 'SYSTEM_APPLICATION_DIRS', (tmp_path,))
    monkeypatch.setattr(catalog.pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=1001, pw_dir=str(tmp_path / 'home')))
    apps = catalog.list_apps(UserAccount(1001, 'child', 'child', False, False, True))
    assert [app['targets'] for app in apps if app['id'] == desktop_id] == [(str(target),)]
    assert target.read_bytes() == source.read_bytes()


@pytest.fixture
def retention_tree(monkeypatch, tmp_path):
    target = tmp_path / 'retention/native-fixture'
    desktop = tmp_path / enforcement.RETENTION_DESKTOP_ID
    source = tmp_path / 'payload/fixtures/mechanical/onpc-test-application'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'deterministic fixture')
    monkeypatch.setattr(enforcement, 'RETENTION_TARGET', target)
    monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'PAYLOAD', tmp_path / 'payload')
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', Mock(side_effect=[
        SimpleNamespace(pw_uid=uid) for uid in (1001, 1002, 1003)]))
    baseline_native(target, desktop, source, root=tmp_path, monkeypatch=monkeypatch)
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
    from tests.support.broker import make_broker

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
            if fault == 'restore-failed' and len(launches) == 10:
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
        assert len(launches) == 10
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
    source = payload / 'fixtures/mechanical/onpc-test-application'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'deterministic fixture')
    monkeypatch.setattr(enforcement, 'PATTERN_TARGET', target)
    monkeypatch.setattr(enforcement, 'PATTERN_DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'PAYLOAD', payload)
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(enforcement.pwd, 'getpwnam', Mock(side_effect=[
        SimpleNamespace(pw_uid=uid) for uid in (1001, 1002, 1003)]))
    baseline_native(target, desktop, source, root=tmp_path, monkeypatch=monkeypatch, unrelated=True)
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
    with pytest.raises(enforcement.guest.GuestError, match='future-fixture-collision'):
        enforcement.provision_future()


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
            if fault == 'restore-failed' and len(launches) == 30:
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
    trusted_future = Mock()
    monkeypatch.setattr(enforcement, 'trust_future', trusted_future)
    if fault == 'creation-failed':
        monkeypatch.setattr(enforcement, 'provision_future',
                            Mock(side_effect=enforcement.guest.GuestError('creation-failed')))
    if fault:
        with pytest.raises(enforcement.guest.GuestError):
            enforcement.native_policy_transition(pattern_tree.accounts, lambda *item: records.append(item), 'pattern')
    else:
        enforcement.native_policy_transition(pattern_tree.accounts, lambda *item: records.append(item), 'pattern')
        assert len(launches) == 30
        trusted_future.assert_called_once_with()
        assert ('onpc.native.pattern.future.trusted-child-denied', 'passed') in records
        assert ('onpc.native.pattern.future.unchanged-rules', 'passed') in records
        for enabled in (False, True):
            assert (enabled, True, 1001, 'pattern-future', False) in launches
            assert (enabled, True, 1001, 'pattern-unrelated', True) in launches
            assert (enabled, True, 1002, 'pattern-future', True) in launches
        assert state['toggles'] == [(True, 45), (False, 45)]
    assert records[-1] == ('onpc.native.pattern.policy-restoration',
                           'failed' if fault in ('other-preferences', 'restore-failed') else 'passed')
    assert state['current'] == original


def test_catalog_fixture_and_broker_assertions_with_real_discovery(installed_catalog_tree):
    tree = installed_catalog_tree
    old_umask = os.umask(0o077)
    try:
        tree.prepare()
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
            assert path.stat().st_uid == os.getuid()
        for directory in (home / '.local/bin', home / 'bin'):
            if directory.exists():
                assert directory.stat().st_mode & 0o777 == 0o755
                for path in directory.iterdir():
                    assert path.stat().st_mode & 0o777 == 0o755
                    assert path.read_bytes() == tree.target.read_bytes()
                    assert path.stat().st_uid == os.getuid()
        assert all(call.args[0] != home for call in tree.chown.call_args_list)
