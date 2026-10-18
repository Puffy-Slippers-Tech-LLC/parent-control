"""Finite native history controller checks using private files and in-memory doubles."""

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_runner as system
import system_snapshots as snapshots
from tests.support.vm_runner import INVENTORIES, RUN, write_junit_results


def selection(**options):
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'], system.NATIVE_UPDATE_CASE)}
    return system.resolve_selection('package', system.NATIVE_UPDATE_CASE,
                                    inventories=inventories, native_inputs=True, **options)


def test_native_selection_is_explicit_input_bound_and_one_baseline_attempt():
    selected = selection()
    assert selected.phases == ('native-update', 'native-update-rebooted')
    assert snapshots.attempts(selected) == [(selected, False)]
    assert {'verified-native-artifacts', 'old-native-before-install',
            'normal-public-station-exit'} <= set(selected.prerequisites)
    assert system.identity_for_case('package', system.NATIVE_UPDATE_CASE).numeric_id == 289
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'], system.NATIVE_UPDATE_CASE)}
    assert not any(item.case_id == system.NATIVE_UPDATE_CASE for item in
                   system.resolve_selection(inventories=inventories).executions)
    with pytest.raises(system.Error, match='requires-native-artifacts'):
        system.resolve_selection('package', system.NATIVE_UPDATE_CASE, inventories=inventories)
    with pytest.raises(system.Error, match='refuses-previous-artifacts'):
        selection(fresh_install=True)
    with pytest.raises(system.Error, match='requires-isolated-history'):
        system.resolve_selection(recording_ids='289,1', native_inputs=True, inventories=inventories)


def test_native_resume_never_splices_phases():
    selected = selection()
    for count in range(3):
        completed = {item.phase + '::' + item.case_id for item in selected.executions[:count]}
        assert system.resume_selection(selected, completed) == selected


def test_native_selection_binds_host_verification_preparation_and_public_session(tmp_path):
    selected = selection()
    system.stage_selected_inputs(selected, tmp_path)
    recorded = json.loads((tmp_path / 'selected-inputs.json').read_bytes())
    assert recorded['host_files'] == system.native_update_host_inputs()
    assert set(system.NATIVE_UPDATE_HOST_INPUTS) <= set(recorded['host_files'])
    assert set(system.KIOSK_ACTIVATION_HOST_INPUTS) <= set(recorded['host_files'])
    assert {'native_transaction.py', 'system_native_update.py'} <= set(recorded['files'])


def test_changed_host_verifier_refuses_before_public_entry(tmp_path, monkeypatch):
    import kiosk_entry
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/selected-inputs.json').write_text(json.dumps({'host_files': {'helper': 'old'}}))
    monkeypatch.setattr(system, 'native_update_host_inputs', lambda: {'helper': 'changed'})
    entry = Mock(side_effect=AssertionError('changed helper released public input'))
    monkeypatch.setattr(kiosk_entry, 'native_update_station', entry)
    with pytest.raises(system.Error, match='host-inputs-changed'):
        system.run_native_update_phase(Mock(), Mock(), tmp_path, selection(), 'native-update')
    entry.assert_not_called()


