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
    verified = SimpleNamespace(recheck=Mock(), lease=SimpleNamespace(state={'run': 'a' * 32},
        capture=SimpleNamespace(state={'guest': {'ubuntu_version': '26.04'}})),
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


def test_suite_setup_installs_without_reboot_before_snapshot_shutdown(setup):
    adapter, vm, _ = setup
    guard = Mock()
    assert adapter.run(guard, verify=False) == {
        'package_verified': False, 'setup_reboot_verified': False}
    assert [call[0] for call in vm.mock_calls] == ['copy', 'call']
    assert vm.call.call_args.args[0][-1] == 'install-suite'
    vm.reboot.assert_not_called()
    assert guard.call_count == 3
    with pytest.raises(EvidenceError, match='already-attempted'):
        adapter.run(guard, verify=False)


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
        lease=lease, host_key='fixture-key', commands=Mock(), installed_snapshot='onpc-v9.8.7')
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


def test_guest_dispatch_accepts_the_fixed_snapshot_verification(monkeypatch):
    verify = Mock()
    monkeypatch.setattr(system_guest, 'verify_snapshot', verify)

    assert system_guest.main(['verify-snapshot']) == 0

    verify.assert_called_once_with()


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


@pytest.mark.parametrize('diagnostic_fault', [None, 'guard', 'copy'])
def test_failed_install_retains_guest_commands_without_masking_first_failure(setup, diagnostic_fault):
    # Reuse the attempt's private allocation and transport; no new resource owner.
    adapter, vm, _ = setup
    original = RuntimeError('installer failed')
    vm.call.side_effect = original
    if diagnostic_fault == 'copy':
        vm.copy.side_effect = [None, RuntimeError('collection failed')]
    guard = Mock(side_effect=[None, None, RuntimeError('ownership lost')]
                 if diagnostic_fault == 'guard' else None)
    with pytest.raises(RuntimeError) as caught:
        adapter.run(guard)
    assert caught.value is original
    assert vm.copy.call_count == (1 if diagnostic_fault == 'guard' else 2)
    if diagnostic_fault != 'guard':
        assert vm.copy.call_args.args == (True, installed_setup.system.PAYLOAD + '/private/',
                                          str(adapter.directory / 'guest-private') + '/')
    vm.reboot.assert_not_called()
    vm.close.assert_not_called()
    before = list(vm.mock_calls)
    with pytest.raises(EvidenceError, match='already-attempted'):
        adapter.run(Mock())
    assert vm.mock_calls == before


def test_cancelled_install_skips_diagnostic_collection(setup):
    adapter, vm, _ = setup
    original = KeyboardInterrupt()
    vm.call.side_effect = original
    with pytest.raises(KeyboardInterrupt) as caught:
        adapter.run(Mock())
    assert caught.value is original
    assert vm.copy.call_count == 1
    vm.reboot.assert_not_called()


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


@pytest.mark.parametrize('mode', ['online', 'offline'])
@pytest.mark.parametrize('changed', [None, 'package', 'baseline', 'recipe',
                                    'metadata', 'age', 'race', 'guard', 'domain'])
