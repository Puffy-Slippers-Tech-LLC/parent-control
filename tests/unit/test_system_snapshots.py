"""System lifecycle and installed cases share E2E snapshot preparation safely."""

import json
from unittest.mock import Mock

import pytest

import system_runner as system
import system_snapshots as snapshots
from tests.support.vm_runner import INVENTORIES, RECOVERY_INVENTORIES, RUN, write_junit_results


@pytest.fixture(autouse=True)
def private_watch_publication(monkeypatch):
    # Exercise real progress state without a desktop registry or heartbeat,
    # including when the unit launcher inherits a privileged caller's env.
    import e2e_watch
    monkeypatch.setattr(e2e_watch, 'ProgressPublication', Mock())


@pytest.fixture
def first_configure_inventories():
    return {**RECOVERY_INVENTORIES,
            'package': (*RECOVERY_INVENTORIES['package'], system.FIRST_CONFIGURE_CASE)}


@pytest.mark.parametrize('area', [None, 'package'])
def test_first_configuration_broad_selection_keeps_its_history_in_an_isolated_baseline_attempt(
        first_configure_inventories, area):
    selection = system.resolve_selection(area, inventories=first_configure_inventories)
    focused = system.resolve_selection('package', system.FIRST_CONFIGURE_CASE,
                                      inventories=first_configure_inventories)
    planned = snapshots.attempts(selection)
    identities = [item for part, _ in planned for item in part.executions]
    assert len(identities) == len(set(identities)) == len(selection.executions)
    assert set(identities) == set(selection.executions)
    matches = [(part, installed) for part, installed in planned
               if any(phase in system.FIRST_CONFIGURE_PHASES for phase in part.phases)]
    assert len(matches) == 1
    part, installed = matches[0]
    assert not installed
    assert part.phases == focused.phases
    assert part.executions == focused.executions
    assert snapshots.attempts(focused) == [(focused, False)]
    for other, _ in planned:
        if other is not part:
            assert not any(item.case_id == system.FIRST_CONFIGURE_CASE for item in other.executions)


def test_first_configuration_resume_replays_both_whole_phases(
        first_configure_inventories):
    focused = system.resolve_selection('package', system.FIRST_CONFIGURE_CASE,
                                      inventories=first_configure_inventories)
    for count in range(3):
        completed = {item.phase + '::' + item.case_id for item in focused.executions[:count]}
        assert system.resume_selection(focused, completed) == focused
    broad = system.resolve_selection(inventories=first_configure_inventories)
    for pending_phase in focused.phases:
        completed = {item.phase + '::' + item.case_id for item in broad.executions
                     if item.phase != pending_phase}
        resumed = system.resume_selection(broad, completed)
        assert resumed.phases == focused.phases
        assert resumed.executions == focused.executions
        assert snapshots.attempts(resumed) == [(resumed, False)]
    completed = {item.phase + '::' + item.case_id for item in broad.executions
                 if item.phase != 'authorization'}
    assert system.resume_selection(broad, completed).phases == ('authorization',)
    with pytest.raises(system.Error, match='selection:resume-inventory-changed'):
        system.resume_selection(focused, {'installed::' + system.FIRST_CONFIGURE_CASE})


