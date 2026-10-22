"""Snapshot qualification boundaries with private records and VM doubles only."""
from collections import Counter
import hashlib
import io
import json
import os
import stat
import sys
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


def test_native_readiness_requires_active_service_and_readable_database():
    transport = Mock()
    vendor = 'debdb /usr/bin/vendor-tool 17 ' + 'a' * 64
    product = 'debdb /usr/lib/oh-no-parent-control/child 23 ' + 'b' * 64
    transport.call.side_effect = [b'active\n', (vendor + '\n' + product + '\n').encode()]
    report, preserved = qualification.audit_native(transport, {'/opt/fixture'},
        {'/usr/lib/oh-no-parent-control/child'})
    assert report['service_active'] is True and report['database_readable'] is True
    assert report['vendor_rows'] == report['product_rows'] == 1
    assert preserved == Counter({vendor: 1})
    assert transport.call.call_args.args[0] == ['/usr/sbin/fapolicyd-cli', '--dump-db']
    transport.call.reset_mock()
    transport.call.side_effect = [b'inactive\n']
    with pytest.raises(Exception, match='native-service-inactive'):
        qualification.audit_native(transport, set())
    assert transport.call.call_count == 1
    transport.call.side_effect = [b'active\n', RuntimeError('mdb_env_open failed, error 2')]
    with pytest.raises(RuntimeError, match='mdb_env_open'):
        qualification.audit_native(transport, set())


def test_native_database_rejects_fixture_trust_and_empty_vendor_inventory():
    fixture = ('filedb /opt/onpc-test-fixtures-trusted-hard/native-fixture 17 ' + 'a' * 64)
    with pytest.raises(Exception, match='native-fixture-trust-retained'):
        qualification.native_rows((fixture + '\n').encode(),
            {'/opt/onpc-test-fixtures-trusted-hard/native-fixture'}, set())
    product = 'debdb /usr/lib/oh-no-parent-control/child 23 ' + 'b' * 64
    with pytest.raises(Exception, match='vendor-trust-missing'):
        qualification.native_rows((product + '\n').encode(), set(),
            {'/usr/lib/oh-no-parent-control/child'})
    with pytest.raises(Exception, match='native-database-size'):
        qualification.native_rows(b'', set(), set())
    with pytest.raises(Exception, match='native-database-row'):
        qualification.native_rows(b'invalid database line\n', set(), set())


@pytest.mark.parametrize('change', [None, 'bytes', 'mode', 'symlink', 'inventory'])
def test_live_policy_reader_checks_actual_bytes_metadata_and_inventory(tmp_path, monkeypatch, change):
    names = ['/etc/fapolicyd/rules.d/95-allow-open.rules',
             '/var/lib/onpc-baseline-native-rules.json']
    program = qualification.NATIVE_POLICY_AUDIT
    expected = {}
    for index, name in enumerate(names):
        path = tmp_path / str(index)
        data = b'qualified vendor source or receipt'
        path.write_bytes(data)
        info = path.stat()
        expected[str(path)] = {'sha256': hashlib.sha256(data).hexdigest(),
            'mode': stat.S_IMODE(info.st_mode), 'uid': os.getuid(), 'gid': os.getgid()}
        program = program.replace(name, str(path))
    path = tmp_path / '0'
    if change == 'bytes':
        path.write_bytes(b'changed')
    elif change == 'mode':
        path.chmod(0o400)
    elif change == 'symlink':
        path.unlink()
        path.symlink_to(tmp_path / '1')
    elif change == 'inventory':
        expected.pop(str(path))
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(expected)))
    if change is None:
        exec(compile(program, '<native-policy-read-only-probe>', 'exec'), {})
    else:
        with pytest.raises(AssertionError, match='native-policy-'):
            exec(compile(program, '<native-policy-read-only-probe>', 'exec'), {})


