"""System lifecycle and installed cases share E2E snapshot preparation safely."""

import json
from unittest.mock import Mock

import pytest

import system_runner as system
import system_snapshots as snapshots
from tests.support.vm_runner import INVENTORIES, RECOVERY_INVENTORIES, RUN, write_junit_results, legacy_lease


@pytest.fixture(params=[{'fixture_boundary': 'clean', 'ubuntu_version': '26.04'},
                        {'fixture_boundary': 'clean', 'os_id': 'fedora', 'version': '44'}],
                ids=['ubuntu', 'fedora'])
def qualified_guest(request):
    return dict(request.param)


@pytest.mark.parametrize('failure', [None, 'provision', 'readiness'])
def test_product_free_preparation_precedes_all_input_and_never_collects_engineering_probe(
        tmp_path, monkeypatch, failure, qualified_guest):
    import system_fixture_preparation as preparation
    events = []
    selection = system.resolve_selection('package', 'test_first_install_requests_reboot',
                                         inventories=INVENTORIES)
    lease = Mock(state={'run': RUN})
    lease.capture.state = {'guest': qualified_guest}
    vm = Mock()
    vm.probe_ready.side_effect = lambda: events.append('ssh-ready')
    record = {'frozen': 'caller-input'}
    monkeypatch.setattr(preparation, 'selection_record', lambda value, target=None: value)
    controller = Mock()
    controller.require_ready.side_effect = lambda receipt: events.append('guard-ready')
    if failure == 'readiness':
        controller.require_ready.side_effect = ValueError('stale-readiness')

    def prepare(transport, owned_lease, directory, frozen):
        assert (transport, owned_lease, directory, frozen) == (vm, lease, tmp_path, record)
        events.append('provision')
        if failure == 'provision':
            raise ValueError('input-refused')
        return {'vm': vm, 'lease': lease, 'directory': directory,
                'controller': controller, 'receipt': 'current-boot'}

    monkeypatch.setattr(preparation, 'prepare', prepare)

    def observer(stage, context):
        events.append(stage)
        assert context['vm'] is vm
        return {'stage': stage}

    arguments = dict(fixture_selection=record, preparation_only=True,
                     preparation_observer=observer)
    if failure:
        with pytest.raises(ValueError):
            system.installed_run(vm, lease, tmp_path, selection, **arguments)
    else:
        assert system.installed_run(vm, lease, tmp_path, selection, **arguments) == {'stage': 'ready'}
    assert events == (['ssh-ready', 'before', 'provision'] if failure == 'provision' else
                      ['ssh-ready', 'before', 'provision', 'ready'] if failure == 'readiness' else
                      ['ssh-ready', 'before', 'provision', 'ready', 'guard-ready'])
    vm.copy.assert_not_called()
    vm.call.assert_not_called()
    vm.reboot.assert_not_called()
    vm.wait_boot_complete.assert_not_called()


@pytest.mark.parametrize('installed,guest', [
    (True, {'fixture_boundary': 'clean', 'os_id': 'fedora', 'version': '44'}),
    (False, {'fixture_boundary': 'clean', 'os_id': 'fedora', 'version': '43'}),
    (False, {'fixture_boundary': 'clean', 'ubuntu_version': '26.10'}),
])
def test_unqualified_clean_system_routes_refuse_before_input(tmp_path, installed, guest):
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
    lease.capture.state = {'guest': guest}
    selection = system.resolve_selection('package', 'test_first_install_requests_reboot',
                                         inventories=INVENTORIES)
    with pytest.raises(system.Error, match='target-not-qualified'):
        system.installed_run(vm, lease, tmp_path, selection, already_installed=installed)
    assert vm.mock_calls == []


def test_clean_system_missing_selection_refuses_before_transport(tmp_path, qualified_guest):
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
    lease.capture.state = {'guest': qualified_guest}
    selection = system.resolve_selection('package', 'test_first_install_requests_reboot',
                                         inventories=INVENTORIES)
    with pytest.raises(ValueError, match='execution-selection-required'):
        system.installed_run(vm, lease, tmp_path, selection)
    assert vm.mock_calls == []


