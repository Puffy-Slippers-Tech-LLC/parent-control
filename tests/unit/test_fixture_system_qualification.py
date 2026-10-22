"""Private source trees and in-memory preparation/lease doubles; no live resources."""
from contextlib import nullcontext
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import fixture_system_qualification as qualification
from tools import fixture_execution


@pytest.fixture
def selection():
    return fixture_execution.Selection('ubuntu', 'a' * 64,
        '/tmp/onpc-native-runtime-ubuntu-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64)


def test_missing_and_incompatible_refuse_the_live_shared_boundary_before_staging(
        tmp_path, selection):
    vm = Mock()
    lease = SimpleNamespace(capture=SimpleNamespace(state={
        'guest': {'ubuntu_version': '26.04', 'fixture_boundary': 'clean'}}))
    context = {'vm': vm, 'lease': lease, 'directory': tmp_path}
    assert qualification.refused_inputs(context, selection) == {
        'missing': 'fixtures:execution-selection-required',
        'incompatible': 'fixtures:system-product-free-target-not-qualified'}
    assert not list(tmp_path.iterdir())
    assert not vm.mock_calls
    assert not hasattr(lease, '_fixture_provision_state')


@pytest.mark.parametrize('target', ['onpc-Fedora44', 'onpc-Ubuntu24.04'])
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


@pytest.mark.parametrize('failure', ['verify', 'bundle'])
def test_input_refusal_precedes_vm_acquisition(monkeypatch, tmp_path, selection, failure):
    monkeypatch.setattr(qualification, 'selected_target', lambda: qualification.TARGET)
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
    source = SimpleNamespace(domain=SimpleNamespace(name=lambda: q.TARGET))
    suite = Mock()
    suite.acquire.return_value = (source, None, lease)
    monkeypatch.setattr(q, 'Suite', Mock(return_value=suite))
    monkeypatch.setattr(q.system, 'artifact_source', lambda _: 'private-artifacts')
    monkeypatch.setattr(q.proof, 'preflight_source', Mock())
    selected = object()
    monkeypatch.setattr(q.system, 'resolve_selection', Mock(return_value=selected))
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
    assert staged[0] == tmp_path / 'history-1/input'


def test_authenticated_pin_outlives_all_runner_cleanup(monkeypatch, tmp_path, selection):
    from contextlib import contextmanager
    events = []

    @contextmanager
    def pin(record):
        events.append('pin-runtime' if record == selection.record() else 'pin-source')
        yield 17
        events.append('unpin-runtime' if record == selection.record() else 'unpin-source')

    monkeypatch.setattr(qualification, 'selected_target', lambda: qualification.TARGET)
    monkeypatch.setattr(qualification.fixture_execution, 'validate_source_selection', lambda *args: {})
    monkeypatch.setattr(qualification, 'authenticated_input', pin)
    monkeypatch.setattr(qualification.fixture_execution, 'verify', lambda _: {'private': 'manifest'})
    monkeypatch.setattr(qualification.fixture_provision, 'authenticated_bundle', Mock())
    monkeypatch.setattr(qualification, 'source_edit_proof', Mock())

    def run(*args):
        assert events == ['pin-runtime', 'pin-source']
        events.append('runner-and-cleanup')
        return {'accepted': True}

    monkeypatch.setattr(qualification, 'qualify_pinned', run)
    assert qualification.qualify(tmp_path, tmp_path / 'assets', selection.record(), {}) == {'accepted': True}
    assert events == ['pin-runtime', 'pin-source', 'runner-and-cleanup', 'unpin-source', 'unpin-runtime']
