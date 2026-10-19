"""Host-safe guard/transport tests; real temporary files, no live VM operations.

Isolation variants transform only synthetic XML in memory; no host mounts,
VM, socket or shared path is accessed. Compatible scheduling remains appropriate.
"""
from tests.support.vm_registry import vm_name

import copy
import hashlib
import json
import os
import stat
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import pytest
from tests.support.vm_baseline import rig, local_preparation_source
from tests.support.vm_runner import UUID, RUN, INVENTORIES, xml, write_junit_results, lease_rig, bootstrap_guest

import system_runner as runner
import system_guest as guest
from guest_test_dependencies import ubuntu_archive_sources
from tests.support.modules import load_module
from tests.support.vm_runner import RECOVERY_INVENTORIES
import system_case_ids


def test_numeric_system_registry_covers_current_parameter_variants_without_vm_operations():
    inventories = {area: runner.collect_area_cases(area) for area in runner.AREA_SOURCES}
    system_case_ids.validate_inventory(inventories)
    identities = [system_case_ids.identity_for_case(area, case)
                  for area, cases in inventories.items() for case in cases]
    assert set(identities) <= set(system_case_ids.CASES)
    assert len({identity.numeric_id for identity in identities}) == len(identities)
    assert all(identity.title and identity.numeric_id > 0 for identity in identities)
    # Saved assignments protect representative IDs independently of collection order.
    assignments = {
        ('package', 'test_installed_package'): 1,
        ('removal', 'test_remove_reboot_reinstall'): 6,
        ('authorization', 'test_method_role_matrix[ListManagedUsers-child1]'): 26,
        ('authorization', 'test_method_role_matrix[ListManagedUsers-child2]'): 27,
        ('enforcement', 'test_kiosk_execution_confinement'): 267,
        ('session', 'test_kiosk_expiry_graphical_runtime'): 282,
        ('package', 'test_pam_environment_installation_variants[plain]'): 283,
        ('package', 'test_pam_environment_installation_variants[distro-profile]'): 284,
        ('package', 'test_pam_environment_installation_variants[administrator-override]'): 285,
        ('package', 'test_pam_environment_installation_variants[pending-vendor]'): 286,
    }
    for selector, numeric_id in assignments.items():
        assert system_case_ids.identity_for_case(*selector).numeric_id == numeric_id
    reversed_inventory = {area: tuple(reversed(cases))
                          for area, cases in reversed(tuple(inventories.items()))}
    system_case_ids.validate_inventory(reversed_inventory)
    assert {system_case_ids.identity_for_case(area, case).numeric_id
            for area, cases in reversed_inventory.items() for case in cases} == {
                identity.numeric_id for identity in identities}


def test_system_lifecycle_events_share_numeric_identity_and_keep_original_selectors(capsys):
    selection = runner.resolve_selection('removal', 'test_remove_reboot_reinstall',
                                         inventories=INVENTORIES)
    selected = [item for item in selection.executions if not item.prerequisite]
    identities = [system_case_ids.identity_for_event(item.phase + '::' + item.case_id)
                  for item in selected]
    assert {identity.numeric_id for identity in identities} == {6}
    runner.print_selection(selection)
    output = capsys.readouterr().out
    for item in selected:
        assert f'{item.phase}::{item.case_id} [selected] [system-6]' in output
    assert 'test_remove_reboot_reinstall [system-6]' in output
    # Numeric metadata never replaces the pytest selection or checkpoint identity.
    assert runner.pytest_command(RUN, 'removal', selection)[-1].endswith(
        'test_removal.py::test_remove_reboot_reinstall')
    resumed = runner.resume_selection(selection, {'removal::test_remove_reboot_reinstall'})
    assert any(item.phase == 'removal' for item in resumed.executions)


def test_unknown_system_cases_need_an_explicit_numeric_assignment():
    assert system_case_ids.identity_for_case('package', 'test_new_case') is None
    assert system_case_ids.identity_for_event('installed::test_new_case') is None
    assert system_case_ids.identity_for_event('test_installed_package') is None
    assert system_case_ids.identity_for_event(None) is None
    with pytest.raises(ValueError, match='system-case-ids:unregistered-case'):
        system_case_ids.validate_inventory({'package': ('test_new_case',)})
    with pytest.raises(runner.Error, match='selection:unregistered-numeric-case-id'):
        runner.collect_area_cases('package', invoke=Mock(return_value=(
            b'test_install_smoke.py::test_new_case\n1 test collected\n')))


@pytest.mark.parametrize('value,reason', [
    ('', 'invalid'), ('0', 'invalid'), ('01', 'invalid'), ('1,', 'invalid'),
    ('1, 6', 'invalid'), ('1,,6', 'invalid'), ('-1', 'invalid'), ('１', 'invalid'),
    ('1,1', 'duplicate'), ('999999', 'unknown'),
])
def test_numeric_system_selection_rejects_before_collection(value, reason, monkeypatch):
    collect = Mock(side_effect=AssertionError('invalid IDs collected tests'))
    monkeypatch.setattr(runner, 'collect_area_cases', collect)
    with pytest.raises(runner.Error, match='selection:.*' + reason):
        runner.resolve_selection(recording_ids=value)
    collect.assert_not_called()


def test_numeric_system_ids_keep_phase_closure_and_collection_order():
    selection = runner.resolve_selection(recording_ids='26,6', inventories=INVENTORIES)
    chosen = {(item.area, item.case_id) for item in selection.executions if not item.prerequisite}
    assert chosen == {('removal', 'test_remove_reboot_reinstall'),
                      ('authorization', 'test_method_role_matrix[ListManagedUsers-child1]')}
    assert selection.scope == 'partial'
    assert selection.phases == tuple(phase for phase in runner.PHASE_ORDER
                                    if phase in ('installed', 'rebooted', 'authorization',
                                                 *runner.REMOVAL_PHASES))
    assert all(item.area == 'package' for item in selection.executions if item.prerequisite)
    reversed_selection = runner.resolve_selection(recording_ids='6,26', inventories=INVENTORIES)
    assert selection.executions == reversed_selection.executions
    assert selection.prerequisites == reversed_selection.prerequisites


@pytest.mark.parametrize('area,test', [('authorization', None), (None, 'test_installed_package')])
def test_numeric_system_ids_refuse_named_selector_combinations(area, test):
    with pytest.raises(runner.Error, match='numeric-id-selector-conflict'):
        runner.resolve_selection(area, test, recording_ids='1', inventories=INVENTORIES)


def test_numeric_system_ids_refuse_reserved_but_absent_cases():
    identity = system_case_ids.BY_ID[26]
    inventories = dict(INVENTORIES, authorization=tuple(
        case for case in INVENTORIES['authorization'] if case != identity.case_id))
    with pytest.raises(runner.Error, match='numeric-id-not-runnable'):
        runner.resolve_selection(recording_ids='26', inventories=inventories)


def test_numeric_password_selection_keeps_credential_prerequisite():
    case = 'test_real_selected_parent_authentication[child1]'
    identifier = system_case_ids.identity_for_case('authorization', case).numeric_id
    selection = runner.resolve_selection(recording_ids=str(identifier), inventories=INVENTORIES)
    assert 'fixture-passwords' in selection.prerequisites


@pytest.mark.parametrize('kind', ['started', 'finished', 'failure'])
def test_system_progress_keeps_phase_nodeid_and_adds_trusted_numeric_metadata(kind, capsys):
    from system_progress import Progress
    from tools.regression_events import PREFIX
    case = 'test_method_role_matrix[ListManagedUsers-child1]'
    parser = Progress('authorization', [SimpleNamespace(case_id=case)])
    data = (PREFIX + json.dumps(dict(kind=kind, nodeid='test_authorization.py::' + case,
                                    case_id=999, title='private guest title',
                                    detail='private guest detail')) + '\n').encode()
    parser(data[:17])
    parser(data[17:])
    parser((PREFIX + json.dumps(dict(kind='started', nodeid='test.py::unregistered'))
            + '\n').encode())
    output = capsys.readouterr().out
    event, = [json.loads(line[len(PREFIX):]) for line in output.splitlines()
              if line.startswith(PREFIX)]
    assert event['kind'] == kind
    assert event['nodeid'] == 'authorization::' + case
    assert event['case_id'] == 26
    assert event['title'] == 'Method role matrix [ListManagedUsers-child1]'
    assert 'private guest title' not in output and 'private guest detail' not in output
    assert 'unregistered' not in output


@pytest.mark.parametrize('interrupted', [False, True])
def test_system_watch_publishes_trusted_case_description_and_restores_owners(
        monkeypatch, interrupted):
    from system_progress import Progress, watching
    from tools.regression_events import PREFIX
    from e2e_watch_protocol import progress_packet
    from e2e_watch_viewer import progress_text
    from system_snapshots import attempts
    import e2e_watch

    selection = runner.resolve_selection('removal', 'test_remove_reboot_reinstall',
                                         inventories=INVENTORIES)
    executions = tuple(item for selected, _ in attempts(selection)
                       for item in selected.executions)
    previous = object()
    lease = SimpleNamespace(watch_progress=previous)
    monkeypatch.setattr(runner, 'watch_progress', previous)
    publication = Mock()
    monkeypatch.setattr(e2e_watch, 'ProgressPublication', Mock(return_value=publication))

    with watching(executions, lease) as watch:
        assert runner.watch_progress is lease.watch_progress is watch
        e2e_watch.ProgressPublication.assert_called_once_with(watch)
        # One permanent case ID spans multiple executions, each with its own
        # description and position in the actual selected lifecycle order.
        selected = [(index, item) for index, item in enumerate(executions, 1)
                    if item.case_id == 'test_remove_reboot_reinstall']
        for index, item in selected:
            watch.prepare_execution(item)
            watch.suite_preparation('Checking retained app snapshot')
            prepared = watch.snapshot(display=True)
            assert prepared['current'] == index
            assert prepared['case_id'] == '6'
            assert prepared['step'].startswith('Preparing system check: Remove reboot reinstall')
            assert prepared['operation'] == 'Preparing system suite: Checking retained app snapshot'
            watch.suite_prepared()
            parser = Progress(item.phase, [item], watch=watch)
            record = (PREFIX + json.dumps(dict(kind='started',
                nodeid='test_removal.py::' + item.case_id,
                title='private title', detail='private detail')) + '\n').encode()
            parser(record[:19])
            parser(record[19:])
            shown = json.loads(progress_packet(watch.snapshot(display=True)))
            title, step, _ = progress_text({'progress': shown})
            assert title.startswith(f'[{index}/{len(executions)}] [6]: Remove reboot reinstall')
            assert step == f'Remove reboot reinstall. System phase: {item.phase}.'
            assert 'private' not in json.dumps(shown)
            before = watch.snapshot()
            parser((PREFIX + json.dumps(dict(kind='started', nodeid='test.py::unknown'))
                    + '\n').encode())
            assert watch.snapshot() == before
            if interrupted:
                parser.close()  # Transport failure without a guest finished event.
            else:
                parser((PREFIX + json.dumps(dict(kind='finished',
                    nodeid='test_removal.py::' + item.case_id)) + '\n').encode())
            assert watch.snapshot()['step'].startswith('Collecting results')
            assert watch.snapshot()['operation'] == ''
    assert runner.watch_progress is previous and lease.watch_progress is previous
    publication.close.assert_called_once_with()


def test_system_watch_restores_publication_after_attempt_failure(monkeypatch):
    from system_progress import watching
    import e2e_watch
    previous = object()
    lease = SimpleNamespace(watch_progress=previous)
    monkeypatch.setattr(runner, 'watch_progress', previous)
    publication = Mock()
    monkeypatch.setattr(e2e_watch, 'ProgressPublication', Mock(return_value=publication))
    execution = runner.CaseExecution('installed', 'package', 'test_installed_package', False)
    with pytest.raises(RuntimeError, match='attempt failed'):
        with watching((execution,), lease):
            raise RuntimeError('attempt failed')
    assert runner.watch_progress is lease.watch_progress is previous
    publication.close.assert_called_once_with()


@pytest.fixture
def first_configure_inventories():
    return {**INVENTORIES,
            'package': (*INVENTORIES['package'], runner.FIRST_CONFIGURE_CASE)}


@pytest.fixture
def pam_inventories():
    return {**RECOVERY_INVENTORIES, 'package': (*RECOVERY_INVENTORIES['package'], *(
        history.case_id for history in runner.PAM_HISTORIES))}


@pytest.fixture
def previous_policy_inventories():
    return {**INVENTORIES, 'package': (*INVENTORIES['package'], runner.PREVIOUS_POLICY_CASE)}


@pytest.fixture
def trusted_fixture_inventories():
    return {**INVENTORIES, 'package': (*INVENTORIES['package'], runner.PREVIOUS_POLICY_CASE,
                                      runner.TRUSTED_FIXTURES_CASE)}


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_current_package_recovery_prerequisites_do_not_add_optional_upgrade_history(package_format):
    inventories = {**RECOVERY_INVENTORIES,
                   'package': (*RECOVERY_INVENTORIES['package'], runner.PREVIOUS_POLICY_CASE)}
    selectors = [{}, {'area': 'removal'}]
    for history in runner.REMOVAL_HISTORIES:
        if history.package_format and history.package_format != package_format:
            continue
        identity = system_case_ids.identity_for_case('removal', history.case_id)
        selectors.extend(({'area': 'removal', 'test': history.case_id},
                          {'recording_ids': str(identity.numeric_id)}))
    for options in selectors:
        expected = runner.resolve_selection(**options, inventories=RECOVERY_INVENTORIES,
                                             target_package_format=package_format)
        selected = runner.resolve_selection(**options, inventories=inventories,
                                             target_package_format=package_format)
        assert selected.phases == expected.phases
        assert selected.executions == expected.executions
        assert selected.prerequisites == expected.prerequisites
        assert all(item.case_id != runner.PREVIOUS_POLICY_CASE for item in selected.executions)


@pytest.mark.parametrize('selectors', [
    ['--area', 'package', '--test', 'test_previous_package_policy_preservation'], ['--id', '287'],
])
def test_explicit_previous_policy_cli_still_requires_previous_inputs(
        monkeypatch, capsys, previous_policy_inventories, selectors):
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: previous_policy_inventories[name])
    with patch.object(runner.tempfile, 'mkdtemp') as allocate, \
            patch.object(runner, 'Lease') as lease:
        assert runner.main(['--vm', vm_name(), '--check-tools', *selectors]) == 1
    assert 'selection:previous-policy-requires-previous-artifacts' in capsys.readouterr().err
    allocate.assert_not_called()
    lease.assert_not_called()


def test_trusted_fixture_selection_is_only_the_explicit_old_package_qualification(
        trusted_fixture_inventories):
    case = runner.TRUSTED_FIXTURES_CASE
    selected = runner.resolve_selection('package', case, inventories=trusted_fixture_inventories,
                                        fresh_install=True)
    numeric = runner.resolve_selection(recording_ids='288', inventories=trusted_fixture_inventories,
                                       fresh_install=True)
    assert selected.phases == ('trusted-fixtures',)
    assert numeric.executions == selected.executions == (
        runner.CaseExecution('trusted-fixtures', 'package', case, False),)
    assert {'genuine-earlier-package', 'previous-install-and-reboot',
            'trusted-native-baseline-fixtures', 'fixture-passwords'} <= set(selected.prerequisites)
    assert runner.pytest_command(RUN, 'trusted-fixtures', selected)[-1] == (
        runner.PAYLOAD + '/test_install_smoke.py::' + case)
    for fresh in (False, True):
        for area in (None, 'package'):
            ordinary = runner.resolve_selection(area, inventories=trusted_fixture_inventories,
                                                fresh_install=fresh)
            assert all(item.case_id != case for item in ordinary.executions)
    for completed in (set(), {'trusted-fixtures::' + case}):
        assert runner.resume_selection(selected, completed, fresh_install=True) == selected
    with pytest.raises(runner.Error, match='trusted-fixtures-requires-isolated-history'):
        runner.resolve_selection(recording_ids='288,287', inventories=trusted_fixture_inventories,
                                 fresh_install=True)


