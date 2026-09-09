"""Host-safe guard/transport tests; real temporary files, no live VM operations."""

import copy
import hashlib
import json
import os
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import pytest
from tests.support.vm_baseline import rig
from tests.support.vm_runner import UUID, RUN, INVENTORIES, xml, write_junit_results, lease_rig

import system_runner as runner
import system_guest as guest



def test_run_ledger_accumulates_monotonic_stage_time_and_preserves_first_failure(capsys):
    clock = iter((10.0, 10.25, 20.0, 20.75))
    ledger = runner.RunLedger(monotonic=lambda: next(clock))
    with ledger.measure('test'):
        pass
    with ledger.measure('test'):
        pass
    ledger.fail_outcome('product', 'pytest:failed:installed')
    ledger.fail_outcome('product', 'pytest:failed:authorization')
    ledger.fail_outcome('collection', 'collection:missing')
    ledger.pass_outcome('product')

    data = ledger.data()
    assert data['stage_durations_seconds'] == {
        'preparation': 0.0, 'bootstrap': 0.0, 'install': 0.0, 'reboot': 0.0,
        'test': 1.0, 'collection': 0.0, 'cleanup': 0.0,
    }
    assert data['outcomes']['product'] == {
        'outcome': 'failed', 'category': 'pytest:failed:installed'}
    assert ledger.first_failure_category == 'pytest:failed:installed'
    assert 'timing:stage=test duration_seconds=0.250' in capsys.readouterr().err


def test_aggregate_category_preserves_pytest_failure_wrapped_by_ssh():
    ledger = runner.RunLedger()
    ledger.fail_outcome('product', 'pytest:failed:authorization')

    assert runner.record_caught_failure(
        ledger, runner.CommandError('command:failed:ssh')) == 'pytest:failed:authorization'
    assert ledger.outcomes['infrastructure'] == {'outcome': 'passed', 'category': None}


def test_bootstrap_normalizes_only_official_deb822_archive_uris():
    sources = '''# URIs: http://us.archive.ubuntu.com/ubuntu/
Types: deb deb-src
URIs: http://us.archive.ubuntu.com/ubuntu/ https://vendor.example/repo
 http://security.ubuntu.com/ubuntu
Suites: resolute resolute-updates resolute-backports resolute-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
Enabled: yes

Types: deb
URIs: https://archive.ubuntu.com.evil.example/ubuntu http://archive.ubuntu.com/other
Signed-By:
 http://archive.ubuntu.com/ubuntu/
'''
    expected = sources.replace(
        'URIs: http://us.archive.ubuntu.com/ubuntu/ https://vendor.example/repo',
        'URIs: https://archive.ubuntu.com/ubuntu/ https://vendor.example/repo').replace(
            ' http://security.ubuntu.com/ubuntu\n', ' https://archive.ubuntu.com/ubuntu/\n')
    assert runner.ubuntu_archive_sources(sources) == expected
    assert runner.ubuntu_archive_sources(expected) == expected


@pytest.mark.parametrize('failure', [False, True])
@pytest.mark.parametrize('observation_only', [False, True])
def test_bootstrap_closes_guest_edits_before_install_and_pins_host_key(tmp_path, failure, observation_only):
    commands, lease, guestfs = Mock(), Mock(), Mock()
    lease.capture.state = {'source': {'layout': {'disk': '/guarded-image'}},
                           'guest': {'preparation_record_sha256': 'e' * 64}}
    lease.state = {'run': RUN, 'baseline_sha256': 'd' * 64}
    lease.source.uuid = UUID
    (tmp_path / 'input').mkdir()
    if not observation_only:
        (tmp_path / 'input/package.deb').write_bytes(b'package')
    (tmp_path / 'input/selected-inputs.json').write_bytes(b'inputs')
    edit, read = Mock(), Mock()
    guestfs.GuestFS.side_effect = [edit, read]
    for g in (edit, read):
        g.inspect_os.return_value = ['/dev/sda2']
        g.inspect_get_mountpoints.return_value = {'/': '/dev/sda2'}
    files = {
        '/etc/apt/sources.list.d/ubuntu.sources': b'URIs: http://us.archive.ubuntu.com/ubuntu/\n',
        '/etc/fstab': b'/dev/sda2 / ext4 defaults 0 1\nData /Data virtiofs defaults 0 0\n',
        '/etc/machine-id': b'b' * 32,
    }
    edit.read_file.side_effect = files.__getitem__
    read.read_file.return_value = b'ssh-ed25519 test-public-key comment'

    def command(args, **kwargs):
        if args[0] == 'virt-customize':
            edit.close.assert_called_once()
            edit.write.assert_any_call('/etc/apt/sources.list.d/ubuntu.sources',
                                       b'URIs: https://archive.ubuntu.com/ubuntu/\n')
            expected = 'openssh-server=1:10.2p1-2ubuntu3.6'
            if not observation_only:
                expected += ',python3-pytest=9.0.2-4'
            assert args[args.index('--install') + 1] == expected
            marker = next(json.loads(c.args[1]) for c in edit.write.call_args_list
                          if c.args[0] == '/etc/onpc-system-test.json')
            assert ('package_sha256' in marker) != observation_only
            if observation_only:
                assert marker['scope'] == 'graphical-observation-only'
            if failure:
                raise runner.CommandError('bootstrap-install-failed')
    commands.run.side_effect = command
    if failure:
        with pytest.raises(runner.CommandError, match='bootstrap-install-failed'):
            runner.bootstrap(commands, lease, tmp_path, guestfs, observation_only=observation_only)
        assert guestfs.GuestFS.call_count == 1
    else:
        assert runner.bootstrap(commands, lease, tmp_path, guestfs,
                                observation_only=observation_only) == 'ssh-ed25519 test-public-key'
        read.add_drive_opts.assert_called_once_with('/guarded-image', format='qcow2', readonly=True)
        read.mount_ro.assert_called_once_with('/dev/sda2', '/')
        read.close.assert_called_once()