@pytest.mark.parametrize('failed', [False, True])
@pytest.mark.parametrize('package_format,guest', [
    ('deb', {'ubuntu_version': '26.04'}),
    ('rpm', {'os_id': 'fedora', 'version': '44'}),
])
def test_native_attempt_stages_binding_before_bootstrap_and_uses_owned_cleanup(
        tmp_path, monkeypatch, failed, package_format, guest):
    import guest_inputs
    import vm_transport
    selected = selection()
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/frozen').write_bytes(b'frozen')
    (tmp_path / 'input/selected-inputs.json').write_text(json.dumps({'host_files': {'helper': 'digest'}}))
    monkeypatch.setattr(system, 'native_update_host_inputs', lambda: {'helper': 'digest'})
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None)
    lease = suite.lease
    lease.state = {'run': RUN, 'baseline_sha256': 'b' * 64}
    lease.capture.state = {'guest': guest}
    events = []
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(side_effect=lambda *args: events.append('owned-cleanup'))
    lease.prepare.side_effect = lambda: events.append('baseline')
    def stage(source, target, **kwargs):
        assert source == tmp_path / 'native-source'
        assert kwargs == {'package_format': package_format, 'baseline_provenance_sha256': 'b' * 64,
                          'selected_inputs_sha256': 's' * 64}
        assert events == ['baseline']
        events.append('native-stage')
        (target / 'native-transaction-binding.json').write_text('{}')
    def bootstrap(commands, owned, directory, guestfs):
        assert events == ['baseline', 'native-stage']
        transfer = json.loads((directory / 'input/transfer-sha256.json').read_text())
        assert 'native-transaction-binding.json' in transfer
        events.append('bootstrap')
        return 'host-key'
    def execute(vm, owned, directory, selection, ledger, *, already_installed):
        assert not already_installed
        write_junit_results(directory, selection)
        if failed:
            raise system.CommandError('native-failed')
        (directory / 'guest-results/result.json').write_text(json.dumps({
            'outcome': 'passed', 'package_sha256': 'package', 'selected_inputs_sha256': 's' * 64}))
    monkeypatch.setattr(system, 'stage_native_assets', stage)
    monkeypatch.setattr(system, 'bootstrap', bootstrap)
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    monkeypatch.setattr(system, 'installed_run', execute)
    monkeypatch.setattr(vm_transport, 'Transport', Mock())
    monkeypatch.setattr(__import__('e2e_watch'), 'ProgressPublication', Mock())
    args = (suite, tmp_path, selected, {'artifacts': {'package': {'sha256': 'package'}}},
            's' * 64, system.RunLedger())
    if failed:
        with pytest.raises(system.CommandError, match='native-failed'):
            snapshots.run_attempts(*args, native_artifacts=tmp_path / 'native-source')
    else:
        snapshots.run_attempts(*args, native_artifacts=tmp_path / 'native-source')
    assert events == ['baseline', 'native-stage', 'bootstrap', 'owned-cleanup']
    suite.prepare_case.assert_not_called()
    assert all((tmp_path / 'guest-results' / (phase + '.xml')).is_file()
               for phase in selected.phases)


@pytest.mark.parametrize('failure', [None, 'native-establish-old', 'install', 'reboot-1',
                                   'verify-setup', 'native-update', 'reboot-2',
                                   'native-update-rebooted'])
@pytest.mark.parametrize('guest', [{'ubuntu_version': '26.04'},
                                  {'os_id': 'fedora', 'version': '44'}])
def test_native_order_and_failure_collection(tmp_path, monkeypatch, failure, guest):
    selected = selection()
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/selected-inputs.json').write_text('{}')
    lease = Mock(state={'run': RUN, 'baseline_sha256': 'b' * 64})
    lease.capture.state = {'guest': guest}
    vm = Mock()
    events = []
    reboots = 0
    monkeypatch.setattr(system, 'verify_native_assets', Mock())
    def event(label):
        events.append(label)
        if label == failure:
            vm.commands.last_returncode = 1
            raise system.CommandError('native-failure')
    def call(command, **kwargs):
        event(command[len(system.guest_command(RUN))])
    def reboot():
        nonlocal reboots
        reboots += 1
        assert events[-1] == 'copy'
        event('reboot-' + str(reboots))
    def copy(download, source, destination):
        if download:
            events.append('copy')
    def phase(vm, owned, directory, chosen, name, ledger):
        assert owned is lease and chosen == selected
        event(name)
        (tmp_path / 'guest-results' / ('station-' + name + '.json')).write_text('{}')
    vm.call.side_effect = call
    vm.reboot.side_effect = reboot
    vm.copy.side_effect = copy
    monkeypatch.setattr(system, 'run_native_update_phase', phase)
    write_junit_results(tmp_path, selected)
    ledger = system.RunLedger()
    if failure:
        with pytest.raises(system.CommandError, match='native-failure'):
            system.installed_run(vm, lease, tmp_path, selected, ledger)
    else:
        assert tuple(system.installed_run(vm, lease, tmp_path, selected, ledger)) == selected.phases
    assert events[-2:] == ['collect', 'copy']
    lifecycle = ['native-establish-old', 'install', 'reboot-1', 'verify-setup',
                 'native-update', 'reboot-2', 'native-update-rebooted']
    actual = [item for item in events if item not in ('collect', 'copy')]
    assert actual == (lifecycle[:lifecycle.index(failure) + 1] if failure else lifecycle)
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()
    if not failure or failure in ('reboot-2', 'native-update-rebooted'):
        assert (tmp_path / 'phase-results/native-update/station-native-update.json').is_file()