def test_product_rows_are_scoped_to_actual_install_manifest(tmp_path):
    manifest = tmp_path / 'installed-files.json'
    manifest.write_text(json.dumps([
        {'path': '/usr/lib/oh-no-parent-control/child', 'kind': 'file'},
        {'path': '/etc/oh-no-parent-control', 'kind': 'directory'}]))
    assert qualification.installed_product_paths(tmp_path) == {
        '/usr/lib/oh-no-parent-control/child', '/etc/oh-no-parent-control'}
    manifest.write_text(json.dumps([{'path': 'relative/path', 'kind': 'file'}]))
    with pytest.raises(Exception, match='product-manifest'):
        qualification.installed_product_paths(tmp_path)


def test_package_inventory_uses_native_binary_package_identities_and_ignores_removed_configs():
    transport = Mock()
    transport.call.return_value = b'libvendor:amd64\t1:2.3-1\tinstalled\nold\t1\tconfig-files\n'
    assert qualification.package_inventory(transport) == {'libvendor:amd64': '1:2.3-1'}
    assert transport.call.call_args.args[0][:2] == ['/usr/bin/dpkg-query', '-W']


@pytest.mark.parametrize('raw', [b'', b'bad row\n', b'a\t1\tunpacked\n',
    b'--argument\t1\tinstalled\n', b'a\t1\tinstalled\na\t1\tinstalled\n'])
def test_package_inventory_refuses_unsafe_ambiguous_or_incomplete_state(raw):
    transport = Mock()
    transport.call.return_value = raw
    with pytest.raises(Exception, match='package-inventory'):
        qualification.package_inventory(transport)


@pytest.mark.parametrize('fault', [None, 'removed-row', 'changed-row', 'duplicate-lost',
                                 'foreign-addition', 'file-trust-addition', 'no-package-change',
                                 'package-removed', 'unsafe-package-file'])
def test_vendor_preservation_authenticates_only_package_owned_additions(fault):
    original = 'debdb /usr/bin/vendor 17 ' + 'a' * 64
    addition = 'debdb /usr/bin/dependency 23 ' + 'b' * 64
    before = Counter({original: 2})
    after = before + Counter({addition: 1})
    old_packages = {'vendor:amd64': '1'}
    new_packages = old_packages | {'dependency': '2'}
    transport = Mock()
    transport.call.return_value = b'/.\n/usr\n\n/.\n/usr/bin\n/usr/bin/dependency\n\n'
    expected = 'unowned-vendor-trust-added'
    if fault == 'removed-row':
        after = Counter({addition: 1})
        expected = 'vendor-trust-changed'
    elif fault == 'changed-row':
        after = Counter({original.replace('17', '18', 1): 2, addition: 1})
        expected = 'vendor-trust-changed'
    elif fault == 'duplicate-lost':
        after = Counter({original: 1, addition: 1})
        expected = 'vendor-trust-changed'
    elif fault == 'foreign-addition':
        after['debdb /foreign/path 1 ' + 'c' * 64] = 1
    elif fault == 'file-trust-addition':
        after[addition.replace('debdb', 'filedb')] = 1
    elif fault == 'no-package-change':
        new_packages = old_packages
    elif fault == 'package-removed':
        new_packages = {'dependency': '2'}
        expected = 'vendor-package-removed'
    elif fault == 'unsafe-package-file':
        transport.call.return_value += b'/usr/../foreign\n'
        expected = 'package-file-inventory'
    if fault is None:
        value = qualification.verify_vendor_preservation(
            transport, before, after, old_packages, new_packages)
        assert value == {'original_vendor_rows_preserved': True, 'original_vendor_rows': 2,
                         'additional_vendor_rows': 1, 'installed_or_updated_packages': {'dependency': '2'}}
        assert transport.call.call_args.args[0] == ['/usr/bin/dpkg-query', '-L', 'dependency']
    else:
        with pytest.raises(Exception, match=expected):
            qualification.verify_vendor_preservation(
                transport, before, after, old_packages, new_packages)