def test_shared_system_adapter_authenticates_before_provision_and_uses_only_hard_subset(
        tmp_path, monkeypatch, qualified_guest):
    import system_fixture_preparation as preparation
    record = {'frozen': 'caller-input'}
    lease, vm = legacy_lease(), Mock()
    lease.capture.state = {'guest': qualified_guest}
    events = []
    expected_target = qualified_guest.get('os_id', 'ubuntu')
    def selection_record(value, target=None):
        assert target == expected_target
        return value
    monkeypatch.setattr(preparation, 'selection_record', selection_record)
    monkeypatch.setattr(preparation.fixture_execution, 'verify',
                        lambda value: events.append(('verify', value)))
    controller = Mock()
    controller.provision.side_effect = lambda *args, **kwargs: events.append(
        ('provision', args, kwargs)) or 'receipt'
    factory = Mock(return_value=controller)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    prepared = preparation.prepare(vm, lease, tmp_path, record)
    assert events == [('verify', record),
        ('provision', (record, ('trusted-hard',)), {'attempt_id': preparation.attempt_id(tmp_path)})]
    controller.require_ready.assert_called_once_with('receipt')
    assert prepared['controller'] is controller and prepared['receipt'] == 'receipt'
    vm.copy.assert_not_called()
    vm.call.assert_not_called()


def test_shared_system_adapter_missing_input_never_constructs_mutating_controller(
        tmp_path, monkeypatch, qualified_guest):
    import system_fixture_preparation as preparation
    lease, vm = legacy_lease(), Mock()
    lease.capture.state = {'guest': qualified_guest}
    monkeypatch.setattr(preparation, 'selection_record', lambda value, target=None: value)
    def missing(_):
        raise ValueError('registered input missing')
    monkeypatch.setattr(preparation.fixture_execution, 'verify', missing)
    factory = Mock()
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    with pytest.raises(ValueError, match='registered input missing'):
        preparation.prepare(vm, lease, tmp_path, {'frozen': 'missing'})
    factory.assert_not_called()
    assert vm.mock_calls == []


def test_system_staging_intent_is_private_exact_and_never_overwritten(tmp_path):
    import system_fixture_preparation as preparation
    from types import SimpleNamespace
    lease = SimpleNamespace(state={'run': RUN, 'domain_uuid': 'vm-uuid'})
    path = '/run/onpc-fixture-' + 'c' * 64
    identity = preparation.attempt_id(tmp_path)
    preparation.register_staging(tmp_path, lease, identity, path)
    target = tmp_path / 'fixture-staging-intent.json'
    assert json.loads(target.read_bytes()) == {'run': RUN, 'vm_uuid': 'vm-uuid',
        'attempt_id': identity, 'staging': path}
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        preparation.register_staging(tmp_path, lease, identity, path)
    assert target.read_bytes() == original
    with pytest.raises(ValueError, match='staging-path'):
        preparation.register_staging(tmp_path, lease, identity, '/run/foreign')
    assert preparation.attempt_id(tmp_path / 'same-phase') != preparation.attempt_id(
        tmp_path / 'another-history' / 'same-phase')


def test_clean_attempt_uses_actual_installed_run_and_observes_under_lease(
        tmp_path, monkeypatch, qualified_guest):
    import guest_inputs
    import vm_transport
    import system_fixture_preparation as preparation
    from contextlib import contextmanager
    selection = system.resolve_selection('package', 'test_first_install_requests_reboot',
                                         inventories=INVENTORIES)
    (tmp_path / 'input').mkdir()
    (tmp_path / 'input/package-input.json').write_text('{}')
    (tmp_path / 'input/fixtures/mechanical').mkdir(parents=True)
    (tmp_path / 'input/fixtures/mechanical/onpc-test-application').write_bytes(b'other phase only')
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None)
    lease = suite.lease
    lease.state = {'run': RUN}
    lease.capture.state = {'guest': qualified_guest}
    active = []
    @contextmanager
    def owned():
        active.append(True)
        try:
            yield lease
        finally:
            active.pop()
    lease.__enter__ = lambda _: owned_context.__enter__()
    lease.__exit__ = lambda _, *args: owned_context.__exit__(*args)
    owned_context = owned()
    bootstrap = Mock(return_value='host-key')
    monkeypatch.setattr(system, 'bootstrap', bootstrap)
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    vm = Mock()
    monkeypatch.setattr(vm_transport, 'Transport', Mock(return_value=vm))
    monkeypatch.setattr(preparation, 'selection_record', lambda value, target=None: value)
    controller = Mock()
    monkeypatch.setattr(preparation, 'prepare', lambda transport, owned_lease, path, frozen:
        {'vm': transport, 'lease': owned_lease, 'directory': path,
         'controller': controller, 'receipt': 'fresh'})
    def observer(stage, context):
        assert active == [True]
        assert context['directory'] == tmp_path / 'attempt-installed'
        inputs = context['directory'] / 'input'
        assert not (inputs / 'fixtures/mechanical/onpc-test-application').exists()
        inventory = json.loads((inputs / 'transfer-sha256.json').read_bytes())
        assert inventory == {'package-input.json': system.baseline.digest(inputs / 'package-input.json')}
        return {'attempt': context['directory'].name, 'stage': stage}
    result = snapshots.run_attempts(suite, tmp_path, selection, {}, 'selected', system.RunLedger(),
        fixture_selection={'frozen': 'caller'}, preparation_only=True, preparation_observer=observer)
    assert result == [{'attempt': 'attempt-installed', 'stage': 'ready'}]
    bootstrap.assert_called_once_with(suite.commands, lease, tmp_path / 'attempt-installed',
                                     suite.guestfs, system_product_free=True)
    lease.prepare.assert_called_once_with()
    suite.prepare_case.assert_not_called()
    assert not active
    vm.copy.assert_not_called()
    vm.call.assert_not_called()