@pytest.mark.parametrize('start', ['installed', 'previous', 'spliced'])
def test_native_refuses_invalid_start_before_mutation(tmp_path, start):
    selected = selection()
    if start == 'previous':
        (tmp_path / 'input').mkdir()
        (tmp_path / 'input/previous-package.deb').write_bytes(b'old')
    if start == 'spliced':
        from dataclasses import replace
        selected = replace(selected, phases=selected.phases[1:], executions=selected.executions[1:])
    vm, lease = Mock(), Mock(state={'run': RUN})
    with pytest.raises(system.Error, match='requires-isolated-baseline'):
        system.installed_run(vm, lease, tmp_path, selected, already_installed=start == 'installed')
    assert [call.args[0] for call in vm.call.call_args_list] == [system.guest_command(RUN, 'collect', 'failed')]
    vm.reboot.assert_not_called()


def test_native_station_receipt_and_retirement_follow_normal_public_exit(tmp_path, monkeypatch):
    import kiosk_entry
    selected = selection()
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/selected-inputs.json').write_text(json.dumps({'host_files': {'helper': 'digest'}}))
    events = []
    @contextmanager
    def station(vm, lease, *, receipt):
        receipt.update(normal_exit=False, boot_sha256='a' * 64)
        events.append('entry')
        yield receipt
        events.append('public-exit')
        receipt['normal_exit'] = True
    monkeypatch.setattr(kiosk_entry, 'native_update_station', station)
    monkeypatch.setattr(system, 'native_update_host_inputs', lambda: {'helper': 'digest'})
    monkeypatch.setattr(system, 'run_pytest', lambda *args: events.append('native-assertions'))
    vm, lease = Mock(), Mock(state={'run': RUN})
    vm.call.side_effect = lambda *args, **kwargs: events.append('retired')
    system.run_native_update_phase(vm, lease, tmp_path, selected, selected.phases[0])
    assert events == ['entry', 'native-assertions', 'public-exit', 'retired']
    receipt = json.loads((tmp_path / 'guest-results/station-native-update.json').read_text())
    assert receipt['normal_exit'] and receipt['phase'] == 'native-update'
    assert receipt['selected_inputs_sha256'] == system.baseline.digest(tmp_path / 'input/selected-inputs.json')
    vm.call.assert_called_once_with(system.guest_command(RUN, 'native-retired'), timeout=180)


@pytest.mark.parametrize('fault', [None, 'mode', 'link', 'size', 'owner'])
def test_native_collection_is_finite_private_bounded_and_redacted(tmp_path, monkeypatch, fault):
    import system_guest as guest
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'private').mkdir()
    source = tmp_path / 'private/native-update-old.json'
    source.write_text(json.dumps({'binding': 'sensitive-value'}))
    (tmp_path / 'private/native-update-foreign.json').write_text('{}')
    output = tmp_path / 'results'
    output.mkdir()
    original = Path.lstat
    def metadata(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path != source:
            return info
        return SimpleNamespace(st_mode=0o100600 if fault != 'mode' else 0o100644,
            st_nlink=2 if fault == 'link' else 1, st_uid=1000 if fault == 'owner' else 0,
            st_gid=0, st_size=9 * 1024 * 1024 if fault == 'size' else info.st_size)
    monkeypatch.setattr(Path, 'lstat', metadata)
    redact = lambda value: value.replace('sensitive-value', '[redacted]')
    if fault:
        with pytest.raises(guest.GuestError, match='collection-checkpoint'):
            guest.collect_native_checkpoints(output, redact)
        assert not list(output.iterdir())
    else:
        guest.collect_native_checkpoints(output, redact)
        assert [path.name for path in output.iterdir()] == ['native-update-old.json']
        assert json.loads((output / source.name).read_text()) == {'binding': '[redacted]'}
        assert 'sensitive-value' in source.read_text()
