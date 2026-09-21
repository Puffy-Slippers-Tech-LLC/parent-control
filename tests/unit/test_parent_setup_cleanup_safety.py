"""First Parent setup refuses changed inputs and never retries partial setup."""

import json
import shutil
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


def test_staged_helpers_survive_checkout_changes_before_capture(setup):
    adapter, vm, _ = setup
    adapter.verified.source_files = {'tests/integration/system_guest.py': 'b' * 64}
    adapter.provision(Mock())
    vm.copy.assert_called_once()


@pytest.mark.parametrize('failure', [None, 'copy', 'changed-source'])
def test_reused_snapshot_refreshes_guarded_payload_before_customer_input(
        setup, tmp_path, monkeypatch, failure):
    import installed_journey as journeys
    import parent_discovery

    adapter, vm, payload = setup
    guest_payload = tmp_path / 'snapshot-payload'
    guest_payload.mkdir()
    for name in ('package.deb', 'system_guest.py', 'e2e_dynamic_account.py',
                 'selected-inputs.json', 'transfer-sha256.json'):
        (guest_payload / name).write_bytes(b'previous snapshot input')
    reply = tmp_path / 'setup-detached.reply.json'

    def copy(download, source, destination):
        assert not reply.exists()
        assert download is False
        assert destination == installed_setup.system.PAYLOAD + '/'
        if failure == 'copy':
            raise RuntimeError('transfer interrupted')
        shutil.copytree(source, guest_payload, dirs_exist_ok=True)

    vm.copy.side_effect = copy
    vm.config = {}
    monkeypatch.setattr(journeys, 'Transport', Mock(return_value=vm))
    monkeypatch.setattr(journeys.system, 'address', Mock(return_value='fixture-host'))
    lease = adapter.verified.lease
    lease.source = SimpleNamespace(uuid='fixture-uuid')
    lease.view = SimpleNamespace(domain_id=7)
    lease.guard = Mock()
    context = SimpleNamespace(directory=tmp_path, verified=adapter.verified,
        lease=lease, host_key='fixture-key', commands=Mock(), installed_snapshot='onpc-v1.1')
    journey = journeys.InstalledJourney(context, Mock(), parent_discovery.PLAN,
                                      actions={'create-account': Mock()})
    for stage in ('ready', 'setup-detached'):
        (tmp_path / (stage + '.request.json')).write_text(
            json.dumps({'stage': stage, 'screenshot': None}))
    journey.step(Mock())
    if failure == 'changed-source':
        (payload / 'e2e_dynamic_account.py').write_bytes(b'unverified helper')
    if failure:
        with pytest.raises((RuntimeError, EvidenceError)):
            journey.step(Mock())
        assert not reply.exists()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
        if failure == 'changed-source':
            vm.copy.assert_not_called()
    else:
        journey.step(Mock())
        assert json.loads(reply.read_text()) == {'setup_complete': True}
        assert installed_setup.system.baseline.digest(guest_payload / 'package.deb') == (
            adapter.verified.inputs['package_sha256'])
        for name, expected in json.loads((guest_payload / 'transfer-sha256.json').read_text()).items():
            assert installed_setup.system.baseline.digest(guest_payload / name) == expected
        assert (guest_payload / 'selected-inputs.json').read_bytes() == (
            payload / 'selected-inputs.json').read_bytes()
    vm.call.assert_not_called()
    vm.reboot.assert_not_called()


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


@pytest.mark.parametrize('changed', ['package.deb', 'e2e_dynamic_account.py',
                                   'selected-inputs.json', 'fixtures/new-input.txt'])
def test_provision_uses_current_manifest_even_when_package_is_unchanged(setup, tmp_path, changed):
    adapter, vm, payload = setup
    guest_payload = tmp_path / 'guest-payload'
    shutil.copytree(payload, guest_payload)
    old_package = (guest_payload / 'package.deb').read_bytes()
    selected_path = payload / 'selected-inputs.json'
    selected = json.loads(selected_path.read_text())
    if changed == 'selected-inputs.json':
        selected['selection'] = {'consumer': 'E2E-003/none'}
    else:
        target = payload / changed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'current input revision')
        if changed in selected['files']:
            entry = selected['files'][changed]
            entry['sha256'] = installed_setup.system.baseline.digest(target)
            adapter.verified.source_files[entry['source']] = entry['sha256']
    selected_path.write_text(json.dumps(selected))
    inventory = {p.relative_to(payload).as_posix(): installed_setup.system.baseline.digest(p)
                 for p in payload.rglob('*') if p.is_file() and p.name != 'transfer-sha256.json'}
    (payload / 'transfer-sha256.json').write_text(json.dumps(inventory))
    adapter.verified.inputs['package_sha256'] = inventory['package.deb']
    vm.copy.side_effect = lambda _up, source, _destination: shutil.copytree(
        source, guest_payload, dirs_exist_ok=True)

    adapter.provision(Mock())

    assert (guest_payload / changed).read_bytes() == (payload / changed).read_bytes()
    assert {p.relative_to(guest_payload).as_posix(): installed_setup.system.baseline.digest(p)
            for p in guest_payload.rglob('*') if p.is_file() and p.name != 'transfer-sha256.json'} == inventory
    if changed != 'package.deb':
        assert (guest_payload / 'package.deb').read_bytes() == old_package
    vm.call.assert_not_called()
    vm.reboot.assert_not_called()


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