def test_clean_installed_attempt_refuses_before_snapshot_preparation_or_boot(
        tmp_path, monkeypatch):
    import guest_inputs
    selection = system.resolve_selection('authorization', inventories=INVENTORIES)
    (tmp_path / 'input').mkdir()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None, lease=legacy_lease(state={'run': RUN}))
    lease = suite.lease
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'os_id': 'fedora', 'version': '44'}}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    bootstrap = Mock()
    monkeypatch.setattr(system, 'bootstrap', bootstrap)
    with pytest.raises(system.Error, match='system-installed-target-not-qualified'):
        snapshots.run_attempts(suite, tmp_path, selection, {}, 'selected', system.RunLedger(),
                               fixture_selection={'frozen': 'caller'})
    suite.prepare_case.assert_not_called()
    lease.prepare.assert_not_called()
    bootstrap.assert_not_called()
    lease.start.assert_not_called()
    lease.__exit__.assert_called_once()


@pytest.mark.parametrize('area', ['authorization', 'enforcement', 'session'])
def test_clean_installed_attempt_uses_offline_restore_and_shared_hard_preparation(
        tmp_path, monkeypatch, area):
    import guest_inputs
    import vm_transport
    import system_fixture_preparation as preparation
    selection = system.resolve_selection(area, inventories=INVENTORIES)
    (tmp_path / 'input').mkdir()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None, snapshot_mode='online')
    suite.prepared = True
    lease = suite.lease
    lease.state = {'run': RUN}
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'ubuntu_version': '26.04'}}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    lease._restored_name = 'onpc-baseline'
    lease.installed_name = 'onpc-v1.4'
    active = []
    record = {'target': 'ubuntu', 'frozen': 'same-caller-input'}
    monkeypatch.setattr(preparation, 'validate_input', lambda value, target=None: value)
    monkeypatch.setattr(preparation, 'selection_record', lambda value, target=None: value)

    def restore(case, *args, **kwargs):
        assert case == snapshots.installed_case(True)
        assert suite.snapshot_mode == 'offline'
        assert suite.prepared is False
        lease.installed_online = lease.online_pending = False
        lease.installed_name = lease._restored_name = 'onpc-v1.4'
        active.append('offline-restore')
    suite.prepare_case.side_effect = restore
    bootstrap = Mock(side_effect=lambda *args, **kwargs: active.append('bootstrap') or 'key')
    monkeypatch.setattr(system, 'bootstrap', bootstrap)
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    vm = Mock()
    vm.probe_ready.side_effect = lambda: active.append('ssh-ready')
    vm.wait_boot_complete.side_effect = lambda: active.append('boot-complete')
    monkeypatch.setattr(vm_transport, 'Transport', Mock(return_value=vm))
    controller = Mock()

    def prepare(transport, owner, directory, frozen, *, installed=False):
        assert installed and frozen is record and transport is vm and owner is lease
        preparation.require_installed_restore(lease)
        assert directory == tmp_path / ('attempt-' + area)
        active.append('provision')
        return {'vm': vm, 'lease': lease, 'directory': directory,
                'controller': controller, 'receipt': 'restored-boot'}
    monkeypatch.setattr(preparation, 'prepare', prepare)
    result = snapshots.run_attempts(suite, tmp_path, selection, {}, 'selected', system.RunLedger(),
        fixture_selection=record, preparation_only=True,
        preparation_observer=lambda stage, context: active.append(stage) or stage)
    assert result == ['ready']
    assert active == ['offline-restore', 'bootstrap', 'ssh-ready', 'boot-complete',
                      'before', 'provision', 'ready']
    bootstrap.assert_called_once_with(suite.commands, lease, tmp_path / ('attempt-' + area),
                                     suite.guestfs, system_installed=True)
    lease.prepare.assert_not_called()
    vm.copy.assert_not_called()
    vm.call.assert_not_called()
    vm.reboot.assert_not_called()
    controller.require_ready.assert_called_once_with('restored-boot')


