"""Trust-fixture writes refuse substituted paths before changing policy."""

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
