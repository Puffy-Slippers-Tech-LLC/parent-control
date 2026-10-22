"""Snapshot qualification boundaries with private records and VM doubles only."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import fixture_snapshot_qualification as qualification
from guest_inputs import Bundle


@pytest.mark.parametrize('name', ['tests/integration/prepare_vm.py', '/tests/integration/prepare_vm.py'])
def test_guestfs_find_separator_is_normalized(name):
    assert qualification.relative_member(name) == 'tests/integration/prepare_vm.py'


@pytest.mark.parametrize('name', ['', '/', '//file', '../file', 'a/../file', 'a//file', 'a\x00b'])
def test_guestfs_find_members_refuse_unsafe_paths(name):
    with pytest.raises(Exception, match='unsafe-member'):
        qualification.relative_member(name)


@pytest.mark.parametrize('name', [
    'fixtures/image-root/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
    'source/tests/fixtures/gui_application.py',
    'native_assets.py',
    '__pycache__/native_assets.cpython-314.pyc',
    'guest/__pycache__/native_assets.cpython-314.pyc',
    'private/onpc-test-application',
])
def test_input_audit_refuses_all_fixture_and_source_copy_locations(name):
    with pytest.raises(ValueError, match='unexpected-input-file'):
        qualification.check_input_files([name], {'system_guest.py', 'guest/redact.py'})


def test_input_audit_accepts_only_known_installation_modules_and_diagnostics():
    qualification.check_input_files([
        'system_guest.py', 'guest/redact.py', '__pycache__/system_guest.cpython-314.pyc',
        'guest/__pycache__/redact.cpython-314.pyc', 'before.json',
        'private/stage-abcdefgh/command-0001.txt',
        'private/stage-abcdefgh/command-0001-stderr.txt',
        'private/redaction-identities/abcdefgh.json'],
        {'system_guest.py', 'guest/redact.py'})


def test_input_audit_does_not_import_old_fixture_bytes_from_archives():
    archived = 'onpc-system-input-snapshot-' + 'a' * 32 + '-' + 'b' * 32
    assert qualification.input_roots(['unrelated', archived, 'onpc-system-input']) == [
        '/var/tmp/onpc-system-input', '/var/tmp/' + archived]
    for files in (['system_guest.py'], ['fixtures/unselected.AppImage']):
        if files[0].startswith('fixtures/'):
            with pytest.raises(ValueError, match='unexpected-input-file'):
                qualification.check_input_files(files, {'system_guest.py'})
        else:
            qualification.check_input_files(files, {'system_guest.py'})


@pytest.mark.parametrize('name', ['onpc-system-input-backup', 'onpc-system-input-snapshot-a',
                                 'onpc-system-input-foreign'])
def test_unknown_retained_input_tree_is_not_silently_ignored(name):
    with pytest.raises(Exception, match='unrecognized-input-tree'):
        qualification.input_roots([name])


def test_source_mutation_uses_frozen_inputs_and_keeps_original_bundle(tmp_path):
    original = {'tests/integration/guest_install_recipe.py': b'VALUE = 1\n',
                'tests/fixtures/native_assets.py': b'VALUE = 2\n'}
    entries = [(source, source.rsplit('/', 1)[1]) for source in original]
    bundle = Bundle(tmp_path, entries, frozen=original)
    changed = qualification.changed_bundle(bundle, ('tests/fixtures/native_assets.py',))
    assert changed.files['native_assets.py'] != bundle.files['native_assets.py']
    assert changed.digest('guest_install_recipe.py') == bundle.digest('guest_install_recipe.py')
    assert changed.digest('native_assets.py') != bundle.digest('native_assets.py')
    assert bundle.files['native_assets.py'] == original['tests/fixtures/native_assets.py']
    assert list(tmp_path.iterdir()) == []


def test_complete_runtime_inventory_preserves_clean_environment_record():
    paths = qualification.runtime_absence()
    assert qualification.baseline_fixtures.RECORD not in paths
    assert qualification.baseline_fixtures.TRUST_FILE in paths
    assert '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage' in paths
    assert '/opt/onpc-test-fixtures/Applications/Versioned/onpc-test-gui.py' in paths
    assert '/usr/bin/onpc-test-catalog-fallback' in paths
    assert '/home/onpc-child-riley/.local/share/applications/com.puffyslippers.ONPCTest.A.desktop' in paths
    assert not any('apt-daily' in path or 'xdg-user-dirs' in path for path in paths)


@pytest.mark.parametrize('link', [False, True])
def test_product_byte_probe_repacks_private_copy_and_refuses_links(tmp_path, link):
    assets = tmp_path / 'original'
    assets.mkdir()
    (assets / 'package.deb').write_bytes(b'original archive')
    target = '/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/duration.py'
    (assets / 'installed-files.json').write_text(json.dumps([
        {'path': target, 'kind': 'file'}]))
    external = tmp_path / 'untouched'
    external.write_bytes(b'original product bytes')
    def package_command(argv, **kwargs):
        if argv[1] == '--raw-extract':
            destination = qualification.Path(argv[3]) / target.removeprefix('/')
            destination.parent.mkdir(parents=True)
            if link:
                destination.symlink_to(external)
            else:
                destination.write_bytes(external.read_bytes())
        else:
            assert argv[1] == '--build'
            root = qualification.Path(argv[2])
            qualification.Path(argv[3]).write_bytes(
                (root / target.removeprefix('/')).read_bytes())
        return b''
    commands = Mock()
    commands.run.side_effect = package_command
    if link:
        with pytest.raises(Exception, match='unsafe-product-copy'):
            qualification.changed_product(tmp_path, assets, commands)
        assert commands.run.call_count == 1
    else:
        changed = qualification.changed_product(tmp_path, assets, commands)
        assert (changed / 'package.deb').read_bytes() != external.read_bytes()
        assert commands.run.call_args.args[0][1] == '--build'
        assert commands.run.call_count == 2
    assert external.read_bytes() == b'original product bytes'
    assert (assets / 'package.deb').read_bytes() == b'original archive'


def test_product_probe_refuses_non_regular_manifest_before_package_commands(tmp_path):
    (tmp_path / 'installed-files.json').write_text(json.dumps([{
        'path': '/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/duration.py',
        'kind': 'symlink'}]))
    commands = Mock()
    with pytest.raises(Exception, match='product-mutation-target'):
        qualification.changed_product(tmp_path, tmp_path, commands)
    commands.run.assert_not_called()


@pytest.fixture
def capture(tmp_path, monkeypatch):
    events = []
    lease = MagicMock()
    lease.state = {'baseline_sha256': 'c' * 64}
    lease.installed_name = 'onpc-v9.8.7'
    lease.installed_xml = '<domainsnapshot/>'
    lease.installed_online = True
    lease.prepare.side_effect = lambda: events.append('prepare')
    lease.stop.side_effect = lambda: events.append('stop')
    suite = Mock(lease=lease)
    source = Mock()
    source.domain.name.return_value = 'onpc-Ubuntu26.04'
    suite.acquire.return_value = source, Mock(), lease
    suite.prepare_installed.side_effect = lambda *a, **kw: events.append('capture') or True
    suite.close.side_effect = lambda: events.append('close')
    monkeypatch.setattr(qualification, 'Suite', lambda _: suite)
    monkeypatch.setattr(qualification.system, 'stage_assets', Mock())
    monkeypatch.setattr(qualification.system, 'artifact_source', lambda path: path)
    monkeypatch.setattr(qualification.system.baseline, 'digest', lambda _: 'd' * 64)
    monkeypatch.setattr(qualification, 'preflight_source', lambda _: {'source_sha256': 'a' * 64})
    monkeypatch.setattr(qualification.installed_setup, 'snapshot_inputs',
                        lambda _: SimpleNamespace(files={'system_guest.py': b'helper'}))
    monkeypatch.setattr(qualification, 'audit_baseline',
                        lambda *_: events.append('baseline-audit') or {'clean': True})
    monkeypatch.setattr(qualification, 'qualify_identities', lambda *_: {'identities': True})
    monkeypatch.setattr(qualification.online_snapshot, 'load', lambda *_: {'run': 'b' * 32})
    monkeypatch.setattr(qualification.online_snapshot, 'restore',
                        lambda *_: events.append('online-restore') or 'guest-address')
    monkeypatch.setattr(qualification.online_snapshot, 'saved_transport',
                        lambda *_: events.append('saved-ssh') or Mock())
    monkeypatch.setattr(qualification, 'audit_online',
                        lambda *_: events.append('online-audit') or {'clean': True})
    return suite, lease, events


def test_real_shared_capture_and_restore_branches_precede_owned_close(tmp_path, capture):
    suite, lease, events = capture
    result = qualification.qualify(tmp_path, tmp_path / 'input')
    assert events == ['prepare', 'baseline-audit', 'stop', 'capture', 'stop', 'prepare',
                      'online-restore', 'saved-ssh', 'online-audit', 'close']
    assert suite.prepare_installed.call_args.kwargs == {
        'root': qualification.ROOT, 'overwrite': True, 'mode': 'online'}
    assert result['owned_baseline_restoration_verified'] is True
    assert result['online_app']['snapshot'] == 'onpc-v9.8.7'
    lease.__exit__.assert_called_once()
    suite.close.assert_called_once_with()


@pytest.mark.parametrize('failure', ['baseline', 'capture', 'credentials', 'audit'])
def test_failures_keep_diagnostics_and_close_existing_owned_lease(
        tmp_path, monkeypatch, capture, failure):
    suite, lease, events = capture
    error = RuntimeError('deliberate owned qualification failure')
    if failure == 'baseline':
        monkeypatch.setattr(qualification, 'audit_baseline', Mock(side_effect=error))
    elif failure == 'capture':
        suite.prepare_installed.side_effect = error
    elif failure == 'credentials':
        monkeypatch.setattr(qualification.online_snapshot, 'load', lambda *_: None)
    else:
        monkeypatch.setattr(qualification, 'audit_online', Mock(side_effect=error))
    with pytest.raises(Exception):
        qualification.qualify(tmp_path, tmp_path / 'input')
    assert (tmp_path / 'private/controller-error.txt').is_file()
    assert 'Traceback' in (tmp_path / 'private/controller-error.txt').read_text()
    suite.close.assert_called_once_with()
    lease.__exit__.assert_called_once()
    assert events[-1] == 'close'


def test_other_target_refuses_before_any_vm_mutation(tmp_path, capture):
    suite, lease, events = capture
    suite.acquire.return_value[0].domain.name.return_value = 'onpc-Fedora44'
    with pytest.raises(Exception, match='target-not-qualified'):
        qualification.qualify(tmp_path, tmp_path / 'input')
    lease.__enter__.assert_not_called()
    lease.prepare.assert_not_called()
    assert events == ['close']


def test_main_requires_canonical_target_before_allocation(monkeypatch):
    monkeypatch.setattr(qualification.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(qualification.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name='onpc-Fedora44'))
    allocate = Mock(side_effect=AssertionError('allocation should not happen'))
    monkeypatch.setattr(qualification, 'allocate', allocate)
    assert qualification.main(assets='unused') == 1
    allocate.assert_not_called()
