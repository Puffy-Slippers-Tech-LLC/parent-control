"""No native launch before guest/credential checks; reuse owned command cleanup."""

from unittest.mock import Mock

import pytest

from test_system_enforcement import enforcement, installed_catalog_tree  # noqa: F401


@pytest.mark.parametrize('boundary', ['guard', 'identity'])
@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_refused_boundary_prevents_exec(monkeypatch, capsys, boundary, variant):
    guard, identity, execute = Mock(), Mock(), Mock()
    (guard if boundary == 'guard' else identity).side_effect = enforcement.guest.GuestError('refused')
    monkeypatch.setattr(enforcement.guest, 'guard', guard)
    monkeypatch.setattr(enforcement, 'drop_identity', identity)
    monkeypatch.setattr(enforcement.os, 'execv', execute)
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.launch_as(1001, variant)
    execute.assert_not_called()
    assert capsys.readouterr().out == ''
    if boundary == 'guard':
        identity.assert_not_called()


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'pattern-future', 'pattern-unrelated', 'retention'])
def test_success_replaces_same_process_with_one_shot_target(monkeypatch, capsys, variant):
    class Replaced(BaseException):
        pass

    events = []
    monkeypatch.setattr(enforcement.guest, 'guard', lambda: events.append('guard'))
    monkeypatch.setattr(enforcement, 'drop_identity', lambda uid: events.append(('identity', uid)))

    def execute(path, args):
        events.append(('exec', path, args))
        raise Replaced()

    monkeypatch.setattr(enforcement.os, 'execv', execute)
    with pytest.raises(Replaced):
        enforcement.launch_as(1001, variant)
    target, _, _ = enforcement.native_paths(variant)
    assert events == ['guard', ('identity', 1001),
                      ('exec', str(target), [str(target)])]
    assert capsys.readouterr().out.encode() == enforcement.IDENTITY


@pytest.mark.parametrize('variant', ['command', 'whitespace', 'pattern', 'retention'])
def test_guest_refusal_prevents_fixture_files(monkeypatch, tmp_path, variant):
    monkeypatch.setattr(enforcement, 'TARGET', tmp_path / 'native/fixture')
    monkeypatch.setattr(enforcement, 'DESKTOP', tmp_path / 'fixture.desktop')
    monkeypatch.setattr(enforcement, 'SPACE_TARGET', tmp_path / 'spaces/native fixture')
    monkeypatch.setattr(enforcement, 'SPACE_DESKTOP', tmp_path / 'spaces.desktop')
    monkeypatch.setattr(enforcement, 'PATTERN_TARGET', tmp_path / 'pattern/Versioned-1.AppImage')
    monkeypatch.setattr(enforcement, 'PATTERN_DESKTOP', tmp_path / 'pattern.desktop')
    monkeypatch.setattr(enforcement, 'RETENTION_TARGET', tmp_path / 'retention/fixture')
    monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', tmp_path / 'retention.desktop')
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(side_effect=enforcement.guest.GuestError('refused')))
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.provision_native(variant)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('variant', ['/usr/bin/true', '../command', '', None, [], 1])
def test_unknown_variant_cannot_select_executable_or_write_fixture(monkeypatch, variant):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    identity, execute, diagnostics = Mock(), Mock(), Mock()
    monkeypatch.setattr(enforcement, 'drop_identity', identity)
    monkeypatch.setattr(enforcement.os, 'execv', execute)
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', diagnostics)
    with pytest.raises(enforcement.guest.GuestError, match='fixture-variant'):
        enforcement.launch_as(1001, variant)
    with pytest.raises(enforcement.guest.GuestError, match='fixture-variant'):
        enforcement.provision_native(variant)
    identity.assert_not_called()
    execute.assert_not_called()
    diagnostics.assert_not_called()


@pytest.mark.parametrize('fault', ['guard', 'existing', 'dangling', 'directory-symlink', 'source-symlink'])
def test_future_creation_refuses_without_overwriting(monkeypatch, tmp_path, fault):
    target = tmp_path / 'pattern/Versioned-1.AppImage'
    target.parent.mkdir()
    target.write_bytes(b'fixture')
    future = target.with_name('Versioned-2.AppImage')
    sentinel = tmp_path / 'sentinel'
    sentinel.write_bytes(b'preserved')
    monkeypatch.setattr(enforcement, 'PATTERN_TARGET', target)
    guard = Mock(side_effect=enforcement.guest.GuestError('refused') if fault == 'guard' else None)
    monkeypatch.setattr(enforcement.guest, 'guard', guard)
    if fault == 'existing':
        future.write_bytes(b'preserved')
    elif fault == 'dangling':
        future.symlink_to(tmp_path / 'missing')
    elif fault == 'directory-symlink':
        alias = tmp_path / 'alias'
        alias.symlink_to(target.parent, target_is_directory=True)
        monkeypatch.setattr(enforcement, 'PATTERN_TARGET', alias / target.name)
    elif fault == 'source-symlink':
        target.unlink()
        target.symlink_to(sentinel)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*'))
    with pytest.raises(enforcement.guest.GuestError):
        enforcement.provision_future()
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*')) == before
    assert sentinel.read_bytes() == b'preserved'
    if fault == 'existing':
        assert future.read_bytes() == b'preserved'


@pytest.mark.parametrize('variant', ['pattern-future', 'pattern-unrelated'])
def test_companion_launch_variant_cannot_provision_its_shared_directory(monkeypatch, variant):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock())
    diagnostics = Mock()
    monkeypatch.setattr(enforcement.guest, 'enable_diagnostics', diagnostics)
    with pytest.raises(enforcement.guest.GuestError, match='fixture-variant'):
        enforcement.provision_native(variant)
    diagnostics.assert_not_called()


