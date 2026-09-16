"""First Parent setup refuses changed inputs and never retries partial setup."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import installed_setup
import system_guest
from private_artifacts import EvidenceError


@pytest.fixture
def setup(tmp_path):
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'package.deb').write_bytes(b'fixture package')
    (assets / 'transfer-sha256.json').write_text('{}')
    installed_setup.stage(tmp_path, assets, {'consumer': 'E2E-030/parent'})
    payload = tmp_path / 'input'
    selected = json.loads((payload / 'selected-inputs.json').read_text())
    verified = SimpleNamespace(recheck=Mock(), lease=SimpleNamespace(state={'run': 'a' * 32}),
        inputs={'package_sha256': installed_setup.system.baseline.digest(payload / 'package.deb')},
        source_files={entry['source']: entry['sha256'] for entry in selected['files'].values()})
    vm = Mock()
    return installed_setup.InstalledSetup(tmp_path, verified, vm), vm, payload


def test_setup_verifies_package_after_owned_reboot(setup):
    adapter, vm, _ = setup
    guard = Mock()
    assert adapter.run(guard) == {'package_verified': True, 'setup_reboot_verified': True}
    assert [call[0] for call in vm.mock_calls] == ['copy', 'call', 'reboot', 'call']
    assert vm.call.call_args_list[0].args[0][-1] == 'install-setup'
    assert vm.call.call_args_list[1].args[0][-1] == 'verify-setup'
    assert guard.call_count == 4
    with pytest.raises(EvidenceError, match='already-attempted'):
        adapter.run(guard)


def test_suite_setup_installs_and_reboots_without_product_validation(setup):
    adapter, vm, _ = setup
    assert adapter.run(Mock(), verify=False) == {
        'package_verified': False, 'setup_reboot_verified': True}
    assert [call[0] for call in vm.mock_calls] == ['copy', 'call', 'reboot']
    assert vm.call.call_args.args[0][-1] == 'install-suite'


def test_guest_suite_install_does_not_check_existing_product_state(monkeypatch):
    monkeypatch.setattr(system_guest, 'guard', lambda: {'selected_inputs_sha256': 'a' * 64})
    monkeypatch.setattr(system_guest, 'sha', lambda _: 'a' * 64)
    before = Mock(side_effect=AssertionError('unexpected product probe'))
    install = Mock()
    monkeypatch.setattr(system_guest, 'before_install', before)
    monkeypatch.setattr(system_guest, 'install_package', install)
    system_guest.install_suite()
    install.assert_called_once_with()
    before.assert_not_called()


@pytest.mark.parametrize('boundary', ['copy', 'call', 'reboot'])
def test_failed_setup_is_terminal_and_never_owns_cleanup(setup, boundary):
    adapter, vm, _ = setup
    getattr(vm, boundary).side_effect = RuntimeError('fixed failure')
    with pytest.raises(RuntimeError):
        adapter.run(Mock())
    before = list(vm.mock_calls)
    with pytest.raises(EvidenceError, match='already-attempted'):
        adapter.run(Mock())
    assert vm.mock_calls == before
    assert not vm.close.called


@pytest.mark.parametrize('target', ['package.deb', 'system_guest.py', 'selected-inputs.json'])
def test_changed_payload_refuses_before_guest_mutation(setup, target):
    adapter, vm, payload = setup
    (payload / target).write_bytes(b'changed')
    with pytest.raises(EvidenceError, match='payload-changed'):
        adapter.run(Mock())
    assert not vm.mock_calls


def test_lost_worker_guard_refuses_before_guest_mutation(setup):
    adapter, vm, _ = setup
    with pytest.raises(RuntimeError):
        adapter.run(Mock(side_effect=RuntimeError('lost worker')))
    assert not vm.mock_calls


def test_guest_selection_mismatch_refuses_install(monkeypatch):
    monkeypatch.setattr(system_guest, 'guard', lambda: {'selected_inputs_sha256': 'a' * 64})
    monkeypatch.setattr(system_guest, 'sha', lambda _: 'b' * 64)
    install = Mock()
    monkeypatch.setattr(system_guest, 'install', install)
    with pytest.raises(system_guest.GuestError, match='selected-inputs-digest'):
        system_guest.install_setup()
    install.assert_not_called()


@pytest.mark.parametrize('failure', [None, 'checkpoint', 'worker-after-checkpoint'])
def test_acknowledgement_requires_durable_evidence_and_fresh_worker(
        tmp_path, monkeypatch, failure):
    import parent_setup_qualification as qualification

    controller = object.__new__(qualification.ParentSetupQualification)
    controller.directory = tmp_path
    controller.commands = Mock()
    controller.ledger = Mock()
    controller.assets = tmp_path / 'assets'
    controller.credentials = SimpleNamespace(provision=Mock(return_value={}))
    controller.result = {}
    verified = SimpleNamespace(inputs={}, source_files={})
    monkeypatch.setattr(qualification.smoke, 'VerifiedInputs', Mock(return_value=verified))
    monkeypatch.setattr(qualification.smoke.runner, 'bootstrap', Mock(return_value='fixture-key'))
    reply = tmp_path / 'ready.reply.json'
    observed = []
    authorized = []

    def checkpoint(event):
        if event == 'stage-observed':
            # A worker may consume the reply as soon as it exists. Evidence
            # storage must succeed before that permission becomes visible.
            assert not reply.exists()
            observed.append(event)
            if failure == 'checkpoint':
                raise RuntimeError('test-checkpoint-failed')

    def guard():
        if observed and failure == 'worker-after-checkpoint':
            raise RuntimeError('test-worker-gone')

    def run_worker(*_args, **kwargs):
        (tmp_path / 'ready.request.json').write_text(json.dumps(
            {'stage': 'ready', 'screenshot': None}))
        kwargs['guarded_observe'](guard)
        assert observed == ['stage-observed']
        authorized.append(json.loads(reply.read_text()))
        return {'outcome': 'passed'}

    controller.checkpoint = checkpoint
    monkeypatch.setattr(qualification.smoke.e2e_worker, 'run_distribution', run_worker)
    if failure is None:
        controller.execute(Mock(), Mock())
        assert authorized == [{'parent_setup': True}]
    else:
        with pytest.raises(RuntimeError, match='test-'):
            controller.execute(Mock(), Mock())
        assert not authorized
        assert not reply.exists()
        assert not (tmp_path / 'ready.reply.tmp').exists()
