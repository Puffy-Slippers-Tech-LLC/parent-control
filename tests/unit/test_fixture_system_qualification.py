"""Private source trees and in-memory preparation/lease doubles; no live resources."""
from contextlib import nullcontext
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import fixture_system_qualification as qualification
from tools import fixture_execution


@pytest.fixture(params=['ubuntu', 'fedora'])
def selection(request):
    return fixture_execution.Selection(request.param, 'a' * 64,
        '/tmp/onpc-native-runtime-' + request.param + '-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64)


def guest_for(target):
    return {'fixture_boundary': 'clean', **({'ubuntu_version': '26.04'}
        if target == 'ubuntu' else {'os_id': 'fedora', 'version': '44'})}


@pytest.mark.parametrize('diagnostic_failure', [False, True])
def test_failed_environment_retains_bounded_diagnostics_without_retry(
        monkeypatch, tmp_path, diagnostic_failure):
    controller, vm, lease = Mock(), Mock(), object()
    controller.wait_environment.side_effect = ValueError('original readiness failure')
    factory = Mock(return_value=controller)
    monkeypatch.setattr(qualification.fixture_provision, 'Provisioner', factory)
    vm.call.side_effect = ([OSError('diagnostic failed'), b'x' * (256 * 1024 + 1)]
                          if diagnostic_failure else [b'ActiveState=activating\n', b'private journal\n'])
    with pytest.raises(ValueError, match='original readiness failure'):
        qualification.wait_environment(vm, lease, tmp_path)
    factory.assert_called_once()
    controller.wait_environment.assert_called_once_with()
    assert vm.call.call_count == 2
    assert all(call.kwargs == {'timeout': 30, 'attempts': 1}
               for call in vm.call.call_args_list)
    if diagnostic_failure:
        assert {path.name for path in tmp_path.iterdir()} == {
            'failure-native-status-error.txt', 'failure-native-journal-error.txt'}
    else:
        assert (tmp_path / 'failure-native-status.txt').read_bytes() == b'ActiveState=activating\n'
        assert (tmp_path / 'failure-native-journal.txt').read_bytes() == b'private journal\n'


def test_diagnostic_storage_failure_preserves_original_readiness_exception(monkeypatch, tmp_path):
    controller, vm = Mock(), Mock()
    original = ValueError('original readiness failure')
    controller.wait_environment.side_effect = original
    monkeypatch.setattr(qualification.fixture_provision, 'Provisioner',
                        Mock(return_value=controller))
    vm.call.return_value = b'bounded diagnostics'
    monkeypatch.setattr(qualification.Path, 'write_bytes', Mock(side_effect=OSError('disk full')))
    monkeypatch.setattr(qualification.Path, 'write_text', Mock(side_effect=OSError('disk full')))
    with pytest.raises(ValueError) as caught:
        qualification.wait_environment(vm, object(), tmp_path)
    assert caught.value is original
    assert original.__notes__ == ['fixture-system:diagnostic-storage-unavailable'] * 2
    controller.wait_environment.assert_called_once_with()
    assert vm.call.call_count == 2


def target_name(target):
    return {'ubuntu': 'onpc-Ubuntu26.04', 'fedora': 'onpc-Fedora44'}[target]


def test_missing_and_incompatible_refuse_the_live_shared_boundary_before_staging(
        tmp_path, selection):
    vm = Mock()
    lease = SimpleNamespace(capture=SimpleNamespace(state={
        'guest': guest_for(selection.target)}))
    context = {'vm': vm, 'lease': lease, 'directory': tmp_path}
    assert qualification.refused_inputs(context, selection) == {
        'missing': 'fixtures:execution-selection-required',
        'incompatible': 'fixtures:system-product-free-target-not-qualified'}
    assert not list(tmp_path.iterdir())
    assert not vm.mock_calls
    assert not hasattr(lease, '_fixture_provision_state')


@pytest.mark.parametrize('target', ['onpc-Fedora43', 'onpc-Ubuntu24.04', 'unknown'])
def test_unqualified_target_never_opens_an_input_or_suite(monkeypatch, tmp_path, selection, target):
    monkeypatch.setattr(qualification.proof.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name=target))
    pin, suite = Mock(), Mock()
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    monkeypatch.setattr(qualification, 'Suite', suite)
    with pytest.raises(qualification.system.Error, match='target-not-qualified'):
        qualification.qualify(tmp_path, tmp_path / 'assets', selection.record(), None)
    pin.assert_not_called()
    suite.assert_not_called()


