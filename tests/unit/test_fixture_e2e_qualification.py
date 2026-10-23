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


@pytest.mark.parametrize('profile', ['activity', 'riley-grid'])
def test_unqualified_native_closures_refuse_before_worker(monkeypatch, tmp_path, selection, profile):
    from installed_journey import InstalledJourney, JourneyPlan
    from native_fixtures import fixture_actions
    from private_artifacts import EvidenceError
    plan = JourneyPlan(prefix='native-scope', worker_mode='native',
        screen_tags={'fixture': 'ui:desktop'}, phases={}, stage_actions={'fixture': 'native-verify'})
    context = SimpleNamespace(directory=tmp_path, fixture_selection=selection.record())
    with pytest.raises(EvidenceError, match='profile-not-qualified'):
        InstalledJourney(context, Mock(), plan,
            actions=fixture_actions(profile=profile, include_refusal=False))
    assert not list(tmp_path.iterdir())


def test_authenticated_selections_outlive_every_history_and_cleanup(monkeypatch, tmp_path, selection):
    events = []
    @contextmanager
    def pin(record):
        events.append('pin-runtime' if record == selection.record() else 'pin-source')
        yield 11
        events.append('unpin-runtime' if record == selection.record() else 'unpin-source')
    target_name = {'ubuntu': 'onpc-Ubuntu26.04', 'fedora': 'onpc-Fedora44'}[selection.target]
    monkeypatch.setattr(qualification, 'selected_target', lambda: target_name)
    monkeypatch.setattr(preparation, 'validate_input', lambda value, **_: value)
    monkeypatch.setattr(qualification.fixture_execution, 'validate_source_selection', lambda *_: {})
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    monkeypatch.setattr(qualification.fixture_execution, 'verify', lambda _: {})
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', Mock())
    monkeypatch.setattr(qualification.shared, 'source_edit_proof', Mock())
    def run(*_):
        assert events == ['pin-runtime', 'pin-source']
        events.append('histories-and-cleanup')
        return {'passed': True}
    monkeypatch.setattr(qualification, 'qualify_pinned', run)
    assert qualification.qualify(tmp_path, tmp_path / 'assets', selection.record(), {}) == {'passed': True}
    assert events == ['pin-runtime', 'pin-source', 'histories-and-cleanup',
                      'unpin-source', 'unpin-runtime']


def test_every_wrapper_final_ordered_class_matches_installed_aliases(monkeypatch):
    """Evaluate actual wrapper loops and the complete real final dispatch block."""
    import ast
    import inspect
    from pathlib import Path
    import runpy
    import sys
    import check_graphical_smoke as smoke
    import test_commands
    from parent_setup_qualification import KioskEntryQualification
    from tools import test_storage

    root = Path(smoke.ROOT)
    tree = ast.parse((root / 'tests/integration/check_graphical_smoke.py').read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    blocks = []
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
    assert len(blocks) == 1
    program = compile(ast.Module(body=blocks[0], type_ignores=[]), str(root), 'exec')
    signature = inspect.signature(smoke.main)
    calls = []
    monkeypatch.setattr(smoke, 'main', lambda **kwargs: calls.append(kwargs) or 0)
    monkeypatch.setattr(test_storage, 'named_input', lambda **_: Path('/private/declared-input'))
    monkeypatch.setattr(sys, 'exit', lambda *_: None)
    monkeypatch.setattr(sys, 'argv', ['qualification-composition'])
    actual, alternatives = set(), {}
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
            scope = dict(vars(smoke), **bound.arguments)
            exec(program, scope)
            cls = scope['qualification_class']
            alternatives.setdefault(path.stem, []).append(cls.__name__)
            if path.stem in test_commands.INSTALLED_E2E_FIXTURE_SELECTORS:
                assert issubclass(cls, KioskEntryQualification), (path.stem, cls.__name__)
            if issubclass(cls, KioskEntryQualification):
                actual.add(path.stem)
    assert actual == set(test_commands.INSTALLED_E2E_FIXTURE_SELECTORS) - {'check_fixture_e2e_installed'}
    assert alternatives['check_e2e_native_fixtures'] == ['NativeFixtureQualification']
    assert alternatives['check_e2e_operate_public_connectivity_controls'] == [
        'PublicConnectivityControlsQualification']
    assert alternatives['check_e2e_approval_flow'] == [
        'ApprovalFlowRejectionQualification', 'ApprovalFlowCancelQualification']
    assert alternatives['check_e2e_time_profiles_daily'] == [
        'DailyTimeProfileQualification', 'SameDailyTimeProfileQualification']