def test_snapshot_attachment_checks_frozen_installed_identity_before_restore(
        setup, monkeypatch, mode, changed):
    import app_snapshot
    from guest_inputs import Bundle
    from parent_setup_qualification import KioskEntryQualification
    from tests.support.paths import ROOT
    from tests.support.vm_runner import UUID, xml as domain_xml

    adapter, _, payload = setup
    controller = object.__new__(KioskEntryQualification)
    controller.directory = payload.parent
    controller.assets = payload
    controller.commands = Mock()
    controller.result = {}
    lease = adapter.verified.lease
    lease.state['baseline_sha256'] = 'b' * 64
    lease.guard = Mock()
    lease.save = Mock()
    lease.snapshot_status = Mock()
    lease.source = SimpleNamespace(domain=Mock(), connection=Mock(), api=Mock())
    lease.view = SimpleNamespace(domain_id=7)
    lease.test_xml = '<isolated/>'
    monkeypatch.setattr(app_snapshot.system, 'package_version', lambda *_: '9.8.7')
    monkeypatch.setattr(app_snapshot.package_content, 'digest', lambda *_: 'c' * 64)
    monkeypatch.setattr(app_snapshot.time, 'time', lambda: 100000)
    bundle = Bundle.from_staged(ROOT, payload)
    expected = json.loads(app_snapshot.input_identity(lease, payload, bundle, controller.commands))
    previous = dict(expected)
    if changed in ('package', 'baseline', 'recipe'):
        previous[{'package': 'package_content_sha256', 'baseline': 'baseline_sha256',
                  'recipe': 'recipe_sha256'}[changed]] = 'd' * 64
    if changed == 'metadata':
        previous = {'schema_version': 2}
    lease.original_xml = domain_xml()
    domain = (app_snapshot.system.isolated_xml(lease.original_xml, UUID, 'a' * 32, graphics_type='vnc')
              if mode == 'online' else lease.original_xml)
    if changed == 'domain':
        import xml.etree.ElementTree as ET
        edited = ET.fromstring(domain)
        ET.SubElement(edited, 'unexpected').text = 'changed'
        domain = ET.tostring(edited, encoding='unicode')
    memory, state = ('internal', 'running') if mode == 'online' else ('no', 'shutoff')
    created = 1 if changed == 'age' else 100000
    xml = (f'<domainsnapshot><description>{json.dumps(previous)}</description>'
           f'<memory snapshot="{memory}"/><state>{state}</state>'
           f'<creationTime>{created}</creationTime>{domain}</domainsnapshot>')
    snapshot = lease.source.domain.snapshotLookupByName.return_value
    snapshot.getXMLDesc.side_effect = [xml, xml + ' ' if changed == 'race' else xml]
    if changed == 'guard':
        lease.guard.side_effect = RuntimeError('lost owner')
    accepted = (changed is None or changed == 'age' and mode == 'offline'
                or changed == 'domain' and mode == 'online')
    if not accepted:
        with pytest.raises((EvidenceError, RuntimeError)):
            controller.attach_installed_snapshot(lease)
        assert not hasattr(lease, 'online_pending')
        lease.source.domain.revertToSnapshot.assert_not_called()
        lease.source.connection.defineXML.assert_not_called()
        assert controller.result == {}
    else:
        from contextlib import nullcontext
        lease.snapshot_status.return_value = nullcontext()
        operations = []
        lease.source.domain.revertToSnapshot.side_effect = lambda *_: operations.append('restore')
        lease.source.connection.defineXML.side_effect = lambda *_: operations.append('isolate')
        controller.attach_installed_snapshot(lease)
        assert controller.result['installed_snapshot'] == {
            'name': 'onpc-v9.8.7', 'mode': mode, 'inputs': previous,
            'expected_inputs': expected}
        if mode == 'online':
            assert lease.online_pending and lease.installed_xml == xml
            lease.source.domain.revertToSnapshot.assert_not_called()
            assert operations == []
        else:
            lease.source.domain.revertToSnapshot.assert_called_once()
            lease.source.connection.defineXML.assert_called_once_with(lease.test_xml)
            assert operations == ['restore', 'isolate']
            assert lease.original_xml == domain_xml()
        lease.guard.assert_any_call(off=True)


@pytest.mark.parametrize('fault', [None, 'unconnected', 'guard', 'command'])
@pytest.mark.parametrize('kind', ['entry', 'duration', 'parent'])
def test_installed_failure_logs_are_private_bounded_and_guarded(tmp_path, fault, kind):
    from kiosk_entry import KioskEntryJourney
    from kiosk_valid_duration import KioskValidDurationJourney
    from parent_about import ParentJourney
    journey_type = {'entry': KioskEntryJourney, 'duration': KioskValidDurationJourney,
                    'parent': ParentJourney}[kind]
    journey = object.__new__(journey_type)
    journey.plan = SimpleNamespace(prefix='fixture-diagnostic')
    journey.context = SimpleNamespace(lease=SimpleNamespace(guard=Mock()))
    journey.transport = None if fault == 'unconnected' else Mock()
    if journey.transport is not None:
        journey.transport.call.side_effect = lambda command, **_: (
            b'oh-no-parent-control:x:1005:1005:Kiosk:/home/oh-no-parent-control:/usr/sbin/nologin\n'
            if command == ['getent', 'passwd', 'oh-no-parent-control'] else b'')
    if fault == 'guard':
        journey.context.lease.guard.side_effect = RuntimeError('lost owner')
    if fault == 'command':
        journey.transport.call.side_effect = RuntimeError('guest unavailable')
    if fault in ('guard', 'command'):
        with pytest.raises(RuntimeError):
            journey.collect_failure()
    else:
        journey.collect_failure()
    if fault == 'unconnected':
        journey.context.lease.guard.assert_not_called()
    elif fault == 'guard':
        journey.transport.call.assert_not_called()
    else:
        calls = journey.transport.call.call_args_list
        assert len(calls) == (1 if fault == 'command' else 5)
        assert calls[0].args[0][:5] == ['journalctl', '-b', '--no-pager', '-n', '600']
        if fault is None:
            assert calls[3].args[0] == ['getent', 'passwd', 'oh-no-parent-control']
            assert calls[4].args[0][:5] == ['journalctl', '-b', '--no-pager', '-n', '300']
            assert '_UID=1005' in calls[4].args[0]
            assert '--user-unit' not in calls[4].args[0]
        assert all(call.kwargs == {'timeout': 20} for call in calls)
        assert journey.context.lease.guard.call_count == len(calls)
    assert list(tmp_path.iterdir()) == []


def test_kiosk_failure_checkpoint_precedes_engineering_collection():
    from parent_setup_qualification import KioskEntryQualification
    controller = object.__new__(KioskEntryQualification)
    order = []
    controller.failure = Mock(side_effect=lambda *_: order.append('checkpoint'))
    journey = Mock()
    journey.collect_failure.side_effect = lambda: order.append('logs')
    controller.journey_failure(journey, 'infrastructure', 'worker-execution-failed')
    assert order == ['checkpoint', 'logs']