@pytest.mark.parametrize('failure', [None, 'first-configure', 'reboot', 'first-configure-rebooted'])
def test_first_configuration_runs_before_normal_reboot_and_never_preinstalls(
        tmp_path, monkeypatch, first_configure_inventories, failure):
    selection = system.resolve_selection('package', system.FIRST_CONFIGURE_CASE,
                                         inventories=first_configure_inventories)
    vm, lease = Mock(), Mock(state={'run': RUN})
    events = []

    def reboot():
        events.append('reboot')
        if failure == 'reboot':
            raise system.CommandError('reboot-failed')

    def execute(vm, token, phase, selected):
        assert token == RUN and selected == selection
        events.append(phase)
        if phase == failure:
            vm.commands.last_returncode = 1
            raise system.CommandError('configure-failed')

    vm.reboot.side_effect = reboot
    monkeypatch.setattr(system, 'run_pytest', execute)
    activation = Mock()
    monkeypatch.setattr(system, 'run_kiosk_activation', activation)
    write_junit_results(tmp_path, selection)
    ledger = system.RunLedger()
    if failure:
        with pytest.raises(system.CommandError):
            system.installed_run(vm, lease, tmp_path, selection, ledger)
        if failure != 'reboot':
            assert ledger.outcomes['product']['category'] == 'pytest:failed:' + failure
    else:
        assert tuple(system.installed_run(vm, lease, tmp_path, selection, ledger)) == selection.phases
    expected = ['first-configure', 'reboot', 'first-configure-rebooted']
    assert events == (expected[:expected.index(failure) + 1] if failure else expected)
    assert [call.args[0] for call in vm.call.call_args_list] == [
        system.guest_command(RUN, 'collect', 'failed' if failure else 'passed')]
    activation.assert_not_called()
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()


@pytest.mark.parametrize('failed', [False, True])
def test_first_configuration_attempt_uses_baseline_and_retains_phase_evidence_on_failure(
        tmp_path, monkeypatch, first_configure_inventories, failed):
    import guest_inputs
    import vm_transport
    selection = system.resolve_selection('package', system.FIRST_CONFIGURE_CASE,
                                         inventories=first_configure_inventories)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/frozen').write_bytes(b'frozen')
    frozen = Mock()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock(return_value=frozen))
    suite = Mock(verified=None)
    lease = suite.lease
    lease.state = {'run': RUN}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(system, 'bootstrap', Mock(return_value='host-key'))
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    monkeypatch.setattr(vm_transport, 'Transport', Mock())

    def execute(vm, owned_lease, directory, selected, ledger, *, already_installed):
        assert owned_lease is lease
        assert not already_installed
        assert selected == selection
        assert (directory / 'input/frozen').read_bytes() == b'frozen'
        write_junit_results(directory, selected)
        if failed:
            (directory / ('guest-results/' + selected.phases[-1] + '.xml')).unlink()
            raise system.CommandError('configure-failed')
        (directory / 'guest-results/result.json').write_text(json.dumps({
            'outcome': 'passed', 'package_sha256': 'package',
            'selected_inputs_sha256': 'selected'}))

    monkeypatch.setattr(system, 'installed_run', execute)
    arguments = (suite, tmp_path, selection, {'artifacts': {'package': {'sha256': 'package'}}},
                 'selected', system.RunLedger())
    if failed:
        with pytest.raises(system.CommandError, match='configure-failed'):
            snapshots.run_attempts(*arguments)
    else:
        snapshots.run_attempts(*arguments)
    lease.prepare.assert_called_once_with()
    lease.__enter__.assert_called_once_with()
    lease.__exit__.assert_called_once()
    lease.start.assert_called_once_with()
    suite.prepare_case.assert_not_called()
    assert suite._input_bundle is frozen
    for phase in selection.phases:
        expected = not failed or phase == selection.phases[0]
        assert (tmp_path / ('guest-results/' + phase + '.xml')).is_file() == expected
        assert (tmp_path / ('guest-results/attempt-first-configure/' + phase + '.xml')).is_file() == expected