@pytest.mark.parametrize('fault', ['online', 'pending', 'wrong-restore', 'missing-name'])
def test_clean_installed_offline_restore_guard_precedes_transport(tmp_path, fault):
    lease, vm = legacy_lease(), Mock()
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'ubuntu_version': '26.04'}}
    lease.installed_online = lease.online_pending = False
    lease.installed_name = lease._restored_name = 'onpc-v1.4'
    if fault == 'online':
        lease.installed_online = True
    elif fault == 'pending':
        lease.online_pending = True
    elif fault == 'wrong-restore':
        lease._restored_name = 'onpc-baseline'
    else:
        lease.installed_name = lease._restored_name = None
    selected = system.resolve_selection('authorization', inventories=INVENTORIES)
    with pytest.raises(ValueError, match='offline-restore-required'):
        system.installed_run(vm, lease, tmp_path, selected, already_installed=True,
                             fixture_selection={'target': 'ubuntu'})
    assert vm.mock_calls == []


@pytest.mark.parametrize('failure', ['missing-input', 'incompatible-input'])
def test_clean_installed_bad_input_refuses_before_app_preparation(tmp_path, monkeypatch, failure):
    import guest_inputs
    import system_fixture_preparation as preparation
    selected = system.resolve_selection('authorization', inventories=INVENTORIES)
    (tmp_path / 'input').mkdir()
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    suite = Mock(verified=None)
    lease = suite.lease
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'ubuntu_version': '26.04'}}
    lease.__enter__ = Mock(return_value=lease)
    lease.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(preparation, 'installed_selection', lambda value: value)
    validate = Mock(side_effect=ValueError(failure))
    monkeypatch.setattr(preparation, 'validate_input', validate)
    bootstrap = Mock()
    monkeypatch.setattr(system, 'bootstrap', bootstrap)
    with pytest.raises(ValueError, match=failure):
        snapshots.run_attempts(suite, tmp_path, selected, {}, 'selected', system.RunLedger(),
                               fixture_selection={'target': 'ubuntu'})
    validate.assert_called_once_with({'target': 'ubuntu'}, target='ubuntu')
    suite.prepare_case.assert_not_called()
    bootstrap.assert_not_called()
    lease.start.assert_not_called()


def test_repeated_clean_installed_histories_use_real_suite_offline_reuse_after_baseline_cleanup(
        tmp_path, monkeypatch):
    import guest_inputs
    import vm_transport
    import system_fixture_preparation as preparation
    from suite_lease import Suite
    selected = system.resolve_selection('authorization', inventories=INVENTORIES)
    lease = legacy_lease(state={'run': RUN})
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'ubuntu_version': '26.04'}}
    lease.installed_online = lease.online_pending = False
    lease.installed_name = None
    lease._restored_name = 'onpc-baseline'
    lease.restore_installed = False
    lease.__enter__ = Mock(return_value=lease)
    def cleanup(*args):
        lease._restored_name = 'onpc-baseline'
        return False
    lease.__exit__ = Mock(side_effect=cleanup)
    def stop():
        assert lease.restore_installed is True
        lease._restored_name = lease.installed_name
    lease.stop.side_effect = stop
    suite = Suite(Mock())
    suite.lease, suite.source, suite.guestfs = lease, Mock(), Mock()
    suite.prepare_installed = Mock(return_value=False)
    monkeypatch.setattr(guest_inputs.Bundle, 'from_staged', Mock())
    monkeypatch.setattr(system, 'package_version', lambda *args: '1.4.0')
    monkeypatch.setattr(system, 'bootstrap', Mock(return_value='key'))
    monkeypatch.setattr(system, 'address', lambda _: 'guest')
    monkeypatch.setattr(vm_transport, 'Transport', Mock())
    monkeypatch.setattr(preparation, 'validate_input', lambda value, target=None: value)
    monkeypatch.setattr(preparation, 'selection_record', lambda value, target=None: value)
    def prepare(*args, **kwargs):
        assert kwargs == {'installed': True}
        preparation.require_installed_restore(lease)
        return {'controller': Mock(), 'receipt': 'actual-restored-boot'}
    monkeypatch.setattr(preparation, 'prepare', prepare)
    for name in ('first', 'second'):
        directory = tmp_path / name
        (directory / 'input').mkdir(parents=True)
        (directory / 'input/package.deb').write_bytes(b'frozen-package')
        assert snapshots.run_attempts(suite, directory, selected, {}, 'selected', system.RunLedger(),
            fixture_selection={'target': 'ubuntu'}, preparation_only=True) == [None]
        assert lease._restored_name == 'onpc-baseline'
    assert suite.prepare_installed.call_count == 2
    for call in suite.prepare_installed.call_args_list:
        assert call.kwargs == {'root': system.ROOT, 'overwrite': False, 'mode': 'offline'}
    assert lease.stop.call_count == 2