@pytest.mark.parametrize('installed', [False, True])
def test_selected_target_accepts_both_canonical_targets(monkeypatch, selection, installed):
    name = target_name(selection.target)
    monkeypatch.setattr(qualification.proof.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name=name))
    assert qualification.selected_target(installed=installed) == name


def test_qualification_target_mismatch_never_pins_input_or_acquires_suite(
        monkeypatch, tmp_path, selection):
    other = 'fedora' if selection.target == 'ubuntu' else 'ubuntu'
    monkeypatch.setattr(qualification, 'selected_target', lambda: target_name(other))
    pin, suite = Mock(), Mock()
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    monkeypatch.setattr(qualification, 'Suite', suite)
    with pytest.raises(ValueError, match='fixtures:system-product-free-target-not-qualified'):
        qualification.qualify(tmp_path, tmp_path / 'assets', selection.record(), None)
    pin.assert_not_called()
    suite.assert_not_called()


@pytest.mark.parametrize('invalid', ['opposite', 'unknown'])
def test_selection_target_refuses_before_authentication_or_staging(
        monkeypatch, tmp_path, selection, invalid):
    preparation = qualification.preparation
    record = selection.record()
    other = 'fedora' if selection.target == 'ubuntu' else 'ubuntu'
    record['target'] = other if invalid == 'opposite' else 'unknown'
    record['allocation'] = record['allocation'].replace(
        'runtime-' + selection.target + '-', 'runtime-' + record['target'] + '-')
    verify, factory, vm = Mock(), Mock(), Mock()
    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', factory)
    lease = SimpleNamespace(capture=SimpleNamespace(state={'guest': guest_for(selection.target)}))
    reason = ('fixtures:system-product-free-target-not-qualified' if invalid == 'opposite'
              else 'fixture execution: invalid selection identity')
    with pytest.raises(ValueError, match=reason):
        preparation.prepare(vm, lease, tmp_path, record)
    verify.assert_not_called()
    factory.assert_not_called()
    assert not vm.mock_calls and not list(tmp_path.iterdir())


@pytest.mark.parametrize('failure', ['verify', 'bundle'])
def test_input_refusal_precedes_vm_acquisition(monkeypatch, tmp_path, selection, failure):
    monkeypatch.setattr(qualification, 'selected_target', lambda: target_name(selection.target))
    monkeypatch.setattr(qualification.fixture_execution, 'validate_source_selection', lambda *args: {})
    monkeypatch.setattr(qualification, 'authenticated_input', lambda _: nullcontext())
    verify, bundle = Mock(return_value={}), Mock()
    (verify if failure == 'verify' else bundle).side_effect = ValueError('private invalid input')
    monkeypatch.setattr(qualification.fixture_execution, 'verify', verify)
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', bundle)
    suite = Mock()
    monkeypatch.setattr(qualification, 'Suite', suite)
    with pytest.raises(ValueError, match='private invalid input'):
        qualification.qualify(tmp_path, tmp_path / 'assets', selection.record(), {})
    suite.assert_not_called()


@pytest.mark.parametrize('invalid', [None, 'origin', 'actual-edit', 'selection'])
def test_source_edit_proof_is_bound_to_actual_producer_tree(monkeypatch, tmp_path, selection, invalid):
    root = tmp_path / 'source'
    root.mkdir()
    name = 'tests/fixtures/onpc_test_application.c'
    source = root / name
    source.parent.mkdir(parents=True)
    source.write_bytes(b'/* private original */\n')
    monkeypatch.setattr(qualification.fixture_bundle.artifact_inputs, 'NATIVE_RUNTIME_SOURCES', (name,))
    original, _ = qualification.fixture_bundle.source_snapshot(root)
    source.write_bytes(b'/* actual private producer changed after selection */\n')
    edited, _ = qualification.fixture_bundle.source_snapshot(root)
    proof = {'schema': 'onpc-fixture-source-edit-v1', 'selection': selection.record(),
             'before': original, 'after': edited, 'environment': {'recipe': 'private'}, 'edited': name}
    manifest = {'inputs': {'source': original, 'toolchain': {'environment': proof['environment']}}}
    if invalid == 'origin':
        proof['before'] = edited
    elif invalid == 'actual-edit':
        source.write_bytes(b'/* unrecorded change */\n')
    elif invalid == 'selection':
        proof['selection'] = {**selection.record(), 'build_identity': 'd' * 64}
    proof_path = tmp_path / 'source-edit.json'
    proof_path.write_bytes(qualification.fixture_manifest._canonical(proof))
    proof_path.chmod(0o600)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        if invalid:
            with pytest.raises(qualification.system.Error, match='source-proof-identity|producer-source-changed'):
                qualification.source_edit_proof(fd, selection, manifest)
        else:
            evidence = qualification.source_edit_proof(fd, selection, manifest)
            assert evidence['original_source_sha256'] != evidence['edited_source_sha256']
            assert evidence['scope'] == 'actual-private-producer-checkout-edited-after-selection'
    finally:
        os.close(fd)