@pytest.mark.parametrize('selectors', [
    ['--area', 'package', '--test', 'test_trusted_native_upgrade_fixtures'], ['--id', '288'],
])
def test_trusted_fixture_cli_requires_previous_inputs_before_host_or_vm_operations(
        monkeypatch, capsys, trusted_fixture_inventories, selectors):
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: trusted_fixture_inventories[name])
    with patch.object(runner.tempfile, 'mkdtemp') as allocate, \
            patch.object(runner, 'Lease') as lease:
        assert runner.main(['--vm', vm_name(), '--check-tools', *selectors]) == 1
    assert 'selection:trusted-fixtures-requires-previous-artifacts' in capsys.readouterr().err
    allocate.assert_not_called()
    lease.assert_not_called()


def test_trusted_fixture_pytest_deadline_and_progress_use_only_its_registered_case(
        monkeypatch, trusted_fixture_inventories):
    import system_progress
    selected = runner.resolve_selection('package', runner.TRUSTED_FIXTURES_CASE,
                                        inventories=trusted_fixture_inventories, fresh_install=True)
    progress = Mock()
    monkeypatch.setattr(system_progress, 'Progress', progress)
    vm = Mock()
    prior = vm.commands.progress
    runner.run_pytest(vm, RUN, 'trusted-fixtures', selected)
    vm.call.assert_called_once_with(runner.pytest_command(RUN, 'trusted-fixtures', selected),
                                    timeout=2400)
    assert progress.call_args.args == ('trusted-fixtures', selected.executions)
    progress.return_value.close.assert_called_once_with()
    assert vm.commands.progress is prior


@pytest.mark.parametrize('phase', ['trusted-fixtures', 'installed', 'rebooted'])
def test_trusted_fixture_collected_case_dispatches_only_qualification(monkeypatch, phase):
    qualify = Mock()
    monkeypatch.setitem(sys.modules, 'system_trusted_fixtures', SimpleNamespace(qualify=qualify))
    case = load_module('private_trusted_fixture_case',
                       runner.ROOT / 'tests/system/test_install_smoke.py')
    monkeypatch.setenv('ONPC_SYSTEM_PHASE', phase)
    record = Mock()
    if phase == 'trusted-fixtures':
        case.test_trusted_native_upgrade_fixtures(record)
        qualify.assert_called_once_with(record)
    else:
        with pytest.raises(guest.GuestError, match='trusted-fixtures:test-phase'):
            case.test_trusted_native_upgrade_fixtures(record)
        qualify.assert_not_called()


@pytest.mark.parametrize('failure', [None, 'install-previous', 'old-reboot', 'trusted-fixtures'])
def test_trusted_fixture_controller_installs_and_boots_only_previous_package(
        tmp_path, monkeypatch, trusted_fixture_inventories, failure):
    selected = runner.resolve_selection('package', runner.TRUSTED_FIXTURES_CASE,
                                        inventories=trusted_fixture_inventories, fresh_install=True)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/previous-package.rpm').write_bytes(b'pinned previous package')
    vm, lease = Mock(), Mock(state={'run': RUN})
    events = []
    def step(name):
        events.append(name)
        if failure == name:
            vm.commands.last_returncode = 1
            raise runner.CommandError('qualification-failed')
    def execute(command, **options):
        for name in ('install-previous', 'install', 'upgrade'):
            if command == runner.guest_command(RUN, name):
                step(name)
    def qualify(owned, token, phase, selection):
        assert owned is vm and token == RUN and selection == selected
        step(phase)
    vm.call.side_effect = execute
    vm.reboot.side_effect = lambda: step('old-reboot')
    monkeypatch.setattr(runner, 'run_pytest', qualify)
    write_junit_results(tmp_path, selected)
    ledger = runner.RunLedger()
    if failure:
        with pytest.raises(runner.CommandError):
            runner.installed_run(vm, lease, tmp_path, selected, ledger)
    else:
        assert runner.installed_run(vm, lease, tmp_path, selected, ledger) == {
            'trusted-fixtures': (('package', runner.TRUSTED_FIXTURES_CASE),)}
        assert ledger.outcomes['product']['outcome'] == 'passed'
    expected = ['install-previous', 'old-reboot', 'trusted-fixtures']
    assert events == (expected[:expected.index(failure) + 1] if failure else expected)
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()
    captures = [call.args[0] for call in vm.call.call_args_list
                if call.args[0] in (runner.guest_command(RUN, 'collect', 'installed'),
                                    runner.guest_command(RUN, 'collect', 'failed'),
                                    runner.guest_command(RUN, 'collect', 'passed'))]
    assert captures == ([runner.guest_command(RUN, 'collect', 'installed')]
                        if failure != 'install-previous' else []) + [
                            runner.guest_command(RUN, 'collect', 'failed' if failure else 'passed')]
    assert vm.call.call_args.args[0] == runner.guest_command(
        RUN, 'collect', 'failed' if failure else 'passed')
    if failure == 'trusted-fixtures':
        assert ledger.outcomes['product']['category'] == 'pytest:failed:trusted-fixtures'


@pytest.mark.parametrize('invalid', ['missing-previous', 'installed-snapshot', 'candidate-phase'])
def test_trusted_fixture_controller_refuses_incompatible_starting_state(
        tmp_path, trusted_fixture_inventories, invalid):
    from dataclasses import replace
    selected = runner.resolve_selection('package', runner.TRUSTED_FIXTURES_CASE,
                                        inventories=trusted_fixture_inventories, fresh_install=True)
    if invalid != 'missing-previous':
        (tmp_path / 'input').mkdir()
        (tmp_path / 'input/previous-package.deb').write_bytes(b'pinned previous package')
    if invalid == 'candidate-phase':
        selected = replace(selected, phases=(*selected.phases, 'installed'))
    vm, lease = Mock(), Mock(state={'run': RUN})
    with pytest.raises(runner.Error, match='trusted-fixtures-requires-isolated-old-package'):
        runner.installed_run(vm, lease, tmp_path, selected,
                             already_installed=invalid == 'installed-snapshot')
    vm.reboot.assert_not_called()
    assert vm.call.call_args_list == [((runner.guest_command(RUN, 'collect', 'failed'),),
                                      {'timeout': 180})]


def test_previous_policy_selection_stages_complete_history_and_replays_partial_results(
        tmp_path, previous_policy_inventories):
    case = runner.PREVIOUS_POLICY_CASE
    selected = runner.resolve_selection('package', case, inventories=previous_policy_inventories,
                                        fresh_install=True)
    numeric = runner.resolve_selection(recording_ids='287', inventories=previous_policy_inventories,
                                       fresh_install=True)
    assert selected.phases == ('previous-policy', 'installed', 'rebooted')
    assert numeric.executions == selected.executions == tuple(
        runner.CaseExecution(phase, 'package', case, False) for phase in selected.phases)
    assert {'genuine-earlier-package', 'previous-install-and-reboot', 'fixture-passwords'} <= set(
        selected.prerequisites)
    ordinary = runner.resolve_selection(inventories=previous_policy_inventories)
    assert all(item.case_id != case for item in ordinary.executions)
    for count in range(len(selected.executions) + 1):
        completed = {item.phase + '::' + case for item in selected.executions[:count]}
        assert runner.resume_selection(selected, completed, fresh_install=True).executions == selected.executions
    output = tmp_path / 'input'
    runner.stage_selected_inputs(selected, output)
    files = json.loads((output / 'selected-inputs.json').read_text())['files']
    assert files['system_previous_upgrade.py']['sha256'] == hashlib.sha256(
        (runner.ROOT / 'tests/integration/system_previous_upgrade.py').read_bytes()).hexdigest()
    write_junit_results(tmp_path, selected)
    assert all(runner.reconcile_junit(tmp_path, phase, selected) == (('package', case),)
               for phase in selected.phases)


@pytest.mark.parametrize('failure', [None, 'previous-policy', 'installed', 'rebooted', 'old-reboot'])
def test_previous_policy_controller_keeps_old_boot_policy_update_and_recovery_in_one_attempt(
        tmp_path, monkeypatch, previous_policy_inventories, failure):
    selected = runner.resolve_selection('package', runner.PREVIOUS_POLICY_CASE,
                                        inventories=previous_policy_inventories, fresh_install=True)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/previous-package.rpm').write_bytes(b'earlier package')
    vm, lease = Mock(), Mock(state={'run': RUN})
    events = []
    def execute(command, **options):
        for operation in ('install-previous', 'upgrade'):
            if command == runner.guest_command(RUN, operation):
                events.append(operation)
    def phase(owned, token, name, selection):
        assert owned is vm and token == RUN and selection == selected
        events.append(name)
        if failure == name:
            vm.commands.last_returncode = 1
            raise runner.CommandError('phase-failed')
    def reboot():
        name = 'old-reboot' if events == ['install-previous'] else 'new-reboot'
        events.append(name)
        if failure == name:
            raise runner.CommandError('reboot-failed')
    vm.call.side_effect = execute
    vm.reboot.side_effect = reboot
    monkeypatch.setattr(runner, 'run_pytest', phase)
    write_junit_results(tmp_path, selected)
    ledger = runner.RunLedger()
    if failure:
        with pytest.raises(runner.CommandError):
            runner.installed_run(vm, lease, tmp_path, selected, ledger)
    else:
        assert tuple(runner.installed_run(vm, lease, tmp_path, selected, ledger)) == selected.phases
    expected = ['install-previous', 'old-reboot', 'previous-policy', 'upgrade',
                'installed', 'new-reboot', 'rebooted']
    assert events == (expected[:expected.index(failure) + 1] if failure else expected)
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()
    assert vm.call.call_args.args[0] == runner.guest_command(RUN, 'collect', 'failed' if failure else 'passed')
    if failure in selected.phases:
        assert ledger.outcomes['product']['category'] == 'pytest:failed:' + failure


def test_previous_policy_refuses_missing_inputs_before_any_installation(
        tmp_path, previous_policy_inventories):
    selected = runner.resolve_selection('package', runner.PREVIOUS_POLICY_CASE,
                                        inventories=previous_policy_inventories)
    vm, lease = Mock(), Mock(state={'run': RUN})
    with pytest.raises(runner.Error, match='previous-policy-requires-isolated-upgrade'):
        runner.installed_run(vm, lease, tmp_path, selected)
    vm.reboot.assert_not_called()
    assert vm.call.call_args_list == [((runner.guest_command(RUN, 'collect', 'failed'),), {'timeout': 180})]


def test_pam_registration_keeps_four_independent_four_phase_baseline_histories():
    variants = ('plain', 'distro-profile', 'administrator-override', 'pending-vendor')
    assert runner.PAM_CASE == 'test_pam_environment_installation_variants'
    assert runner.PAM_VARIANTS == variants
    assert tuple(history.case_id for history in runner.PAM_HISTORIES) == tuple(
        f'{runner.PAM_CASE}[{variant}]' for variant in variants)
    for history, variant in zip(runner.PAM_HISTORIES, variants):
        assert history.start == 'baseline'
        assert history.prerequisites == ()
        assert history.phases == (f'pam-{variant}', f'pam-{variant}-rebooted',
                                  f'pam-{variant}-configured-rebooted',
                                  f'pam-{variant}-removed-rebooted')
        assert runner.case_phases('package', history.case_id) == history.phases
    assert len(runner.PHASE_ORDER) == len(set(runner.PHASE_ORDER))


@pytest.mark.parametrize('variant,identifier', [
    ('plain', 283), ('distro-profile', 284), ('administrator-override', 285),
    ('pending-vendor', 286)])
def test_pam_exact_and_numeric_selection_keep_only_the_complete_history(
        pam_inventories, variant, identifier):
    case = f'{runner.PAM_CASE}[{variant}]'
    exact = runner.resolve_selection('package', case, inventories=pam_inventories)
    numeric = runner.resolve_selection(recording_ids=str(identifier), inventories=pam_inventories)
    history = next(item for item in runner.PAM_HISTORIES if item.case_id == case)
    assert exact.phases == numeric.phases == history.phases
    assert exact.executions == numeric.executions == tuple(
        runner.CaseExecution(phase, 'package', case, False) for phase in history.phases)
    assert {'accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap'} <= set(exact.prerequisites)
    assert not {'installed-phase', 'retained-app-snapshot'} & set(exact.prerequisites)
    for phase in history.phases:
        assert system_case_ids.identity_for_event(phase + '::' + case).numeric_id == identifier
        command = runner.pytest_command(RUN, phase, exact)
        assert 'ONPC_SYSTEM_PHASE=' + phase in command
        assert command[-1] == runner.PAYLOAD + '/test_install_smoke.py::' + case
        assert sum('::' in argument for argument in command) == 1