@pytest.mark.parametrize('failure', [None, 'initial-boot', 'reboot-boot', 'renewal'])
def test_clean_installed_session_renews_same_controller_after_reboot_before_phase(
        tmp_path, monkeypatch, failure):
    import system_fixture_preparation as preparation
    selected = system.resolve_selection('session', inventories=INVENTORIES)
    lease, vm = legacy_lease(state={'run': RUN}), Mock()
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'ubuntu_version': '26.04'}}
    lease.installed_online = lease.online_pending = False
    lease.installed_name = lease._restored_name = 'onpc-v1.4'
    record = {'target': 'ubuntu'}
    monkeypatch.setattr(preparation, 'selection_record', lambda value, target=None: value)
    controller = Mock()
    events = []
    controller.require_ready.side_effect = lambda receipt: events.append(('ready', receipt))
    def renew(receipt):
        events.append(('renew', receipt))
        if failure == 'renewal':
            raise ValueError('renewal-refused')
        return 'new-boot'
    controller.renew_after_reboot.side_effect = renew
    prepare = Mock(return_value={'controller': controller, 'receipt': 'restored-boot'})
    monkeypatch.setattr(preparation, 'prepare', prepare)
    observer = Mock()
    def boot_complete():
        events.append(('boot-complete',))
        if ((failure == 'initial-boot' and vm.wait_boot_complete.call_count == 1) or
                (failure == 'reboot-boot' and vm.wait_boot_complete.call_count == 2)):
            raise system.Error('transport:boot-not-complete')
    vm.wait_boot_complete.side_effect = boot_complete
    vm.reboot.side_effect = lambda: events.append(('reboot',))
    def run_phase(*args):
        events.append(('phase',))
    monkeypatch.setattr(system, 'run_pytest', run_phase)
    monkeypatch.setattr(system, 'capture_session_screen', Mock())
    write_junit_results(tmp_path, selected)
    if failure:
        with pytest.raises((ValueError, system.Error), match=(
                'renewal-refused' if failure == 'renewal' else 'transport:boot-not-complete')):
            system.installed_run(vm, lease, tmp_path, selected, already_installed=True,
                                 fixture_selection=record, preparation_observer=observer)
        assert ('phase',) not in events
    else:
        system.installed_run(vm, lease, tmp_path, selected, already_installed=True,
                             fixture_selection=record, preparation_observer=observer)
        assert events[-6:] == [('reboot',), ('boot-complete',), ('renew', 'restored-boot'),
                              ('ready', 'new-boot'), ('ready', 'new-boot'), ('phase',)]
    if failure in ('initial-boot', 'reboot-boot'):
        controller.renew_after_reboot.assert_not_called()
    else:
        controller.renew_after_reboot.assert_called_once_with('restored-boot')
    assert vm.reboot.call_count == int(failure != 'initial-boot')
    assert vm.wait_boot_complete.call_count == (1 if failure == 'initial-boot' else 2)
    calls = [call.args[0] for call in vm.call.call_args_list]
    if failure == 'initial-boot':
        prepare.assert_not_called()
        observer.assert_not_called()
        vm.copy.assert_not_called()
        vm.call.assert_not_called()
    else:
        assert system.guest_command(RUN, 'verify-installed') in calls
    assert not any(system.guest_command(RUN, action) in calls
                   for action in ('install', 'install-previous', 'upgrade'))


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


