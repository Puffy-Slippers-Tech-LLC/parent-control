"""System lifecycle and installed cases share E2E snapshot preparation safely."""

import json
from unittest.mock import Mock

import pytest

import system_runner as system
import system_snapshots as snapshots
from tests.support.vm_runner import INVENTORIES, RUN, write_junit_results


@pytest.mark.parametrize('area', [None, 'package', 'authorization', 'enforcement', 'session'])
def test_attempt_partition_preserves_every_selected_execution(area):
    selection = system.resolve_selection(area, inventories=INVENTORIES)
    planned = snapshots.attempts(selection)
    assert tuple(item for part, _ in planned for item in part.executions) == selection.executions
    for part, installed in planned:
        assert installed == all(item.area != 'package' for item in part.executions)
        if installed:
            assert len(part.phases) == 1
        else:
            assert set(part.phases) <= {'installed', 'rebooted'}


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
def test_attempts_restore_before_each_area_and_stop_after_failure(tmp_path, monkeypatch, failure):
    import vm_transport
    import guest_inputs
    selection = system.resolve_selection(inventories=INVENTORIES)
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
        assert len(seen) == (2 if failure == 'test' else 1)
    else:
        snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert seen == [('installed', 'rebooted'), ('authorization',), ('enforcement',), ('session',)]
        assert suite.prepare_case.call_count == 3
        for phase in selection.phases:
            system.reconcile_junit(tmp_path, phase, selection)
    lease.prepare.assert_called_once()
    assert lease.__enter__.call_count == lease.__exit__.call_count
    lease.source.domain.snapshotLookupByName.assert_not_called()  # Only shared E2E code owns snapshots.
    assert suite._input_bundle is frozen