@pytest.mark.parametrize('fault', ['guard', 'replacement', 'symlink', 'hardlink',
                                 'edited', 'directory', 'parent-symlink', 'missing'])
def test_launcher_removal_preserves_unexpected_files(monkeypatch, tmp_path, fault):
    desktop = tmp_path / 'fixture.desktop'
    desktop.write_text('owned launcher')
    identity = desktop.lstat()
    sentinel = tmp_path / 'sentinel'
    sentinel.write_text('preserved')
    monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', desktop)
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(
        side_effect=enforcement.guest.GuestError('refused') if fault == 'guard' else None))
    if fault == 'replacement':
        desktop.rename(tmp_path / 'original')
        desktop.write_text('replacement')
    elif fault in ('symlink', 'directory', 'missing'):
        desktop.unlink()
        if fault == 'symlink':
            desktop.symlink_to(sentinel)
        elif fault == 'directory':
            desktop.mkdir()
    elif fault == 'hardlink':
        (tmp_path / 'alias').hardlink_to(desktop)
    elif fault == 'edited':
        desktop.write_text('changed launcher')
    elif fault == 'parent-symlink':
        alias = tmp_path / 'alias'
        alias.symlink_to(tmp_path, target_is_directory=True)
        monkeypatch.setattr(enforcement, 'RETENTION_DESKTOP', alias / desktop.name)
    before = sorted(path.name for path in tmp_path.iterdir())
    with pytest.raises((enforcement.guest.GuestError, FileNotFoundError)):
        enforcement.remove_retention_launcher(identity)
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert sentinel.read_text() == 'preserved'
    if fault in ('guard', 'replacement', 'hardlink', 'edited', 'parent-symlink'):
        assert desktop.read_text() == {
            'replacement': 'replacement', 'edited': 'changed launcher',
        }.get(fault, 'owned launcher')


def test_catalog_guest_refusal_precedes_account_or_file_access(monkeypatch):
    monkeypatch.setattr(enforcement.guest, 'guard', Mock(side_effect=enforcement.guest.GuestError('refused')))
    lookup = Mock()
    monkeypatch.setattr(enforcement.pwd, 'getpwuid', lookup)
    with pytest.raises(enforcement.guest.GuestError, match='refused'):
        enforcement.provision_catalog({'child': 1001})
    lookup.assert_not_called()


@pytest.mark.parametrize('fault', ['launcher', 'dangling-launcher', 'ancestor-symlink',
                                 'ancestor-file', 'target-directory', 'binary',
                                 'dangling-binary', 'binary-ancestor-symlink',
                                 'binary-ancestor-file', 'system-binary',
                                 'dangling-system-binary', 'system-ancestor-symlink',
                                 'system-ancestor-file', 'fallback-shadow'])
def test_catalog_collision_preserves_existing_files(installed_catalog_tree, tmp_path, fault):
    tree = installed_catalog_tree
    home = tmp_path / 'child'
    preserved = tmp_path / 'preserved'
    preserved.mkdir()
    sentinel = preserved / 'sentinel'
    sentinel.write_text('unchanged')
    if fault in ('launcher', 'dangling-launcher'):
        directory = home / '.local/share/applications'
        directory.mkdir(parents=True)
        path = directory / (enforcement.CATALOG_PREFIX + 'ChildOnly.desktop')
        if fault == 'launcher':
            path.write_text('existing launcher')
        else:
            path.symlink_to(preserved / 'missing')
    elif fault == 'ancestor-symlink':
        (home / '.local').symlink_to(preserved, target_is_directory=True)
    elif fault == 'ancestor-file':
        (home / '.local').write_text('existing file')
    elif fault in ('binary', 'dangling-binary'):
        # Use a later planned command to prove complete preflight, including
        # account binaries, occurs before earlier launchers/targets are written.
        directory = tmp_path / 'parent/.local/bin'
        directory.mkdir(parents=True)
        path = directory / enforcement.CATALOG_PARENT_COMMAND
        if fault == 'binary':
            path.write_text('existing binary')
        else:
            path.symlink_to(preserved / 'missing')
    elif fault == 'binary-ancestor-symlink':
        (home / 'bin').symlink_to(preserved, target_is_directory=True)
    elif fault == 'binary-ancestor-file':
        (home / 'bin').write_text('existing file')
    elif fault in ('system-binary', 'dangling-system-binary', 'fallback-shadow'):
        directory = tree.local_bin if fault == 'fallback-shadow' else tree.system_bin
        directory.mkdir()
        path = directory / enforcement.CATALOG_FALLBACK_COMMAND
        if fault == 'dangling-system-binary':
            path.symlink_to(preserved / 'missing')
        else:
            path.write_text('existing binary')
    elif fault == 'system-ancestor-symlink':
        tree.system_bin.symlink_to(preserved, target_is_directory=True)
    elif fault == 'system-ancestor-file':
        tree.system_bin.write_text('existing file')
    else:
        (tree.target.parent / 'catalog').symlink_to(preserved, target_is_directory=True)
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*'))
    with pytest.raises(enforcement.guest.GuestError, match='catalog:(fixture-collision|unsafe-directory)'):
        enforcement.provision_catalog(tree.accounts)
    assert sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*')) == before
    assert sentinel.read_text() == 'unchanged'
    if fault == 'launcher':
        assert path.read_text() == 'existing launcher'
    if fault in ('binary', 'system-binary', 'fallback-shadow'):
        assert path.read_text() == 'existing binary'
    tree.chown.assert_not_called()