@pytest.fixture
def pam_inventories():
    return {**RECOVERY_INVENTORIES, 'package': (*RECOVERY_INVENTORIES['package'], *(
        history.case_id for history in system.PAM_HISTORIES))}


def test_previous_policy_history_never_restores_between_old_package_and_final_reboot():
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'], system.PREVIOUS_POLICY_CASE)}
    selected = system.resolve_selection('package', system.PREVIOUS_POLICY_CASE,
                                        inventories=inventories, fresh_install=True)
    assert snapshots.attempts(selected, fresh_install=True) == [(selected, False)]
    assert selected.phases == ('previous-policy', 'installed', 'rebooted')


def test_trusted_fixture_qualification_uses_one_product_free_baseline_attempt():
    inventories = {**INVENTORIES, 'package': (*INVENTORIES['package'],
                                            system.TRUSTED_FIXTURES_CASE)}
    selected = system.resolve_selection('package', system.TRUSTED_FIXTURES_CASE,
                                        inventories=inventories, fresh_install=True)
    assert selected.phases == ('trusted-fixtures',)
    assert snapshots.attempts(selected, fresh_install=True) == [(selected, False)]
    assert snapshots.attempts(selected) == [(selected, False)]


@pytest.mark.parametrize('area', [None, 'package'])
def test_pam_broad_selection_partitions_each_variant_into_its_own_baseline_history(
        pam_inventories, area):
    selection = system.resolve_selection(area, inventories=pam_inventories)
    planned = snapshots.attempts(selection)
    executions = [item for part, _ in planned for item in part.executions]
    assert len(executions) == len(set(executions)) == len(selection.executions)
    assert set(executions) == set(selection.executions)
    for history in system.PAM_HISTORIES:
        exact = system.resolve_selection('package', history.case_id, inventories=pam_inventories)
        matches = [(part, installed) for part, installed in planned
                   if any(item.case_id == history.case_id for item in part.executions)]
        assert len(matches) == 1
        part, installed = matches[0]
        assert not installed
        assert part.phases == exact.phases == history.phases
        assert part.executions == exact.executions
        assert snapshots.attempts(exact) == [(exact, False)]