def test_isolation_removes_shares_and_spice_transfer_but_preserves_disk():
    root = ET.fromstring(runner.isolated_xml(xml(), UUID, RUN))
    assert root.findtext('uuid') == UUID
    assert root.find('devices/disk/source').get('file') == '/image'
    for name in ('filesystem', 'channel', 'redirdev', 'hostdev'):
        assert not root.findall('devices/' + name)
    assert root.find('devices/graphics/clipboard').get('copypaste') == 'no'
    assert root.find('devices/graphics/filetransfer').get('enable') == 'no'
    assert root.findtext('description') == runner.TAG + RUN


@pytest.mark.parametrize('old,new', [
    ('ubuntu26.04', 'host'), (UUID, 'other'), ('type="qcow2"', 'type="raw"'),
    ('source network="default"', 'source network="bridged"'),
    ('console type="pty"', 'console type="file"'),
    ('</devices>', '<hostdev/></devices>'),
])
def test_refuses_unsupported_or_replaced_vm_layout(old, new):
    with pytest.raises(runner.Error):
        runner.isolated_xml(xml().replace(old, new), UUID, RUN)


def test_active_domain_id_is_required_even_with_same_uuid_and_marker():
    source = Mock()
    layout = runner.baseline.domain_layout(runner.isolated_xml(xml(), UUID, RUN), UUID)
    source.snapshot.return_value = (layout, False)
    domain = source.connection.lookupByName.return_value
    domain.XMLDesc.return_value = runner.isolated_xml(xml(), UUID, RUN)
    domain.ID.return_value = 9
    view = runner.SourceView(source)
    view.run, view.domain_id, view.original_shares = RUN, 8, []
    with pytest.raises(runner.Error, match='domain-replaced'):
        view.snapshot()


def test_source_view_preserves_task12_inventory_contract():
    source = Mock()
    original = runner.baseline.domain_layout(xml(), UUID)
    layout = runner.baseline.domain_layout(runner.isolated_xml(xml(), UUID, RUN), UUID)
    source.snapshot.return_value = (layout, True)
    source.connection.lookupByName.return_value.XMLDesc.return_value = runner.isolated_xml(xml(), UUID, RUN)
    view = runner.SourceView(source)
    view.run, view.original_shares = RUN, original['source_shares']
    assert view.snapshot() == (original, True)


def marker():
    return {'purpose': 'onpc-system-test', 'run': RUN, 'machine_id': 'b' * 32,
            'host_machine_id': 'c' * 32, 'domain_uuid': UUID,
            'baseline_sha256': 'd' * 64, 'preparation_sha256': 'e' * 64,
            'package_sha256': 'f' * 64, 'selected_inputs_sha256': 'a' * 64}


def test_guest_guard_accepts_only_matching_isolated_vm():
    guest.validate_marker(marker(), RUN, 'b' * 32, UUID, ['ext4', 'proc'])


@pytest.mark.parametrize('field,value', [
    ('purpose', 'other'), ('run', 'b' * 32), ('domain_uuid', 'other'),
    ('host_machine_id', 'b' * 32), ('package_sha256', 'invalid'),
    ('selected_inputs_sha256', 'invalid'),
    ('machine_id', 'c' * 32),
])
def test_guest_marker_refuses_host_or_replacement(field, value):
    with pytest.raises(guest.GuestError):
        guest.validate_marker(marker() | {field: value}, RUN, 'b' * 32, UUID, ['ext4'])


@pytest.mark.parametrize('filesystem', ['virtiofs', '9p', 'nfs', 'nfs4', 'cifs', 'fuse.sshfs'])
def test_guest_refuses_host_filesystems(filesystem):
    with pytest.raises(guest.GuestError, match='host-filesystem-exposed'):
        guest.validate_marker(marker(), RUN, 'b' * 32, UUID, ['ext4', filesystem])