@pytest.mark.parametrize('failure', [None, 'attempt', 'freshness'])
def test_real_runner_seam_owns_two_restorations_and_suite_closes_on_failure(
        monkeypatch, tmp_path, selection, failure):
    import fixture_system_qualification as q
    lease = SimpleNamespace(state={'phase': 'complete'},
        view=SimpleNamespace(domain_id=None, snapshot=lambda: (None, True)))
    source = SimpleNamespace(domain=SimpleNamespace(name=lambda: target_name(selection.target)))
    monkeypatch.setattr(q, 'selected_target', lambda: target_name(selection.target))
    suite = Mock()
    suite.acquire.return_value = (source, None, lease)
    monkeypatch.setattr(q, 'Suite', Mock(return_value=suite))
    monkeypatch.setattr(q.system, 'artifact_source', lambda _: 'private-artifacts')
    monkeypatch.setattr(q.proof, 'preflight_source', Mock())
    selected = object()
    resolve = Mock(return_value=selected)
    monkeypatch.setattr(q.system, 'resolve_selection', resolve)
    staged = []

    def stage(assets, destination, commands, **kwargs):
        assert assets == 'private-artifacts' and kwargs == {'package_only': True}
        staged.append(destination)
        return {'private': 'package metadata'}

    monkeypatch.setattr(q.system, 'stage_assets', stage)
    monkeypatch.setattr(q.system, 'stage_selected_inputs', Mock(return_value='selected-digest'))
    runs = []

    def run(actual_suite, history, actual_selection, manifest, digest, ledger, **kwargs):
        assert actual_suite is suite and actual_selection is selected
        assert manifest == {'private': 'package metadata'} and digest == 'selected-digest'
        assert kwargs['fixture_selection'] == selection.record() and kwargs['preparation_only'] is True
        runs.append(history.name)
        if failure == 'attempt':
            raise ValueError('private attempt failure')
        output = kwargs['preparation_observer']
        output['binding'] = {'boot_sha256': 'same' if failure == 'freshness' else history.name,
            'attempt_id': history.name, 'vm_uuid': 'vm', 'manifest_sha256': 'manifest',
            'content_identity': 'content'}

    monkeypatch.setattr(q, 'observer', lambda _selection, _manifest, output, _previous, _source: output)
    monkeypatch.setattr(q.system_snapshots, 'run_attempts', run)
    verify = Mock(return_value={})
    monkeypatch.setattr(q.fixture_execution, 'verify', verify)
    if failure:
        with pytest.raises((ValueError, q.system.Error)):
            q.qualify_pinned(tmp_path, tmp_path / 'unused', selection, {}, None)
    else:
        result = q.qualify_pinned(tmp_path, tmp_path / 'unused', selection, {}, None)
        assert result['owned_baseline_restoration_verified'] is True
        assert all(item['owned_restoration_verified'] for item in result['attempts'])
        assert runs == ['history-1', 'history-2']
        verify.assert_called_once_with(selection)
    suite.close.assert_called_once_with()
    resolve.assert_called_once_with('package', q.system.FIRST_CONFIGURE_CASE,
        target_package_format='deb' if selection.target == 'ubuntu' else 'rpm')
    assert staged[0] == tmp_path / 'history-1/input'