@pytest.mark.parametrize('scope,ready_reply', [
    ('installed-parent-setup-qualification', {'parent_setup': True}),
    ('installed-parent-input-qualification', {'parent_setup': True, 'parent_input': True}),
    ('installed-standard-input-qualification', {'parent_setup': True, 'parent_standard_input': True}),
])
@pytest.mark.parametrize('failure', [None, 'provision', 'readiness'])
def test_fedora_parent_alias_scopes_prepare_after_probe_before_installed_setup(
        tmp_path, monkeypatch, scope, ready_reply, failure):
    import parent_setup_qualification as qualification
    import system_fixture_preparation as preparation
    from tools import fixture_execution

    controller = object.__new__(qualification.ParentSetupQualification)
    controller.directory = tmp_path
    controller.commands = Mock()
    controller.ledger = Mock()
    controller.assets = tmp_path / 'assets'
    controller.credentials = SimpleNamespace(provision=Mock(return_value={}))
    controller.result = {'scope': scope}
    controller.checkpoint = Mock()
    controller.fixture_selection = fixture_execution.Selection('fedora', 'a' * 64,
        '/tmp/onpc-native-runtime-fedora-' + 'a' * 64 + '-private',
        1, 2, '/tmp/retention-private', 3, 4, 'b' * 32, 'c' * 64).record()
    lease = Mock(state={'run': 'a' * 32})
    lease.capture.state = {'guest': {'fixture_boundary': 'clean', 'os_id': 'fedora', 'version': '44'}}
    verified = SimpleNamespace(inputs={}, source_files={})
    events = []
    vm = Mock()
    vm.probe_ready.side_effect = lambda **_: events.append('ssh-ready')
    monkeypatch.setattr(qualification.smoke, 'VerifiedInputs', Mock(return_value=verified))
    bootstrap = Mock(return_value='fixture-key')
    monkeypatch.setattr(qualification.smoke.runner, 'bootstrap', bootstrap)
    monkeypatch.setattr(qualification.smoke.runner, 'address', Mock(return_value='fixture-host'))
    monkeypatch.setattr(qualification.smoke, 'Transport', Mock(return_value=vm))

    def verify(record):
        assert record == controller.fixture_selection and events == ['ssh-ready']
        events.append('verified')

    monkeypatch.setattr(preparation.fixture_execution, 'verify', verify)
    provisioner = Mock()

    def provision(record, subsets, **kwargs):
        assert record == controller.fixture_selection and subsets == ('trusted-hard',)
        assert kwargs == {'attempt_id': preparation.attempt_id(tmp_path)}
        events.append('provision')
        if failure == 'provision':
            raise ValueError('fixture-provision-failed')
        return 'current-boot'

    def ready(receipt):
        assert receipt == 'current-boot'
        events.append('ready')
        if failure == 'readiness':
            raise ValueError('fixture-readiness-failed')

    provisioner.provision.side_effect = provision
    provisioner.require_ready.side_effect = ready
    monkeypatch.setattr(preparation.fixture_provision, 'Provisioner', Mock(return_value=provisioner))
    setup = Mock()
    setup.run.side_effect = lambda _: events.append('install') or {'setup_complete': True}

    def installed(directory, actual_verified, transport):
        assert (directory, actual_verified, transport) == (tmp_path, verified, vm)
        events.append('installed-setup')
        return setup

    factory = Mock(side_effect=installed)
    monkeypatch.setattr(qualification.smoke.installed_setup, 'InstalledSetup', factory)

    def worker(*_args, **kwargs):
        for stage in ('ready', 'setup-detached'):
            (tmp_path / (stage + '.request.json')).write_text(
                json.dumps({'stage': stage, 'screenshot': None}))
            kwargs['guarded_observe'](Mock())
            if stage == 'ready':
                assert json.loads((tmp_path / 'ready.reply.json').read_text()) == ready_reply
        return {'outcome': 'passed'}

    monkeypatch.setattr(qualification.smoke.e2e_worker, 'run_distribution', worker)
    if failure:
        with pytest.raises(ValueError, match='fixture-.*-failed'):
            controller.execute(lease, Mock())
        factory.assert_not_called()
        setup.run.assert_not_called()
        assert not (tmp_path / 'setup-detached.reply.json').exists()
        assert events == ['ssh-ready', 'verified', 'provision'] + (['ready'] if failure == 'readiness' else [])
    else:
        controller.execute(lease, Mock())
        assert events == ['ssh-ready', 'verified', 'provision', 'ready', 'installed-setup', 'ready', 'install']
        assert json.loads((tmp_path / 'setup-detached.reply.json').read_text()) == {'setup_complete': True}
    assert bootstrap.call_args.kwargs == {'system_product_free': True}
    vm.copy.assert_not_called()
    vm.call.assert_not_called()


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