def test_asset_tree_rejects_symlink_and_special_file(tmp_path):
    root = tmp_path / 'assets'
    root.mkdir()
    path = root / 'link'
    path.symlink_to(tmp_path)
    with pytest.raises(runner.Error, match='special-file'):
        runner.check_tree(root)
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(runner.Error, match='special-file'):
        runner.check_tree(root)


def test_pytest_command_selects_both_required_tests_without_skips():
    selection = runner.resolve_selection(inventories=INVENTORIES)
    before = runner.pytest_command(RUN, 'installed', selection)
    after = runner.pytest_command(RUN, 'rebooted', selection)
    assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1' in before
    assert before[-1].endswith('::test_first_install_requests_reboot')
    assert after[-1].endswith('::test_reboot_applies_installation')
    assert before[-2] == after[-2]
    assert before[-2].endswith('::test_installed_package')
    assert runner.guest_command(RUN, 'install')[-2:] == [runner.PAYLOAD + '/system_guest.py', 'install']
    authorization = runner.pytest_command(RUN, 'authorization', selection)
    assert authorization[-1].endswith(
        '/test_authorization.py::test_real_selected_parent_authentication[child1]')




def test_host_collection_uses_public_collect_only_without_guest_fixture_execution():
    output = (
        'test_authorization.py::test_method_role_matrix[ListManagedUsers-child1]\n'
        'test_authorization.py::test_real_selected_parent_authentication[child1]\n'
        '2 tests collected in 0.01s\n').encode()
    invoke = Mock(return_value=output)
    assert runner.collect_area_cases('authorization', invoke=invoke) == INVENTORIES['authorization']
    command = invoke.call_args.args[0]
    assert command[:4] == [
        '/usr/bin/env', f'PYTHONPATH={runner.ROOT / "tests/integration"}',
        'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1', 'PYTHONDONTWRITEBYTECODE=1']
    assert '--collect-only' in command
    assert '--noconftest' in command
    assert command[-1].endswith('/tests/system/test_authorization.py')
    assert invoke.call_args.kwargs == {'timeout': 60}


@pytest.mark.parametrize(('result', 'category'), [
    (runner.CommandError('command:failed:env'), 'selection:collection-failed:package'),
    (b'no tests collected in 0.01s\n', 'selection:invalid-registry:package'),
    (b'test_install_smoke.py::duplicate\ntest_install_smoke.py::duplicate\n',
     'selection:invalid-registry:package'),
])
def test_host_collection_rejects_failed_empty_or_duplicate_registries(result, category):
    invoke = Mock(side_effect=result) if isinstance(result, Exception) else Mock(return_value=result)
    with pytest.raises(runner.Error, match=category):
        runner.collect_area_cases('package', invoke=invoke)


def test_authorization_selection_includes_exact_package_phase_prerequisites():
    case = 'test_method_role_matrix[ListManagedUsers-child1]'
    selection = runner.resolve_selection('authorization', case, inventories=INVENTORIES)
    assert selection.scope == 'partial'
    assert selection.phases == ('installed', 'rebooted', 'authorization')
    assert [(item.phase, item.case_id, item.prerequisite) for item in selection.executions] == [
        ('installed', 'test_installed_package', True),
        ('installed', 'test_first_install_requests_reboot', True),
        ('rebooted', 'test_installed_package', True),
        ('rebooted', 'test_reboot_applies_installation', True),
        ('authorization', case, False),
    ]
    assert selection.prerequisites == (
        'accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap', 'package-install',
        'installed-phase', 'guest-reboot', 'boot-readiness', 'rebooted-phase',
        'authorization-accounts',
    )
    assert selection.available == {'authorization': INVENTORIES['authorization']}


def test_password_case_registers_its_additional_fixture_prerequisite():
    selection = runner.resolve_selection(
        'authorization', 'test_real_selected_parent_authentication[child1]',
        inventories=INVENTORIES)
    assert selection.prerequisites[-1] == 'fixture-passwords'


def test_remote_fixture_is_declared_for_selected_and_full_authorization_runs():
    case = 'test_remote_accounts_are_excluded'
    inventories = {**INVENTORIES, 'authorization': (*INVENTORIES['authorization'], case)}
    for selected in (case, None):
        selection = runner.resolve_selection('authorization', selected, inventories=inventories)
        assert 'remote-ldap-nss-fixtures' in selection.prerequisites
    assert ('tests/integration/system_remote_accounts.py', 'system_remote_accounts.py') in (
        runner.AREA_SELECTED_HELPERS['authorization'])


@pytest.mark.parametrize('case', (
    'test_administrator_eligibility_predicates',
    'test_authenticated_request_rejects_deleted_target',
    'test_requester_disconnect_during_approval',
    'test_request_rejects_locked_approver_during_authentication[child1]',
    'test_request_rejects_locked_approver_during_authentication[kiosk]',
))
def test_inflight_case_registers_passwords_and_exact_execution(case):
    inventories = {**INVENTORIES, 'authorization': (*INVENTORIES['authorization'], case)}
    selection = runner.resolve_selection('authorization', case, inventories=inventories)
    assert selection.prerequisites[-1] == 'fixture-passwords'
    assert [(item.phase, item.case_id) for item in selection.executions
            if not item.prerequisite] == [('authorization', case)]