def test_pam_family_resume_replays_whole_unfinished_histories(pam_inventories):
    selection = system.resolve_selection('package', system.PAM_CASE, inventories=pam_inventories)
    exact = [system.resolve_selection('package', history.case_id, inventories=pam_inventories)
             for history in system.PAM_HISTORIES]
    planned = snapshots.attempts(selection)
    assert len(planned) == len(exact)
    for (part, installed), focused in zip(planned, exact):
        assert not installed
        assert part.phases == focused.phases
        assert part.executions == focused.executions
    for count in range(len(selection.executions) + 1):
        completed = {item.phase + '::' + item.case_id for item in selection.executions[:count]}
        resumed = system.resume_selection(selection, completed)
        remaining = exact[min(count // 4, len(exact) - 1):]
        assert resumed.executions == tuple(item for part in remaining for item in part.executions)
        assert len(snapshots.attempts(resumed)) == len(remaining)
    broad = system.resolve_selection(inventories=pam_inventories)
    for focused in exact:
        for phase in focused.phases:
            completed = {item.phase + '::' + item.case_id for item in broad.executions
                         if item.phase != phase}
            resumed = system.resume_selection(broad, completed)
            assert resumed.phases == focused.phases
            assert resumed.executions == focused.executions
            assert snapshots.attempts(resumed) == [(resumed, False)]
        with pytest.raises(system.Error, match='selection:resume-inventory-changed'):
            system.resume_selection(focused, {'foreign::' + focused.test})


@pytest.mark.parametrize('variant', ['plain', 'distro-profile', 'administrator-override', 'pending-vendor'])
@pytest.mark.parametrize('failure', [None, 'initial', 'first-archive', 'first-reboot', 'configured',
                                   'second-reboot', 'removal', 'third-reboot', 'removed'])
def test_pam_controller_never_preinstalls_and_retains_results_before_each_reboot(
        tmp_path, monkeypatch, pam_inventories, variant, failure):
    selection = system.resolve_selection('package', f'{system.PAM_CASE}[{variant}]',
                                         inventories=pam_inventories)
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
    events = []
    phases = selection.phases
    phase_labels = dict(zip(phases, ('initial', 'configured', 'removal', 'removed')))
    reboots = iter(('first-reboot', 'second-reboot', 'third-reboot'))
    archives = []

    def reboot():
        label = next(reboots)
        # A complete result transfer from the preceding phase must finish
        # before a reboot can make its guest artifacts unavailable.
        assert events[-3:] == ['collect', 'copy-results', 'archive-results']
        assert archives[-1] == phases[('first-reboot', 'second-reboot', 'third-reboot').index(label)]
        events.append(label)
        if failure == label:
            raise system.CommandError('pam-reboot-failed')

    def execute(owned_vm, token, phase, selected):
        assert owned_vm is vm and token == RUN and selected == selection
        label = phase_labels[phase]
        events.append(label)
        if failure == label:
            vm.commands.last_returncode = 1
            raise system.CommandError('pam-phase-failed')

    def call(command, *, timeout):
        # The phase owns install/configure/removal; the controller may only
        # collect its evidence, never invoke an installer or activation probe.
        assert command[:len(system.guest_command(RUN, 'collect'))] == system.guest_command(RUN, 'collect')
        assert timeout == 180
        events.append('collect')

    def copy(download, source, destination):
        if download:
            assert source == system.PAYLOAD + '/results/'
            if destination == str(tmp_path / 'guest-results') + '/':
                events.append('copy-results')
            else:
                prior = phases[len(archives)]
                retained = tmp_path / 'phase-results' / prior
                assert destination == str(retained) + '/'
                assert retained.is_dir()
                assert events[-2:] == ['collect', 'copy-results']
                archives.append(prior)
                events.append('archive-results')
                if failure == 'first-archive':
                    raise system.CommandError('pam-archive-failed')

    vm.reboot.side_effect = reboot
    vm.call.side_effect = call
    vm.copy.side_effect = copy
    monkeypatch.setattr(system, 'run_pytest', execute)
    activation = Mock()
    monkeypatch.setattr(system, 'run_kiosk_activation', activation)
    write_junit_results(tmp_path, selection)
    ledger = system.RunLedger()
    if failure:
        with pytest.raises(system.CommandError):
            system.installed_run(vm, lease, tmp_path, selection, ledger)
        if failure in phase_labels.values():
            failed_phase = next(phase for phase, label in phase_labels.items() if label == failure)
            assert ledger.outcomes['product']['category'] == 'pytest:failed:' + failed_phase
    else:
        assert tuple(system.installed_run(vm, lease, tmp_path, selection, ledger)) == phases
    lifecycle = ['initial', 'first-reboot', 'configured', 'second-reboot',
                 'removal', 'third-reboot', 'removed']
    expected = (['initial'] if failure == 'first-archive' else
                lifecycle[:lifecycle.index(failure) + 1] if failure else lifecycle)
    assert [event for event in events
            if event not in ('collect', 'copy-results', 'archive-results')] == expected
    assert archives == list(phases[:len(archives)])
    assert all((tmp_path / 'phase-results' / phase).is_dir() for phase in archives)
    if failure == 'first-archive':
        vm.reboot.assert_not_called()
    assert events[-2:] == ['collect', 'copy-results']
    activation.assert_not_called()
    lease.prepare.assert_not_called()
    lease.restore.assert_not_called()


def test_pam_controller_refuses_installed_snapshot_before_any_phase(
        tmp_path, monkeypatch, pam_inventories):
    selection = system.resolve_selection('package', system.PAM_HISTORIES[0].case_id,
                                         inventories=pam_inventories)
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
    execute = Mock()
    monkeypatch.setattr(system, 'run_pytest', execute)
    with pytest.raises(system.Error, match='installation-requires-baseline'):
        system.installed_run(vm, lease, tmp_path, selection, already_installed=True)
    execute.assert_not_called()
    vm.reboot.assert_not_called()
    assert [call.args[0] for call in vm.call.call_args_list] == [
        system.guest_command(RUN, 'collect', 'failed')]


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
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
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
    suite = Mock(verified=None, lease=legacy_lease())
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
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
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
    vm, lease = Mock(), legacy_lease()
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
    vm, lease = Mock(), legacy_lease()
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
    vm, lease = Mock(), legacy_lease()
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
    vm, lease = Mock(), legacy_lease(state={'run': RUN})
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
    vm, lease = Mock(), legacy_lease()
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