@pytest.mark.parametrize('installed', [False, True])
def test_authenticated_pin_outlives_all_runner_cleanup(monkeypatch, tmp_path, selection, installed):
    from contextlib import contextmanager
    events = []

    @contextmanager
    def pin(record):
        events.append('pin-runtime' if record == selection.record() else 'pin-source')
        yield 17
        events.append('unpin-runtime' if record == selection.record() else 'unpin-source')

    monkeypatch.setattr(qualification, 'selected_target', lambda **_: target_name(selection.target))
    monkeypatch.setattr(qualification.fixture_execution, 'validate_source_selection', lambda *args: {})
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    monkeypatch.setattr(qualification.fixture_execution, 'verify', lambda _: {'private': 'manifest'})
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', Mock())
    monkeypatch.setattr(qualification, 'source_edit_proof', Mock())

    def run(*args, **options):
        assert events == ['pin-runtime', 'pin-source']
        assert options == ({'installed': True} if installed else {})
        events.append('runner-and-cleanup')
        return {'accepted': True}

    monkeypatch.setattr(qualification, 'qualify_pinned', run)
    assert qualification.qualify(tmp_path, tmp_path / 'assets', selection.record(), {},
                                 installed=installed) == {'accepted': True}
    assert events == ['pin-runtime', 'pin-source', 'runner-and-cleanup', 'unpin-source', 'unpin-runtime']


@pytest.fixture
def installed_selection(selection):
    return selection


@pytest.mark.parametrize('target', ['onpc-Fedora43', 'onpc-Ubuntu24.04', 'unknown'])
def test_installed_target_refuses_before_authentication_or_suite(
        monkeypatch, tmp_path, installed_selection, target):
    monkeypatch.setattr(qualification.proof.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name=target))
    pin, suite = Mock(), Mock()
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    monkeypatch.setattr(qualification, 'Suite', suite)
    with pytest.raises(qualification.system.Error, match='target-not-qualified'):
        qualification.qualify(tmp_path, tmp_path / 'assets',
                              installed_selection.record(), None, installed=True)
    pin.assert_not_called()
    suite.assert_not_called()


def test_installed_missing_and_incompatible_refuse_before_staging(tmp_path, installed_selection):
    vm = Mock()
    lease = SimpleNamespace(capture=SimpleNamespace(state={
        'guest': guest_for(installed_selection.target)}),
        installed_online=False, online_pending=False,
        installed_name='onpc-private', _restored_name='onpc-private')
    assert qualification.refused_inputs({'vm': vm, 'lease': lease, 'directory': tmp_path},
        installed_selection, installed=True) == {
            'missing': 'fixtures:execution-selection-required',
            'incompatible': 'fixtures:system-installed-target-not-qualified'}
    assert not list(tmp_path.iterdir())
    assert not vm.mock_calls and not hasattr(lease, '_fixture_provision_state')


