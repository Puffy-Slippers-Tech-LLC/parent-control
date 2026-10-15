"""System lifecycle and installed cases share E2E snapshot preparation safely."""

import json
from unittest.mock import Mock

import pytest

import system_runner as system
import system_snapshots as snapshots
from tests.support.vm_runner import INVENTORIES, RECOVERY_INVENTORIES, RUN, write_junit_results


@pytest.mark.parametrize('area', [None, 'package', 'removal', 'authorization', 'enforcement', 'session'])
def test_attempt_partition_preserves_every_selected_execution(area):
    selection = system.resolve_selection(area, inventories=INVENTORIES)
    planned = snapshots.attempts(selection)
    assert tuple(item for part, _ in planned for item in part.executions) == selection.executions
    for part, installed in planned:
        assert installed == all(item.area != 'package' for item in part.executions)
        if installed:
            assert len(part.phases) == 1
        else:
            assert set(part.phases) <= {'installed', 'rebooted', *system.REMOVAL_PHASES}


def test_explicit_upgrade_keeps_installation_and_post_install_checks_together():
    selection = system.resolve_selection('authorization', inventories=INVENTORIES, fresh_install=True)
    assert selection.phases == ('installed', 'rebooted', 'authorization')
    assert 'retained-app-snapshot' not in selection.prerequisites
    assert sum(item.prerequisite for item in selection.executions) == 4
    assert snapshots.attempts(selection, fresh_install=True) == [(selection, False)]


@pytest.mark.parametrize('area', ['authorization', 'enforcement', 'session'])
def test_restored_app_runs_checks_without_installation_or_install_reboot(tmp_path, monkeypatch, area):
    selection = system.resolve_selection(area, inventories=INVENTORIES)
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    monkeypatch.setattr(system, 'capture_session_screen', Mock())
    write_junit_results(tmp_path, selection)
    system.installed_run(vm, lease, tmp_path, selection, already_installed=True)
    calls = [call.args[0] for call in vm.call.call_args_list]
    assert calls[0] == system.guest_command(RUN, 'verify-installed')
    assert system.pytest_command(RUN, area, selection) in calls
    assert not any(system.guest_command(RUN, action) in calls
                   for action in ('install', 'install-previous', 'upgrade'))
    assert vm.reboot.call_count == int(area == 'session')


def test_snapshot_verification_failure_never_installs_or_runs_tests(tmp_path):
    selection = system.resolve_selection('authorization', inventories=INVENTORIES)
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.call.side_effect = [system.CommandError('snapshot-mismatch'), b'']
    with pytest.raises(system.CommandError, match='snapshot-mismatch'):
        system.installed_run(vm, lease, tmp_path, selection, already_installed=True)
    assert [call.args[0] for call in vm.call.call_args_list] == [
        system.guest_command(RUN, 'verify-installed'), system.guest_command(RUN, 'collect', 'failed')]
    vm.reboot.assert_not_called()


@pytest.mark.parametrize('failure', [None, 'prepare', 'test', 'evidence'])
@pytest.mark.parametrize('recovery', [False, True])
def test_attempts_restore_before_each_area_and_stop_after_failure(tmp_path, monkeypatch, failure, recovery):
    import vm_transport
    import guest_inputs
    selection = system.resolve_selection(inventories=RECOVERY_INVENTORIES if recovery else INVENTORIES)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/frozen').write_bytes(b'input')
    frozen = Mock()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock(return_value=frozen))
    suite = Mock()
    suite.verified = None
    suite.lease = Mock(state={'run': RUN})
    lease = suite.lease
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(system, 'bootstrap', Mock(return_value='host-key'))
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    monkeypatch.setattr(vm_transport, 'Transport', Mock())
    manifest = {'artifacts': {'package': {'sha256': 'package'}}}
    seen = []

    def prepare(case, *args, **kwargs):
        assert case == snapshots.installed_case(True)
        if failure == 'prepare':
            raise system.Error('preparation-refused')

    suite.prepare_case.side_effect = prepare

    def execute(vm, lease, directory, selected, ledger, *, already_installed):
        seen.append(selected.phases)
        assert (directory / 'input/frozen').read_bytes() == b'input'
        write_junit_results(directory, selected)
        (directory / 'guest-results/result.json').write_text(json.dumps({
            'outcome': 'passed', 'package_sha256': 'wrong' if failure == 'evidence' else 'package',
            'selected_inputs_sha256': 'selected'}))
        if failure == 'test' and already_installed:
            raise system.Error('test-refused')

    monkeypatch.setattr(system, 'installed_run', execute)
    ledger = system.RunLedger()
    if failure:
        with pytest.raises(system.Error):
            snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert len(seen) == ((3 if recovery else 2) if failure == 'test' else
                             (2 if recovery else 1) if failure == 'prepare' else 1)
    else:
        snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert seen == [('installed', 'rebooted', *system.REMOVAL_PHASES),
                        *([system.ROLLBACK_PHASES] if recovery else []),
                        ('authorization',), ('enforcement',), ('session',)]
        assert suite.prepare_case.call_count == 3
        for phase in selection.phases:
            system.reconcile_junit(tmp_path, phase, selection)
    assert lease.prepare.call_count == (2 if recovery and failure != 'evidence' else 1)
    assert lease.__enter__.call_count == lease.__exit__.call_count
    lease.source.domain.snapshotLookupByName.assert_not_called()  # Only shared E2E code owns snapshots.
    assert suite._input_bundle is frozen