def test_selected_input_digest_is_stable_and_selector_sensitive(tmp_path):
    first = runner.resolve_selection(
        'package', 'test_first_install_requests_reboot', inventories=INVENTORIES)
    second = runner.resolve_selection(
        'package', 'test_reboot_applies_installation', inventories=INVENTORIES)
    first_digest = runner.stage_selected_inputs(first, tmp_path / 'first')
    repeated_digest = runner.stage_selected_inputs(first, tmp_path / 'repeated')
    second_digest = runner.stage_selected_inputs(second, tmp_path / 'second')

    assert first_digest == repeated_digest
    assert first_digest != second_digest
    identity = json.loads((tmp_path / 'first/selected-inputs.json').read_text())
    assert identity['selection']['test'] == 'test_first_install_requests_reboot'
    assert set(identity['files']) == {
        'system_guest.py', 'owned_commands.py', 'guest/redact.py', 'pytest.ini',
        'test_install_smoke.py',
    }


def test_authorization_selected_inputs_include_prerequisite_test_and_helper(tmp_path):
    selection = runner.resolve_selection(
        'authorization', 'test_method_role_matrix[ListManagedUsers-child1]',
        inventories=INVENTORIES)
    digest = runner.stage_selected_inputs(selection, tmp_path)
    identity = json.loads((tmp_path / 'selected-inputs.json').read_text())

    assert digest == hashlib.sha256((tmp_path / 'selected-inputs.json').read_bytes()).hexdigest()
    assert {'test_install_smoke.py', 'test_authorization.py', 'system_caller.py'} <= set(
        identity['files'])
    assert identity['selection']['executions'][-1]['case_id'] == selection.test


def test_full_selection_stages_shared_helpers_once(tmp_path):
    selection = runner.resolve_selection(inventories=INVENTORIES)
    runner.stage_selected_inputs(selection, tmp_path)
    identity = json.loads((tmp_path / 'selected-inputs.json').read_text())
    for name in ('system_caller.py', 'system_assertions.py', 'system_accounts.py'):
        assert identity['files'][name] == {
            'source': 'tests/integration/' + name,
            'sha256': hashlib.sha256((runner.ROOT / 'tests/integration' / name).read_bytes()).hexdigest(),
        }
        assert (tmp_path / name).read_bytes() == (runner.ROOT / 'tests/integration' / name).read_bytes()
    assert {item['area'] for item in identity['selection']['executions']} == set(INVENTORIES)