@pytest.mark.parametrize('start', ['installed', 'previous-deb', 'previous-rpm', 'mixed-selection'])
def test_first_configuration_refuses_nonbaseline_or_mixed_start_before_any_guest_action(
        tmp_path, monkeypatch, first_configure_inventories, start):
    selection = system.resolve_selection('package', None if start == 'mixed-selection'
                                         else system.FIRST_CONFIGURE_CASE,
                                         inventories=first_configure_inventories)
    if start.startswith('previous-'):
        (tmp_path / 'input').mkdir()
        (tmp_path / ('input/previous-package.' + start.removeprefix('previous-'))).write_bytes(b'old')
    vm, lease = Mock(), Mock(state={'run': RUN})
    execute = Mock()
    monkeypatch.setattr(system, 'run_pytest', execute)
    category = ('installation-requires-baseline' if start == 'installed' else
                'first-configure-requires-isolated-baseline')
    with pytest.raises(system.Error, match=category):
        system.installed_run(vm, lease, tmp_path, selection, already_installed=start == 'installed')
    assert [call.args[0] for call in vm.call.call_args_list] == [
        system.guest_command(RUN, 'collect', 'failed')]
    vm.reboot.assert_not_called()
    execute.assert_not_called()


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
    lease.capture.state = {'guest': {'os_id': 'fedora', 'version': '44'}}
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
    baseline_count = len(system.REMOVAL_HISTORIES) if recovery else 1
    if failure:
        with pytest.raises(system.Error):
            snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert len(seen) == (baseline_count + 1 if failure == 'test' else
                             baseline_count if failure == 'prepare' else 1)
    else:
        snapshots.run_attempts(suite, tmp_path, selection, manifest, 'selected', ledger)
        assert seen == [('installed', 'rebooted', *system.REMOVAL_PHASES),
                        *([(*history.prerequisites, *history.phases)
                           for history in system.REMOVAL_HISTORIES[1:]] if recovery else []),
                        ('authorization',), ('enforcement',), ('session',)]
        assert suite.prepare_case.call_count == 3
        for phase in selection.phases:
            system.reconcile_junit(tmp_path, phase, selection)
    assert lease.prepare.call_count == (baseline_count if failure != 'evidence' else 1)
    assert lease.__enter__.call_count == lease.__exit__.call_count
    lease.source.domain.snapshotLookupByName.assert_not_called()  # Only shared E2E code owns snapshots.
    assert suite._input_bundle is frozen


def test_broad_recovery_partitions_unique_executions_into_baseline_history():
    selection = system.resolve_selection(inventories=RECOVERY_INVENTORIES)
    planned = snapshots.attempts(selection)
    identities = [item.phase + '::' + item.case_id for part, _ in planned for item in part.executions]
    assert len(identities) == len(set(identities)) == len(selection.executions)
    assert set(identities) == {item.phase + '::' + item.case_id for item in selection.executions}
    for history in system.REMOVAL_HISTORIES[1:]:
        focused, installed = next((part, installed) for part, installed in planned
                                  if history.phases[0] in part.phases)
        assert focused.phases == (*history.prerequisites, *history.phases)
        assert not installed
        assert len(focused.executions) == 8


@pytest.mark.parametrize('release,accepted', [
    ({'os_id': 'fedora', 'version': '44'}, True),
    ({'ubuntu_version': '26.04'}, False),
    ({'os_id': 'fedora', 'version': '45'}, False),
])
def test_rpm_posterase_attempt_checks_accepted_guest_before_preparation(
        tmp_path, monkeypatch, release, accepted):
    import guest_inputs
    import vm_transport
    selection = system.resolve_selection('removal', 'test_rpm_posterase_recovery',
                                         inventories=RECOVERY_INVENTORIES)
    (tmp_path / 'input').mkdir()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None)
    lease = suite.lease
    lease.state = {'run': RUN}
    lease.capture.state = {'guest': release}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    bootstrap = Mock(side_effect=system.Error('bootstrap-reached'))
    monkeypatch.setattr(system, 'bootstrap', bootstrap)
    execute = Mock()
    monkeypatch.setattr(system, 'installed_run', execute)
    transport = Mock()
    monkeypatch.setattr(vm_transport, 'Transport', transport)
    category = ('bootstrap-reached' if accepted else
                'history-package-format-mismatch' if release.get('ubuntu_version') else
                'guest:unsupported-package-platform')
    with pytest.raises(system.Error, match=category):
        snapshots.run_attempts(suite, tmp_path, selection, {}, 'selected', system.RunLedger())
    assert lease.prepare.call_count == int(accepted)
    assert bootstrap.call_count == int(accepted)
    execute.assert_not_called()
    transport.assert_not_called()
    lease.__exit__.assert_called_once()