def test_baseline_native_probe_uses_observation_only_guarded_ssh(tmp_path, monkeypatch):
    events = []
    suite = Mock()
    suite.source.uuid = 'a' * 36
    suite.lease.state = {'run': 'b' * 32}
    suite.lease.view.domain_id = 7
    monkeypatch.setattr(qualification.system, 'bootstrap',
        lambda *args, **kwargs: events.append(('bootstrap', kwargs)) or 'ssh-ed25519 host-key')
    monkeypatch.setattr(qualification.system, 'address',
                        lambda *_: events.append('address') or '192.168.122.10')
    suite.lease.start.side_effect = lambda: events.append('start')
    transport = Mock()
    def make_transport(config, commands, guard, lease):
        events.append(('transport', config))
        guard(None)
        return transport
    monkeypatch.setattr(qualification, 'Transport', make_transport)
    result = qualification.baseline_transport(suite, tmp_path)
    assert result is transport
    assert events[0] == ('bootstrap', {'observation_only': True, 'environment_only': True})
    assert events[1:3] == ['start', 'address']
    assert events[3][1]['domain_id'] == 7
    assert (tmp_path / 'baseline-observation/known-hosts').read_text() == (
        '192.168.122.10 ssh-ed25519 host-key\n')
    assert (tmp_path / 'baseline-observation/input/selected-inputs.json').is_file()
    suite.lease.guard.assert_called_once_with()
    transport.probe_ready.assert_called_once_with()


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
                        lambda *_: events.append('baseline-audit') or {'clean': True, 'native_policy': {}})
    monkeypatch.setattr(qualification, 'baseline_transport',
                        lambda *_: events.append('baseline-ssh') or Mock())
    monkeypatch.setattr(qualification, 'audit_native',
                        lambda *args: (events.append('native-audit') or
                                      ({'service_active': True, 'database_readable': True,
                                        'product_rows': 0}, Counter({'vendor-row': 1}))))
    monkeypatch.setattr(qualification, 'installed_product_paths', lambda _: set())
    monkeypatch.setattr(qualification, 'package_inventory', lambda _: {'vendor': '1'})
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
    assert events == ['prepare', 'baseline-audit', 'baseline-ssh', 'native-audit', 'stop',
                      'capture', 'stop', 'prepare', 'online-restore', 'saved-ssh',
                      'online-audit', 'native-audit', 'close']
    assert suite.prepare_installed.call_args.kwargs == {
        'root': qualification.ROOT, 'overwrite': True, 'mode': 'online'}
    assert result['owned_baseline_restoration_verified'] is True
    assert result['online_app']['snapshot'] == 'onpc-v9.8.7'
    assert result['baseline']['native']['service_active'] is True
    assert result['online_app']['native']['database_readable'] is True
    lease.__exit__.assert_called_once()
    suite.close.assert_called_once_with()


@pytest.mark.parametrize('failure', ['baseline', 'native', 'capture', 'credentials', 'audit'])
def test_failures_keep_diagnostics_and_close_existing_owned_lease(
        tmp_path, monkeypatch, capture, failure):
    suite, lease, events = capture
    error = RuntimeError('deliberate owned qualification failure')
    if failure == 'baseline':
        monkeypatch.setattr(qualification, 'audit_baseline', Mock(side_effect=error))
    elif failure == 'native':
        monkeypatch.setattr(qualification, 'audit_native', Mock(side_effect=error))
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


def test_vendor_database_drift_refuses_app_capture_and_closes_owned_lease(
        tmp_path, monkeypatch, capture):
    suite, lease, events = capture
    inventories = iter([({'product_rows': 0}, Counter({'vendor': 1})),
                        ({'product_rows': 1}, Counter({'changed-vendor': 1}))])
    monkeypatch.setattr(qualification, 'audit_native', lambda *_: next(inventories))
    with pytest.raises(Exception, match='vendor-trust-changed'):
        qualification.qualify(tmp_path, tmp_path / 'input')
    suite.close.assert_called_once_with()
    lease.__exit__.assert_called_once()


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