def test_broad_recovery_partitions_unique_executions_into_baseline_history():
    selection = system.resolve_selection(inventories=RECOVERY_INVENTORIES)
    planned = snapshots.attempts(selection)
    identities = [item.phase + '::' + item.case_id for part, _ in planned for item in part.executions]
    assert len(identities) == len(set(identities)) == len(selection.executions)
    assert set(identities) == {item.phase + '::' + item.case_id for item in selection.executions}
    focused, installed = next((part, installed) for part, installed in planned
                              if 'rollback' in part.phases)
    assert focused.phases == system.ROLLBACK_PHASES
    assert not installed
    assert len(focused.executions) == 8


@pytest.mark.parametrize('area,case', [(None, None), ('removal', None),
                                     ('removal', 'test_aborted_cleanup_rollback_retry')])
def test_recovery_refuses_previous_package_selection(area, case):
    with pytest.raises(system.Error, match='selection:recovery-requires-current-package'):
        system.resolve_selection(area, case, inventories=RECOVERY_INVENTORIES, fresh_install=True)


@pytest.mark.parametrize('failed_phase', [None, *system.ROLLBACK_PHASES])
def test_recovery_dispatch_is_continuous_and_stops_on_failure(tmp_path, monkeypatch, failed_phase):
    selection = system.resolve_selection(
        'removal', 'test_aborted_cleanup_rollback_retry', inventories=RECOVERY_INVENTORIES)
    assert snapshots.attempts(selection) == [(selection, False)]
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    events = []
    vm.reboot.side_effect = lambda: events.append('reboot')
    monkeypatch.setattr(system, 'run_kiosk_activation', Mock())
    def execute(vm, token, phase, selected):
        events.append(phase)
        if phase == failed_phase:
            vm.commands.last_returncode = 1
            raise system.CommandError('recovery-failed')
    monkeypatch.setattr(system, 'run_pytest', execute)
    write_junit_results(tmp_path, selection)
    ledger = system.RunLedger()
    if failed_phase:
        with pytest.raises(system.CommandError, match='recovery-failed'):
            system.installed_run(vm, lease, tmp_path, selection, ledger)
        assert ledger.outcomes['product']['category'] == 'pytest:failed:' + failed_phase
    else:
        assert set(system.installed_run(vm, lease, tmp_path, selection, ledger)) == set(selection.phases)
    expected = ['rollback-installed', 'reboot', 'rollback-rebooted', 'rollback',
                'reboot', 'rollback-rearmed-rebooted']
    assert events == (expected[:expected.index(failed_phase) + 1] if failed_phase else expected)
    calls = [call.args[0] for call in vm.call.call_args_list]
    assert calls[0] == system.guest_command(RUN, 'install')
    assert calls[-1] == system.guest_command(RUN, 'collect', 'failed' if failed_phase else 'passed')
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()


def test_focused_recovery_refuses_app_snapshot_start_before_install(tmp_path):
    selection = system.resolve_selection(
        'removal', 'test_aborted_cleanup_rollback_retry', inventories=RECOVERY_INVENTORIES)
    vm, lease = Mock(), Mock(state={'run': RUN})
    with pytest.raises(system.Error, match='installation-requires-baseline'):
        system.installed_run(vm, lease, tmp_path, selection, already_installed=True)
    assert [call.args[0] for call in vm.call.call_args_list] == [
        system.guest_command(RUN, 'collect', 'failed')]
    vm.reboot.assert_not_called()


@pytest.mark.parametrize('failed_phase', [None, *system.REMOVAL_PHASES])
def test_removal_is_one_continuous_history_and_failure_stops_transitions(
        tmp_path, monkeypatch, failed_phase):
    selection = system.resolve_selection('removal', inventories=INVENTORIES)
    assert selection.phases == ('installed', 'rebooted', *system.REMOVAL_PHASES)
    assert snapshots.attempts(selection) == [(selection, False)]
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    events = []
    vm.reboot.side_effect = lambda: events.append('reboot')
    def run(vm, token, phase, selected):
        events.append(phase)
        if phase == failed_phase:
            vm.commands.last_returncode = 1
            raise system.CommandError('failed-test')
    monkeypatch.setattr(system, 'run_pytest', run)
    write_junit_results(tmp_path, selection)
    if failed_phase:
        with pytest.raises(system.CommandError, match='failed-test'):
            system.installed_run(vm, lease, tmp_path, selection)
    else:
        system.installed_run(vm, lease, tmp_path, selection)
    expected = ['installed', 'reboot', 'rebooted', 'removal',
                'reboot', 'removed-rebooted', 'reboot', 'reinstalled-rebooted',
                'reboot', 'purged-rebooted', 'reboot', 'purge-reinstalled-rebooted']
    assert events == (expected[:expected.index(failed_phase) + 1] if failed_phase else expected)
    assert vm.call.call_args_list[0].args[0] == system.guest_command(RUN, 'install')
    lease.prepare.assert_not_called()