def test_pam_family_stages_exact_sources_selectors_and_junit_identities(
        tmp_path, capsys, pam_inventories):
    selection = runner.resolve_selection('package', runner.PAM_CASE, inventories=pam_inventories)
    exact = [runner.resolve_selection('package', history.case_id, inventories=pam_inventories)
             for history in runner.PAM_HISTORIES]
    assert selection.executions == tuple(item for part in exact for item in part.executions)
    assert selection.phases == tuple(phase for part in exact for phase in part.phases)
    assert len(selection.executions) == 16
    assert not any(item.prerequisite for item in selection.executions)
    staged = tmp_path / 'input'
    digest = runner.stage_selected_inputs(selection, staged)
    identity = json.loads((staged / 'selected-inputs.json').read_text())
    assert digest == runner.baseline.digest(staged / 'selected-inputs.json')
    assert identity['selection']['test'] == runner.PAM_CASE
    assert identity['selection']['phases'] == list(selection.phases)
    assert identity['selection']['executions'] == [
        {'phase': item.phase, 'area': item.area, 'case_id': item.case_id,
         'prerequisite': False} for item in selection.executions]
    for name in ('test_install_smoke.py', 'system_pam_variants.py', 'system_kiosk_accounts.py',
                 'system_kiosk_confinement.py', 'system_first_configure.py', 'system_removal.py'):
        source = (runner.AREA_SOURCES['package'] if name == 'test_install_smoke.py'
                  else runner.ROOT / 'tests/integration' / name)
        assert identity['files'][name] == {
            'source': str(source.relative_to(runner.ROOT)),
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        assert (staged / name).read_bytes() == source.read_bytes()
    runner.print_selection(selection)
    output = capsys.readouterr().out
    assert 'expected-executions: 16' in output
    for item in selection.executions:
        assert item.phase + '::' + item.case_id in output
    write_junit_results(tmp_path, selection)
    for phase in selection.phases:
        expected = next(item for item in selection.executions if item.phase == phase)
        assert runner.reconcile_junit(tmp_path, phase, selection) == (('package', expected.case_id),)
    evidence = runner.selection_evidence(tmp_path, selection)
    assert evidence['executed_cases'] == [
        {'phase': item.phase, 'area': item.area, 'case_id': item.case_id}
        for item in selection.executions]


@pytest.mark.parametrize('fault', ['missing', 'extra', 'empty'])
def test_pam_family_refuses_changed_inventory(pam_inventories, fault):
    cases = tuple(history.case_id for history in runner.PAM_HISTORIES)
    cases = {'missing': cases[:-1], 'extra': (*cases, runner.PAM_CASE + '[unknown]'),
             'empty': ()}[fault]
    inventory = {**pam_inventories, 'package': (*INVENTORIES['package'], *cases)}
    with pytest.raises(runner.Error, match='selection:invalid-family-registry'):
        runner.resolve_selection('package', runner.PAM_CASE, inventories=inventory)


@pytest.mark.parametrize('case', [None, 'test_pam_environment_installation_variants',
                                'test_pam_environment_installation_variants[plain]'])
def test_pam_selection_refuses_previous_package_upgrade(pam_inventories, case):
    with pytest.raises(runner.Error, match='selection:.*require.*current-package'):
        runner.resolve_selection('package', case, inventories=pam_inventories, fresh_install=True)


def test_first_configuration_selection_has_only_its_two_exact_package_executions(
        first_configure_inventories, capsys):
    assert runner.FIRST_CONFIGURE_CASE == 'test_first_configuration_interruption_retry'
    assert runner.FIRST_CONFIGURE_PHASES == ('first-configure', 'first-configure-rebooted')
    selection = runner.resolve_selection('package', runner.FIRST_CONFIGURE_CASE,
                                         inventories=first_configure_inventories)
    assert selection.phases == runner.FIRST_CONFIGURE_PHASES
    assert selection.executions == tuple(runner.CaseExecution(
        phase, 'package', runner.FIRST_CONFIGURE_CASE, False) for phase in selection.phases)
    assert runner.PHASE_DEPENDENCIES[selection.phases[0]] == ()
    assert runner.PHASE_DEPENDENCIES[selection.phases[1]] == selection.phases[:1]
    assert {'accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap'} <= set(selection.prerequisites)
    assert not {'installed-phase', 'retained-app-snapshot'} & set(selection.prerequisites)
    assert len(runner.PHASE_ORDER) == len(set(runner.PHASE_ORDER))
    runner.print_selection(selection)
    output = capsys.readouterr().out
    assert 'expected-executions: 2' in output
    assert 'phases: first-configure,first-configure-rebooted' in output
    for phase in selection.phases:
        assert phase + '::' + runner.FIRST_CONFIGURE_CASE + ' [selected]' in output
        command = runner.pytest_command(RUN, phase, selection)
        assert 'ONPC_SYSTEM_PHASE=' + phase in command
        assert runner.PAYLOAD + '/results/' + phase + '.xml' in command
        assert command[-1] == runner.PAYLOAD + '/test_install_smoke.py::' + runner.FIRST_CONFIGURE_CASE
        assert sum('::' in argument for argument in command) == 1


@pytest.mark.parametrize('area,case', [(None, None), ('package', None),
                                     ('package', 'test_first_configuration_interruption_retry')])
def test_first_configuration_rejects_previous_artifact_selection(
        first_configure_inventories, area, case):
    with pytest.raises(runner.Error, match='selection:first-configure-requires-current-package'):
        runner.resolve_selection(area, case, inventories=first_configure_inventories,
                                 fresh_install=True)


@pytest.mark.parametrize('phase', ['first-configure', 'first-configure-rebooted'])
@pytest.mark.parametrize('fault', [None, 'missing', 'extra', 'duplicate', 'identity', 'failure', 'skipped'])
def test_first_configuration_junit_requires_exact_unskipped_package_identity(
        tmp_path, first_configure_inventories, phase, fault):
    selection = runner.resolve_selection('package', runner.FIRST_CONFIGURE_CASE,
                                         inventories=first_configure_inventories)
    write_junit_results(tmp_path, selection, fault)
    if fault:
        output = tmp_path / 'guest-results'
        (output / (phase + '.xml')).write_bytes(
            (output / (selection.phases[-1] + '.xml')).read_bytes())
        with pytest.raises(runner.Error):
            runner.reconcile_junit(tmp_path, phase, selection)
    else:
        assert runner.reconcile_junit(tmp_path, phase, selection) == (
            ('package', runner.FIRST_CONFIGURE_CASE),)
        evidence = runner.selection_evidence(tmp_path, selection)
        assert evidence['expected_executions'] == [
            {'phase': item, 'area': 'package', 'case_id': runner.FIRST_CONFIGURE_CASE,
             'prerequisite': False} for item in selection.phases]
        assert evidence['executed_cases'] == [
            {'phase': item, 'area': 'package', 'case_id': runner.FIRST_CONFIGURE_CASE}
            for item in selection.phases]


@pytest.mark.parametrize('fails', [False, True])
def test_first_configuration_has_bounded_install_timeout_and_restores_progress(
        first_configure_inventories, fails, monkeypatch):
    from system_progress import SystemWatchProgress
    from tools.regression_events import PREFIX
    selection = runner.resolve_selection('package', runner.FIRST_CONFIGURE_CASE,
                                         inventories=first_configure_inventories)
    watch = SystemWatchProgress(selection.executions)
    monkeypatch.setattr(runner, 'watch_progress', watch)
    vm = Mock()
    previous = vm.commands.progress
    phase = selection.phases[0]

    def call(command, *, timeout):
        assert timeout == 2400
        assert command == runner.pytest_command(RUN, phase, selection)
        assert vm.commands.progress.phase == phase
        vm.commands.progress((PREFIX + json.dumps(dict(kind='started',
            nodeid='test_install_smoke.py::' + runner.FIRST_CONFIGURE_CASE)) + '\n').encode())
        assert watch.snapshot()['step'] == (
            'First configuration interruption retry. System phase: first-configure.')
        if fails:
            raise runner.CommandError('first-configure-failed')
        return b'passed'

    vm.call.side_effect = call
    if fails:
        with pytest.raises(runner.CommandError, match='first-configure-failed'):
            runner.run_pytest(vm, RUN, phase, selection)
    else:
        assert runner.run_pytest(vm, RUN, phase, selection) == b'passed'
    assert vm.commands.progress is previous
    assert watch.snapshot()['step'].startswith('Collecting results')


def test_rpm_posterase_registration_is_one_fedora_baseline_history():
    history = next(history for history in runner.REMOVAL_HISTORIES
                   if history.case_id == 'test_rpm_posterase_recovery')
    assert history.start == 'baseline'
    assert history.package_format == 'rpm'
    assert history.prerequisites == ('rpm-posterase-installed', 'rpm-posterase-rebooted')
    assert history.phases == ('rpm-posterase', 'rpm-posterase-reinstalled-rebooted')
    assert len(runner.PHASE_ORDER) == len(set(runner.PHASE_ORDER))


@pytest.mark.parametrize('area', [None, 'removal'])
@pytest.mark.parametrize('target_format', [None, 'deb', 'rpm'])
def test_rpm_posterase_broad_selection_uses_explicit_target_format(area, target_format):
    selection = runner.resolve_selection(area, inventories=RECOVERY_INVENTORIES,
                                         target_package_format=target_format)
    cases = {item.case_id for item in selection.executions}
    assert ('test_rpm_posterase_recovery' in cases) == (target_format != 'deb')
    assert ('test_rpm_posterase_recovery' in selection.available['removal']) == (target_format != 'deb')
    # Filtering the Fedora-only history never shortens the full removal history.
    assert set(runner.REMOVAL_PHASES) <= set(selection.phases)
    full = [item for item in selection.executions if item.case_id == 'test_remove_reboot_reinstall']
    assert tuple(item.phase for item in full) == runner.REMOVAL_PHASES


def test_rpm_posterase_explicit_wrong_target_refuses():
    with pytest.raises(runner.Error, match='selection:history-package-format-mismatch'):
        runner.resolve_selection('removal', 'test_rpm_posterase_recovery',
                                 inventories=RECOVERY_INVENTORIES, target_package_format='deb')


@pytest.mark.parametrize('target_format', [None, 'rpm'])
def test_rpm_posterase_list_mode_preserves_exact_history_without_vm_access(
        monkeypatch, capsys, target_format):
    configured = (SimpleNamespace(require_package_format=lambda: target_format)
                  if target_format else None)
    monkeypatch.setattr(runner.baseline.guest_contract.vm_config, 'extract',
                        lambda argv, **_: (argv, configured))
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: RECOVERY_INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which', Mock(side_effect=AssertionError('tool probe ran')))
    monkeypatch.setattr(runner, 'artifact_source', Mock(side_effect=AssertionError('artifact probe ran')))
    monkeypatch.setattr(runner.baseline, 'LibvirtSource',
                        Mock(side_effect=AssertionError('VM probe ran')))
    assert runner.main(['--list', '--area', 'removal', '--test', 'test_rpm_posterase_recovery']) == 0
    output = capsys.readouterr().out
    assert 'expected-executions: 8' in output
    assert 'required-package-format: test_rpm_posterase_recovery=rpm' in output
    assert 'phases: rpm-posterase-installed,rpm-posterase-rebooted,rpm-posterase,' in output


def test_rpm_posterase_wrong_target_stops_before_tool_artifact_or_vm_checks(monkeypatch, capsys):
    configured = SimpleNamespace(require_package_format=lambda: 'deb')
    monkeypatch.setattr(runner.baseline.guest_contract.vm_config, 'extract',
                        lambda argv, **_: (argv, configured))
    monkeypatch.setattr(runner.baseline.guest_contract.vm_config, 'selected', Mock())
    monkeypatch.setattr(runner.baseline.guest_contract, 'CHECKOUT', runner.ROOT)
    monkeypatch.setattr(runner.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(runner.os, 'getegid', lambda: 0)
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: RECOVERY_INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which', Mock(side_effect=AssertionError('tool probe ran')))
    monkeypatch.setattr(runner, 'artifact_source', Mock(side_effect=AssertionError('artifact probe ran')))
    assert runner.main(['--area', 'removal', '--test', 'test_rpm_posterase_recovery']) == 1
    assert 'selection:history-package-format-mismatch' in capsys.readouterr().err


def test_interrupted_finalization_registration_has_three_distinct_baseline_histories():
    variants = ('denial-publication', 'mac-unload', 'account-finalization')
    histories = tuple(history for history in runner.REMOVAL_HISTORIES
                      if history.case_id.startswith('test_interrupted_finalization_retry['))
    assert tuple(history.case_id for history in histories) == tuple(
        f'test_interrupted_finalization_retry[{variant}]' for variant in variants)
    for history, variant in zip(histories, variants):
        assert history.start == 'baseline'
        assert history.prerequisites == (variant + '-installed', variant + '-rebooted')
        assert history.phases == (variant, variant + '-retry-rebooted')
    assert len(runner.PHASE_ORDER) == len(set(runner.PHASE_ORDER))


OWNERSHIP_FAMILIES = (
    ('test_ownership_refusal_retry', (
        'systemd-user-edit', 'gdm-password-link', 'systemd-user-link', 'gdm-hook-link',
        'confinement-record-owner', 'confinement-record-link', 'confinement-record-uid')),
    ('test_identity_filesystem_refusal_retry', (
        'kiosk-marker-uid', 'home-owner', 'home-link', 'home-mount',
        'state-owner', 'state-link', 'state-mount')),
)


@pytest.mark.parametrize('family,variants', OWNERSHIP_FAMILIES)
def test_ownership_registration_has_seven_distinct_baseline_histories(family, variants):
    histories = tuple(history for history in runner.REMOVAL_HISTORIES
                      if history.case_id.startswith(family + '['))
    assert tuple(history.case_id for history in histories) == tuple(
        f'{family}[{variant}]' for variant in variants)
    assert runner.REMOVAL_FAMILIES[family] == tuple(history.case_id for history in histories)
    for history, variant in zip(histories, variants):
        assert history.start == 'baseline'
        assert history.prerequisites == (variant + '-installed', variant + '-rebooted')
        assert history.phases == (variant, variant + '-retry-rebooted')
    assert len(runner.PHASE_ORDER) == len(set(runner.PHASE_ORDER))


@pytest.mark.parametrize('family,variants', OWNERSHIP_FAMILIES)
def test_ownership_family_listing_and_results_keep_all_exact_execution_identities(
        tmp_path, capsys, family, variants):
    selection = runner.resolve_selection('removal', family, inventories=RECOVERY_INVENTORIES)
    exact = [runner.resolve_selection('removal', case, inventories=RECOVERY_INVENTORIES)
             for case in runner.REMOVAL_FAMILIES[family]]
    assert selection.test == family
    assert len(selection.executions) == 56
    assert sum(item.prerequisite for item in selection.executions) == 42
    assert selection.executions == tuple(item for part in exact for item in part.executions)
    assert selection.phases == tuple(phase for part in exact for phase in part.phases)
    staged = tmp_path / 'input'
    digest = runner.stage_selected_inputs(selection, staged)
    identity = json.loads((staged / 'selected-inputs.json').read_text())
    assert digest == runner.baseline.digest(staged / 'selected-inputs.json')
    assert identity['selection']['test'] == family
    assert len(identity['selection']['executions']) == 56
    assert {item['case_id'] for item in identity['selection']['executions']
            if item['area'] == 'removal'} == set(runner.REMOVAL_FAMILIES[family])
    runner.print_selection(selection)
    output = capsys.readouterr().out
    assert 'expected-executions: 56' in output
    assert 'test: ' + family in output
    for part in exact:
        for item in part.executions:
            assert item.phase + '::' + item.case_id in output
        for phase in part.phases[-2:]:
            assert runner.pytest_command(RUN, phase, selection)[-1] == (
                runner.PAYLOAD + '/test_removal.py::' + part.test)
    write_junit_results(tmp_path, selection)
    for phase in selection.phases:
        runner.reconcile_junit(tmp_path, phase, selection)
    evidence = runner.selection_evidence(tmp_path, selection)
    assert len(evidence['expected_executions']) == len(evidence['executed_cases']) == 56
    assert {item['case_id'] for item in evidence['executed_cases']
            if item['area'] == 'removal'} == set(runner.REMOVAL_FAMILIES[family])


@pytest.mark.parametrize('fault', ['missing', 'extra', 'empty'])
@pytest.mark.parametrize('family,variants', OWNERSHIP_FAMILIES)
def test_ownership_family_refuses_incomplete_or_changed_registry(fault, family, variants):
    cases = runner.REMOVAL_FAMILIES[family]
    cases = {'missing': cases[:-1], 'extra': (*cases, family + '[unknown]'), 'empty': ()}[fault]
    inventories = {**RECOVERY_INVENTORIES,
                   'removal': ('test_remove_reboot_reinstall', *cases)}
    with pytest.raises(runner.Error, match='selection:invalid-family-registry'):
        runner.resolve_selection('removal', family, inventories=inventories)


@pytest.mark.parametrize('area,test', [('removal', 'test_ownership_refusal'),
                                     ('removal', 'test_ownership_refusal_retry[unknown]'),
                                     ('authorization', 'test_ownership_refusal_retry'),
                                     ('removal', 'test_identity_filesystem_refusal'),
                                     ('removal', 'test_identity_filesystem_refusal_retry[unknown]'),
                                     ('authorization', 'test_identity_filesystem_refusal_retry')])
def test_ownership_family_does_not_enable_partial_unknown_or_other_area_selectors(area, test):
    with pytest.raises(runner.Error, match='selection:unknown-test'):
        runner.resolve_selection(area, test, inventories=RECOVERY_INVENTORIES)


def removal_dispatch_helpers():
    return SimpleNamespace(**{name: Mock() for name in (
        'remove', 'removed_rebooted', 'reinstalled_rebooted', 'purged_rebooted',
        'purge_reinstalled_rebooted', 'aborted_cleanup_rollback_retry',
        'rollback_rearmed_rebooted', 'interrupted_finalization_retry',
        'finalization_retry_rebooted', 'ownership_refusal_retry',
        'ownership_retry_rebooted', 'identity_filesystem_refusal_retry',
        'identity_filesystem_retry_rebooted', 'rpm_posterase_recovery',
        'rpm_posterase_reinstalled_rebooted')})


@pytest.mark.parametrize('phase,expected', [
    ('rpm-posterase', 'rpm_posterase_recovery'),
    ('rpm-posterase-reinstalled-rebooted', 'rpm_posterase_reinstalled_rebooted'),
    ('rollback', None), ('removal', None), ('rpm-posterase-rebooted', None),
])
def test_rpm_posterase_guest_dispatch_requires_exact_continuous_phase(monkeypatch, phase, expected):
    helpers = removal_dispatch_helpers()
    monkeypatch.setitem(sys.modules, 'system_removal', helpers)
    case = load_module('private_rpm_posterase_dispatch', runner.ROOT / 'tests/system/test_removal.py')
    monkeypatch.setenv('ONPC_SYSTEM_PHASE', phase)
    record = Mock()
    if expected is None:
        with pytest.raises(KeyError):
            case.test_rpm_posterase_recovery(record)
    else:
        case.test_rpm_posterase_recovery(record)
    for name, helper in vars(helpers).items():
        if name == expected:
            helper.assert_called_once_with(record)
        else:
            helper.assert_not_called()


@pytest.mark.parametrize('variant', ['denial-publication', 'mac-unload', 'account-finalization'])
@pytest.mark.parametrize('phase_kind', ['interruption', 'rebooted', 'foreign'])
def test_interrupted_finalization_guest_dispatch_keeps_exact_variant(
        monkeypatch, variant, phase_kind):
    helpers = removal_dispatch_helpers()
    monkeypatch.setitem(sys.modules, 'system_removal', helpers)
    case = load_module('private_finalization_dispatch',
                       runner.ROOT / 'tests/system/test_removal.py')
    registration = case.test_interrupted_finalization_retry.pytestmark[0]
    assert registration.args == ('variant', ['denial-publication', 'mac-unload', 'account-finalization'])
    phase = {'interruption': variant, 'rebooted': variant + '-retry-rebooted',
             'foreign': 'rollback'}[phase_kind]
    monkeypatch.setenv('ONPC_SYSTEM_PHASE', phase)
    record = Mock()
    if phase_kind == 'foreign':
        with pytest.raises(KeyError):
            case.test_interrupted_finalization_retry(record, variant)
    else:
        case.test_interrupted_finalization_retry(record, variant)
    expected = {'interruption': 'interrupted_finalization_retry',
                'rebooted': 'finalization_retry_rebooted'}.get(phase_kind)
    for name, helper in vars(helpers).items():
        if name == expected:
            helper.assert_called_once_with(record, variant)
        else:
            helper.assert_not_called()


@pytest.mark.parametrize('family,variant', [(family, variant)
                         for family, variants in OWNERSHIP_FAMILIES for variant in variants])
@pytest.mark.parametrize('phase_kind', ['refusal', 'rebooted', 'foreign', 'other-variant', 'other-family'])
def test_ownership_guest_dispatch_keeps_exact_variant(monkeypatch, family, variant, phase_kind):
    helpers = removal_dispatch_helpers()
    monkeypatch.setitem(sys.modules, 'system_removal', helpers)
    case = load_module('private_ownership_dispatch', runner.ROOT / 'tests/system/test_removal.py')
    dispatch = getattr(case, family)
    registration = dispatch.pytestmark[0]
    variants = dict(OWNERSHIP_FAMILIES)[family]
    assert registration.args == ('variant', list(variants))
    other_family = next(name for name, _ in OWNERSHIP_FAMILIES if name != family)
    phase = {'refusal': variant, 'rebooted': variant + '-retry-rebooted',
             'foreign': 'rollback',
             'other-variant': next(item for item in variants if item != variant),
             'other-family': dict(OWNERSHIP_FAMILIES)[other_family][0]}[phase_kind]
    monkeypatch.setenv('ONPC_SYSTEM_PHASE', phase)
    record = Mock()
    if phase_kind not in ('refusal', 'rebooted'):
        with pytest.raises(KeyError):
            dispatch(record, variant)
    else:
        dispatch(record, variant)
    prefix = family.removeprefix('test_').removesuffix('_refusal_retry')
    expected = {'refusal': prefix + '_refusal_retry',
                'rebooted': prefix + '_retry_rebooted'}.get(phase_kind)
    for name, helper in vars(helpers).items():
        if name == expected:
            helper.assert_called_once_with(record, variant)
        else:
            helper.assert_not_called()


@pytest.mark.parametrize('history', runner.REMOVAL_HISTORIES[1:], ids=lambda history: history.case_id)
def test_focused_recovery_listing_has_exact_prerequisite_closure(capsys, history):
    selection = runner.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    assert selection.phases == (*history.prerequisites, *history.phases)
    assert len(selection.executions) == 8
    assert sum(item.prerequisite for item in selection.executions) == 6
    assert [sum(item.phase == phase for item in selection.executions)
            for phase in history.prerequisites] == [3, 3]
    assert selection.executions[-1] == runner.CaseExecution(
        history.phases[-1], 'removal', selection.test, False)
    assert runner.PHASE_DEPENDENCIES[history.phases[-1]] == (
        *history.prerequisites, history.phases[0])
    assert 'package-install' in selection.prerequisites
    assert 'retained-app-snapshot' not in selection.prerequisites
    runner.print_selection(selection)
    output = capsys.readouterr().out
    assert 'expected-executions: 8' in output
    for phase in history.phases:
        assert f'{phase}::{history.case_id} [selected]' in output
        command = runner.pytest_command(RUN, phase, selection)
        assert 'ONPC_SYSTEM_PHASE=' + phase in command
        assert runner.PAYLOAD + '/results/' + phase + '.xml' in command
        assert command[-1] == runner.PAYLOAD + '/test_removal.py::' + history.case_id
    for phase, semantic in zip(history.prerequisites, ('installed', 'rebooted')):
        assert runner.PHASE_SEMANTICS[phase] == semantic
        command = runner.pytest_command(RUN, phase, selection)
        assert 'ONPC_SYSTEM_PHASE=' + semantic in command
        assert runner.PAYLOAD + '/results/' + phase + '.xml' in command


@pytest.mark.parametrize('history', runner.REMOVAL_HISTORIES[1:], ids=lambda history: history.case_id)
def test_focused_recovery_inputs_freeze_full_import_closure(tmp_path, history):
    selection = runner.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    digest = runner.stage_selected_inputs(selection, tmp_path)
    identity = json.loads((tmp_path / 'selected-inputs.json').read_text())
    assert digest == runner.baseline.digest(tmp_path / 'selected-inputs.json')
    assert identity['selection']['phases'] == [*history.prerequisites, *history.phases]
    assert len(identity['selection']['executions']) == 8
    assert identity['selection']['executions'][-1] == {
        'phase': history.phases[-1], 'area': 'removal', 'case_id': history.case_id,
        'prerequisite': False}
    sources = ('test_removal.py', 'system_removal.py', 'system_removal_ownership.py',
               'system_guest.py', 'test_install_smoke.py', 'system_kiosk_accounts.py')
    if (history.case_id.startswith('test_identity_filesystem_refusal_retry[') or
            history.case_id == 'test_rpm_posterase_recovery'):
        sources += ('system_removal_identity.py',)
    if history.case_id == 'test_rpm_posterase_recovery':
        sources += ('guest_install_recipe.py',)
    for name in sources:
        record = identity['files'][name]
        assert (tmp_path / name).read_bytes() == (runner.ROOT / record['source']).read_bytes()
        assert record['sha256'] == runner.baseline.digest(tmp_path / name)
    for source in ('tests/integration/system_runner.py', 'tests/integration/system_snapshots.py'):
        assert identity['host_files'][source] == runner.baseline.digest(runner.ROOT / source)


@pytest.mark.parametrize('fault', [None, 'missing', 'extra', 'duplicate', 'identity', 'failure', 'skipped'])
@pytest.mark.parametrize('history,phase', [(history, phase)
                         for history in runner.REMOVAL_HISTORIES[1:]
                         for phase in history.phases])
def test_focused_recovery_junit_requires_exact_logical_identities(tmp_path, fault, history, phase):
    selection = runner.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    write_junit_results(tmp_path, selection, fault)
    if fault:
        # Both recovery phases execute the same registered case, while keeping
        # separate JUnit identities. Exercise each phase's audit independently.
        output = tmp_path / 'guest-results'
        (output / (phase + '.xml')).write_bytes(
            (output / (history.phases[-1] + '.xml')).read_bytes())
        with pytest.raises(runner.Error):
            runner.reconcile_junit(tmp_path, phase, selection)
    else:
        for phase in selection.phases:
            runner.reconcile_junit(tmp_path, phase, selection)
        evidence = runner.selection_evidence(tmp_path, selection)
        assert len(evidence['expected_executions']) == len(evidence['executed_cases']) == 8
        assert evidence['executed_cases'][-1] == {
            'phase': history.phases[-1], 'area': 'removal', 'case_id': selection.test}


@pytest.mark.parametrize('history,phase', [(history, phase)
                         for history in runner.REMOVAL_HISTORIES[1:]
                         for phase in history.phases])
def test_recovery_timeout_and_progress_use_logical_phase_and_restore_callback(history, phase):
    selection = runner.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    vm = Mock()
    previous = vm.commands.progress
    def call(command, *, timeout):
        assert timeout == 2400
        assert vm.commands.progress.phase == phase
        assert command == runner.pytest_command(RUN, phase, selection)
        raise runner.CommandError('test-refused')
    vm.call.side_effect = call
    with pytest.raises(runner.CommandError, match='test-refused'):
        runner.run_pytest(vm, RUN, phase, selection)
    assert vm.commands.progress is previous


@pytest.mark.parametrize('history', runner.REMOVAL_HISTORIES[1:], ids=lambda history: history.case_id)
def test_recovery_installed_activation_calls_guest_and_observer_with_installed_semantics(
        tmp_path, monkeypatch, history):
    import kiosk_entry
    selection = runner.resolve_selection(
        'removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    (tmp_path / 'input').mkdir()
    identity = {'entry.py': 'a' * 64}
    (tmp_path / 'input/selected-inputs.json').write_text(json.dumps({'host_files': identity}))
    monkeypatch.setattr(runner, 'kiosk_activation_host_inputs', Mock(return_value=identity))
    state = {'phase': 'installed', 'boot_sha256': 'a' * 64, 'execution_rules': {}}
    vm, lease = Mock(), Mock(state={'run': RUN})
    vm.call.side_effect = [json.dumps(state).encode(), b'', json.dumps(state).encode()]
    observer = Mock(return_value={'boot_sha256': 'a' * 64})
    monkeypatch.setattr(kiosk_entry, 'observe_activation', observer)
    runner.observe_kiosk_activation(vm, lease, tmp_path, selection, history.prerequisites[0])
    observer.assert_called_once_with(vm, lease, 'installed')
    assert [call.args[0] for call in vm.call.call_args_list] == [
        runner.guest_command(RUN, 'activation-state', 'installed'),
        runner.guest_command(RUN, 'prepare-activation-greeter'),
        runner.guest_command(RUN, 'activation-state', 'installed')]
    assert (tmp_path / ('guest-results/gdm-' + history.prerequisites[0] + '.json')).is_file()


@pytest.mark.parametrize('history', runner.REMOVAL_HISTORIES[1:], ids=lambda history: history.case_id)
def test_focused_recovery_rejects_foreign_phase_and_result_identity(tmp_path, history):
    selection = runner.resolve_selection('removal', history.case_id, inventories=RECOVERY_INVENTORIES)
    with pytest.raises(runner.Error, match='pytest:unselected-phase'):
        runner.pytest_command(RUN, 'removal', selection)
    write_junit_results(tmp_path, selection)
    path = tmp_path / ('guest-results/' + history.phases[-1] + '.xml')
    root = ET.parse(path)
    next(root.iter('testcase')).set('name', 'test_interrupted_finalization_retry[foreign]')
    root.write(path)
    with pytest.raises(runner.Error, match='pytest:missing-extra-or-duplicate-tests'):
        runner.reconcile_junit(tmp_path, history.phases[-1], selection)


@pytest.mark.parametrize('fault', [None, 'name', 'relative', 'traversal', 'special', 'empty'])
def test_rpm_staging_preserves_file_inventory_and_exact_transfer_digests(tmp_path, monkeypatch, fault):
    source = tmp_path / 'source'
    (source / 'fixtures').mkdir(parents=True)
    (source / 'fixtures/onpc-test-application.flatpak').write_bytes(b'fixture')
    (source / 'product.rpm').write_bytes(b'RPM archive')
    manifest = {'artifacts': {'package': {'path': 'product.rpm'},
                              'fixtures': {'path': 'fixtures'}}}
    monkeypatch.setitem(sys.modules, 'build_test_artifacts', Mock(verify=Mock(return_value=manifest)))
    monkeypatch.setitem(sys.modules, 'build_test_applications', Mock(verify=Mock()))
    path = {'relative': 'usr/bin/app', 'traversal': '/usr/../app'}.get(fault, '/usr/bin/app')
    mode = stat.S_IFIFO | 0o644 if fault == 'special' else stat.S_IFREG | 0o755
    rows = (f'{path}\t{mode}\t\n/usr/bin/link\t{stat.S_IFLNK | 0o777}\tapp\n'
            f'/usr/share/app\t{stat.S_IFDIR | 0o755}\t\n').encode()
    commands = Mock()
    commands.run.side_effect = [b'other' if fault == 'name' else b'oh-no-parent-control',
                                b'' if fault == 'empty' else rows]
    destination = tmp_path / 'staged'
    if fault:
        category = {'name': 'name', 'relative': 'path', 'traversal': 'path',
                    'special': 'special-file', 'empty': 'empty-package'}[fault]
        with pytest.raises(runner.Error, match='assets:' +
                ('package-' + category if category != 'empty-package' else category)):
            runner.stage_assets(source, destination, commands)
    else:
        assert runner.stage_assets(source, destination, commands) == manifest
        assert not (destination / 'package.deb').exists()
        assert json.loads((destination / 'installed-files.json').read_bytes()) == [
            {'path': '/usr/bin/app', 'kind': 'file', 'mode': 0o755, 'target': ''},
            {'path': '/usr/bin/link', 'kind': 'symlink', 'mode': 0o777, 'target': 'app'}]
        inventory = json.loads((destination / 'transfer-sha256.json').read_bytes())
        assert inventory == {str(p.relative_to(destination)): runner.baseline.digest(p)
                             for p in destination.rglob('*')
                             if p.is_file() and p.name != 'transfer-sha256.json'}
        assert inventory['package.rpm'] == hashlib.sha256(b'RPM archive').hexdigest()
    assert all(call.args[0][0] == 'rpm' for call in commands.run.call_args_list)



@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'format', 'identical'])
def test_explicit_previous_artifacts_bind_same_format_and_distinct_payload(
        tmp_path, monkeypatch, package_format, fault):
    (tmp_path / 'input').mkdir()
    previous_format = ('rpm' if package_format == 'deb' else 'deb') if fault == 'format' else package_format
    current = {'artifacts': {'package': {'path': 'current.' + package_format, 'sha256': 'a' * 64}}}
    old_digest = 'a' * 64 if fault == 'identical' else hashlib.sha256(b'previous').hexdigest()
    previous = {'artifacts': {'package': {'path': 'previous.' + previous_format,
                                        'sha256': old_digest}}, 'source': {'revision': 'previous'}}
    def stage(source, destination, commands):
        destination.mkdir()
        (destination / ('package.' + previous_format)).write_bytes(b'previous')
        return previous
    monkeypatch.setattr(runner, 'stage_assets', stage)
    if fault:
        with pytest.raises(runner.Error, match='assets:' + (
                'previous-package-format' if fault == 'format' else 'identical-update-payload')):
            runner.stage_previous_assets(tmp_path / 'source', tmp_path / 'previous', Mock(), current)
        assert list((tmp_path / 'input').iterdir()) == []
        assert 'previous_package' not in current
    else:
        runner.stage_previous_assets(tmp_path / 'source', tmp_path / 'previous', Mock(), current)
        copied = tmp_path / 'input' / ('previous-package.' + package_format)
        assert copied.read_bytes() == b'previous'
        assert runner.baseline.digest(copied) == old_digest
        receipt = json.loads((tmp_path / 'input/previous-inputs.json').read_bytes())
        assert receipt == current['previous_package'] == {
            'sha256': old_digest, 'source': previous['source']}


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
        'test': 1.0, 'collection': 0.0, 'cleanup': 0.0, 'finalization': 0.0,
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
    assert ubuntu_archive_sources(sources) == expected
    assert ubuntu_archive_sources(expected) == expected


@pytest.mark.parametrize('failure', [None, 'write', 'readback', 'missing-tools', 'symlink', 'wrong-package'])
@pytest.mark.parametrize('observation_only', [False, True])
@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_bootstrap_reuses_prepared_tools_and_independently_verifies_writes(tmp_path, failure, observation_only, package_format):
    commands, lease, guestfs = Mock(), Mock(), Mock()
    lease.capture.state = {'source': {'layout': {'disk': '/guarded-image'}},
                           'guest': {'preparation_record_sha256': 'e' * 64}}
    lease.state = {'run': RUN, 'baseline_sha256': 'd' * 64}
    lease.source.uuid = UUID
    (tmp_path / 'input').mkdir()
    if not observation_only:
        staged_format = ('rpm' if package_format == 'deb' else 'deb') if failure == 'wrong-package' else package_format
        (tmp_path / ('input/package.' + staged_format)).write_bytes(b'package')
    (tmp_path / 'input/selected-inputs.json').write_bytes(b'inputs')
    g, files = bootstrap_guest('fedora' if package_format == 'rpm' else 'ubuntu')
    if package_format == 'rpm':
        from guest_test_dependencies import FEDORA_VERSIONS
        g.inspect_get_distro.return_value = 'fedora'
        g.inspect_get_major_version.return_value = 44
        g.inspect_get_minor_version.return_value = 0
        files.pop('/var/lib/dpkg/status')
        files.pop('/etc/apt/sources.list.d/ubuntu.sources')
        files['/etc/os-release'] = b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n'
        files['/etc/selinux/config'] = b'SELINUX=enforcing\nSELINUXTYPE=targeted\n'
        g.inspect_list_applications2.return_value = [
            {'app2_name': name, 'app2_version': version} for name, version in FEDORA_VERSIONS.items()]
        g.feature_available.return_value = False
        g.is_file.return_value = True
    retire = Mock()
    guestfs.GuestFS.return_value = g
    authorized = '/root/.ssh/authorized_keys'
    prior = b'ssh-ed25519 QkJC prior-key\n'
    files[authorized] = prior
    if failure == 'missing-tools':
        if package_format == 'deb':
            files['/var/lib/dpkg/status'] = b''
        else:
            g.inspect_list_applications2.return_value = []
    if failure == 'symlink':
        g.is_symlink.side_effect = lambda path: path == authorized
    def write(path, data):
        if path == authorized and failure == 'write':
            raise runner.CommandError('bootstrap-write-failed')
        files[path] = data
    g.write.side_effect = write
    def close():
        if failure == 'readback':
            files[authorized] = b'wrong-key'
    g.close.side_effect = close
    (tmp_path / 'ssh-key.pub').write_bytes(b'ssh-ed25519 QUFB onpc-system-test\n')
    if failure and not (failure == 'wrong-package' and observation_only):
        with patch.object(runner, 'retire_snapshot_payload', retire), pytest.raises(
                (runner.CommandError, runner.Error, ValueError),
                match='assets:package-platform-mismatch' if failure == 'wrong-package' else None):
            runner.bootstrap(commands, lease, tmp_path, guestfs, observation_only=observation_only)
        assert g.close.call_count == (2 if failure == 'readback' else 1)
    else:
        with patch.object(runner, 'retire_snapshot_payload', retire):
            assert runner.bootstrap(commands, lease, tmp_path, guestfs,
                                    observation_only=observation_only) == 'ssh-ed25519 public-test-key'
        if observation_only:
            retire.assert_not_called()
        else:
            retire.assert_called_once_with(g, RUN)
        assert files[authorized] == prior + (tmp_path / 'ssh-key.pub').read_bytes()
        marker = json.loads(files['/etc/onpc-system-test.json'])
        assert ('package_sha256' in marker) != observation_only
        if observation_only:
            assert marker['scope'] == 'graphical-observation-only'
        g.add_drive_opts.assert_any_call('/guarded-image', format='qcow2', readonly=True)
        g.mount_ro.assert_called_once_with('/dev/sda2', '/')
        assert g.close.call_count == guestfs.GuestFS.call_count == 2
        # inspect_os unmounts filesystems. Never invoke it again after mounting
        # just to recover the root device for OS/package inspection.
        assert g.inspect_os.call_count == guestfs.GuestFS.call_count
        g.sync.assert_called_once()
        if package_format == 'rpm':
            import chinese_language_assets as language
            assert [call.args[0] for call in g.command.call_args_list] == [
                language.RPM_LIST_COMMAND,
                *map(language.rpm_file_command, language.FEDORA_PACKAGES),
                language.LOCALE_COMMAND, ['/usr/sbin/setfiles', '-m',
                '/etc/selinux/targeted/contexts/files/file_contexts',
                '/etc/onpc-system-test.json', '/root/.ssh']]
    assert [call.args[0][0] for call in commands.run.call_args_list] == ['ssh-keygen']




def test_isolation_enables_clipboard_and_preserves_disk():
    root = ET.fromstring(runner.isolated_xml(xml(), UUID, RUN))
    assert root.findtext('uuid') == UUID
    assert root.find('devices/disk/source').get('file') == '/image'
    for name in ('redirdev', 'hostdev'):
        assert not root.findall('devices/' + name)
    assert len(root.findall('devices/channel')) == 1
    assert root.find('devices/channel').attrib == {'type': 'spicevmc'}
    assert root.find('devices/channel/target').attrib == {
        'type': 'virtio', 'name': 'com.redhat.spice.0'}
    runner.validate_host_sharing(root)
    assert root.find('devices/graphics/clipboard').get('copypaste') == 'yes'
    assert root.find('devices/graphics/filetransfer').get('enable') == 'no'
    assert root.findtext('description') == runner.TAG + RUN


@pytest.mark.parametrize('driver', ['virtiofs', 'path'])
@pytest.mark.parametrize('graphics_type', ['spice', 'vnc'])
def test_isolation_removes_host_filesystems_without_changing_original(driver, graphics_type):
    original = ET.fromstring(xml())
    devices = original.find('devices')
    share = ET.SubElement(devices, 'filesystem', type='mount', accessmode='passthrough')
    ET.SubElement(share, 'driver', type=driver)
    ET.SubElement(share, 'source', dir='/host-checkout')
    ET.SubElement(share, 'target', dir='pst')
    original_xml = ET.tostring(original, encoding='unicode')

    isolated = ET.fromstring(runner.isolated_xml(
        original_xml, UUID, RUN, graphics_type=graphics_type))

    assert not isolated.findall('devices/filesystem')
    assert (runner.baseline.domain_layout(ET.tostring(isolated, encoding='unicode'), UUID) ==
            runner.baseline.domain_layout(original_xml, UUID))
    runner.validate_host_sharing(isolated)
    assert ET.fromstring(original_xml).find('devices/filesystem/source').get('dir') == '/host-checkout'


@pytest.mark.parametrize('old,new', [
    (runner.baseline.DOMAIN, 'host'), (UUID, 'other'), ('type="qcow2"', 'type="raw"'),
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
    view.run, view.domain_id = RUN, 8
    with pytest.raises(runner.Error, match='domain-replaced'):
        view.snapshot()


def test_source_view_preserves_task12_inventory_contract():
    source = Mock()
    original = runner.baseline.domain_layout(xml(), UUID)
    layout = runner.baseline.domain_layout(runner.isolated_xml(xml(), UUID, RUN), UUID)
    source.snapshot.return_value = (layout, True)
    source.connection.lookupByName.return_value.XMLDesc.return_value = runner.isolated_xml(xml(), UUID, RUN)
    view = runner.SourceView(source)
    view.run = RUN
    assert view.snapshot() == (original, True)


def marker():
    return {'purpose': 'onpc-system-test', 'run': RUN, 'machine_id': 'b' * 32,
            'host_machine_id': 'c' * 32, 'domain_uuid': UUID,
            'baseline_sha256': 'd' * 64, 'preparation_sha256': 'e' * 64,
            'package_sha256': 'f' * 64, 'selected_inputs_sha256': 'a' * 64}


def test_guest_guard_accepts_only_matching_isolated_vm():
    guest.validate_marker(marker(), RUN, 'b' * 32, UUID)


@pytest.mark.parametrize('field,value', [
    ('purpose', 'other'), ('run', 'b' * 32), ('domain_uuid', 'other'),
    ('host_machine_id', 'b' * 32), ('package_sha256', 'invalid'),
    ('selected_inputs_sha256', 'invalid'),
    ('machine_id', 'c' * 32),
])
def test_guest_marker_refuses_host_or_replacement(field, value):
    with pytest.raises(guest.GuestError):
        guest.validate_marker(marker() | {field: value}, RUN, 'b' * 32, UUID)




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
    assert 'ONPC_SYSTEM_PHASE=installed' in before
    assert 'ONPC_SYSTEM_PHASE=rebooted' in after
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


def test_authorization_selection_uses_retained_app_snapshot():
    case = 'test_method_role_matrix[ListManagedUsers-child1]'
    selection = runner.resolve_selection('authorization', case, inventories=INVENTORIES)
    assert selection.scope == 'partial'
    assert selection.phases == ('authorization',)
    assert [(item.phase, item.case_id, item.prerequisite) for item in selection.executions] == [
        ('authorization', case, False),
    ]
    assert selection.prerequisites == (
        'accepted-baseline', 'exclusive-vm-lease', 'offline-bootstrap',
        'retained-app-snapshot', 'authorization-accounts',
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
        'test_install_smoke.py', 'system_progress.py',
            'guest_test_dependencies.py',
            'chinese_language_assets.py',
        'guest_install_recipe.py', 'install-source/Makefile',
        'system_kiosk_accounts.py',
        'system_kiosk_admission.py', 'system_assertions.py',
        'system_kiosk_confinement.py', 'system_kiosk_scope.py',
        'system_kiosk_platform.py', 'system_wellbeing_qualification.py',
        'system_native_update.py', 'native_transaction.py',
            'system_first_configure.py', 'system_pam_variants.py', 'system_previous_upgrade.py',
        'system_removal.py', 'system_removal_faults.py',
        'system_removal_identity.py', 'system_removal_ownership.py',
        'system_enforcement.py', 'system_session_expiry.py', 'system_caller.py',
        'baseline_assets.py', 'native_assets.py', 'native_trust.py', 'system_trusted_fixtures.py', 'tests/__init__.py',
        'tests/fixtures/__init__.py', 'tests/fixtures/native_assets.py',
        'tests/fixtures/baseline_assets.py', 'tests/fixtures/native_trust.py',
    }


def test_authorization_selected_inputs_include_selected_test_and_helper(tmp_path):
    selection = runner.resolve_selection(
        'authorization', 'test_method_role_matrix[ListManagedUsers-child1]',
        inventories=INVENTORIES)
    digest = runner.stage_selected_inputs(selection, tmp_path)
    identity = json.loads((tmp_path / 'selected-inputs.json').read_text())

    assert digest == hashlib.sha256((tmp_path / 'selected-inputs.json').read_bytes()).hexdigest()
    assert {'test_authorization.py', 'system_caller.py'} <= set(
        identity['files'])
    assert 'test_install_smoke.py' not in identity['files']
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


def test_kiosk_classification_selection_preserves_its_reboot_history(tmp_path):
    case = 'test_kiosk_account_classification_survives_reboot'
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'], case)}
    selection = runner.resolve_selection('package', case, inventories=inventories)
    assert selection.phases == ('installed', 'rebooted')
    assert [(item.phase, item.case_id) for item in selection.executions] == [
        ('installed', case), ('rebooted', case)]
    runner.stage_selected_inputs(selection, tmp_path)
    identity = json.loads((tmp_path / 'selected-inputs.json').read_text())
    assert {'system_kiosk_accounts.py', 'system_kiosk_admission.py',
            'system_kiosk_confinement.py', 'system_assertions.py'} <= identity['files'].keys()
    for phase in selection.phases:
        assert runner.pytest_command(RUN, phase, selection)[-1].endswith('::' + case)
    assert identity['host_files'] == runner.kiosk_activation_host_inputs()


@pytest.mark.parametrize('fault', [None, 'before-source', 'after-source', 'policy', 'boot', 'same-boot'])
@pytest.mark.parametrize('history', [None, *runner.REMOVAL_HISTORIES[1:]],
                         ids=lambda history: history.case_id if history else 'package')
def test_real_activation_binds_exact_sources_policy_and_new_boot(tmp_path, monkeypatch, fault, history):
    import kiosk_entry
    case = runner.KIOSK_ACTIVATION_CASE
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'], case)}
    selection = (runner.resolve_selection('removal', history.case_id,
                                         inventories=RECOVERY_INVENTORIES) if history else
                 runner.resolve_selection('package', case, inventories=inventories))
    installed_phase, phase = history.prerequisites if history else ('installed', 'rebooted')
    (tmp_path / 'input').mkdir()
    (tmp_path / 'guest-results').mkdir()
    identity = {'entry.py': 'a' * 64}
    (tmp_path / 'input/selected-inputs.json').write_text(json.dumps({'host_files': identity}))
    (tmp_path / ('guest-results/gdm-' + installed_phase + '.json')).write_text(json.dumps({
        'boot_sha256': ('b' if fault == 'same-boot' else 'a') * 64}))
    inputs = Mock(side_effect=[{'entry.py': 'changed'} if fault == 'before-source' else identity,
                              {'entry.py': 'changed'} if fault == 'after-source' else identity])
    monkeypatch.setattr(runner, 'kiosk_activation_host_inputs', inputs)
    before = {'phase': 'rebooted', 'boot_sha256': 'b' * 64, 'execution_rules': {}}
    after = {**before, 'execution_rules': {'changed': True}} if fault == 'policy' else before
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.call.side_effect = [json.dumps(before).encode(), json.dumps(after).encode()]
    observation = {'phase': 'rebooted', 'boot_sha256': ('c' if fault == 'boot' else 'b') * 64,
                   'public_observations': [], 'engineering_confinement': {'backend': 'apparmor'}}
    entry = Mock(return_value=observation)
    monkeypatch.setattr(kiosk_entry, 'observe_activation', entry)
    if fault:
        with pytest.raises(runner.Error, match='kiosk-activation:'):
            runner.observe_kiosk_activation(vm, lease, tmp_path, selection, phase)
        assert not (tmp_path / ('guest-results/gdm-' + phase + '.json')).exists()
        if fault == 'before-source':
            entry.assert_not_called()
            vm.call.assert_not_called()
    else:
        runner.observe_kiosk_activation(vm, lease, tmp_path, selection, phase)
        retained = json.loads((tmp_path / ('guest-results/gdm-' + phase + '.json')).read_bytes())
        assert retained == {**observation, 'activation_state': after, 'host_files': identity}
        entry.assert_called_once_with(vm, lease, 'rebooted')
        assert [call.args[0] for call in vm.call.call_args_list] == [
            runner.guest_command(RUN, 'activation-state', 'rebooted')] * 2


@pytest.mark.parametrize('fault', [None, 'installed', 'rebooted'])
def test_real_gdm_stays_in_the_native_install_reboot_attempt(tmp_path, monkeypatch, fault):
    case = runner.KIOSK_ACTIVATION_CASE
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'], case)}
    selection = runner.resolve_selection('package', case, inventories=inventories)
    write_junit_results(tmp_path, selection)
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    events = []
    monkeypatch.setattr(runner, 'run_pytest', lambda _vm, _run, phase, _selection:
                        events.append('native-' + phase))
    vm.reboot.side_effect = lambda: events.append('reboot')
    def graphical(_vm, _lease, _directory, _selection, phase):
        assert (_vm, _lease, _directory, _selection) == (vm, lease, tmp_path, selection)
        events.append('gdm-' + phase)
        if phase == fault:
            raise runner.Error('gdm-observation-failed')
    monkeypatch.setattr(runner, 'observe_kiosk_activation', graphical)
    if fault:
        with pytest.raises(runner.Error, match='gdm-observation-failed'):
            runner.installed_run(vm, lease, tmp_path, selection)
    else:
        runner.installed_run(vm, lease, tmp_path, selection)
    expected = ['gdm-installed', 'native-installed', 'reboot', 'native-rebooted', 'gdm-rebooted']
    assert events == (expected[:1] if fault == 'installed' else expected)
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()


def test_unselected_package_case_never_enters_gdm(tmp_path):
    selection = runner.resolve_selection('package', 'test_first_install_requests_reboot',
                                         inventories=INVENTORIES)
    vm, lease = Mock(), Mock()
    runner.observe_kiosk_activation(vm, lease, tmp_path, selection, 'installed')
    vm.call.assert_not_called()
    lease.save.assert_not_called()


@pytest.mark.parametrize('failure,status,domain,category', [
    ('ui:restart-response', 0, 'product', 'ui:restart-response'),
    ('kiosk-activation:recipient', 0, 'infrastructure', 'kiosk-activation:recipient'),
    ('guest', 1, 'product', 'kiosk-activation:guest-check-failed'),
    ('guest', 255, 'infrastructure', 'command:failed:ssh'),
    ('kiosk-activation:boot-or-policy-changed', 0, 'product', 'kiosk-activation:boot-or-policy-changed'),
    ('kiosk-activation:host-inputs-changed', 0, 'infrastructure', 'kiosk-activation:host-inputs-changed'),
])
def test_gdm_failure_keeps_actionable_category_and_correct_domain(
        monkeypatch, failure, status, domain, category):
    from private_artifacts import EvidenceError
    error = (runner.CommandError('command:failed:ssh') if failure == 'guest' else
             runner.Error(failure) if failure.endswith(('policy-changed', 'inputs-changed')) else
             EvidenceError(failure))
    monkeypatch.setattr(runner, 'observe_kiosk_activation', Mock(side_effect=error))
    vm = Mock()
    vm.commands.last_returncode = status
    ledger = runner.RunLedger()
    with pytest.raises(type(error)):
        runner.run_kiosk_activation(vm, Mock(), Mock(), Mock(), 'installed', ledger)
    assert ledger.outcomes[domain] == {'outcome': 'failed', 'category': category}
    assert runner.record_caught_failure(ledger, error) == category


@pytest.mark.parametrize('phase,fault', [
    ('installed', None), ('rebooted', None),
    ('installed', 'routing'), ('installed', 'exercise'),
    ('installed', 'gates'), ('installed', 'execution'),
    ('installed', 'reboot-gate'), ('rebooted', 'verify-reboot'),
    ('rebooted', 'gates'), ('rebooted', 'execution'),
    ('installed', 'reboot-requested'), ('rebooted', 'reboot-cleared'),
    ('installed', 'policy-changed'),
])
def test_kiosk_activation_keeps_boundary_checks_in_the_same_guarded_history(
        monkeypatch, phase, fault):
    import system_kiosk_accounts as accounts
    import system_kiosk_admission as admission
    import system_kiosk_confinement as confinement

    case = load_module('private_install_activation',
                       runner.ROOT / 'tests/system/test_install_smoke.py')
    monkeypatch.setenv('ONPC_SYSTEM_PHASE', phase)
    events = []
    expected = {
        'installed': ['policy', 'installed', 'reboot-requested', 'routing', 'exercise',
                      'gates', 'execution', 'reboot-gate', 'policy'],
        'rebooted': ['installed', 'reboot-cleared', 'verify-reboot', 'gates', 'execution'],
    }[phase]

    def action(name, result=None):
        def invoke(*arguments, **options):
            events.append(name)
            if name == fault:
                if name in ('reboot-requested', 'reboot-cleared'):
                    return False
                raise guest.GuestError('activation:' + name)
            return result
        return invoke

    installed = Mock(side_effect=action('installed'))
    monkeypatch.setattr(guest, 'installed', installed)
    for name in ('reboot_requested', 'reboot_cleared'):
        monkeypatch.setattr(guest, name, action(name.replace('_', '-'), True))
    rule_reads = iter(('original', 'changed' if fault == 'policy-changed' else 'original'))

    def read_rules():
        events.append('policy')
        return next(rule_reads)

    monkeypatch.setattr(guest, 'execution_rule_state', read_rules)
    monkeypatch.setattr(guest, 'verify_reboot_gate', action('reboot-gate'))
    monkeypatch.setattr(accounts, 'exercise', action('exercise'))
    monkeypatch.setattr(accounts, 'verify_reboot', action('verify-reboot'))
    monkeypatch.setattr(admission, 'verify', action('routing'))
    monkeypatch.setattr(admission, 'verify_gates', action('gates'))
    monkeypatch.setattr(confinement, 'verify', action('execution'))

    if fault is None:
        case.test_kiosk_account_classification_survives_reboot(Mock())
    else:
        category = {'policy-changed': 'policy-changed-before-reboot',
                    'reboot-requested': 'reboot-not-requested',
                    'reboot-cleared': 'reboot-request-retained'}.get(fault, 'activation:')
        with pytest.raises(guest.GuestError, match=category):
            case.test_kiosk_account_classification_survives_reboot(Mock())
    assert events == (expected if fault in (None, 'policy-changed') else
                      expected[:expected.index(fault) + 1])
    installed.assert_called_once_with(reboot_required=phase == 'installed')


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('fault', [None, 'premature', 'account', 'nonroot', 'pidfd',
                                  'release-timeout', 'end', 'exit', 'body', 'body-timeout'])
def test_held_admission_owns_real_worker_protocol_and_failure_cleanup(
        monkeypatch, fault, package_format):
    import system_kiosk_admission as admission
    import system_kiosk_confinement as confinement

    child = Mock(pid=42, returncode=None)
    child.poll.return_value = 0 if fault == 'premature' else None
    spawn = Mock(return_value=child)
    monkeypatch.setattr(admission.subprocess, 'Popen', spawn)
    monkeypatch.setattr(guest, 'guard', Mock())
    monkeypatch.setattr(guest, 'package_path', Mock(return_value=admission.Path('package.' + package_format)))
    caller = Mock()
    caller.return_value.__enter__ = Mock(return_value=['fedora-caller', '-B'])
    caller.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(confinement, 'pam_caller_command', caller)
    monkeypatch.setattr(admission.os, 'pidfd_open', Mock(
        side_effect=OSError('pidfd-original') if fault == 'pidfd' else None, return_value=142))
    monkeypatch.setattr(admission.os, 'close', closed := Mock())
    monkeypatch.setattr(admission.signal, 'pidfd_send_signal', sent := Mock())
    root = Mock(side_effect=guest.GuestError('held-root-credentials') if fault == 'nonroot'
                else None)
    monkeypatch.setattr(admission, 'root_uids', root)
    monkeypatch.setattr(confinement, 'exited', Mock(return_value=fault == 'premature'))
    ready = {'pid': 42, 'uids': [0] * 4, 'account': 6 if fault == 'account' else 0}
    finished = (guest.GuestError('event-timeout') if fault == 'release-timeout' else
                {'account': 0, 'end': 4 if fault == 'end' else 0})
    monkeypatch.setattr(confinement, 'lifecycle_event', events := Mock(side_effect=[ready, finished]))
    monkeypatch.setattr(confinement, 'lifecycle_wait', waited := Mock(
        return_value=1 if fault == 'exit' else 0))
    if fault in ('body-timeout', 'pidfd'):
        child.wait.side_effect = [admission.subprocess.TimeoutExpired('owned-worker', 10), 0]
    if fault == 'body-timeout':
        child.stdout.close.side_effect = OSError('close-secondary')
    record = Mock()

    def exercise():
        with admission.held_account(record) as pid:
            assert pid == 42
            assert events.call_count == 1
            if fault in ('body', 'body-timeout'):
                raise guest.GuestError('body-original')
            if fault in (None, 'end', 'exit'):
                child.poll.return_value = 0

    if fault:
        category = {'premature': 'held-premature-exit', 'account': 'held-ready',
                    'nonroot': 'held-root-credentials', 'release-timeout': 'event-timeout',
                    'end': 'held-end-status', 'exit': 'held-exit-status',
                    'body': 'body-original', 'body-timeout': 'body-original',
                    'pidfd': 'pidfd-original'}[fault]
        with pytest.raises(OSError if fault == 'pidfd' else guest.GuestError,
                           match='pidfd-original' if fault == 'pidfd' else category) as caught:
            exercise()
        if fault == 'body-timeout':
            assert caught.value.__notes__ == ['kiosk-admission:held-cleanup-failed']
    else:
        exercise()
    assert spawn.call_args.args[0][-1] == 'held-account'
    assert spawn.call_args.kwargs == {'stdin': admission.subprocess.PIPE,
                                     'stdout': admission.subprocess.PIPE, 'close_fds': True}
    assert spawn.call_args.args[0][0] == ('fedora-caller' if package_format == 'rpm'
                                          else '/usr/bin/python3')
    assert caller.call_count == (package_format == 'rpm')
    if caller.called:
        caller.assert_called_once_with(guest.PAYLOAD, 'gdm-password')
    assert child.kill.call_count == (fault == 'pidfd')
    assert sent.call_count == (fault == 'body-timeout')
    if sent.called:
        sent.assert_called_once_with(142, admission.signal.SIGKILL)
        assert child.wait.call_count == 2
        assert all(call.kwargs == {'timeout': 10} for call in child.wait.call_args_list)
    assert waited.call_count == (fault in (None, 'exit'))
    child.stdin.close.assert_called()
    child.stdout.close.assert_called_once_with()
    assert closed.call_count == (fault != 'pidfd')


@pytest.mark.parametrize('uids', ['0\t0\t0\t0', '0\t0\t1007\t0', '0\t0\t0'])
def test_held_admission_checks_all_four_kernel_uids(monkeypatch, uids):
    import system_kiosk_admission as admission

    monkeypatch.setattr(admission.Path, 'read_text', Mock(return_value='Name:\tpython\nUid:\t' + uids))
    if uids == '0\t0\t0\t0':
        assert admission.root_uids(42) == [0] * 4
    else:
        with pytest.raises(guest.GuestError, match='held-root-credentials'):
            admission.root_uids(42)


@pytest.mark.parametrize('status,hold_failure', [(0, False), (6, False), (0, True)])
def test_held_admission_ends_actual_pam_handle_after_hold(monkeypatch, status, hold_failure):
    import system_kiosk_admission as admission

    monkeypatch.setattr(guest, 'guard', Mock())
    monkeypatch.setattr(guest, 'package_path', Mock(return_value=admission.Path('package.deb')))
    monkeypatch.setattr(admission.Path, 'exists', Mock(return_value=True))
    monkeypatch.setattr(admission.Path, 'lstat', Mock(return_value=SimpleNamespace(
        st_mode=stat.S_IFREG | 0o644, st_uid=0)))
    monkeypatch.setattr(admission.pwd, 'getpwnam', Mock(return_value=SimpleNamespace(
        pw_uid=1007, pw_name='oh-no-parent-control')))
    pam = Mock()
    pam.pam_start.return_value = 0
    pam.pam_acct_mgmt.return_value = status
    pam.pam_end.return_value = 0
    monkeypatch.setattr(admission.ctypes, 'CDLL', Mock(return_value=pam))

    def hold(observed):
        assert observed == status
        pam.pam_end.assert_not_called()
        if hold_failure:
            raise guest.GuestError('held-original')

    if hold_failure:
        with pytest.raises(guest.GuestError, match='held-original'):
            admission.pam_account('gdm-password', 'kiosk', hold=hold)
    else:
        assert admission.pam_account('gdm-password', 'kiosk', hold=hold) == {
            'account': status, 'end': 0}
    assert pam.pam_start.call_args.args[:2] == (b'gdm-password', b'oh-no-parent-control')
    pam.pam_end.assert_called_once_with(pam.pam_acct_mgmt.call_args.args[0], status)


@pytest.mark.parametrize('status,release', [(0, 'eof'), (6, 'eof'), (0, 'timeout'), (0, 'data')])
def test_held_admission_worker_requires_success_and_bounded_eof(monkeypatch, capsys, status, release):
    import system_kiosk_admission as admission

    monkeypatch.setattr(guest, 'guard', Mock())
    monkeypatch.setattr(admission, 'root_uids', Mock(return_value=[0] * 4))
    monkeypatch.setattr(admission.os, 'getpid', Mock(return_value=42))
    poll = Mock()
    poll.poll.return_value = [] if release == 'timeout' else [(0, 1)]
    monkeypatch.setattr(admission.select, 'poll', Mock(return_value=poll))
    monkeypatch.setattr(admission.os, 'read', read := Mock(
        return_value=b'x' if release == 'data' else b''))
    ended = Mock()

    def account(service, role, *, hold):
        assert (service, role) == ('gdm-password', 'kiosk')
        try:
            hold(status)
        finally:
            ended()
        return {'account': status, 'end': 0}

    monkeypatch.setattr(admission, 'pam_account', account)
    if status or release != 'eof':
        with pytest.raises(guest.GuestError, match='held-'):
            admission.held_worker()
    else:
        admission.held_worker()
    ended.assert_called_once_with()
    assert poll.poll.call_count == (status == 0)
    if status == 0:
        poll.poll.assert_called_once_with(240000)
    assert read.call_count == (status == 0 and release != 'timeout')
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == (0 if status else 2 if release == 'eof' else 1)


@pytest.mark.parametrize('states,fault', [
    (['inactive'], None), (['failed'], None),
    (['active', 'activating', 'deactivating', 'inactive'], None),
    (['deactivating', 'failed'], None),
    (['active'], 'deadline'), (['unknown'], 'state'),
    ([], 'guard'), ([], 'identity'),
    (['active'], 'later-guard'), (['active'], 'later-identity'),
])
def test_native_kiosk_handoff_wait_is_guarded_bounded_and_read_only(monkeypatch, states, fault):
    import system_kiosk_confinement as confinement

    account = SimpleNamespace(pw_uid=1007)
    guard = Mock(side_effect=(guest.GuestError('handoff:guard') if fault == 'guard' else
                             [None, guest.GuestError('handoff:guard')] if fault == 'later-guard'
                             else None))
    identities = [account] * max(1, len(states))
    if fault == 'later-identity':
        identities.append(SimpleNamespace(pw_uid=9999))
    elif fault == 'identity':
        identities[-1] = SimpleNamespace(pw_uid=9999)
    identity = Mock(side_effect=identities)
    run, sleep = Mock(side_effect=states), Mock()
    monkeypatch.setattr(confinement.guest, 'guard', guard)
    monkeypatch.setattr(confinement.pwd, 'getpwnam', identity)
    monkeypatch.setattr(confinement.guest, 'run', run)
    monkeypatch.setattr(confinement.time, 'sleep', sleep)
    monkeypatch.setattr(confinement.time, 'monotonic', Mock(
        side_effect=[0, 75] if fault == 'deadline' else [0] + [1] * len(states)))
    if fault:
        category = ('handoff:guard' if 'guard' in fault else
                    'kiosk-confinement:kiosk-identity-changed' if 'identity' in fault else
                    'kiosk-confinement:manager-already-active')
        with pytest.raises(guest.GuestError, match=category):
            confinement.wait_kiosk_inactive(account)
    else:
        confinement.wait_kiosk_inactive(account)
    assert run.call_count == len(states)
    assert sleep.call_count == (1 if fault in ('later-guard', 'later-identity') else
                                0 if fault else len(states) - 1)
    assert all(call.args == (['systemctl', 'show', '--value', '--property=ActiveState',
                             'user@1007.service'],) for call in run.call_args_list)
    assert all(call.args == ('oh-no-parent-control',) for call in identity.call_args_list)
    assert guard.call_count == len(states) + (fault in (
        'guard', 'identity', 'later-guard', 'later-identity'))
    if fault == 'guard':
        identity.assert_not_called()


@pytest.mark.parametrize('settled', ['inactive', 'failed', None])
@pytest.mark.parametrize('entrypoint', ['verify', 'verify_execution_boundary'])
def test_native_confinement_requires_natural_inactivity_before_start(monkeypatch, settled, entrypoint):
    import system_kiosk_confinement as confinement

    account = SimpleNamespace(pw_uid=1007, pw_shell='/usr/sbin/nologin')
    monkeypatch.setattr(confinement.guest, 'guard', Mock())
    monkeypatch.setattr(confinement.guest, 'enable_diagnostics', Mock())
    monkeypatch.setattr(confinement.Path, 'read_text', Mock(return_value='{"backend":"apparmor"}'))
    monkeypatch.setattr(confinement, 'record_native_packages', Mock())
    monkeypatch.setattr(confinement.pwd, 'getpwnam', Mock(return_value=account))
    monkeypatch.setattr(confinement.time, 'sleep', Mock())
    monkeypatch.setattr(confinement.time, 'monotonic', Mock(
        side_effect=[0, 1] if settled else [0, 75]))
    classification = ['busctl', '--system', 'get-property', 'org.freedesktop.Accounts',
                      '/org/freedesktop/Accounts/User1007', 'org.freedesktop.Accounts.User',
                      'SystemAccount']
    query = ['systemctl', 'show', '--value', '--property=ActiveState', 'user@1007.service']
    start = ['systemctl', 'start', 'user@1007.service']
    run = Mock(side_effect=['b false', 'active', settled, guest.GuestError('owned-start')]
               if settled else ['b false', 'active'])
    monkeypatch.setattr(confinement.guest, 'run', run)
    admission = Mock()
    monkeypatch.setattr(confinement, 'verify_loader_admission_refusal', admission)
    sequence, record = Mock(), Mock()
    sequence.attach_mock(run, 'run')
    sequence.attach_mock(admission, 'admission')
    with pytest.raises(guest.GuestError, match=(
            'owned-start' if settled else 'kiosk-confinement:manager-already-active')):
        getattr(confinement, entrypoint)(record)
    assert [call.args[0] for call in run.call_args_list] == (
        [classification, query, query, start] if settled else [classification, query])
    if settled:
        assert run.call_args.kwargs == {'timeout': 75}
        admission.assert_called_once_with({'backend': 'apparmor'}, record)
        assert [call[0] for call in sequence.mock_calls] == [
            'run', 'run', 'run', 'admission', 'run']
    else:
        admission.assert_not_called()


@pytest.mark.parametrize('backend', ['apparmor', 'selinux'])
@pytest.mark.parametrize('execution_failed', [False, True])
def test_complete_native_matrix_retains_policy_loss_checks_after_execution(
        tmp_path, monkeypatch, backend, execution_failed):
    import system_kiosk_confinement as confinement
    account, record = SimpleNamespace(pw_uid=1007), Mock()
    execution = Mock(side_effect=guest.GuestError('execution-failed') if execution_failed else None,
                     return_value=(account, backend))
    faults = Mock()
    monkeypatch.setattr(confinement, 'verify_execution_boundary', execution)
    monkeypatch.setattr(confinement, 'verify_admission_faults', faults)
    monkeypatch.setattr(confinement.guest, 'PAYLOAD', tmp_path)
    if execution_failed:
        with pytest.raises(guest.GuestError, match='execution-failed'):
            confinement.verify(record)
        faults.assert_not_called()
    else:
        confinement.verify(record)
        observed_account, directory, observed_backend, observed_record = faults.call_args.args
        assert (observed_account, observed_backend, observed_record) == (account, backend, record)
        assert directory.parent == tmp_path and not directory.exists()
        faults.assert_called_once()
    execution.assert_called_once_with(record)


@pytest.fixture
def native_census(monkeypatch):
    import system_kiosk_confinement as confinement

    config = {'backend': 'apparmor'}
    monkeypatch.setattr(confinement.guest, 'guard', guard := Mock())
    monkeypatch.setattr(confinement.pwd, 'getpwnam', Mock(
        return_value=SimpleNamespace(pw_uid=1007)))
    read_text = confinement.Path.read_text
    monkeypatch.setattr(confinement.Path, 'read_text', Mock(return_value=json.dumps(config)))
    monkeypatch.setattr(confinement.runpy, 'run_path', Mock(
        return_value={'enforcing': (enforcing := Mock())}))
    monkeypatch.setattr(confinement, 'manager_pid', manager := Mock(return_value=42))
    opened, closed = Mock(return_value=142), Mock()
    monkeypatch.setattr(confinement, 'os', SimpleNamespace(
        pidfd_open=opened, close=closed, readlink=confinement.os.readlink))
    monkeypatch.setattr(confinement, 'exited', exited := Mock(return_value=False))
    monkeypatch.setattr(confinement.time, 'sleep', sleep := Mock())
    monkeypatch.setattr(confinement.time, 'monotonic', Mock(return_value=0))
    observe = confinement.census_processes
    monkeypatch.setattr(confinement, 'census_processes', observation := Mock(
        return_value={'backend': 'apparmor', 'confined_thread_roles': {'onpc-kiosk-manager': 1}}))
    return SimpleNamespace(helper=confinement, config=config, guard=guard, enforcing=enforcing,
                           manager=manager, opened=opened, closed=closed, exited=exited,
                           sleep=sleep, observation=observation, read_text=read_text,
                           observe=observe)


def test_census_retries_complete_observation_with_one_pinned_manager(native_census):
    model = native_census
    error = guest.GuestError('kiosk-census:process-lifecycle-changed')
    complete = {'backend': 'apparmor', 'confined_thread_roles': {'onpc-kiosk-manager': 1}}
    model.observation.side_effect = [error, complete]
    assert model.helper.census(required_roles=('manager',)) == complete
    assert model.observation.call_count == model.guard.call_count == model.enforcing.call_count == 2
    assert model.observation.call_args_list[0] == model.observation.call_args_list[1]
    assert model.observation.call_args.args[3:] == (
        model.helper.PROC / '42', 142, 'user@1007.service')
    assert model.observation.call_args.kwargs == {'required_roles': ('manager',)}
    model.opened.assert_called_once_with(42)
    model.closed.assert_called_once_with(142)
    model.sleep.assert_called_once_with(0.05)


@pytest.fixture
def native_census_processes(native_census, tmp_path, monkeypatch):
    model = native_census
    helper = model.helper
    # Exercise the real observation, with two private proc-shaped processes.
    monkeypatch.setattr(helper, 'census_processes', model.observe)
    monkeypatch.setattr(helper, 'PROC', tmp_path)
    model.config.update(domains=['manager', 'app'],
                        apparmor_profiles=['onpc-kiosk-manager', 'onpc-kiosk-app'])
    processes = []
    for pid, role in ((42, 'manager'), (43, 'app')):
        process = tmp_path / str(pid)
        process.mkdir()
        processes.append(process)
        fields = ['S', '1'] + ['0'] * 17 + [str(pid * 100)]
        (process / 'stat').write_text(f'{pid} (fixture) ' + ' '.join(fields))
        (process / 'status').write_text('PPid:\t1\nUid:\t1007\t1007\t1007\t1007\n')
        (process / 'ns').mkdir()
        (process / 'ns/mnt').symlink_to('mnt:[private]')
        marker = process / 'root/usr/share/oh-no-parent-control/confinement/generation'
        marker.parent.mkdir(parents=True)
        marker.write_text('fixture-generation')
        attribute = 'attr/apparmor/current'
        (process / attribute).parent.mkdir(parents=True)
        (process / attribute).write_text('onpc-kiosk-' + role + ' (enforce)')
        thread = process / 'task' / str(pid)
        thread.mkdir(parents=True)
        for name in ('stat', 'status', 'ns', 'root', 'attr'):
            (thread / name).symlink_to(process / name)
    host = tmp_path / '1/ns/mnt'
    host.parent.mkdir(parents=True)
    host.symlink_to('mnt:[host]')
    iterate = helper.Path.iterdir
    monkeypatch.setattr(helper.Path, 'iterdir', lambda path: (
        iter(processes) if path == tmp_path else iterate(path)))
    monkeypatch.setattr(helper.Path, 'read_text', lambda path, *args, **kwargs: (
        json.dumps(model.config) if str(path) == '/usr/share/oh-no-parent-control/confinement/config.json'
        else model.read_text(path, *args, **kwargs)))
    model.processes = processes
    model.opened.side_effect = [100, 101, 102, 103, 104]
    return model


@pytest.mark.parametrize('race,error', [
    ('process-reused', None),
    ('thread-initial', FileNotFoundError), ('thread-final', FileNotFoundError),
    ('thread-initial', ProcessLookupError), ('thread-final', ProcessLookupError),
], ids=['process-reused', 'initial-enoent', 'final-enoent', 'initial-esrch', 'final-esrch'])
def test_census_transient_task_race_discards_partial_role_counts(
        native_census_processes, monkeypatch, race, error):
    model = native_census_processes
    helper, processes = model.helper, model.processes
    identity = helper.process_identity
    reads = 0

    def changing_identity(path):
        nonlocal reads
        value = identity(path)
        if path == processes[1]:
            reads += 1
            if reads == 2 and race == 'process-reused':
                return ('transient-change', *value[1:])
        return value

    monkeypatch.setattr(helper, 'process_identity', changing_identity)
    thread_stat = processes[1] / 'task/43/stat'
    read_text = helper.Path.read_text
    thread_reads = 0

    def disappearing_thread(path, *args, **kwargs):
        nonlocal thread_reads
        if path == thread_stat:
            thread_reads += 1
            if race != 'process-reused' and thread_reads == (1 if race == 'thread-initial' else 2):
                thread_stat.unlink()
                if error is ProcessLookupError:
                    raise ProcessLookupError('fixture task exited while parent remains live')
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(helper.Path, 'read_text', disappearing_thread)
    model.sleep.side_effect = lambda _delay: (
        thread_stat.symlink_to(processes[1] / 'stat') if not thread_stat.exists() else None)
    result = helper.census(required_roles=('manager', 'app'))
    assert result == {'backend': 'apparmor', 'confined_thread_roles': {
        'onpc-kiosk-manager': 1, 'onpc-kiosk-app': 1}}
    assert reads == (4 if race == 'process-reused' else 3)
    assert model.guard.call_count == model.enforcing.call_count == 2
    assert [call.args for call in model.manager.call_args_list] == [('user@1007.service',)] * 3
    assert model.exited.return_value is False  # The parent never exits to excuse the task race.
    model.sleep.assert_called_once_with(0.05)
    assert [call.args[0] for call in model.opened.call_args_list] == [42, 42, 43, 42, 43]
    assert [call.args[0] for call in model.closed.call_args_list] == [101, 102, 103, 104, 100]


@pytest.mark.parametrize('point', ['initial', 'final'])
def test_census_disappearing_thread_churn_reaches_original_deadline(
        native_census_processes, monkeypatch, point):
    model = native_census_processes
    helper = model.helper
    thread_stat = model.processes[1] / 'task/43/stat'
    read_text = helper.Path.read_text
    reads = 0

    def disappearing_thread(path, *args, **kwargs):
        nonlocal reads
        if path == thread_stat:
            reads += 1
            if point == 'initial' or reads % 2 == 0:
                thread_stat.unlink()
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(helper.Path, 'read_text', disappearing_thread)
    model.sleep.side_effect = lambda _delay: thread_stat.symlink_to(model.processes[1] / 'stat')
    monkeypatch.setattr(helper.time, 'monotonic', Mock(side_effect=[0, 1, 2, 5]))
    with pytest.raises(guest.GuestError, match='^kiosk-census:process-lifecycle-changed$'):
        helper.census(required_roles=('manager', 'app'))
    assert reads == (2 if point == 'initial' else 4)
    assert model.guard.call_count == model.enforcing.call_count == 2
    model.sleep.assert_called_once_with(0.05)
    assert model.exited.return_value is False
    assert [call.args[0] for call in model.opened.call_args_list] == [42, 42, 43, 42, 43]
    assert [call.args[0] for call in model.closed.call_args_list] == [101, 102, 103, 104, 100]


@pytest.mark.parametrize('fault,category', [
    ('label', 'kiosk-census:unconfined-thread'),
    ('generation', 'kiosk-census:unconfined-generation'),
    ('namespace', 'kiosk-census:unconfined-namespace'),
    ('credentials', 'kiosk-census:required-service-missing:app'),
    ('missing-label', 'kiosk-census:live-process-unreadable'),
    ('missing-generation', 'kiosk-census:live-process-unreadable'),
    ('missing-namespace', 'kiosk-census:live-process-unreadable'),
    ('unreadable-initial-identity', None),
    ('unreadable-final-identity', None),
])
def test_census_live_thread_security_failure_is_terminal(
        native_census_processes, monkeypatch, fault, category):
    model = native_census_processes
    helper = model.helper
    process = model.processes[1]
    if fault in ('label', 'missing-label'):
        target = process / 'attr/apparmor/current'
        if fault == 'missing-label':
            target.unlink()
        else:
            target.write_text('unconfined (enforce)')
    elif fault in ('generation', 'missing-generation'):
        target = process / 'root/usr/share/oh-no-parent-control/confinement/generation'
        if fault == 'missing-generation':
            target.unlink()
        else:
            target.write_text('different-generation')
    elif fault in ('namespace', 'missing-namespace'):
        target = process / 'ns/mnt'
        target.unlink()
        if fault == 'namespace':
            target.symlink_to('mnt:[host]')
    elif fault == 'credentials':
        (process / 'status').write_text('PPid:\t1\nUid:\t0\t0\t0\t0\n')
    else:
        read_text = helper.Path.read_text
        reads = 0

        def unreadable_identity(path, *args, **kwargs):
            nonlocal reads
            if path == process / 'task/43/stat':
                reads += 1
                if reads == (1 if fault == 'unreadable-initial-identity' else 2):
                    raise PermissionError('fixture live task identity access denied')
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(helper.Path, 'read_text', unreadable_identity)
    with pytest.raises(guest.GuestError if category else PermissionError,
                       match='^' + category + '$' if category else 'identity access denied'):
        helper.census(required_roles=('manager', 'app'))
    model.sleep.assert_not_called()
    assert model.guard.call_count == model.enforcing.call_count == 1
    assert model.exited.return_value is False
    assert [call.args[0] for call in model.opened.call_args_list] == [42, 42, 43]
    assert [call.args[0] for call in model.closed.call_args_list] == [101, 102, 100]


@pytest.mark.parametrize('expires', ['before-retry', 'after-guard', 'persistent'])
def test_census_persistent_race_retains_first_error_and_closes_manager(native_census, monkeypatch, expires):
    model = native_census
    first = guest.GuestError('kiosk-census:process-lifecycle-changed')
    later = guest.GuestError('kiosk-census:process-lifecycle-changed')
    model.observation.side_effect = [first, later]
    monkeypatch.setattr(model.helper.time, 'monotonic', Mock(side_effect={
        'before-retry': [0, 5], 'after-guard': [0, 1, 5], 'persistent': [0, 1, 2, 5],
    }[expires]))
    with pytest.raises(guest.GuestError) as failure:
        model.helper.census()
    assert failure.value is first
    assert model.observation.call_count == (2 if expires == 'persistent' else 1)
    model.closed.assert_called_once_with(142)
    model.opened.assert_called_once_with(42)


@pytest.mark.parametrize('category', [
    'kiosk-census:manager-lifecycle-changed', 'kiosk-census:manager-uid',
    'kiosk-census:manager-label', 'kiosk-census:manager-generation',
    'kiosk-census:required-service-missing:app', 'kiosk-census:unknown-required-role',
    'kiosk-census:unconfined-thread', 'kiosk-census:unenforced-thread',
    'kiosk-census:unconfined-namespace', 'kiosk-census:unconfined-generation',
    'kiosk-census:live-process-unreadable', 'kiosk-password:credentials',
])
def test_census_never_retries_security_or_ownership_failure(native_census, category):
    model = native_census
    original = guest.GuestError(category)
    model.observation.side_effect = original
    with pytest.raises(guest.GuestError) as failure:
        model.helper.census()
    assert failure.value is original
    model.observation.assert_called_once()
    model.sleep.assert_not_called()
    model.closed.assert_called_once_with(142)


@pytest.mark.parametrize('fault', ['guard', 'enforcing', 'manager-exited', 'manager-replaced'])
def test_census_rechecks_policy_and_pinned_manager_before_retry(native_census, fault):
    model = native_census
    model.observation.side_effect = guest.GuestError('kiosk-census:process-lifecycle-changed')
    if fault in ('guard', 'enforcing'):
        getattr(model, fault).side_effect = [None, guest.GuestError('retry:' + fault)]
        category = 'retry:' + fault
    else:
        model.exited.return_value = fault == 'manager-exited'
        model.manager.side_effect = [42, 99] if fault == 'manager-replaced' else None
        category = 'kiosk-census:manager-lifecycle-changed'
    with pytest.raises(guest.GuestError, match=category):
        model.helper.census()
    model.observation.assert_called_once()
    model.opened.assert_called_once_with(42)
    model.closed.assert_called_once_with(142)


def test_conflicting_helper_targets_are_refused_before_any_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'COMMON_SELECTED_INPUTS', (
        *runner.COMMON_SELECTED_INPUTS,
        ('tests/integration/system_enforcement.py', 'system_guest.py'),
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
    assert 'retained-app-snapshot' in output
    assert 'installed::test_installed_package' not in output


def test_selected_execution_reaches_normal_guarded_prerequisite_checks(monkeypatch, capsys):
    monkeypatch.setattr(runner.baseline.guest_contract, 'CHECKOUT', runner.ROOT)
    monkeypatch.setattr(runner, 'collect_area_cases', lambda name: INVENTORIES[name])
    monkeypatch.setattr(runner.shutil, 'which', Mock(return_value=None))
    monkeypatch.setattr(runner.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(runner.os, 'getegid', lambda: 0)
    assert runner.main(['--vm', vm_name(), '--area', 'authorization']) == 1
    output = capsys.readouterr().err
    assert 'selection:scope=partial phases=1 executions=2' in output
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
        assert runner.main(['--vm', vm_name(), '--check-tools']) == 1
    assert f'tools:missing:{missing}; run ./setup.sh' in capsys.readouterr().err
    mkdir.assert_not_called()
    lease.assert_not_called()


def test_preparation_failure_category_preserves_reason_without_private_details():
    error = runner.baseline.guest_contract.PreparationError(
        'marker:dependencies', 'private guest details')
    assert runner.error_category(error) == 'marker:dependencies'
    assert runner.error_category(RuntimeError('private guest details')) == 'unexpected-failure-or-interruption'


@pytest.mark.parametrize('message', [
    'guest-tools:missing-or-mismatched-package; run tools/prepare-vm on the host',
    'baseline:chinese-locale-runtime; run tools/prepare-vm',
    'baseline:chinese-missing-file; run tools/prepare-vm',
    'baseline:chinese-package-bytes; run tools/prepare-vm',
    'baseline:chinese-read-command; run tools/prepare-vm',
    'baseline:chinese-command-bound; run tools/prepare-vm',
    'baseline:chinese-release; run tools/prepare-vm',
    'baseline:chinese-selinux; run tools/prepare-vm',
    'baseline:chinese-package-status; run tools/prepare-vm',
    'baseline:chinese-missing-package; run tools/prepare-vm',
    'baseline:chinese-receipt-platform; run tools/prepare-vm',
])
def test_baseline_prerequisite_failure_keeps_only_exact_public_reason(message):
    assert runner.error_category(ValueError(message)) == message
    for text in (message + ':private details', message + '\nprivate details',
                 'baseline:chinese-private-details; run tools/prepare-vm',
                 'guest-tools:private-details'):
        assert runner.error_category(ValueError(text)) == 'unexpected-failure-or-interruption'
    assert runner.error_category(RuntimeError(message)) == 'unexpected-failure-or-interruption'


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
        assert runner.main(['--vm', vm_name(), '--artifacts', str(runner.ROOT)]) == 1
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
    with pytest.raises(runner.Error, match='pytest:unselected-phase'):
        runner.pytest_command(RUN, 'installed', selection)


@pytest.mark.parametrize('lease_count', [0, 2])
def test_readiness_timeout_is_bounded_without_fixed_sleep(monkeypatch, capsys, lease_count):
    source = Mock()
    source.api.VIR_IP_ADDR_TYPE_IPV4 = 1
    source.domain.interfaceAddresses.return_value = {
        str(index): {'addrs': [{'type': 1, 'addr': f'192.168.122.{index + 2}'}]}
        for index in range(lease_count)}
    clock = iter([0, 0, 2, 2])
    monkeypatch.setattr(runner.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(runner.threading, 'Event', Mock)
    with pytest.raises(runner.Error, match='readiness-timeout'):
        runner.address(source, timeout=1)
    assert f'ipv4-lease-count={lease_count}' in capsys.readouterr().err
    source.api.virEventRemoveTimeout.assert_called_once()


def test_address_waits_for_one_valid_lease_after_initial_absence(monkeypatch):
    source = Mock()
    source.api.VIR_IP_ADDR_TYPE_IPV4 = 1
    source.domain.interfaceAddresses.side_effect = [
        {}, {'eth0': {'addrs': [{'type': 1, 'addr': '192.168.122.14'}]}}]
    monkeypatch.setattr(runner.time, 'monotonic', lambda: 0)
    event = Mock()
    monkeypatch.setattr(runner.threading, 'Event', lambda: event)
    assert runner.address(source, timeout=1) == '192.168.122.14'
    event.wait.assert_called_once()
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




@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
@pytest.mark.parametrize('update', [False, True])
def test_all_pytest_phases_reconcile_exact_unskipped_identities(tmp_path, update, monkeypatch, package_format):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    capture = Mock()
    monkeypatch.setattr(runner, 'capture_session_screen', capture)
    selection = runner.resolve_selection(inventories=INVENTORIES)
    if update:
        (tmp_path / 'input').mkdir()
        (tmp_path / 'input' / ('previous-package.' + package_format)).write_bytes(b'old payload')
    write_junit_results(tmp_path, selection)
    ledger = runner.RunLedger()
    result = runner.installed_run(vm, lease, tmp_path, selection, ledger)
    # The controller starts one continuous installation history. Later package
    # changes belong to the guarded lifecycle phases, without a snapshot reset.
    install_command = runner.guest_command(RUN, 'upgrade' if update else 'install')
    assert sum(call.args[0] == install_command for call in vm.call.call_args_list) == 1
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()
    assert result['authorization'] == (
        ('authorization', 'test_method_role_matrix[ListManagedUsers-child1]'),
        ('authorization', 'test_real_selected_parent_authentication[child1]'),
    )
    assert vm.reboot.call_count == 6 + update
    assert vm.call.call_count == 14 + update
    assert vm.call.call_args_list[2 + update].args[0] == runner.guest_command(RUN, 'collect', 'installed')
    if update:
        calls = vm.method_calls
        old = next(i for i, c in enumerate(calls)
                   if c[0] == 'call' and c.args[0] == runner.guest_command(RUN, 'install-previous'))
        new = next(i for i, c in enumerate(calls)
                   if c[0] == 'call' and c.args[0] == runner.guest_command(RUN, 'upgrade'))
        assert old < new and any(c[0] == 'reboot' for c in calls[old + 1:new])
    assert [call.args[0] for call in vm.call.call_args_list
            if '--junitxml' in call.args[0]] == [
        runner.pytest_command(RUN, phase, selection) for phase in selection.phases]
    assert ledger.outcomes['product'] == {'outcome': 'passed', 'category': None}
    assert ledger.outcomes['collection'] == {'outcome': 'passed', 'category': None}
    capture.assert_called_once_with(lease, tmp_path / 'guest-results')


@pytest.mark.parametrize('lost', [False, True])
@pytest.mark.parametrize('fresh', [False, True])
def test_session_capture_checks_ownership_before_and_after_stream(tmp_path, monkeypatch, lost, fresh):
    if fresh:
        tmp_path = tmp_path / 'guest-results'
    monkeypatch.setattr(runner.time, 'sleep', lambda _seconds: None)
    lease = Mock()
    lease.source.domain.screenshot.return_value = 'image/png'
    stream = lease.source.connection.newStream.return_value
    stream.recvAll.side_effect = lambda callback, opaque: callback(stream, b'fixed-image', opaque)
    if lost:
        lease.guard.side_effect = [None, None, None, runner.Error('guard:replaced')]
        with pytest.raises(runner.Error, match='guard:replaced'):
            runner.capture_session_screen(lease, tmp_path)
        stream.abort.assert_called_once()
    else:
        runner.capture_session_screen(lease, tmp_path)
        assert (tmp_path / 'session-screen.png').read_bytes() == b'fixed-image'
        stream.abort.assert_not_called()
    assert lease.guard.call_count == 4
    lease.source.domain.sendKey.assert_called_once_with(
        lease.source.api.VIR_KEYCODE_SET_LINUX, 100, [42], 1, 0)
    stream.finish.assert_called_once()


def test_session_capture_refuses_before_vm_access(tmp_path):
    lease = Mock()
    lease.guard.side_effect = runner.Error('guard:refused')
    with pytest.raises(runner.Error, match='guard:refused'):
        runner.capture_session_screen(lease, tmp_path)
    lease.source.connection.newStream.assert_not_called()
    lease.source.domain.screenshot.assert_not_called()
    lease.source.domain.sendKey.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('after_wait', [False, True])
def test_session_capture_refuses_lost_ownership_after_waking(tmp_path, monkeypatch, after_wait):
    monkeypatch.setattr(runner.time, 'sleep', lambda _seconds: None)
    lease = Mock()
    lease.guard.side_effect = [None, *([None] if after_wait else []), runner.Error('guard:replaced')]
    with pytest.raises(runner.Error, match='guard:replaced'):
        runner.capture_session_screen(lease, tmp_path)
    lease.source.domain.sendKey.assert_called_once()
    lease.source.connection.newStream.assert_not_called()
    lease.source.domain.screenshot.assert_not_called()
    assert not list(tmp_path.iterdir())


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
    assert selection.phases == ('enforcement',)
    assert [(item.area, item.case_id) for item in selection.executions if not item.prerequisite] == [
        ('enforcement', case)]
    assert len(selection.executions) == 1
    assert 'native-enforcement-fixture' in selection.prerequisites
    assert 'authorization-accounts' not in selection.prerequisites
    digest = runner.stage_selected_inputs(selection, tmp_path)
    manifest = json.loads((tmp_path / 'selected-inputs.json').read_text())
    assert len(digest) == 64
    assert {'test_enforcement.py', 'system_enforcement.py', 'system_caller.py'} <= manifest['files'].keys()
    assert 'test_install_smoke.py' not in manifest['files']
    assert 'test_authorization.py' not in manifest['files']
    command = runner.pytest_command(RUN, 'enforcement', selection)
    assert command[-1] == f'{runner.PAYLOAD}/test_enforcement.py::{case}'


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'failure', 'skipped', 'identity'])
def test_enforcement_results_must_match_executed_case(tmp_path, fault):
    selection = runner.resolve_selection('enforcement', inventories=INVENTORIES)
    write_junit_results(tmp_path, selection, fault)
    with pytest.raises(runner.Error, match=':enforcement'):
        runner.reconcile_junit(tmp_path, 'enforcement', selection)


@pytest.mark.parametrize(('area', 'capture_failure'), [
    ('enforcement', False), ('session', False), ('session', True),
])
def test_runtime_failure_keeps_product_attribution_and_collects(
        tmp_path, monkeypatch, area, capture_failure):
    vm, lease = Mock(), Mock()
    lease.state = {'run': RUN}
    vm.commands.last_returncode = 1
    capture = Mock(side_effect=runner.Error('capture:failed') if capture_failure else None)
    monkeypatch.setattr(runner, 'capture_session_screen', capture)
    selection = runner.resolve_selection(area, inventories=INVENTORIES)
    failed_command = runner.pytest_command(RUN, area, selection)

    def invoke(command, **kwargs):
        if command == failed_command:
            raise runner.CommandError('command:failed:ssh')
        return b''

    vm.call.side_effect = invoke
    ledger = runner.RunLedger()
    with pytest.raises(runner.CommandError, match='command:failed:ssh'):
        runner.installed_run(vm, lease, tmp_path, selection, ledger)
    assert ledger.outcomes['product'] == {
        'outcome': 'failed', 'category': 'pytest:failed:' + area}
    assert vm.call.call_args.args[0] == runner.guest_command(RUN, 'collect', 'failed')
    assert sum(call.args[0] == failed_command for call in vm.call.call_args_list) == 1
    assert capture.call_count == int(area == 'session')
    if capture_failure:
        assert ledger.outcomes['collection'] == {'outcome': 'failed', 'category': 'capture:failed'}


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
    assert result['junit_collection'] == {'authorization': 'collected'}
    assert len(result['expected_executions']) == len(result['executed_cases']) == 1
    assert result['expected_executions'][-1] == {
        'phase': 'authorization', 'area': 'authorization', 'case_id': case,
        'prerequisite': False,
    }
    assert result['executed_cases'][-1] == {
        'phase': 'authorization', 'area': 'authorization', 'case_id': case,
    }


def test_public_evidence_records_stage_timings_and_separate_outcomes(tmp_path):
    from tools import test_retention
    tmp_path.chmod(0o700)
    info = tmp_path.stat()
    record = dict(path=str(tmp_path), device=info.st_dev, inode=info.st_ino, mode=0o700)
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
    lease.capture.verification_totals = {'calls': 2, 'bytes_read': 8192, 'failures': 0,
                                        'duration_seconds': 0.5}
    ledger = runner.RunLedger()
    ledger.durations['preparation'] = 1.25
    ledger.pass_outcome('product')
    ledger.pass_outcome('infrastructure')
    ledger.fail_outcome('collection', 'collection:missing')
    ledger.pass_outcome('cleanup')

    assert runner.evidence(tmp_path, manifest, lease, False, 'collection:missing',
                           selection, 'd' * 64, ledger) == (False, 'collection:missing')
    test_retention.remove(record, validate_only=True)

    result = json.loads((tmp_path / 'evidence/result.json').read_text())
    assert result['category'] == 'collection:missing'
    assert result['selected_inputs_sha256'] == 'd' * 64
    assert result['stage_durations_seconds']['preparation'] == 1.25
    assert result['baseline_verification'] == lease.capture.verification_totals
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
    lease.capture.verification_totals = {}
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


@pytest.mark.parametrize('name', runner.baseline.SNAPSHOT_NAMES)
def test_restore_never_requests_boot_or_deletes_snapshot(local_preparation_source, name):
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.state = {'proof': {'name': name}}
    lease.capture.revalidate = Mock()
    lease.snapshot_xml = 'snapshot'
    lease.source.baseline.return_value = 'snapshot'
    lease.source.uuid = UUID
    lease.state = {'domain_uuid': UUID}
    original = lease.source.domain
    fresh = Mock(UUIDString=Mock(return_value=UUID))
    lease.source.connection.lookupByUUIDString.return_value = fresh
    snapshot = lease.source.domain.snapshotLookupByName.return_value
    snapshot.getXMLDesc.return_value = 'snapshot'
    lease.restore()
    original.snapshotLookupByName.assert_called_once_with(name, 0)
    original.revertToSnapshot.assert_called_once_with(snapshot, 0)
    lease.source.connection.lookupByUUIDString.assert_called_once_with(UUID)
    assert lease.source.domain is fresh
    snapshot.delete.assert_not_called()
    lease.source.domain.create.assert_not_called()
    original.create.assert_not_called()


def test_restore_refuses_changed_snapshot(local_preparation_source):
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.revalidate = Mock()
    lease.snapshot_xml = 'snapshot'
    lease.source.domain.snapshotLookupByName.return_value.getXMLDesc.return_value = 'replaced'
    with pytest.raises(runner.Error, match='snapshot-metadata-changed'):
        lease.restore()
    lease.source.domain.revertToSnapshot.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'restore', 'off-guard'])
def test_recording_seals_reset_only_after_owned_restore_and_final_off_guard(
        local_preparation_source, monkeypatch, fault):
    from tools import vm_recording
    release = Mock()
    monkeypatch.setattr(vm_recording, 'capture_safe_after_shutdown', release)
    lease = runner.Lease(Mock(), Mock(), Mock())
    lease.capture.state = {'proof': {'name': 'onpc_baseline'}}
    lease.snapshot_xml = 'snapshot'
    lease.source.uuid = UUID
    lease.state = {'domain_uuid': UUID}
    lease.source.domain.snapshotLookupByName.return_value.getXMLDesc.return_value = 'snapshot'
    lease.source.connection.lookupByUUIDString.return_value = Mock(UUIDString=Mock(return_value=UUID))
    lease.guard = Mock(side_effect=[None, RuntimeError('off proof failed')]
                       if fault == 'off-guard' else None)
    if fault == 'restore':
        lease.source.domain.revertToSnapshot.side_effect = RuntimeError('restore failed')
    if fault:
        with pytest.raises(RuntimeError):
            lease.restore()
        release.assert_not_called()
    else:
        lease.restore()
        release.assert_called_once_with(root=runner.ROOT)
        assert lease.guard.call_count == 2
        assert lease.guard.call_args.kwargs == {'off': True}


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
        assert lease.commands.lock_fd == lease.fd
        lease.capture.verify_snapshot()
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