@pytest.mark.parametrize('failure', [None, 'first-phase', 'second-phase'])
def test_rpm_posterase_attempt_releases_owned_lease_and_preserves_exact_junits(
        tmp_path, monkeypatch, failure):
    import guest_inputs
    import vm_transport
    selection = system.resolve_selection('removal', 'test_rpm_posterase_recovery',
                                         inventories=RECOVERY_INVENTORIES)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/frozen').write_bytes(b'frozen')
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None)
    lease = suite.lease
    lease.state = {'run': RUN}
    lease.capture.state = {'guest': {'os_id': 'fedora', 'version': '44'}}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(system, 'bootstrap', Mock(return_value='host-key'))
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    monkeypatch.setattr(vm_transport, 'Transport', Mock())

    def execute(vm, lease, directory, selected, ledger, *, already_installed):
        assert selected == selection
        assert not already_installed
        assert (directory / 'input/frozen').read_bytes() == b'frozen'
        write_junit_results(directory, selected)
        if failure == 'first-phase':
            (directory / ('guest-results/' + selected.phases[-1] + '.xml')).unlink()
        if failure:
            raise system.CommandError('history-failed')
        (directory / 'guest-results/result.json').write_text(json.dumps({
            'outcome': 'passed', 'package_sha256': 'package',
            'selected_inputs_sha256': 'selected'}))

    monkeypatch.setattr(system, 'installed_run', execute)
    arguments = (suite, tmp_path, selection, {'artifacts': {'package': {'sha256': 'package'}}},
                 'selected', system.RunLedger())
    if failure:
        with pytest.raises(system.CommandError, match='history-failed'):
            snapshots.run_attempts(*arguments)
    else:
        snapshots.run_attempts(*arguments)
    lease.prepare.assert_called_once_with()
    lease.__enter__.assert_called_once_with()
    lease.__exit__.assert_called_once()
    suite.prepare_case.assert_not_called()
    result = tmp_path / 'guest-results'
    for phase in selection.phases:
        expected = failure != 'first-phase' or phase != selection.phases[-1]
        assert (result / (phase + '.xml')).is_file() == expected
        assert (result / ('attempt-' + selection.phases[0]) / (phase + '.xml')).is_file() == expected


@pytest.mark.parametrize('family', ['test_ownership_refusal_retry',
                                   'test_identity_filesystem_refusal_retry'])
