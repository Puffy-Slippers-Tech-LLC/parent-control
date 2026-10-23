"""Private files and synchronous preparation/lease doubles; no live resources."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import e2e_fixture_preparation as preparation
import fixture_e2e_qualification as qualification
from tools import fixture_execution


@pytest.fixture(params=['ubuntu', 'fedora'])
def selection(request):
    target = request.param
    return fixture_execution.Selection(target, 'a' * 64,
        '/tmp/onpc-native-runtime-' + target + '-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64)


def lease_for(target, mode='online'):
    # Ordinary smoke Lease has no installed_online property. The shared owner
    # records actual snapshot XML; SuiteLease's convenience property is optional.
    guest = {'fixture_boundary': 'clean'}
    guest.update({'ubuntu_version': '26.04'} if target == 'ubuntu' else
                 {'os_id': 'fedora', 'version': '44'})
    return SimpleNamespace(capture=SimpleNamespace(state={'guest': guest}),
        installed_name='onpc-private', _restored_name='onpc-private',
        online_pending=False, online_bootstrap=None,
        installed_xml='<domainsnapshot><memory snapshot="' +
                      ('internal' if mode == 'online' else 'no') + '"/></domainsnapshot>')


def test_transfer_target_and_missing_input_refuse_without_guest_mutation(monkeypatch, selection):
    import smoke_fixture_preparation as transfer
    verify = Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    with pytest.raises(ValueError, match='execution-selection-required'):
        transfer.validate_input(None)
    other = 'fedora' if selection.target == 'ubuntu' else 'ubuntu'
    with pytest.raises(ValueError, match='transfer-target-not-qualified'):
        transfer.validate_input(selection.record(), target=other)
    verify.assert_not_called()
    assert transfer.validate_input(selection.record(), target=selection.target) == selection.record()
    verify.assert_called_once_with(selection.record())


def test_transfer_qualification_refuses_cross_target_before_guest_mutation(
        monkeypatch, tmp_path, selection):
    import fixture_transfer_qualification as transfer
    verify, factory, vm = Mock(), Mock(), Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    lease = lease_for(selection.target)
    assert transfer.refused_inputs({'vm': vm, 'lease': lease, 'directory': tmp_path},
        selection) == {'missing': 'fixtures:execution-selection-required',
                      'incompatible': 'fixtures:transfer-target-not-qualified'}
    verify.assert_not_called()
    factory.assert_not_called()
    assert not list(tmp_path.iterdir()) and not vm.mock_calls


@pytest.mark.parametrize('serial,install', [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize('supplied', [False, True])
def test_standalone_clean_input_and_serial_gates_precede_prepare(
        monkeypatch, tmp_path, selection, serial, install, supplied):
    import check_graphical_smoke as smoke
    monkeypatch.setattr(preparation.fixture_execution, 'verify', Mock())
    lease = lease_for(selection.target)
    lease.prepare = Mock()
    result = {'steps': []}
    controller = smoke.Qualification(tmp_path, Mock(), smoke.runner.RunLedger(), Mock(), result,
        'host', assets=tmp_path, serial=serial, install=install,
        credentials=Mock() if serial else None)
    controller.checkpoint = Mock()
    controller.fixture_selection = selection.record() if supplied else None
    if supplied:
        # The qualified branch reaches the real preparation boundary.
        lease.prepare.side_effect = RuntimeError('preparation-boundary')
        code = 'preparation-boundary'
    else:
        code = 'execution-selection-required'
    with pytest.raises((ValueError, RuntimeError, smoke.EvidenceError), match=code):
        controller.execute(lease, Mock())
    assert lease.prepare.call_count == int(code == 'preparation-boundary')


@pytest.mark.parametrize('assets,refusal', [(False, False), (True, False), (True, True)])
def test_serial_preboot_guards_and_deferred_assets_precede_ready_boundary(
        monkeypatch, tmp_path, selection, assets, refusal):
    import check_graphical_smoke as smoke
    monkeypatch.setattr(preparation.fixture_execution, 'verify', Mock())
    events = []
    lease = lease_for(selection.target)
    lease.prepare = lambda: events.append('restore')
    lease.guard = lambda **_: None
    lease.save = lambda _: None
    credentials = Mock()
    credentials.provision.side_effect = lambda *_: events.append('credentials') or {}
    monkeypatch.setattr(smoke.runner, 'bootstrap',
        lambda *_, **kwargs: events.append(('bootstrap', kwargs)) or 'key')
    verified = Mock(inputs={}, source_files={})
    monkeypatch.setattr(smoke, 'VerifiedInputs', Mock(return_value=verified))
    monkeypatch.setattr(smoke, 'provision_getty', lambda *_: events.append('getty'))
    transfer = Mock()
    transfer.provision.side_effect = lambda *_, **kwargs: events.append(('defer', kwargs)) or {}
    monkeypatch.setattr(smoke, 'AssetTransfer', Mock(return_value=transfer))
    boundary = Mock()
    monkeypatch.setattr(smoke, 'InstallationBoundary', boundary)
    def backend(*_, **options):
        assert options['serial'] and options['credentials'] is credentials
        assert options['fixture_selection'] == record
        assert options['transfer'] is (transfer if assets else None)
        events.append('ready-boundary')
        return {}
    monkeypatch.setattr(smoke, 'run_backend', backend)
    controller = smoke.Qualification(tmp_path, Mock(), smoke.runner.RunLedger(), Mock(), {},
        'host', assets=tmp_path if assets else None, credentials=credentials,
        serial=True, install=assets and not refusal, install_refusal=refusal)
    controller.checkpoint = Mock()
    record = selection.record()
    controller.fixture_selection = record
    controller.execute(lease, Mock())
    assert events == ['restore', ('bootstrap', {'observation_only': True,
        'environment_only': False, 'e2e_product_free': True}), 'credentials', 'getty',
        *([('defer', {'fixture_selection': record})] if assets else []), 'ready-boundary']
    smoke.VerifiedInputs.assert_called_once_with(lease=lease, assets=tmp_path if assets else None,
        **({'package_only': True} if assets else {}))
    if assets:
        boundary.assert_called_once_with(None, verified, transfer, refusal=refusal)
    else:
        boundary.assert_not_called()


@pytest.mark.parametrize('mode', ['transfer', 'serial', 'install', 'refusal'])
@pytest.mark.parametrize('stale', [False, True])
def test_smoke_transfer_provisions_after_ssh_and_checks_before_first_reply(
        monkeypatch, tmp_path, selection, stale, mode):
    import json
    import check_graphical_smoke as smoke
    import smoke_fixture_preparation as transfer_preparation
    events = []
    (tmp_path / 'ready.request.json').write_text(json.dumps({'stage': 'ready', 'screenshot': None}))
    lease, transport, observations = Mock(), Mock(), Mock()
    lease.state = {'run': 'a' * 32}
    lease.guard.side_effect = lambda: events.append('guard')
    transport.probe_ready.side_effect = lambda **_: events.append('ssh-ready')
    native = Mock()
    def ready(_):
        events.append('native-ready')
        if stale and native.require_ready.call_count == 2:
            raise ValueError('fixtures:stale-readiness')
    native.require_ready.side_effect = ready
    prepared = {'controller': native, 'receipt': 'native', 'lease': lease}
    prepare = Mock(side_effect=lambda *args: events.append('native') or prepared)
    monkeypatch.setattr(transfer_preparation, 'prepare', prepare)
    monkeypatch.setattr(smoke.runner, 'address', lambda *_args, **_kwargs: '192.0.2.1')
    monkeypatch.setattr(smoke, 'Transport', Mock(return_value=transport))
    monkeypatch.setattr(smoke, 'ReadOnlyObservations', Mock(return_value=observations))
    monkeypatch.setattr(smoke, 'harness_observation', lambda *_: events.append('greeter'))
    assets = Mock()
    assets.provision_product_free.side_effect = lambda *_: events.append('assets')
    assets.observe.side_effect = lambda _: events.append('inventory') or {'verified': True}
    def observed(stage, _):
        assert not (tmp_path / 'ready.reply.json').exists()
        events.append('observe-' + stage)
    installation = Mock(refusal=mode == 'refusal') if mode in ('install', 'refusal') else None
    if installation is not None:
        installation.transfer = assets
    control = smoke.Smoke(tmp_path, lease, Mock(), 'key',
        progress=lambda stage, data: events.append('progress-' + ('start' if data is None else 'done')),
        transfer=assets, fixture_selection=selection.record(), fixture_observer=observed,
        serial=mode != 'transfer', authenticate=mode != 'transfer', installation=installation)
    if mode == 'install':
        assert 'reboot-requested' in control.stages and 'reboot-observed' in control.stages
        assert 'serial-logout' not in control.stages
    elif mode == 'refusal':
        assert 'install-refused' in control.stages and 'serial-logout' in control.stages
        assert not any(stage.startswith('reboot-') for stage in control.stages)
    if stale:
        with pytest.raises(ValueError, match='stale-readiness'):
            control.step()
        assert not (tmp_path / 'ready.reply.json').exists()
        with pytest.raises(RuntimeError, match='previous-failure'):
            control.step()
    else:
        control.step()
        assert (tmp_path / 'ready.reply.json').is_file()
    assert events == ['progress-start', 'guard', 'ssh-ready', 'observe-before', 'native',
                      'assets', 'native-ready', 'observe-ready', 'inventory', 'greeter',
                      'progress-done', 'guard', 'native-ready']
    assert assets.verified.fixture_prepared is prepared
    prepare.assert_called_once_with(transport, lease, tmp_path, selection.record())


def test_missing_incompatible_refuse_before_staging_and_guest_calls(monkeypatch, tmp_path, selection):
    verify, factory, vm = Mock(), Mock(), Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    lease = lease_for(selection.target)
    assert qualification.refused_inputs({'vm': vm, 'lease': lease, 'directory': tmp_path},
        selection) == {'missing': 'fixtures:execution-selection-required',
                      'incompatible': 'fixtures:e2e-installed-target-not-qualified'}
    verify.assert_not_called()
    factory.assert_not_called()
    assert not list(tmp_path.iterdir()) and not vm.mock_calls
    assert not hasattr(lease, '_fixture_provision_state')


@pytest.mark.parametrize('mode', ['online', 'offline'])
@pytest.mark.parametrize('failure', [None, 'pending', 'rebind', 'restore'])
def test_actual_restore_and_rebind_gate_precedes_provision(
        monkeypatch, tmp_path, selection, mode, failure):
    lease = lease_for(selection.target, mode)
    if failure == 'pending':
        lease.online_pending = True
    if failure == 'rebind':
        lease.online_bootstrap = ('private', {})
    if failure == 'restore':
        lease._restored_name = 'baseline'
    monkeypatch.setattr(preparation.fixture_execution, 'verify', Mock(return_value={}))
    controller = Mock()
    controller.provision.return_value = 'receipt'
    factory = Mock(return_value=controller)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    refused = failure == 'pending' or mode == 'online' and failure == 'rebind' or (
        mode == 'offline' and failure == 'restore')
    if refused:
        with pytest.raises(ValueError, match='restored-rebound-required'):
            preparation.prepare(Mock(), lease, tmp_path, selection.record())
        factory.assert_not_called()
    else:
        result = preparation.prepare(Mock(), lease, tmp_path, selection.record())
        controller.provision.assert_called_once_with(selection.record(), ('native',),
            attempt_id=preparation.attempt_id(tmp_path))
        controller.require_ready.assert_called_once_with('receipt')
        assert result['lease'] is lease


@pytest.mark.parametrize('guest', [
    {'fixture_boundary': 'clean', 'os_id': 'fedora', 'version': '43'},
    {'ubuntu_version': '26.04'}, {'fixture_boundary': 'clean', 'ubuntu_version': '24.04'}])
def test_unqualified_guest_refuses_before_input_and_transport(monkeypatch, tmp_path, selection, guest):
    lease = lease_for(selection.target)
    lease.capture.state['guest'] = guest
    verify, factory, vm = Mock(), Mock(), Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    with pytest.raises(ValueError, match='target-not-qualified'):
        preparation.prepare(vm, lease, tmp_path, selection.record())
    verify.assert_not_called()
    factory.assert_not_called()
    assert not vm.mock_calls and not list(tmp_path.iterdir())


def test_native_observation_hashes_come_from_selected_manifest(monkeypatch, selection):
    declarations = preparation.fixture_manifest.declarations()
    manifest = {'members': {key: {'sha256': key} for key in declarations}}
    verify = Mock(return_value=manifest)
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    hashes = preparation.asset_hashes(selection.record())
    from tests.fixtures import native_assets
    assert set(hashes) == set(native_assets.sources())
    for source, (destination, _mode) in native_assets.source_destinations('@other@').items():
        key = next(key for key, value in declarations.items() if value['destination'] == destination)
        assert hashes[source] == key
    verify.assert_called_once_with(selection.record())


def test_shared_journey_setup_checks_readiness_after_asset_transfer(monkeypatch, tmp_path, selection):
    import installed_journey
    import installed_setup
    events = []
    lease = lease_for(selection.target)
    verified = SimpleNamespace()
    controller = Mock()
    controller.require_ready.side_effect = lambda _: events.append('ready')
    prepared = {'controller': controller, 'receipt': 'receipt'}
    setup = Mock()
    setup.provision.side_effect = lambda *args, **kwargs: events.append('provision') or prepared
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock(return_value=setup))
    monkeypatch.setattr(preparation, 'validate_input', lambda value: value)
    transfer = Mock()
    transfer.provision_installed.side_effect = lambda *_: events.append('assets')
    context = SimpleNamespace(directory=tmp_path, lease=lease, verified=verified,
        fixture_selection=selection.record(), asset_transfer=transfer)
    assert installed_journey.prepare_installed_setup(context, Mock(), Mock()) == prepared
    assert events == ['provision', 'assets', 'ready']
    assert setup.provision.call_args.kwargs == {'fixture_selection': selection.record()}


def test_product_free_missing_or_incompatible_input_refuses_before_mutation(
        monkeypatch, tmp_path, selection):
    import fixture_e2e_product_free_qualification as product_free
    verify, factory, vm = Mock(), Mock(), Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    lease = lease_for(selection.target)
    lease.installed_name = None
    assert product_free.refused_inputs({'vm': vm, 'lease': lease, 'directory': tmp_path},
        selection) == {'missing': 'fixtures:execution-selection-required',
                      'incompatible': 'fixtures:e2e-product-free-target-not-qualified'}
    verify.assert_not_called()
    factory.assert_not_called()
    assert not vm.mock_calls and not list(tmp_path.iterdir())


@pytest.mark.parametrize('invalid', ['target', 'installed', 'pending', 'observation', 'mixed'])
def test_product_free_bootstrap_refuses_incompatible_envelopes_before_mutation(tmp_path, invalid):
    import system_runner
    lease = lease_for('fedora' if invalid == 'target' else 'ubuntu')
    if invalid == 'target':
        lease.capture.state['guest']['version'] = '43'
    lease.capture.state['proof'] = {'name': 'baseline'}
    lease.installed_name = 'installed' if invalid == 'installed' else None
    lease.online_pending = invalid == 'pending'
    commands, guestfs = Mock(), Mock()
    with pytest.raises(system_runner.Error, match='e2e-product-free-target-not-qualified'):
        system_runner.bootstrap(commands, lease, tmp_path, guestfs,
            e2e_product_free=True, observation_only=invalid != 'observation',
            e2e_installed=invalid == 'mixed')
    assert not commands.mock_calls and not guestfs.mock_calls
    assert not list(tmp_path.iterdir())


def test_empty_product_free_setup_has_no_native_input_or_asset_dependency(monkeypatch, tmp_path, selection):
    import installed_journey
    import installed_setup
    lease = lease_for(selection.target)
    lease.installed_name = None
    context = SimpleNamespace(directory=tmp_path, lease=lease)
    prepare, verify, setup = Mock(), Mock(), Mock()
    monkeypatch.setattr(preparation, 'prepare', prepare)
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    observer = Mock()
    assert installed_journey.prepare_product_free_setup(context, Mock(), Mock(),
                                                        observer=observer) is None
    assert [call.args[0] for call in observer.call_args_list] == ['before', 'empty']
    prepare.assert_not_called()
    verify.assert_not_called()
    setup.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_empty_entry_audits_all_declarations_without_native_input(monkeypatch, tmp_path):
    import json
    import fixture_e2e_product_free_qualification as product_free
    audit = dict(installed=False, files={}, unselected_present=[], staging=[],
                 trust_entries={}, admissions={}, preserved={})
    requests = []

    def call(argv, **kwargs):
        if argv[0] == '/usr/bin/test':
            return b''
        requests.append(json.loads(kwargs['input']))
        return json.dumps(audit).encode()

    verify = Mock(side_effect=AssertionError('empty entry must not read native input'))
    monkeypatch.setattr(product_free.fixture_execution, 'verify', verify)
    result = {}
    observe = product_free.empty_observer(result, {})
    context = {'vm': SimpleNamespace(call=call), 'directory': tmp_path}
    observe('before', context)
    observe('empty', context)
    assert len(requests) == 2 and requests[0] == requests[1]
    assert requests[0]['selected'] == []
    assert set(requests[0]['members']) == set(preparation.fixture_manifest.declarations())
    assert result['native_input_required'] is False and result['product_absent'] is True
    assert result['empty_without_writes'] is True
    verify.assert_not_called()


@pytest.mark.parametrize('stale', [False, True])
def test_product_free_setup_requires_readiness_after_transfer_and_final_guard(
        monkeypatch, tmp_path, stale, selection):
    import installed_journey
    import installed_setup
    events = []
    lease = lease_for(selection.target)
    lease.installed_name = None
    selection = {'selected': 'private'}
    monkeypatch.setattr(preparation, 'validate_input',
        lambda value, **_: events.append('verify') or value)
    controller = Mock()
    def ready(_):
        events.append('ready')
        if stale and controller.require_ready.call_count == 2:
            raise ValueError('fixtures:stale-readiness')
    controller.require_ready.side_effect = ready
    prepared = {'controller': controller, 'receipt': 'receipt'}
    prepare = Mock(side_effect=lambda *_, **__: events.append('prepare') or prepared)
    monkeypatch.setattr(preparation, 'prepare', prepare)
    setup = Mock()
    setup.provision.side_effect = lambda *_: events.append('setup')
    monkeypatch.setattr(installed_setup, 'InstalledSetup', Mock(return_value=setup))
    transfer = Mock()
    transfer.provision_product_free.side_effect = lambda *_: events.append('assets')
    context = SimpleNamespace(directory=tmp_path, lease=lease, verified=SimpleNamespace(),
        fixture_selection=selection, asset_transfer=transfer)
    guard = lambda: events.append('guard')
    observer = lambda stage, _: events.append('observe-' + stage)
    if stale:
        with pytest.raises(ValueError, match='stale-readiness'):
            installed_journey.prepare_product_free_setup(context, Mock(), guard, observer=observer)
    else:
        assert installed_journey.prepare_product_free_setup(
            context, Mock(), guard, observer=observer) is prepared
    assert events == ['verify', 'guard', 'observe-before', 'prepare', 'setup', 'assets',
                      'ready', 'observe-ready', 'guard', 'ready']
    assert prepare.call_args.kwargs == {'product_free': True}
    assert context.verified.fixture_selection is selection
    assert context.verified.fixture_prepared is prepared
    setup.run.assert_not_called()


def test_dormant_current_install_on_clean_baseline_refuses_before_connection(monkeypatch, tmp_path):
    import installed_journey
    from private_artifacts import EvidenceError
    address, transport = Mock(), Mock()
    monkeypatch.setattr(installed_journey.system, 'address', address)
    monkeypatch.setattr(installed_journey, 'Transport', transport)
    context = SimpleNamespace(directory=tmp_path, lease=lease_for('ubuntu'),
                              install_current_package=True)
    plan = installed_journey.JourneyPlan(prefix='dormant-install', worker_mode='native',
                                        screen_tags={}, phases={})
    journey = installed_journey.InstalledJourney(context, Mock(), plan)
    journey.steps = [{'stage': 'ready'}]
    request = tmp_path / 'setup-detached.request.json'
    request.write_text('{"stage": "setup-detached", "screenshot": null}')
    with pytest.raises(EvidenceError, match='fixtures:e2e-install-current-not-qualified'):
        journey._step(Mock())
    address.assert_not_called()
    transport.assert_not_called()
    assert not (tmp_path / 'setup-detached.reply.json').exists()
    assert list(tmp_path.iterdir()) == [request]


@pytest.mark.parametrize('installed,fast,next_installed', [
    (False, False, True), (True, True, True),
    (True, True, False), (True, True, None)])
def test_product_free_suite_boundary_restores_baseline_then_selects_existing_next_snapshot(
        monkeypatch, installed, fast, next_installed):
    import ast
    from pathlib import Path
    import execution
    from suite_lease import needs_installed
    from tools import fixture_provision

    tree = ast.parse((Path(execution.__file__)).read_text())
    branches = [node.orelse for node in ast.walk(tree) if isinstance(node, ast.If)
        and any(isinstance(child, ast.If) and isinstance(child.test, ast.Name)
                and child.test.id == 'product_free_consumer' for child in node.orelse)]
    assert len(branches) == 1
    program = compile(ast.Module(body=branches[0], type_ignores=[]), execution.__file__, 'exec')
    events = []
    lease = SimpleNamespace(_fast=fast, installed_name='installed' if installed else None,
                            restore_installed=True, _fixture_provision_state=object())
    monkeypatch.setattr(fixture_provision, 'reset_after_restore',
                        lambda value: events.append(('reset', value is lease)))
    lease.stop = lambda: events.append(('stop', lease.restore_installed))
    lease.prepare = lambda: events.append(('prepare',))
    next_case = (None if next_installed is None else {'preconditions': [
        'installed-digest-verified-product' if next_installed
        else 'declared-package-lifecycle-fixture']})
    suite = SimpleNamespace(next_case=next_case, prepare_case=Mock())
    exec(program, {'lease': lease, 'suite': suite, 'product_free_consumer': True,
                   'needs_installed': needs_installed})
    assert events == [('reset', True), *([('stop', False)] if fast else []), ('prepare',)]
    assert lease.restore_installed is (installed and next_installed is True)
    suite.prepare_case.assert_not_called()


@pytest.mark.parametrize('mode', ['target', 'missing', 'gdm-input', 'gdm-empty'])
def test_smoke_product_free_input_guards_precede_storage_and_credentials(monkeypatch, mode):
    import ast
    from pathlib import Path
    import check_graphical_smoke as smoke
    import vm_config
    from owned_commands import CommandError

    tree = ast.parse(Path(smoke.__file__).read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    guards = [(index, node) for index, node in enumerate(main.body)
        if isinstance(node, ast.If) and ast.unparse(node.test) in (
            'product_free_entry or gdm_product_free', 'product_free_entry', 'gdm_product_free')]
    assert len(guards) == 3
    credential_index = next(index for index, node in enumerate(main.body)
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id == 'credentials' for target in node.targets))
    storage_index = next(index for index, node in enumerate(main.body)
        if isinstance(node, ast.With) and any(isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Name)
            and item.context_expr.func.id == 'storage_session' for item in node.items))
    assert max(index for index, _ in guards) < credential_index < storage_index
    program = compile(ast.Module(body=[node for _, node in guards], type_ignores=[]),
                      smoke.__file__, 'exec')
    monkeypatch.setattr(vm_config, 'selected', lambda: SimpleNamespace(
        name='unqualified-target' if mode == 'target' else 'onpc-Fedora44'))
    verify = Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    scope = dict(vars(smoke), product_free_entry=not mode.startswith('gdm'),
                 gdm_product_free=mode.startswith('gdm'),
                 fixture_selection={} if mode == 'gdm-input' else None)
    if mode == 'missing':
        with pytest.raises(ValueError, match='^fixtures:execution-selection-required$'):
            exec(program, scope)
    elif mode == 'gdm-empty':
        exec(program, scope)
    else:
        code = ('target-not-qualified' if mode == 'target' else 'empty-selection')
        with pytest.raises(CommandError, match='^fixtures:e2e-product-free-' + code + '$'):
            exec(program, scope)
    verify.assert_not_called()


@pytest.mark.parametrize('profile', ['activity', 'riley-grid'])
@pytest.mark.parametrize('product_free', [False, True])
def test_unqualified_native_closures_refuse_before_worker(
        monkeypatch, tmp_path, selection, profile, product_free):
    from installed_journey import InstalledJourney, JourneyPlan
    from native_fixtures import fixture_actions
    from private_artifacts import EvidenceError
    plan = JourneyPlan(prefix='native-scope', worker_mode='native',
        screen_tags={'fixture': 'ui:desktop'}, phases={}, stage_actions={'fixture': 'native-verify'})
    context = SimpleNamespace(directory=tmp_path, fixture_selection=selection.record(),
                              product_free=product_free)
    with pytest.raises(EvidenceError, match='profile-not-qualified'):
        InstalledJourney(context, Mock(), plan,
            actions=fixture_actions(profile=profile, include_refusal=False))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('product_free', [False, True])
def test_authenticated_selections_outlive_every_history_and_cleanup(monkeypatch, tmp_path, selection, product_free):
    if product_free:
        import fixture_e2e_product_free_qualification as subject
    else:
        subject = qualification
    events = []
    @contextmanager
    def pin(record):
        events.append('pin-runtime' if record == selection.record() else 'pin-source')
        yield 11
        events.append('unpin-runtime' if record == selection.record() else 'unpin-source')
    target_name = {'ubuntu': 'onpc-Ubuntu26.04', 'fedora': 'onpc-Fedora44'}[selection.target]
    monkeypatch.setattr(subject, 'selected_target', lambda: target_name)
    def validate(value, **options):
        assert options == {'target': selection.target, **({'product_free': True} if product_free else {})}
        return value
    monkeypatch.setattr(preparation, 'validate_input', validate)
    monkeypatch.setattr(subject.fixture_execution, 'validate_source_selection', lambda *_: {})
    monkeypatch.setattr(subject, 'authenticated_input', pin)
    monkeypatch.setattr(subject.fixture_execution, 'verify', lambda _: {})
    monkeypatch.setattr(subject.fixture_provision, 'authenticated_bundle', Mock())
    monkeypatch.setattr(subject.shared, 'source_edit_proof', Mock())
    def run(*_):
        assert events == ['pin-runtime', 'pin-source']
        events.append('histories-and-cleanup')
        return {'passed': True}
    monkeypatch.setattr(subject, 'qualify_pinned', run)
    assert subject.qualify(tmp_path, tmp_path / 'assets', selection.record(), {}) == {'passed': True}
    assert events == ['pin-runtime', 'pin-source', 'histories-and-cleanup',
                      'unpin-source', 'unpin-runtime']


def test_every_wrapper_final_ordered_class_matches_installed_aliases(monkeypatch, selection):
    """Evaluate actual wrapper loops and the complete real final dispatch block."""
    import ast
    import inspect
    from pathlib import Path
    import runpy
    import sys
    import check_graphical_smoke as smoke
    import fixture_transfer_qualification as transfer
    import test_commands
    import vm_config
    import parent_setup_qualification as parent
    from parent_setup_qualification import KioskEntryQualification
    from owned_commands import CommandError
    from tools import test_storage

    root = Path(smoke.ROOT)
    tree = ast.parse((root / 'tests/integration/check_graphical_smoke.py').read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    serial_guards = [node for node in main.body if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Name) and node.test.id == 'serial']
    assert len(serial_guards) == 1
    serial_guard = compile(ast.Module(body=serial_guards, type_ignores=[]), str(root), 'exec')
    target_name = {'ubuntu': 'onpc-Ubuntu26.04', 'fedora': 'onpc-Fedora44'}[selection.target]
    monkeypatch.setattr(vm_config, 'selected', lambda: SimpleNamespace(name=target_name))
    monkeypatch.setattr(transfer.proof.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name=target_name))
    monkeypatch.setattr(preparation.fixture_execution, 'verify', Mock())
    assert transfer.selected_target(serial=True) == target_name
    blocks = []
    selection_guards = []
    for node in ast.walk(main):
        body = getattr(node, 'body', None)
        if not isinstance(body, list):
            continue
        starts = [index for index, statement in enumerate(body)
            if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == 'qualification_class' for target in statement.targets)]
        if starts:
            start = starts[0]
            if isinstance(body[start].value, ast.Name) and body[start].value.id == 'Qualification':
                stop = next(index for index in range(start + 1, len(body))
                    if isinstance(body[index], ast.Assign) and any(isinstance(target, ast.Name)
                        and target.id == 'qualification' for target in body[index].targets))
                blocks.append(body[start:stop])
                selection_guards.append(body[stop + 1])
    assert len(blocks) == 1
    program = compile(ast.Module(body=blocks[0], type_ignores=[]), str(root), 'exec')
    selection_guard = compile(ast.Module(body=selection_guards, type_ignores=[]), str(root), 'exec')
    signature = inspect.signature(smoke.main)
    calls = []
    monkeypatch.setattr(smoke, 'main', lambda **kwargs: calls.append(kwargs) or 0)
    monkeypatch.setattr(test_storage, 'named_input', lambda **_: Path('/private/declared-input'))
    monkeypatch.setattr(sys, 'exit', lambda *_: None)
    monkeypatch.setattr(sys, 'argv', ['qualification-composition'])
    product_free_classes = {
        'check_e2e_gdm_product_free': parent.GdmProductFreeQualification,
        'check_e2e_product_free_entry': parent.ProductFreeEntryQualification,
        'check_e2e_upgrade_assets': parent.UpgradeAssetsQualification,
        'check_e2e_chinese_language_assets': parent.ChineseLanguageQualification,
        'check_e2e_desktop_language': parent.DesktopLanguageQualification,
        'check_e2e_package_authority': parent.PackageAuthorityQualification,
        'check_e2e_package_command': parent.PackageInstallQualification,
        'check_e2e_customer_reboot': parent.CustomerRebootQualification,
        'check_e2e_restart_notice': parent.RestartNoticeQualification,
        'check_e2e_unrelated_reboot_request': parent.UnrelatedRebootQualification,
        'check_e2e_package_upgrade': parent.PackageUpgradeQualification,
        'check_e2e_chinese_kiosk_lifecycle': parent.ChineseKioskLifecycleQualification,
        'check_e2e_chinese_current_install': parent.ChineseCurrentInstallQualification,
    }
    actual, product_free, alternatives = set(), set(), {}
    # Discovery is intentional: wrappers are the inventory being independently
    # compared. Every loop emission is evaluated, including later overrides.
    for path in sorted((root / 'tests/integration').glob('check_*.py')):
        wrapper = ast.parse(path.read_text())
        if not any(isinstance(node, ast.ImportFrom) and node.module == 'check_graphical_smoke'
                   and any(alias.name == 'main' for alias in node.names)
                   for node in ast.walk(wrapper)):
            continue
        calls.clear()
        try:
            runpy.run_path(str(path), run_name='__main__')
        except SystemExit as error:
            assert error.code == 0
        for kwargs in calls:
            bound = signature.bind(**kwargs)
            bound.apply_defaults()
            scope = dict(vars(smoke), **bound.arguments, transfer_entry=False)
            exec(program, scope)
            cls = scope['qualification_class']
            alternatives.setdefault(path.stem, []).append(cls.__name__)
            if path.stem in ('check_parent_about', 'check_parent_access'):
                scope.update(qualification=SimpleNamespace(), fixture_selection={'private': True})
                with pytest.raises(CommandError, match='^fixtures:e2e-installed-branch-not-qualified$'):
                    exec(selection_guard, scope)
                assert not hasattr(scope['qualification'], 'fixture_selection')
            if cls is smoke.Qualification and kwargs.get('serial', False):
                scope.update(qualification=SimpleNamespace(), fixture_selection=selection.record())
                exec(serial_guard, scope)
                exec(selection_guard, scope)
                assert scope['qualification'].fixture_selection == selection.record()
            if path.stem in test_commands.INSTALLED_E2E_FIXTURE_SELECTORS:
                assert issubclass(cls, KioskEntryQualification), (path.stem, cls.__name__)
            if issubclass(cls, KioskEntryQualification):
                actual.add(path.stem)
            if issubclass(cls, (parent.ProductFreeEntryQualification,
                               parent.GdmProductFreeQualification)):
                product_free.add(path.stem)
                assert cls is product_free_classes[path.stem], (path.stem, cls.__name__)
    assert actual == set(test_commands.INSTALLED_E2E_FIXTURE_SELECTORS) - {'check_fixture_e2e_installed'}
    assert product_free == set(product_free_classes)
    for name, cls in product_free_classes.items():
        assert alternatives[name] == [cls.__name__]
    assert alternatives['check_parent_about'] == ['ParentAboutQualification']
    assert alternatives['check_parent_access'] == ['ParentAccessQualification']
    assert alternatives['check_e2e_native_fixtures'] == ['NativeFixtureQualification']
    assert alternatives['check_e2e_operate_public_connectivity_controls'] == [
        'PublicConnectivityControlsQualification']
    assert alternatives['check_e2e_approval_flow'] == [
        'ApprovalFlowRejectionQualification', 'ApprovalFlowCancelQualification']
    assert alternatives['check_e2e_time_profiles_daily'] == [
        'DailyTimeProfileQualification', 'SameDailyTimeProfileQualification']
    bound = signature.bind(assets=Path('/private/assets'), transfer_qualification=True)
    bound.apply_defaults()
    scope = dict(vars(smoke), **bound.arguments, transfer_entry=True)
    exec(program, scope)
    assert scope['qualification_class'] is smoke.Qualification
    scope.update(qualification=SimpleNamespace(), fixture_selection={'frozen': True})
    exec(selection_guard, scope)
    assert scope['qualification'].fixture_selection == {'frozen': True}