@pytest.mark.parametrize('failure', [None, 'attempt', 'freshness'])
def test_installed_qualification_reenters_offline_prepare_case_for_both_histories(
        monkeypatch, tmp_path, installed_selection, failure):
    q = qualification
    real_suite = q.Suite(lambda: None)
    snapshots = SimpleNamespace(getXMLDesc=lambda _: 'private-offline-snapshot')
    domain = SimpleNamespace(name=lambda: target_name(installed_selection.target),
        snapshotLookupByName=lambda name, flags: snapshots)
    source = SimpleNamespace(domain=domain)
    lease = SimpleNamespace(state={'phase': 'complete'},
        view=SimpleNamespace(domain_id=None, snapshot=lambda: (None, True)),
        capture=SimpleNamespace(state={'guest': guest_for(installed_selection.target),
                                      'proof': {'name': 'baseline'}}),
        source=source, installed_online=False, online_pending=False,
        installed_name=None, _restored_name='baseline', prepare=Mock())
    restores = []
    def stop():
        lease._restored_name = lease.installed_name if lease.restore_installed else 'baseline'
        restores.append(lease._restored_name)
    lease.stop = stop
    monkeypatch.setattr(q.proof.prepare_vm.vm_config, 'selected',
                        lambda: SimpleNamespace(name=target_name(installed_selection.target)))
    suite = real_suite
    suite.lease = lease
    suite.acquire = Mock(return_value=(source, None, lease))
    suite.close = Mock()
    suite.prepare_installed = Mock(return_value=False)
    monkeypatch.setattr(q.system, 'package_version', lambda *_: '1.2')
    monkeypatch.setattr(q.system, 'watch_progress', None)
    monkeypatch.setattr(q, 'Suite', Mock(return_value=suite))
    monkeypatch.setattr(q.system, 'artifact_source', lambda _: 'private-artifacts')
    monkeypatch.setattr(q.proof, 'preflight_source', Mock())
    selected = object()
    resolve = Mock(return_value=selected)
    monkeypatch.setattr(q.system, 'resolve_selection', resolve)
    stage = Mock(return_value={'private': 'package metadata'})
    monkeypatch.setattr(q.system, 'stage_assets', stage)
    monkeypatch.setattr(q.system, 'stage_selected_inputs', Mock(return_value='selected-digest'))
    observations = []
    def make_observer(selection, manifest, result, previous, source, **options):
        assert options == {'installed': True}
        observations.append(result)
        return result
    monkeypatch.setattr(q, 'observer', make_observer)
    runs = []
    def run(actual_suite, history, actual_selection, manifest, digest, ledger, **options):
        assert actual_suite is suite and actual_selection is selected
        assert suite.snapshot_mode == 'offline' and suite.prepared is False
        assert options['fixture_selection'] == installed_selection.record()
        assert options['preparation_only'] is True
        runs.append(history.name)
        suite.next_case = None
        try:
            # Keep the actual installed-case restore composition. Merely
            # setting offline on a Mock Suite misses the second-history bug.
            suite.prepare_case(q.system_snapshots.installed_case(True), history,
                history / 'input', {}, root=q.ROOT)
            q.preparation.require_installed_restore(lease)
            if failure == 'attempt':
                raise ValueError('private attempt failure')
            options['preparation_observer']['binding'] = {
                'boot_sha256': 'same' if failure == 'freshness' else history.name,
                'attempt_id': history.name, 'vm_uuid': 'vm', 'manifest_sha256': 'manifest',
                'content_identity': 'content'}
        finally:
            lease.stop()
    monkeypatch.setattr(q.system_snapshots, 'run_attempts', run)
    verify = Mock(return_value={})
    monkeypatch.setattr(q.fixture_execution, 'verify', verify)
    if failure:
        with pytest.raises((ValueError, q.system.Error)):
            q.qualify_pinned(tmp_path, tmp_path / 'unused', installed_selection, {}, None,
                             installed=True)
    else:
        result = q.qualify_pinned(tmp_path, tmp_path / 'unused', installed_selection, {}, None,
                                  installed=True)
        assert result['owned_baseline_restoration_verified'] is True
        assert runs == ['history-1', 'history-2']
        assert all(item['owned_restoration_verified'] for item in result['attempts'])
        verify.assert_called_once_with(installed_selection)
        assert restores == ['onpc-v1.2', 'baseline', 'onpc-v1.2', 'baseline']
        assert suite.prepare_installed.call_count == 2
        assert all(call.kwargs['mode'] == 'offline' and call.kwargs['overwrite'] is False
                   for call in suite.prepare_installed.call_args_list)
    suite.close.assert_called_once_with()
    resolve.assert_called_once_with('authorization',
        target_package_format='rpm' if installed_selection.target == 'fedora' else 'deb')
    assert all(call.kwargs == {'package_only': True} for call in stage.call_args_list)


@pytest.mark.parametrize('online,restored', [(True, 'onpc-private'), (False, 'baseline')])
def test_installed_observer_refuses_wrong_restore_before_guest_reads(
        monkeypatch, tmp_path, installed_selection, online, restored):
    lease = SimpleNamespace(capture=SimpleNamespace(state={
        'guest': guest_for(installed_selection.target)}),
        installed_online=online, online_pending=False,
        installed_name='onpc-private', _restored_name=restored)
    audit = Mock()
    monkeypatch.setattr(qualification.proof, 'audit', audit)
    vm = Mock()
    observe = qualification.observer(installed_selection, {}, {}, installed=True)
    with pytest.raises((ValueError, qualification.system.Error), match='offline-restore-required'):
        observe('before', {'vm': vm, 'lease': lease, 'directory': tmp_path})
    audit.assert_not_called()
    assert not vm.mock_calls and not list(tmp_path.iterdir())