def test_conflicting_helper_targets_are_refused_before_any_staging(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.AREA_SELECTED_HELPERS, 'enforcement', (
        ('tests/integration/system_enforcement.py', 'system_caller.py'),
    ))
    selection = runner.resolve_selection(inventories=INVENTORIES)
    with pytest.raises(runner.Error, match='selection:duplicate-input-target'):
        runner.stage_selected_inputs(selection, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_pre_reboot_package_case_omits_unneeded_later_phases():
    selection = runner.resolve_selection(
        'package', 'test_first_install_requests_reboot', inventories=INVENTORIES)
    assert selection.phases == ('installed',)
    assert [(item.phase, item.case_id) for item in selection.executions] == [
        ('installed', 'test_first_install_requests_reboot')]
    assert 'guest-reboot' not in selection.prerequisites


@pytest.mark.parametrize(('area', 'test', 'category'), [
    ('missing', None, 'selection:unknown-area'),
    ('', None, 'selection:empty-area'),
    ('authorization', '', 'selection:empty-test'),
    (None, 'test_installed_package', 'selection:test-requires-area'),
    ('authorization', 'test_installed_package', 'selection:incompatible-test'),
    ('authorization', 'test_missing', 'selection:unknown-test'),
])
def test_invalid_or_incompatible_selections_fail_closed(area, test, category):
    with pytest.raises(runner.Error, match=category):
        runner.resolve_selection(area, test, inventories=INVENTORIES)


def test_resolution_rejects_an_incomplete_registry():
    with pytest.raises(runner.Error, match='selection:incomplete-registry'):
        runner.resolve_selection('package', inventories={'package': INVENTORIES['package']})


def test_list_mode_returns_before_artifact_root_tool_or_vm_checks(monkeypatch, capsys):
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which', Mock(side_effect=AssertionError('tool probe ran')))
    case = 'test_method_role_matrix[ListManagedUsers-child1]'
    assert runner.main(['--list', '--area', 'authorization', '--test', case]) == 0
    output = capsys.readouterr().out
    assert 'mode: list-only (no root, artifacts, VM, or guest fixtures)' in output
    assert f'authorization::{case} [selected]' in output
    assert 'installed::test_installed_package [prerequisite]' in output


def test_selected_execution_reaches_normal_guarded_prerequisite_checks(monkeypatch, capsys):
    monkeypatch.setattr(runner.baseline.guest_contract, 'CHECKOUT', runner.ROOT)
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which', Mock(return_value=None))
    monkeypatch.setattr(runner.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(runner.os, 'getegid', lambda: 0)
    assert runner.main(['--area', 'authorization']) == 1
    output = capsys.readouterr().err
    assert 'selection:scope=partial phases=3 executions=6' in output
    assert 'tools:missing' in output
    assert 'selection:execution-not-implemented' not in output


@pytest.mark.parametrize('missing', ['dpkg-deb', 'dpkg-query'])
def test_check_tools_rejects_missing_package_inspection_tool(monkeypatch, capsys, missing):
    monkeypatch.setattr(runner.baseline.guest_contract, 'CHECKOUT', runner.ROOT)
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which',
                        lambda name: None if name == missing else '/usr/bin/' + name)
    with patch.object(runner.tempfile, 'mkdtemp') as mkdir, \
            patch.object(runner, 'Lease') as lease:
        assert runner.main(['--check-tools']) == 1
    assert f'tools:missing:{missing}; run ./setup.sh' in capsys.readouterr().err
    mkdir.assert_not_called()
    lease.assert_not_called()


@pytest.mark.parametrize(('failure', 'category'), [
    (FileNotFoundError('private input path'), 'assets:source-missing'),
    (PermissionError('private input path'), 'assets:source-inaccessible'),
    (OSError('private input path'), 'assets:source-unavailable'),
])
def test_unavailable_artifacts_fail_before_storage_or_vm_access(
        monkeypatch, capsys, failure, category):
    monkeypatch.setattr(runner.baseline.guest_contract, 'CHECKOUT', runner.ROOT)
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(runner.importlib, 'import_module', Mock())
    monkeypatch.setattr(runner.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(runner.os, 'getegid', lambda: 0)
    with patch.object(runner, 'check_tree', side_effect=failure), \
            patch.object(runner.tempfile, 'mkdtemp') as mkdir, \
            patch.object(runner, 'Lease') as lease:
        assert runner.main(['--artifacts', str(runner.ROOT)]) == 1
    output = capsys.readouterr().err
    assert category in output
    assert 'private input path' not in output
    assert 'unexpected-failure' not in output
    mkdir.assert_not_called()
    lease.assert_not_called()


def test_artifact_source_resolves_valid_input_and_classifies_missing_path(tmp_path):
    assert runner.artifact_source(tmp_path) == tmp_path.resolve()
    with pytest.raises(runner.Error, match='assets:source-missing'):
        runner.artifact_source(tmp_path / 'absent')
    file = tmp_path / 'regular-file'
    file.write_text('payload')
    with pytest.raises(runner.Error, match='assets:directory'):
        runner.artifact_source(file)


def test_selected_pytest_command_forwards_only_resolved_case_and_prerequisites():
    case = 'test_method_role_matrix[ListManagedUsers-child1]'
    selection = runner.resolve_selection('authorization', case, inventories=INVENTORIES)
    command = runner.pytest_command(RUN, 'authorization', selection)
    assert command[-1] == f'{runner.PAYLOAD}/test_authorization.py::{case}'
    assert not any('real_selected_parent_authentication' in item for item in command)
    installed = runner.pytest_command(RUN, 'installed', selection)
    assert installed[-2:] == [
        f'{runner.PAYLOAD}/test_install_smoke.py::test_installed_package',
        f'{runner.PAYLOAD}/test_install_smoke.py::test_first_install_requests_reboot',
    ]


def test_readiness_timeout_is_bounded_without_fixed_sleep(monkeypatch):
    source = Mock()
    source.domain.interfaceAddresses.return_value = {}
    clock = iter([0, 0, 2, 2])
    monkeypatch.setattr(runner.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(runner.threading, 'Event', Mock)
    with pytest.raises(runner.Error, match='readiness-timeout'):
        runner.address(source, timeout=1)
    source.api.virEventRemoveTimeout.assert_called_once()


def test_install_assertion_failure_collects_evidence_without_reboot_or_retry(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    failure = runner.CommandError('test-assertion-failed')
    vm.call.side_effect = [b'', failure, b'']
    with pytest.raises(runner.CommandError, match='test-assertion-failed'):
        runner.installed_run(vm, lease, tmp_path,
                             runner.resolve_selection(inventories=INVENTORIES))
    assert vm.call.call_count == 3
    assert vm.call.call_args.args[0] == runner.guest_command(RUN, 'collect', 'failed')
    vm.reboot.assert_not_called()
    assert vm.copy.call_args.args[0] is True


def test_collection_failure_does_not_hide_original_connection_failure(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.ready.side_effect = runner.CommandError('original-connection-failed')
    vm.call.side_effect = runner.CommandError('collection-failed')
    ledger = runner.RunLedger()
    with pytest.raises(runner.CommandError, match='original-connection-failed'):
        runner.installed_run(vm, lease, tmp_path,
                             runner.resolve_selection(inventories=INVENTORIES), ledger)
    assert ledger.outcomes['infrastructure'] == {
        'outcome': 'failed', 'category': 'original-connection-failed'}
    assert ledger.outcomes['collection'] == {
        'outcome': 'failed', 'category': 'collection-failed'}
    vm.reboot.assert_not_called()


def test_collection_failure_does_not_hide_original_pytest_failure_or_its_domain(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.commands.last_returncode = 1
    original = runner.CommandError('command:failed:ssh')
    vm.call.side_effect = [b'', original, runner.CommandError('command:failed:ssh')]
    selection = runner.resolve_selection(
        'package', 'test_first_install_requests_reboot', inventories=INVENTORIES)
    ledger = runner.RunLedger()

    with pytest.raises(runner.CommandError, match='command:failed:ssh') as caught:
        runner.installed_run(vm, lease, tmp_path, selection, ledger)

    assert caught.value is original
    assert ledger.outcomes['product'] == {
        'outcome': 'failed', 'category': 'pytest:failed:installed'}
    assert ledger.outcomes['collection'] == {
        'outcome': 'failed', 'category': 'command:failed:ssh'}
    assert ledger.durations['install'] >= 0
    assert ledger.durations['test'] >= 0
    assert ledger.durations['collection'] >= 0




def test_all_pytest_phases_reconcile_exact_unskipped_identities(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    selection = runner.resolve_selection(inventories=INVENTORIES)
    write_junit_results(tmp_path, selection)
    ledger = runner.RunLedger()
    result = runner.installed_run(vm, lease, tmp_path, selection, ledger)
    assert result['authorization'] == (
        ('authorization', 'test_method_role_matrix[ListManagedUsers-child1]'),
        ('authorization', 'test_real_selected_parent_authentication[child1]'),
    )
    assert vm.reboot.call_count == 2
    assert vm.call.call_count == 9
    assert vm.call.call_args_list[2].args[0] == runner.guest_command(RUN, 'collect', 'installed')
    assert ledger.outcomes['product'] == {'outcome': 'passed', 'category': None}
    assert ledger.outcomes['collection'] == {'outcome': 'passed', 'category': None}


@pytest.mark.parametrize(('fault', 'category'), [
    ('missing', 'pytest:missing-extra-or-duplicate-tests:authorization'),
    ('extra', 'pytest:missing-extra-or-duplicate-tests:authorization'),
    ('duplicate', 'pytest:missing-extra-or-duplicate-tests:authorization'),
    ('failure', 'pytest:failed-or-skipped-tests:authorization'),
    ('skipped', 'pytest:failed-or-skipped-tests:authorization'),
    ('identity', 'pytest:incorrect-test-identity:authorization'),
])
def test_junit_reconciliation_rejects_incomplete_or_unhealthy_identities(tmp_path, fault, category):
    selection = runner.resolve_selection('authorization', inventories=INVENTORIES)
    write_junit_results(tmp_path, selection, fault)
    with pytest.raises(runner.Error, match=category):
        runner.reconcile_junit(tmp_path, 'authorization', selection)


@pytest.mark.parametrize('case', INVENTORIES['enforcement'])
def test_enforcement_selection_freezes_helpers_and_only_package_prerequisites(tmp_path, case):
    selection = runner.resolve_selection('enforcement', case, inventories=INVENTORIES)
    assert selection.phases == ('installed', 'rebooted', 'enforcement')
    assert [(item.area, item.case_id) for item in selection.executions if not item.prerequisite] == [
        ('enforcement', case)]
    assert len(selection.executions) == 5
    assert 'native-enforcement-fixture' in selection.prerequisites
    assert 'authorization-accounts' not in selection.prerequisites
    digest = runner.stage_selected_inputs(selection, tmp_path)
    manifest = json.loads((tmp_path / 'selected-inputs.json').read_text())
    assert len(digest) == 64
    assert {'test_enforcement.py', 'system_enforcement.py', 'system_caller.py',
            'test_install_smoke.py'} <= manifest['files'].keys()
    assert 'test_authorization.py' not in manifest['files']
    command = runner.pytest_command(RUN, 'enforcement', selection)
    assert command[-1] == f'{runner.PAYLOAD}/test_enforcement.py::{case}'


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'failure', 'skipped', 'identity'])
def test_enforcement_results_must_match_executed_case(tmp_path, fault):
    selection = runner.resolve_selection('enforcement', inventories=INVENTORIES)
    write_junit_results(tmp_path, selection, fault)
    with pytest.raises(runner.Error, match=':enforcement'):
        runner.reconcile_junit(tmp_path, 'enforcement', selection)


def test_enforcement_failure_keeps_product_attribution_and_collects(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.commands.last_returncode = 1
    selection = runner.resolve_selection('enforcement', inventories=INVENTORIES)
    failed_command = runner.pytest_command(RUN, 'enforcement', selection)

    def invoke(command, **kwargs):
        if command == failed_command:
            raise runner.CommandError('command:failed:ssh')
        return b''

    vm.call.side_effect = invoke
    ledger = runner.RunLedger()
    with pytest.raises(runner.CommandError, match='command:failed:ssh'):
        runner.installed_run(vm, lease, tmp_path, selection, ledger)
    assert ledger.outcomes['product'] == {
        'outcome': 'failed', 'category': 'pytest:failed:enforcement'}
    assert vm.call.call_args.args[0] == runner.guest_command(RUN, 'collect', 'failed')
    assert sum(call.args[0] == failed_command for call in vm.call.call_args_list) == 1


def test_selected_pre_reboot_execution_omits_reboot_and_later_phases(tmp_path):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    selection = runner.resolve_selection(
        'package', 'test_first_install_requests_reboot', inventories=INVENTORIES)
    write_junit_results(tmp_path, selection)
    assert runner.installed_run(vm, lease, tmp_path, selection) == {
        'installed': (('package', 'test_first_install_requests_reboot'),),
    }
    vm.reboot.assert_not_called()
    commands = [call.args[0] for call in vm.call.call_args_list]
    assert runner.pytest_command(RUN, 'installed', selection) in commands
    assert all('rebooted.xml' not in item and 'authorization.xml' not in item
               for command in commands for item in command)


def test_partial_selection_evidence_records_expected_and_executed_ids(tmp_path):
    case = 'test_method_role_matrix[ListManagedUsers-child1]'
    selection = runner.resolve_selection('authorization', case, inventories=INVENTORIES)
    write_junit_results(tmp_path, selection)
    result = runner.selection_evidence(tmp_path, selection)
    assert result['scope'] == 'partial'
    assert result['area'] == 'authorization'
    assert result['test'] == case
    assert result['junit_collection'] == {
        'installed': 'collected', 'rebooted': 'collected', 'authorization': 'collected'}
    assert result['expected_executions'][-1] == {
        'phase': 'authorization', 'area': 'authorization', 'case_id': case,
        'prerequisite': False,
    }
    assert result['executed_cases'][-1] == {
        'phase': 'authorization', 'area': 'authorization', 'case_id': case,
    }


def test_public_evidence_records_stage_timings_and_separate_outcomes(tmp_path):
    selection = runner.resolve_selection(
        'package', 'test_first_install_requests_reboot', inventories=INVENTORIES)
    manifest = {
        'artifacts': {
            'package': {'sha256': 'a' * 64},
            'fixtures': {'sha256': 'b' * 64},
        },
        'source': {'commit': 'test'},
    }
    lease = Mock()
    lease.state = {'baseline_sha256': 'c' * 64, 'phase': 'complete'}
    ledger = runner.RunLedger()
    ledger.durations['preparation'] = 1.25
    ledger.pass_outcome('product')
    ledger.pass_outcome('infrastructure')
    ledger.fail_outcome('collection', 'collection:missing')
    ledger.pass_outcome('cleanup')

    assert runner.evidence(tmp_path, manifest, lease, False, 'collection:missing',
                           selection, 'd' * 64, ledger) == (False, 'collection:missing')

    result = json.loads((tmp_path / 'evidence/result.json').read_text())
    assert result['category'] == 'collection:missing'
    assert result['selected_inputs_sha256'] == 'd' * 64
    assert result['stage_durations_seconds']['preparation'] == 1.25
    assert result['outcomes'] == {
        'product': {'outcome': 'passed', 'category': None},
        'infrastructure': {'outcome': 'passed', 'category': None},
        'collection': {'outcome': 'failed', 'category': 'collection:missing'},
        'cleanup': {'outcome': 'passed', 'category': None},
    }


def test_unsafe_guest_evidence_fails_collection_without_replacing_product_category(tmp_path):
    selection = runner.resolve_selection(
        'package', 'test_first_install_requests_reboot', inventories=INVENTORIES)
    manifest = {
        'artifacts': {
            'package': {'sha256': 'a' * 64},
            'fixtures': {'sha256': 'b' * 64},
        },
        'source': {'commit': 'test'},
    }
    lease = Mock()
    lease.state = {'baseline_sha256': 'c' * 64, 'phase': 'complete'}
    collected = tmp_path / 'guest-results'
    collected.mkdir()
    (collected / 'unsafe').symlink_to(tmp_path)
    ledger = runner.RunLedger()
    ledger.fail_outcome('product', 'pytest:failed:installed')
    ledger.pass_outcome('infrastructure')
    ledger.pass_outcome('collection')
    ledger.pass_outcome('cleanup')

    assert runner.evidence(tmp_path, manifest, lease, False, 'command:failed:ssh',
                           selection, 'd' * 64, ledger) == (False, 'command:failed:ssh')

    result = json.loads((tmp_path / 'evidence/result.json').read_text())
    assert result['category'] == 'command:failed:ssh'
    assert result['outcomes']['product'] == {
        'outcome': 'failed', 'category': 'pytest:failed:installed'}
    assert result['outcomes']['collection'] == {
        'outcome': 'failed', 'category': 'collection:unsafe-or-unavailable-evidence'}
    assert not (tmp_path / 'evidence/guest').exists()


def test_restore_never_requests_boot_or_deletes_snapshot():
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.revalidate = Mock()
    lease.snapshot_xml = 'snapshot'
    snapshot = lease.source.domain.snapshotLookupByName.return_value
    snapshot.getXMLDesc.return_value = 'snapshot'
    lease.restore()
    lease.source.domain.revertToSnapshot.assert_called_once_with(snapshot, 0)
    snapshot.delete.assert_not_called()
    lease.source.domain.create.assert_not_called()


def test_restore_refuses_changed_snapshot():
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.revalidate = Mock()
    lease.snapshot_xml = 'snapshot'
    lease.source.domain.snapshotLookupByName.return_value.getXMLDesc.return_value = 'replaced'
    with pytest.raises(runner.Error, match='snapshot-metadata-changed'):
        lease.restore()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_libvirt_shutting_down_is_active_not_offline():
    api = Mock(VIR_DOMAIN_RUNNING=1, VIR_DOMAIN_SHUTDOWN=4, VIR_DOMAIN_SHUTOFF=5,
               VIR_DOMAIN_XML_INACTIVE=2)
    connection = api.open.return_value
    connection.getURI.return_value = runner.baseline.URI
    domain = connection.lookupByName.return_value
    domain.UUIDString.return_value = UUID
    domain.isPersistent.return_value = True
    domain.hasManagedSaveImage.return_value = False
    domain.state.return_value = (4, 0)
    domain.XMLDesc.return_value = xml()
    domain.blockJobInfo.return_value = {}
    source = runner.baseline.LibvirtSource(api)
    assert source.snapshot()[1] is False
    domain.blockJobInfo.assert_called_once()




def test_full_lease_preserves_baseline_and_restores_original_config(lease_rig):
    lease, current = lease_rig
    baseline_xml = lease.source.baseline()
    with lease:
        original = lease.original_xml
        lease.prepare()
        assert not lease.source.layout['source_shares']
        lease.start()
        assert lease.view.domain_id == 71
    assert lease.state['phase'] == 'complete'
    assert lease.source.off
    assert current['xml'] == original
    assert lease.source.baseline() == baseline_xml
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert lease.fd is None


@pytest.mark.parametrize('fault', [None, 'mismatch', 'interrupt'])
def test_baseline_proof_time_is_recorded_on_success_refusal_and_interruption(lease_rig, fault):
    lease, _ = lease_rig
    clock = iter((10.0, 17.5, 20.0, 20.25))
    ledger = runner.RunLedger(monotonic=lambda: next(clock))
    lease.ledger = ledger
    if fault == 'mismatch':
        lease.capture.verify_snapshot = Mock(return_value={'changed': True})
    elif fault == 'interrupt':
        lease.capture.verify_snapshot = Mock(side_effect=KeyboardInterrupt)
    expected = (pytest.raises(runner.Error, match='baseline:changed') if fault == 'mismatch'
                else pytest.raises(KeyboardInterrupt) if fault == 'interrupt'
                else runner.nullcontext())
    with expected:
        with lease:
            assert ledger.durations['preparation'] == 7.5
    assert ledger.durations['preparation'] == 7.5
    assert lease.fd is None
    lease.source.domain.create.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_interruption_restores_owned_vm_and_preserves_failure(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(KeyboardInterrupt):
        with lease:
            lease.prepare()
            lease.start()
            raise KeyboardInterrupt
    assert lease.state['phase'] == 'complete'
    assert lease.source.off


def test_busy_lease_refuses_without_vm_mutation(lease_rig):
    lease, _ = lease_rig
    with lease:
        another = runner.Lease(lease.source, lease.commands, lease.inspect,
                               directory=lease.directory, anchor=lease.capture.anchor)
        with pytest.raises(runner.Error, match='busy-controller'):
            another.__enter__()
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()


def test_unfinished_journal_refuses_before_vm_mutation(lease_rig):
    lease, _ = lease_rig
    lease.journal.write_text('{"phase":"running"}')
    lease.journal.chmod(0o600)
    with pytest.raises(runner.Error, match='interrupted-run'):
        lease.__enter__()
    assert lease.fd is None
    lease.source.domain.create.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()


def test_snapshot_changed_during_run_leaves_recovery_evidence(lease_rig):
    lease, _ = lease_rig
    with pytest.raises(runner.Error, match='snapshot-metadata-changed'):
        with lease:
            lease.prepare()
            lease.start()
            lease.source.baseline_xml += ' '
    assert lease.state['phase'] == 'cleanup-requested'
    assert lease.fd is None
    # Initial restore only; no revert or force stop against the changed identity.
    assert lease.source.domain.revertToSnapshot.call_count == 1
    lease.source.domain.destroyFlags.assert_not_called()