def test_ownership_family_is_seven_baseline_attempts_and_replays_unfinished_histories(family):
    selection = system.resolve_selection('removal', family, inventories=RECOVERY_INVENTORIES)
    exact = [system.resolve_selection('removal', case, inventories=RECOVERY_INVENTORIES)
             for case in system.REMOVAL_FAMILIES[family]]
    planned = snapshots.attempts(selection)
    assert len(planned) == 7
    for (part, installed), focused in zip(planned, exact):
        assert not installed
        assert part.phases == focused.phases
        assert part.executions == focused.executions
        assert len(part.executions) == 8
        assert part.test == family
    assert tuple(item for part, _ in planned for item in part.executions) == selection.executions
    for count in range(len(selection.executions) + 1):
        completed = {item.phase + '::' + item.case_id for item in selection.executions[:count]}
        resumed = system.resume_selection(selection, completed)
        # An unfinished history replays its six prerequisites and both phases;
        # completely passed earlier histories remain omitted. An end-of-suite
        # audit failure still retries the final complete history.
        remaining = exact[min(count // 8, len(exact) - 1):]
        assert resumed.executions == tuple(item for part in remaining for item in part.executions)
        assert len(snapshots.attempts(resumed)) == len(remaining)
    for focused in exact:
        for pending_phase in focused.phases:
            completed = {item.phase + '::' + item.case_id for item in selection.executions
                         if item.phase != pending_phase}
            resumed = system.resume_selection(selection, completed)
            assert resumed.executions == focused.executions
            assert snapshots.attempts(resumed) == [(resumed, False)]


@pytest.mark.parametrize('area,case', [(None, None), ('removal', None),
                                     ('removal', 'test_ownership_refusal_retry'),
                                     ('removal', 'test_identity_filesystem_refusal_retry'),
                                     *(('removal', history.case_id)
                                       for history in system.REMOVAL_HISTORIES[1:])])
def test_recovery_refuses_previous_package_selection(area, case):
    with pytest.raises(system.Error, match='selection:recovery-requires-current-package'):
        system.resolve_selection(area, case, inventories=RECOVERY_INVENTORIES, fresh_install=True)


@pytest.mark.parametrize('history,failed_phase', [(history, phase)
                         for history in system.REMOVAL_HISTORIES[1:]
                         for phase in (None, *history.prerequisites, *history.phases)])
def test_recovery_dispatch_is_continuous_and_stops_on_failure(
        tmp_path, monkeypatch, history, failed_phase):
    selection = system.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
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
    expected = [history.prerequisites[0], 'reboot', history.prerequisites[1], history.phases[0],
                'reboot', history.phases[1]]
    assert events == (expected[:expected.index(failed_phase) + 1] if failed_phase else expected)
    calls = [call.args[0] for call in vm.call.call_args_list]
    assert calls[0] == system.guest_command(RUN, 'install')
    assert calls[-1] == system.guest_command(RUN, 'collect', 'failed' if failed_phase else 'passed')
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()


@pytest.mark.parametrize('history', system.REMOVAL_HISTORIES[1:], ids=lambda history: history.case_id)
def test_focused_recovery_refuses_app_snapshot_start_before_install(tmp_path, history):
    selection = system.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    vm, lease = Mock(), Mock(state={'run': RUN})
    with pytest.raises(system.Error, match='installation-requires-baseline'):
        system.installed_run(vm, lease, tmp_path, selection, already_installed=True)
    assert [call.args[0] for call in vm.call.call_args_list] == [
        system.guest_command(RUN, 'collect', 'failed')]
    vm.reboot.assert_not_called()


@pytest.mark.parametrize('history', system.REMOVAL_HISTORIES[1:], ids=lambda history: history.case_id)
def test_focused_recovery_resume_replays_only_whole_unfinished_history(history):
    selection = system.resolve_selection(inventories=RECOVERY_INVENTORIES)
    focused = system.resolve_selection('removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    for pending_phase in focused.phases:
        completed = {item.phase + '::' + item.case_id for item in selection.executions
                     if item.phase != pending_phase}
        resumed = system.resume_selection(selection, completed)
        assert resumed.phases == focused.phases
        assert resumed.executions == focused.executions
        assert snapshots.attempts(resumed) == [(resumed, False)]
    for count in range(len(focused.executions) + 1):
        completed = {item.phase + '::' + item.case_id for item in focused.executions[:count]}
        assert system.resume_selection(focused, completed) == focused
    with pytest.raises(system.Error, match='selection:resume-inventory-changed'):
        system.resume_selection(focused, {'foreign::' + history.case_id})
    completed = {item.phase + '::' + item.case_id for item in selection.executions
                 if item.phase != 'authorization'}
    assert system.resume_selection(selection, completed).phases == ('authorization',)


@pytest.mark.parametrize('fault', [None, 'outcome', 'package_sha256', 'selected_inputs_sha256'])
def test_attempt_result_requires_exact_frozen_package_and_source_inputs(tmp_path, fault):
    (tmp_path / 'guest-results').mkdir()
    result = {'outcome': 'passed', 'package_sha256': 'package', 'selected_inputs_sha256': 'selected'}
    if fault:
        result[fault] = 'foreign'
    (tmp_path / 'guest-results/result.json').write_text(json.dumps(result))
    manifest = {'artifacts': {'package': {'sha256': 'package'}}}
    ledger = system.RunLedger()
    if fault:
        with pytest.raises(system.Error, match='pytest:guest-evidence'):
            snapshots.verify_result(tmp_path, manifest, 'selected', ledger)
        assert ledger.outcomes['collection']['category'] == 'pytest:guest-evidence'
    else:
        snapshots.verify_result(tmp_path, manifest, 'selected', ledger)


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
