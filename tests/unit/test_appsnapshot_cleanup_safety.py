"""Standalone entry points cannot bypass validation, ownership or failed setup."""
from tests.support.vm_registry import vm_name
from contextlib import nullcontext
import runpy
import time
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest
import vm_selection

import cleanup_e2e
import prepare_appsnapshot as launcher
import test_recovery
import test_retention
import test_storage
import prepare_snapshot as controller
import app_snapshot
from tests.support.paths import ROOT
from tests.support.vm_runner import UUID, xml as domain_xml

VM_ARGS = ['--vm', vm_name()]


@pytest.mark.parametrize('version', ['9.8.7', '9.8.7+ppa1~ubuntu26.04.1',
    '9.8.7-ppa1-ubuntu26.04.1', '9.8.7+ppa2~ubuntu26.04.1'])
def test_snapshot_name_uses_app_release(version):
    assert controller.snapshot_name(version) == 'onpc-v9.8.7'


def test_snapshot_name_preserves_release_components():
    assert controller.snapshot_name('9.8.7.6+ppa1~ubuntu26.04.1') == 'onpc-v9.8.7.6'


@pytest.mark.parametrize('argv, expected', [([], 'false'), (['--mode', 'offline'], 'true'),
    (['--overwrite'], 'true'),
    (['--overwrite', 'true'], 'true'), (['--overwrite', 'false'], 'false'),
    (['--overwrite=false'], 'false')])
def test_overwrite_defaults_and_explicit_values(argv, expected):
    assert launcher.arguments([*argv, *VM_ARGS]).overwrite == expected


@pytest.mark.parametrize('argv, mode', [([], 'online'), (['--mode', 'offline'], 'offline'),
                                      (['--mode', 'online'], 'online')])
def test_snapshot_mode_defaults_and_explicit_values(argv, mode):
    assert launcher.arguments([*argv, *VM_ARGS]).mode == mode


@pytest.mark.parametrize('mode, memory, state, created, expected', [
    ('online', 'internal', 'running', 100000, None),
    ('online', 'internal', 'running', 13600, None),  # Exactly 24 hours is reusable.
    ('online', 'internal', 'running', 13599, 'more than 24 hours'),
    ('online', 'internal', 'paused', 100000, 'not running'),
    ('online', 'internal', 'running', '', 'invalid'),
    ('online', 'internal', 'running', 100001, 'invalid'),
    ('online', 'no', 'shutoff', 100000, 'mode changed'),
    ('offline', 'internal', 'running', 100000, 'mode changed'),
    ('offline', 'no', 'shutoff', 1, None)])
def test_snapshot_mode_and_host_age(mode, memory, state, created, expected):
    domain = controller.system.isolated_xml(domain_xml(), UUID, 'a' * 32, graphics_type='vnc')
    xml = (f'<domainsnapshot><memory snapshot="{memory}"/><state>{state}</state>'
           f'<creationTime>{created}</creationTime>{domain}</domainsnapshot>')
    reason = app_snapshot.mode_mismatch(xml, mode, now=100000)
    assert reason is None if expected is None else expected in reason


@pytest.mark.parametrize('mode', ['online', 'offline'])
def test_host_share_snapshot_requires_refresh_only_before_memory_restore(mode):
    domain = ET.fromstring(controller.system.isolated_xml(
        domain_xml(), UUID, 'a' * 32, graphics_type='vnc'))
    share = ET.SubElement(domain.find('devices'), 'filesystem', type='mount')
    ET.SubElement(share, 'driver', type='virtiofs')
    ET.SubElement(share, 'source', dir='/host-checkout')
    ET.SubElement(share, 'target', dir='pst')
    memory, state = ('internal', 'running') if mode == 'online' else ('no', 'shutoff')
    xml = (f'<domainsnapshot><memory snapshot="{memory}"/><state>{state}</state>'
           '<creationTime>100000</creationTime>' + ET.tostring(domain, encoding='unicode') +
           '</domainsnapshot>')

    # Existing recorded owners keep their cleanup/isolation proof. A new
    # memory restore must instead replace this stale snapshot through prepare.
    controller.system.validate_host_sharing(domain)
    reason = app_snapshot.mode_mismatch(xml, mode, now=100000)
    assert reason == ('online snapshot contains host filesystem sharing' if mode == 'online' else None)


@pytest.mark.parametrize('mode', ['online', 'offline'])
def test_channel_free_snapshot_refreshes_but_remains_recoverable(mode):
    domain = ET.fromstring(controller.system.isolated_xml(
        domain_xml(), UUID, 'a' * 32, graphics_type='vnc'))
    domain.find('devices').remove(domain.find('devices/channel'))
    # The old layout is still safe for its exact recorded owner's cleanup.
    controller.system.validate_host_sharing(domain)
    memory, state = ('internal', 'running') if mode == 'online' else ('no', 'shutoff')
    xml = (f'<domainsnapshot><memory snapshot="{memory}"/><state>{state}</state>'
           '<creationTime>100000</creationTime>' + ET.tostring(domain, encoding='unicode') +
           '</domainsnapshot>')
    assert app_snapshot.mode_mismatch(xml, mode, now=100000) == 'snapshot display-agent channel missing'


@pytest.mark.parametrize('mode', ['online', 'offline'])
def test_clipboard_opt_in_refreshes_disabled_snapshot_and_reuses_enabled(mode, monkeypatch):
    domain = controller.system.isolated_xml(domain_xml(), UUID, 'a' * 32, graphics_type='vnc')
    memory, state = ('internal', 'running') if mode == 'online' else ('no', 'shutoff')
    xml = (f'<domainsnapshot><memory snapshot="{memory}"/><state>{state}</state>'
           '<creationTime>100000</creationTime>' + domain + '</domainsnapshot>')
    config = controller.system.baseline.guest_contract.vm_config
    selected = config.selected()
    from dataclasses import replace
    monkeypatch.setattr(config, 'selected', lambda **_: replace(selected, clipboard=True))
    assert app_snapshot.mode_mismatch(xml, mode, now=100000) == 'snapshot clipboard configuration changed'
    assert app_snapshot.mode_mismatch(xml.replace('copypaste="no"', 'copypaste="yes"'),
                                     mode, now=100000) is None


@pytest.mark.parametrize('argv', [['--overwrite', 'yes'], ['--overwrite='],
    ['--overwrite', 'FALSE'], ['--over', 'false'], ['--snapshot', 'onpc-9.8.7'],
    ['--mode', 'running'], ['--mod', 'online']])
def test_invalid_options_refused_before_any_work(argv, monkeypatch):
    check = Mock(side_effect=AssertionError('authorization attempted'))
    monkeypatch.setattr(launcher, 'check', check)
    with pytest.raises(SystemExit) as error:
        launcher.main([*argv, *VM_ARGS])
    assert error.value.code == 2
    check.assert_not_called()


@pytest.fixture
def launch(tmp_path, monkeypatch):
    import test_storage
    monkeypatch.setattr(test_storage, 'scratch_directory', lambda: tmp_path)
    monkeypatch.setattr(launcher, '__file__', str(tmp_path / 'tools/prepare_appsnapshot.py'))
    monkeypatch.setattr(launcher.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(launcher.test_activity, 'activity', lambda _, **kw: nullcontext())
    monkeypatch.setattr(launcher, 'check', Mock())
    cleanup = Mock(return_value=0)
    monkeypatch.setattr(launcher, 'cleanup', cleanup)
    controller = Mock()
    controller.installed.return_value = nullcontext(controller)
    controller.stopped.is_set.return_value = False
    monkeypatch.setattr(launcher, 'Control', lambda: controller)
    allocation = Mock(return_value=str(tmp_path / 'artifacts'))
    monkeypatch.setattr(launcher.tempfile, 'mkdtemp', allocation)
    store = Mock()
    store.session.return_value = nullcontext('a' * 32)
    monkeypatch.setattr(launcher.test_retention, 'Store', lambda _: store)
    monkeypatch.setattr(launcher.test_retention, 'allocate', lambda factory, **kw: factory(**kw))
    return controller, cleanup, allocation


def test_assume_yes_without_vm_uses_enabled_selection(launch, monkeypatch, capsys):
    control, cleanup, allocation = launch
    configured = vm_selection.vm_config.execution()[1][0]
    # This single-dispatch test must stay inside its mocked controller even
    # when the development registry enables several VMs. Queue scope is below.
    monkeypatch.setattr(vm_selection.vm_config, 'execution', lambda name=None: (1, (configured,)))
    chooser = Mock(side_effect=AssertionError('VM prompt attempted'))
    monkeypatch.setattr(vm_selection, 'choose_vm', chooser)
    control.run.return_value = 0
    assert launcher.main(['--y']) == 0
    configured, = vm_selection.vm_config.execution()[1]
    assert control.run.call_args.args[0][-2:] == ['--vm', configured.name]
    chooser.assert_not_called()
    cleanup.assert_not_called()
    allocation.assert_not_called()


@pytest.mark.parametrize('selector', [None, 'all', 'all-enabled', '17,83', 'Alpha-guest,Beta-guest'])
def test_appsnapshot_queue_uses_shared_selection_and_scheduler(launch, monkeypatch, selector):
    from types import SimpleNamespace
    vms = tuple(SimpleNamespace(name=name) for name in ('Alpha-guest', 'Beta-guest'))
    selection = Mock(return_value=(2, vms))
    monkeypatch.setattr(vm_selection.vm_config, 'execution', selection)
    prepare = Mock(return_value=({'Alpha-guest': 0, 'Beta-guest': 7}, 7))
    monkeypatch.setattr(launcher, 'preparation', prepare)
    assert launcher.main(['--y', *([] if selector is None else ['--vm', selector])]) == 7
    selection.assert_called_once_with(selector)
    assert prepare.call_args.args[3:] == (2, vms)
    launch[0].run.assert_not_called()


@pytest.mark.parametrize('mode', ['online', 'offline'])
def test_assume_yes_with_vm_never_prompts(launch, monkeypatch, mode, capsys):
    control, cleanup, allocation = launch
    control.run.return_value = 0
    monkeypatch.setattr(vm_selection, 'choose_vm', Mock(side_effect=AssertionError('VM prompt attempted')))
    monkeypatch.setattr(launcher, 'input', Mock(side_effect=AssertionError('confirmation attempted')),
                        raising=False)
    assert launcher.main([*VM_ARGS, '--y', '--mode', mode, '--overwrite', 'false']) == 0
    control.run.assert_called_once()
    assert capsys.readouterr().out == ''


def test_assume_yes_resolves_vm_id_before_dispatch(launch, monkeypatch):
    control, cleanup, allocation = launch
    control.run.return_value = 0
    configured = list(vm_selection.registry().values())[1]
    monkeypatch.setattr(launcher, 'input', Mock(side_effect=AssertionError('confirmation attempted')),
                        raising=False)
    assert launcher.main(['--vm', configured.id, '--y']) == 0
    assert control.run.call_args.args[0][-2:] == ['--vm', configured.name]


@pytest.mark.parametrize('answer', ['n', EOFError, KeyboardInterrupt])
def test_manual_decline_or_cancel_never_starts_work(launch, monkeypatch, capsys, answer):
    control, cleanup, allocation = launch
    prompt = Mock(return_value=answer) if isinstance(answer, str) else Mock(side_effect=answer)
    monkeypatch.setattr(launcher, 'input', prompt, raising=False)
    activity = Mock(side_effect=AssertionError('activity attempted'))
    monkeypatch.setattr(launcher.test_activity, 'activity', activity)
    assert launcher.main(VM_ARGS) == 0
    prompt.assert_called_once_with('Proceed (y/n)? ')
    assert 'cancelled; no app snapshot was prepared' in capsys.readouterr().out
    activity.assert_not_called()
    launcher.check.assert_not_called()
    control.run.assert_not_called()
    cleanup.assert_not_called()
    allocation.assert_not_called()


def test_manual_missing_vm_confirms_enabled_selection(launch, monkeypatch, capsys):
    control, cleanup, allocation = launch
    control.run.return_value = 0
    configured = vm_selection.vm_config.execution()[1][0]
    monkeypatch.setattr(vm_selection.vm_config, 'execution', lambda name=None: (1, (configured,)))
    answers = iter(['invalid', ' Y '])
    def confirm(prompt):
        assert prompt == 'Proceed (y/n)? '
        launcher.check.assert_not_called()
        return next(answers)
    monkeypatch.setattr(launcher, 'input', confirm, raising=False)
    assert launcher.main([]) == 0
    control.run.assert_called_once()
    assert control.run.call_args.args[0][-2:] == ['--vm', configured.name]
    output = capsys.readouterr().out
    assert f'on {configured.name}' in output
    assert 'Please enter y to proceed or n to exit.' in output


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
def test_cancelled_default_confirmation_never_dispatches(launch, monkeypatch, capsys, exception):
    control, cleanup, allocation = launch
    prompt = Mock(side_effect=exception)
    monkeypatch.setattr(launcher, 'input', prompt, raising=False)
    assert launcher.main([]) == 0
    assert 'cancelled' in capsys.readouterr().out
    prompt.assert_called_once()
    launcher.check.assert_not_called()
    control.run.assert_not_called()
    cleanup.assert_not_called()
    allocation.assert_not_called()


@pytest.mark.parametrize('status', [0, 1, 2, 130])
def test_reuse_or_probe_failure_never_builds_or_cleans(launch, status):
    control, cleanup, allocation = launch
    control.run.return_value = status
    assert launcher.main(['--overwrite', 'false', *VM_ARGS, '--y']) == status
    assert control.run.call_args.args[0] == [
        '/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
        '/usr/local/libexec/onpc-test-runner', 'appsnapshot', '--probe', '--mode', 'online',
        '--overwrite', 'false', *VM_ARGS]
    control.run.assert_called_once()
    cleanup.assert_not_called()
    allocation.assert_not_called()


def test_fresh_online_snapshot_resumes_without_cleanup_or_build(launch):
    control, cleanup, allocation = launch
    control.run.side_effect = [4, 0]
    assert launcher.main(['--mode', 'online', *VM_ARGS, '--y']) == 0
    assert control.run.call_args.args[0][-7:] == [
        '/usr/local/libexec/onpc-test-runner',
        'appsnapshot', '--resume', '--mode', 'online', *VM_ARGS]
    cleanup.assert_not_called()
    allocation.assert_not_called()


@pytest.mark.parametrize('recovered_status', [0, 4, 1])
def test_unfinished_attempt_recovers_before_reprobe_without_forcing_build(launch, recovered_status):
    control, cleanup, allocation = launch
    control.run.side_effect = [6, recovered_status, 0]
    assert launcher.main([*VM_ARGS, '--y']) == (1 if recovered_status == 1 else 0)
    cleanup.assert_called_once()
    assert control.run.call_args_list[0].args == control.run.call_args_list[1].args
    allocation.assert_not_called()


def test_unfinished_attempt_recovery_failure_prevents_reprobe_and_build(launch):
    control, cleanup, allocation = launch
    control.run.return_value = 6
    cleanup.side_effect = ValueError('retention: automatic recovery failed')
    assert launcher.main([*VM_ARGS, '--y']) == 2
    control.run.assert_called_once()
    allocation.assert_not_called()


def test_online_credentials_are_private_and_bound_to_exact_snapshot(tmp_path, monkeypatch):
    import online_snapshot
    monkeypatch.setattr(online_snapshot.test_storage, 'directory', lambda _: tmp_path)
    source = Mock(uuid='f95890e1-88e7-4779-8ae3-53fdcc34330a')
    lease = Mock(source=source, installed_name='onpc-v9.8.7', installed_xml='<snapshot/>',
                 state={'run': 'a' * 32})
    setup = tmp_path / 'setup'
    setup.mkdir()
    (setup / 'ssh-key').write_text('private fixture key')
    (setup / 'ssh-key.pub').write_text('ssh-ed25519 AAAA fixture\n')
    assert online_snapshot.load(source, 'onpc-v9.8.7', '<snapshot/>') is None
    online_snapshot.publish(lease, setup, 'ssh-ed25519 AAAA')
    record = online_snapshot.load(source, 'onpc-v9.8.7', '<snapshot/>')
    assert record['private_key'] == 'private fixture key'
    assert online_snapshot.load(source, 'onpc-v9.8.8', '<snapshot/>') is None
    assert online_snapshot.load(source, 'onpc-v9.8.7', '<snapshot/> ') is None
    path = online_snapshot.record_store(source).path / 'snapshot.json'
    assert path.stat().st_mode & 0o777 == 0o600
    path.chmod(0o644)
    with pytest.raises(ValueError):
        online_snapshot.load(source, 'onpc-v9.8.7', '<snapshot/>')
    path.chmod(0o600)
    path.rename(path.with_suffix('.saved'))
    path.symlink_to(path.with_suffix('.saved'))
    with pytest.raises(OSError):
        online_snapshot.load(source, 'onpc-v9.8.7', '<snapshot/>')


@pytest.mark.parametrize('clock, delay, accepted', [
    (b'1000\n', 0, True), (b'900\n', 0, False), (b'invalid\n', 0, False),
    (b'1000\n', 100, False), (b'1100\n', 100, True)])
def test_saved_transport_verifies_clock_after_resuming(tmp_path, monkeypatch, clock, delay, accepted):
    import online_snapshot
    import vm_transport
    transport = Mock()
    transport.call.side_effect = [b'', clock]
    factory = Mock(return_value=transport)
    monkeypatch.setattr(vm_transport, 'Transport', factory)
    times = iter((1000, 1000 + delay, 1000 + delay))
    monkeypatch.setattr(online_snapshot.time, 'time', lambda: next(times))
    lease = Mock()
    lease.capture.state = {'guest': {'ubuntu_version': '26.04'}}
    import chinese_language_assets
    readiness = Mock()
    monkeypatch.setattr(chinese_language_assets, 'verify_transport', readiness)
    record = {'run': 'a' * 32, 'private_key': 'private-fixture-key',
              'host_key': 'ssh-ed25519 fixture'}
    if not accepted:
        with pytest.raises(RuntimeError, match='clock-not-corrected'):
            online_snapshot.saved_transport(lease, tmp_path, record, 'fixture-host')
    else:
        assert online_snapshot.saved_transport(lease, tmp_path, record, 'fixture-host') is transport
    transport.probe_ready.assert_called_once()
    assert readiness.call_count == int(accepted)
    assert transport.call.call_args_list[0].args[0] == ['date', '--set', '@1000']
    assert (tmp_path / 'snapshot-transport/ssh-key').stat().st_mode & 0o777 == 0o600


def test_connecting_for_a_probe_does_not_restore_or_change_guest_time(tmp_path, monkeypatch):
    import online_snapshot
    import vm_transport
    transport = Mock()
    factory = Mock(return_value=transport)
    monkeypatch.setattr(vm_transport, 'Transport', factory)
    lease = Mock()
    record = {'run': 'a' * 32, 'private_key': 'private-fixture-key',
              'host_key': 'ssh-ed25519 fixture'}
    assert online_snapshot.connect_saved_transport(lease, tmp_path, record, '192.168.122.20') is transport
    transport.probe_ready.assert_called_once()
    transport.call.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()
    assert factory.call_args.args[0]['run'] == record['run']
    assert (tmp_path / 'snapshot-transport/ssh-key').stat().st_mode & 0o777 == 0o600
    assert (tmp_path / 'snapshot-transport/known-hosts').read_text() == '192.168.122.20 ssh-ed25519 fixture\n'


def test_online_bootstrap_never_mounts_or_writes_offline_guest(tmp_path, monkeypatch):
    import online_snapshot
    lease = Mock(online_pending=True)
    staged = Mock(return_value='ssh-ed25519 fixture')
    monkeypatch.setattr(online_snapshot, 'stage', staged)
    guestfs = Mock()
    commands = Mock()
    assert controller.system.bootstrap(commands, lease, tmp_path, guestfs) == 'ssh-ed25519 fixture'
    staged.assert_called_once_with(commands, lease, tmp_path)
    guestfs.GuestFS.assert_not_called()


@pytest.mark.parametrize('fault', [None, 'interrupt', 'replaced', 'down-not-applied',
                                 'up-not-applied'])
def test_online_network_reconnect_is_live_guarded_and_restores_carrier(monkeypatch, fault):
    import online_snapshot
    lease = Mock()
    domain = lease.source.domain
    lease.source.api.VIR_DOMAIN_AFFECT_LIVE = 1
    current = ET.fromstring('''<domain><devices><interface type="network">
        <mac address="52:54:00:11:22:33"/><source network="default"/>
        <model type="virtio"/><target dev="vnet7"/>
        </interface></devices></domain>''')
    domain.XMLDesc.side_effect = lambda _: ET.tostring(current, encoding='unicode')
    changes = []
    events = []

    def update(xml, flags):
        assert flags == 1
        interface = ET.fromstring(xml)
        assert interface.find('mac').get('address') == '52:54:00:11:22:33'
        assert interface.find('source').get('network') == 'default'
        state = interface.find('link').get('state')
        changes.append(state)
        events.append(state)
        if fault == state + '-not-applied':
            return
        devices = current.find('devices')
        devices.remove(devices.find('interface'))
        devices.append(interface)

    def wait(seconds):
        assert seconds > 6
        events.append('carrier-loss-grace')
        if fault == 'interrupt':
            raise KeyboardInterrupt()
        if fault == 'replaced':
            lease.guard.side_effect = RuntimeError('guard:domain-replaced')

    domain.updateDeviceFlags.side_effect = update
    monkeypatch.setattr(online_snapshot.time, 'sleep', wait)
    if fault:
        with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else RuntimeError):
            online_snapshot.reconnect_network(lease)
    else:
        online_snapshot.reconnect_network(lease)
        assert events == ['down', 'carrier-loss-grace', 'up']
    assert changes == (['down'] if fault == 'replaced' else ['down', 'up'])
    assert lease.guard.call_count >= 4
    lease.source.connection.defineXML.assert_not_called()
    domain.destroy.assert_not_called()
    domain.create.assert_not_called()


@pytest.mark.parametrize('interface', [
    '', '<interface type="bridge"/>', '<interface type="network"/>',
    '<interface type="network"><mac address="invalid"/><source network="default"/></interface>',
    '<interface type="network"><mac address="52:54:00:11:22:33"/><source network="default"/>'
    '<link state="invalid"/></interface>',
    '<interface type="network"/><interface type="network"/>'])
def test_online_network_invalid_layout_refuses_before_mutation(interface):
    import online_snapshot
    lease = Mock()
    lease.source.domain.XMLDesc.return_value = '<domain><devices>' + interface + '</devices></domain>'
    with pytest.raises(RuntimeError, match='network-layout'):
        online_snapshot.reconnect_network(lease)
    lease.source.domain.updateDeviceFlags.assert_not_called()


def test_memory_restore_reconnects_before_waiting_for_host_dhcp(monkeypatch):
    import json
    import online_snapshot
    import vm_control
    import e2e_watch
    lease = Mock()
    lease.state = {'run': 'a' * 32, 'baseline_sha256': 'b' * 64}
    lease.capture.state = {'source': {'layout': {}}}
    lease.source.uuid = 'fixture-uuid'
    lease.source.api.VIR_DOMAIN_AFFECT_LIVE = 1
    lease.source.api.VIR_DOMAIN_AFFECT_CONFIG = 2
    lease.installed_xml = ('<domainsnapshot><description>' +
        json.dumps({'baseline_sha256': 'b' * 64}) + '</description><domain>'
        '<uuid>fixture-uuid</uuid><description>onpc-system-run:' + 'c' * 32 +
        '</description></domain></domainsnapshot>')
    lease.source.domain.snapshotLookupByName.return_value.getXMLDesc.return_value = lease.installed_xml
    lease.source.connection.lookupByUUIDString.return_value = lease.source.domain
    lease.source.domain.ID.return_value = 71
    lease.snapshot_status.return_value = nullcontext()
    monkeypatch.setattr(app_snapshot, 'mode_mismatch', lambda *a: None)
    monkeypatch.setattr(controller.system.baseline, 'domain_layout', lambda *a: {})
    monkeypatch.setattr(controller.system, 'validate_private_vnc', Mock())
    monkeypatch.setattr(vm_control, 'check_identity', Mock())
    events = []
    lease.source.domain.revertToSnapshot.side_effect = lambda *a: events.append('memory')
    monkeypatch.setattr(e2e_watch, 'attach', lambda _: events.append('watch'))
    monkeypatch.setattr(online_snapshot, 'reconnect_network', lambda _: events.append('reconnect'))

    def address(source):
        assert source is lease.source
        assert events == ['memory', 'watch', 'reconnect']
        return '192.168.122.10'

    monkeypatch.setattr(controller.system, 'address', address)
    assert online_snapshot.restore(lease, {'run': 'c' * 32}) == '192.168.122.10'


def test_disconnected_snapshot_restores_without_carrier_grace(monkeypatch):
    import online_snapshot
    update = Mock()
    monkeypatch.setattr(online_snapshot, 'network_link', lambda _: ('down', update))
    wait = Mock(side_effect=AssertionError('restore must not repeat preparation wait'))
    monkeypatch.setattr(online_snapshot.time, 'sleep', wait)
    online_snapshot.reconnect_network(Mock())
    update.assert_called_once_with('up')
    wait.assert_not_called()


@pytest.mark.parametrize('failure', [False, True])
def test_network_disconnected_through_snapshot_and_restored_on_capture_failure(monkeypatch, failure):
    import online_snapshot
    events = []
    monkeypatch.setattr(online_snapshot, 'network_link', lambda _: ('up', events.append))
    monkeypatch.setattr(online_snapshot.time, 'sleep', lambda seconds: events.append(seconds))
    with pytest.raises(RuntimeError) if failure else nullcontext():
        with online_snapshot.disconnected_network(Mock()):
            assert events == ['down', 10]
            events.append('capture-memory')
            if failure:
                raise RuntimeError('snapshot-failed')
    assert events == ['down', 10, 'capture-memory', 'up']


@pytest.mark.parametrize('running', [False, True])
@pytest.mark.parametrize('transport_failure', [False, True])
def test_resume_keeps_persistent_isolation_until_maintenance_stop(
        tmp_path, monkeypatch, running, transport_failure):
    import online_snapshot
    import vm_control
    from tools import test_retention
    source = Mock()
    source.domain.ID.return_value = 71 if running else -1
    lease = Mock()
    lease.__enter__ = Mock()
    lease.state = {'run': 'b' * 32}
    lease.capture.state = {'source': {'layout': {}}, 'proof': {}}
    lease.capture.verify_snapshot.return_value = {}
    monkeypatch.setattr(test_retention, 'allocate', lambda *a, **kw: str(tmp_path))
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    monkeypatch.setattr(controller.system, 'Lease', Mock(return_value=lease))
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-v9.8.7')
    monkeypatch.setattr(controller, 'mode_mismatch', lambda *a: None)
    monkeypatch.setattr(vm_control, 'save_owner', Mock())
    monkeypatch.setattr(vm_control, 'resume', Mock())
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value={'run': 'a' * 32}))
    def restore_running(held, record, *, maintenance):
        assert held.watch_detached is True
        assert maintenance is True
        held.state['phase'] = 'running'
        return 'fixture-host'
    restore = Mock(side_effect=restore_running)
    monkeypatch.setattr(online_snapshot, 'restore', restore)
    monkeypatch.setattr(online_snapshot, 'saved_transport', Mock(
        side_effect=RuntimeError('clock-not-ready') if transport_failure else None))
    if transport_failure:
        with pytest.raises(RuntimeError, match='clock-not-ready'):
            controller.resume('pinned-fixture')
        lease.finish.assert_called_once()
        assert lease.watch_detached is False
    else:
        assert controller.resume('pinned-fixture') == 0
        lease.finish.assert_not_called()
        assert lease.watch_detached is True
    restore.assert_called_once()
    source.connection.defineXML.assert_not_called()
    lease.release.assert_called_once()
    if running:
        vm_control.resume.assert_called_once_with(lease)


@pytest.mark.parametrize('phase,running,owned,status', [
    ('cleanup-requested', False, False, 6), ('running', False, True, 6),
    ('running', True, False, 6), ('start-requested', True, True, 6),
    ('running', True, True, 4), ('complete', False, False, 4)])
def test_probe_routes_unfinished_attempts_to_recovery_and_keeps_healthy_online_reuse(
        tmp_path, monkeypatch, phase, running, owned, status):
    import online_snapshot
    import json
    base = controller.system.baseline
    lock = tmp_path / 'baseline.lock'
    lock.touch(mode=0o600)
    monkeypatch.setattr(base, 'BASELINES', tmp_path)
    monkeypatch.setattr(base, 'identity', Mock())
    monkeypatch.setattr(base, 'baseline_lock_path', lambda _: lock)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-v9.8.7')
    monkeypatch.setattr(controller, 'preparation_format', lambda *_: 'deb')
    source = Mock()
    source.domain.ID.return_value = 17 if running else -1
    source.domain.snapshotListNames.return_value = ['onpc-v9.8.7']
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    monkeypatch.setattr(controller, 'mode_mismatch', lambda *_: None)
    monkeypatch.setattr(online_snapshot, 'load', lambda *_: {'run': 'a' * 32})
    journal = tmp_path / 'system-run.json'
    raw = json.dumps({'phase': phase, 'run': 'a' * 32}).encode()
    journal.write_bytes(raw)
    (tmp_path / 'vm-control.json').write_text(json.dumps({'run': ('a' if owned else 'b') * 32}))
    assert controller.probe('pinned') == status
    assert journal.read_bytes() == raw
    source.domain.create.assert_not_called()
    source.domain.revertToSnapshot.assert_not_called()


def test_baseline_preparation_cpu_is_migratable_and_preserves_other_settings():
    import baseline_guest
    import xml.etree.ElementTree as ET
    original = ('<domain><cpu mode="host-passthrough" migratable="off">'
        '<topology cores="3"/><feature name="invtsc" policy="require"/>'
        '<feature name="aes" policy="require"/></cpu></domain>')
    root = ET.fromstring(original)
    baseline_guest.configure_cpu(root)
    baseline_guest.configure_cpu(root)
    cpu = root.find('cpu')
    assert cpu.get('migratable') == 'on'
    assert cpu.find("feature[@name='invtsc']").get('policy') == 'disable'
    assert cpu.find("feature[@name='aes']").get('policy') == 'require'
    assert cpu.find('topology').get('cores') == '3'
    assert len(cpu.findall("feature[@name='invtsc']")) == 1


def test_online_guest_rebind_replaces_marker_and_key_and_retires_payload(tmp_path, monkeypatch):
    import io
    import json
    import os
    from pathlib import Path
    import sys
    import online_snapshot
    marker = tmp_path / 'marker'
    marker.write_text(json.dumps(dict(run='a' * 32, baseline_sha256='baseline',
        preparation_sha256='preparation', machine_id='guest', host_machine_id='host',
        domain_uuid='domain', package_sha256='old', selected_inputs_sha256='old')))
    marker.chmod(0o600)
    ssh = tmp_path / 'ssh'
    ssh.mkdir(mode=0o700)
    authorized = ssh / 'authorized_keys'
    authorized.write_text('ssh-ed25519 AAAA old\nssh-ed25519 BBBB unrelated\n')
    authorized.chmod(0o600)
    payload = tmp_path / 'onpc-system-input'
    payload.mkdir(mode=0o700)
    (payload / 'obsolete.py').write_text('old fixture')
    data = dict(run='b' * 32, baseline_sha256='baseline', preparation_sha256='preparation',
        selected_inputs_sha256='new-inputs', package_sha256='new-package',
        public_key='ssh-ed25519 CCCC new\n', old_public_key='ssh-ed25519 AAAA old\n')
    program = online_snapshot.REBIND.replace('/etc/onpc-system-test.json', str(marker)).replace(
        '/root/.ssh', str(ssh)).replace('/var/tmp', str(tmp_path))
    native_stat = Path.stat
    native_lstat = Path.lstat
    # Model guest root ownership on caller-private test files; no root or VM.
    def guest_stat(method):
        def inspect(path, *args, **kwargs):
            result = method(path, *args, **kwargs)
            if path.is_relative_to(tmp_path):
                values = list(result)
                values[4:6] = [0, 0]
                return os.stat_result(values)
            return result
        return inspect
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'stat', guest_stat(native_stat))
        patch.setattr(Path, 'lstat', guest_stat(native_lstat))
        patch.setattr(sys, 'stdin', io.StringIO(json.dumps(data)))
        exec(compile(program, '<guest-rebind>', 'exec'), {})
    assert authorized.read_text() == 'ssh-ed25519 BBBB unrelated\nssh-ed25519 CCCC new\n'
    updated = json.loads(marker.read_text())
    assert updated['run'] == 'b' * 32 and updated['selected_inputs_sha256'] == 'new-inputs'
    assert updated['machine_id'] == 'guest' and updated['domain_uuid'] == 'domain'
    assert not payload.exists()
    retired = list(tmp_path.glob('onpc-system-input-snapshot-*'))
    assert len(retired) == 1 and (retired[0] / 'obsolete.py').read_text() == 'old fixture'


@pytest.mark.parametrize('argv, results, calls', [([], [3, 0, 0, 0], 4),
    (['--overwrite'], [3, 0, 0, 0], 4), (['--overwrite', 'true'], [3, 0, 0, 0], 4),
    (['--overwrite', 'false'], [3, 0, 0, 0], 4)])
def test_needed_preparation_cleans_builds_and_passes_overwrite(launch, argv, results, calls):
    control, cleanup, allocation = launch
    control.run.side_effect = results
    assert launcher.main([*argv, *VM_ARGS, '--y']) == 0
    cleanup.assert_called_once()
    allocation.assert_called_once()
    assert control.run.call_count == calls
    build = control.run.call_args_list[-3].args[0]
    assert build == ['/usr/bin/python3', '-B',
                     str(control.run.call_args_list[-3].kwargs['cwd'] /
                         'tools/build_test_artifacts.py'),
                     '--output', allocation.return_value, '--package-format', 'deb']
    command = control.run.call_args_list[-2].args[0]
    assert command[1] == '--disable-internal-agent'
    assert '--retention-run=' + 'a' * 32 in command
    assert command[2] == '--keep-cwd'
    assert command[5:8] == ['--unattended', 'appsnapshot', '--overwrite']
    assert command[8] == 'true'
    assert command[9:] == ['--artifacts', allocation.return_value, '--mode', 'online', *VM_ARGS]
    assert control.run.call_args_list[-2].kwargs['cooperative'] is True
    assert control.run.call_args.args[0][-6:] == ['appsnapshot', '--resume', '--mode', 'online', *VM_ARGS]


def test_failed_cleanup_does_not_build_or_install(launch):
    control, cleanup, allocation = launch
    cleanup.side_effect = ValueError('cleanup refused')
    assert launcher.main(['--overwrite', *VM_ARGS, '--y']) == 2
    allocation.assert_not_called()
    control.run.assert_not_called()


@pytest.mark.parametrize('argv', [['--mode', 'offline'], ['--overwrite'], ['--overwrite', 'true']])
def test_failed_build_does_not_install(launch, argv):
    control, cleanup, allocation = launch
    control.run.side_effect = [3, 17]
    assert launcher.main([*argv, *VM_ARGS, '--y']) == 17
    assert control.run.call_count == 2
    assert control.run.call_args.args[0][2].endswith('/tools/build_test_artifacts.py')


def test_missing_snapshot_failed_build_does_not_install(launch):
    control, cleanup, allocation = launch
    control.run.side_effect = [3, 17]
    assert launcher.main(['--overwrite', 'false', *VM_ARGS, '--y']) == 17
    cleanup.assert_called_once()
    assert control.run.call_count == 2
    assert control.run.call_args.args[0][2].endswith('/tools/build_test_artifacts.py')


def test_cleanup_requires_checkout_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(test_recovery.test_activity, 'descriptors', lambda: ())
    with pytest.raises(ValueError, match='ownership required'):
        test_recovery.cleanup(tmp_path)


def test_standalone_cleanup_uses_the_shared_module_under_activity(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup_e2e, '__file__', str(tmp_path / 'tools/cleanup_e2e.py'))
    monkeypatch.setattr(cleanup_e2e.os, 'geteuid', lambda: 1000)
    def cleanup(root):
        assert root == tmp_path
        assert cleanup_e2e.test_activity.descriptors()
        return 7
    monkeypatch.setattr(cleanup_e2e, 'cleanup', cleanup)
    assert cleanup_e2e.main(VM_ARGS) == 7


@pytest.mark.parametrize('status', [0, 7])
def test_standalone_cleanup_reconciles_both_retention_scopes(tmp_path, monkeypatch, status):
    monkeypatch.setattr(cleanup_e2e, '__file__', str(tmp_path / 'tools/cleanup_e2e.py'))
    monkeypatch.setattr(cleanup_e2e.os, 'geteuid', lambda: 1000)
    retention = test_retention
    store = retention.Store(test_storage.directory('state', root=tmp_path) / 'retention-host')
    with store.session() as run:
        retention.preserve_for_recovery()
    paths = []
    def cleanup(root):
        assert cleanup_e2e.test_activity.descriptors()
        paths.append(cleanup_e2e.test_activity.retention_path(root))
        assert paths == [tmp_path / f'output/test-runs/host/state/retention-{vm_name()}']
        return status
    monkeypatch.setattr(cleanup_e2e, 'cleanup', cleanup)
    assert cleanup_e2e.main(VM_ARGS) == status
    assert paths == [tmp_path / f'output/test-runs/host/state/retention-{vm_name()}']
    assert (store.path / 'recovery-required').exists() == bool(status)
    assert (store.path / f'recovered-{run}.json').exists() == (status == 0)
    if not status:
        with store.session():
            pass


def test_host_cleanup_needs_no_vm_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup_e2e, '__file__', str(tmp_path / 'tools/cleanup_e2e.py'))
    monkeypatch.setattr(cleanup_e2e.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(cleanup_e2e.vm_config, 'execution',
                        lambda *_: pytest.fail('host cleanup accessed VM configuration'))
    monkeypatch.setattr(cleanup_e2e.vm_config, 'load',
                        lambda *_: pytest.fail('host cleanup loaded a selected VM'))
    monkeypatch.setattr(cleanup_e2e, 'cleanup',
                        lambda *_: pytest.fail('host cleanup accessed VM recovery'))
    store = test_retention.Store(test_storage.directory('state', root=tmp_path) / 'retention-host')
    with store.session() as run:
        test_retention.preserve_for_recovery()
    assert cleanup_e2e.main(['--host-only']) == 0
    assert (store.path / f'recovered-{run}.json').exists()
    assert not (store.path / 'recovery-required').exists()


def test_host_cleanup_refuses_a_vm_selector():
    with pytest.raises(SystemExit) as error:
        cleanup_e2e.main(['--host-only', *VM_ARGS])
    assert error.value.code == 2


@pytest.fixture
def dispatch():
    module = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))
    select = module['selection']
    select.__globals__['VM_UUIDS'] = {vm_name(): 'pinned-test-uuid'}
    return select


def test_snapshot_dispatch_pins_vm_and_confines_inputs(dispatch, tmp_path):
    assert dispatch(ROOT, ['appsnapshot', '--probe', '--overwrite', 'false', *VM_ARGS])[-7:] == [
        '--expected-uuid', 'pinned-test-uuid', *VM_ARGS, '--probe', '--overwrite', 'false']
    with pytest.raises(ValueError):
        dispatch(ROOT, ['appsnapshot', '--artifacts', '/etc'])
    with pytest.raises(ValueError):
        dispatch(ROOT, ['appsnapshot', '--probe', '--artifacts', str(tmp_path)])
    with pytest.raises(ValueError):
        dispatch(ROOT, ['appsnapshot', '--expected-uuid', 'other'])
    dispatch.__globals__['VM_UUIDS'] = {}
    with pytest.raises(ValueError, match='prepare-baseline'):
        dispatch(ROOT, ['appsnapshot', '--probe', *VM_ARGS])


@pytest.mark.parametrize('exists', [False, True])
@pytest.mark.parametrize('mode, memory, age, status', [
    ('offline', 'no', 0, 0), ('online', 'internal', 0, 4),
    ('online', 'internal', 86401, 3), ('online', 'no', 0, 3),
    ('offline', 'internal', 0, 3)])
def test_probe_uses_exclusive_vm_lock_and_never_mutates(
        tmp_path, monkeypatch, exists, mode, memory, age, status):
    import online_snapshot
    import fcntl
    import os
    base = controller.system.baseline
    lock = tmp_path / 'baseline.lock'
    lock.touch(mode=0o600)
    monkeypatch.setattr(base, 'BASELINES', tmp_path)
    monkeypatch.setattr(base, 'canonical', Mock())
    monkeypatch.setattr(base, 'identity', Mock())
    monkeypatch.setattr(base, 'baseline_lock_path', lambda _: lock)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-9.8.7')
    monkeypatch.setattr(controller, 'preparation_format', lambda *_: 'deb')
    source = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    def names(flags):
        other = os.open(lock, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(other)
        return ['onpc-9.8.7'] if exists else ['onpc-0.9']
    source.domain.snapshotListNames.side_effect = names
    domain = controller.system.isolated_xml(domain_xml(), UUID, 'a' * 32, graphics_type='vnc')
    source.domain.snapshotLookupByName.return_value.getXMLDesc.return_value = (
        f'<domainsnapshot><memory snapshot="{memory}"/><state>running</state>'
        f'<creationTime>{int(time.time()) - age}</creationTime>{domain}</domainsnapshot>')
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value={'bound': True}))
    assert controller.probe('pinned', mode=mode) == (status if exists else 3)
    source.domain.snapshotListNames.assert_called_once_with(0)
    assert len(source.domain.mock_calls) == (3 if exists else 1)
    source.close.assert_called_once()
    assert list(tmp_path.iterdir()) == [lock]
    with lock.open() as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_probe_rejects_foreign_vm_before_reading_snapshots(tmp_path, monkeypatch):
    base = controller.system.baseline
    lock = tmp_path / 'baseline.lock'
    lock.touch(mode=0o600)
    monkeypatch.setattr(base, 'BASELINES', tmp_path)
    monkeypatch.setattr(base, 'canonical', Mock())
    monkeypatch.setattr(base, 'identity', Mock())
    monkeypatch.setattr(base, 'baseline_lock_path', lambda _: lock)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-9.8.7')
    source = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock(side_effect=ValueError('foreign VM')))
    with pytest.raises(ValueError, match='foreign VM'):
        controller.probe('pinned')
    source.domain.snapshotListNames.assert_not_called()
    source.close.assert_called_once()


@pytest.mark.parametrize('overwrite', ['true', 'false'])
def test_fedora_preparation_selects_rpm_builder_from_probe(launch, overwrite):
    control, cleanup, allocation = launch
    control.run.side_effect = [5, 0, 0, 0]
    assert launcher.main([*VM_ARGS, '--y', '--overwrite', overwrite]) == 0
    assert control.run.call_args_list[0].args[0][-4:] == ['--overwrite', overwrite, *VM_ARGS]
    assert control.run.call_args_list[1].args[0][-2:] == ['--package-format', 'rpm']
    cleanup.assert_called_once()
    allocation.assert_called_once()


@pytest.mark.parametrize('format,expected', [('deb', 3), ('rpm', 5)])
def test_forced_probe_selects_backend_without_snapshot_mutation(tmp_path, monkeypatch, format, expected):
    base = controller.system.baseline
    lock = tmp_path / 'baseline.lock'
    lock.touch(mode=0o600)
    for name in ('canonical', 'identity'):
        monkeypatch.setattr(base, name, Mock())
    monkeypatch.setattr(base, 'BASELINES', tmp_path)
    monkeypatch.setattr(base, 'baseline_lock_path', lambda _: lock)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-v9.8.8')
    monkeypatch.setattr(controller, 'preparation_format', lambda *_: format)
    source = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    assert controller.probe('pinned', overwrite=True) == expected
    assert source.domain.mock_calls == []
    source.close.assert_called_once()


@pytest.mark.parametrize('guest,expected', [({'ubuntu_version': '26.04'}, 'deb'),
    ({'os_id': 'fedora', 'version': '44'}, 'rpm')])
@pytest.mark.parametrize('fault', [None, 'uuid', 'script', 'phase', 'proof'])
def test_package_backend_uses_bound_baseline_metadata(monkeypatch, guest, expected, fault):
    source = Mock(uuid='pinned')
    capture = Mock(script_digest='current')
    proof = {'name': 'onpc_baseline', 'creation_time': 123, 'storage': 'internal', 'state': 'shutoff'}
    capture.read_state.return_value = {'phase': 'other' if fault == 'phase' else 'finalized',
        'source': {'layout': {'uuid': 'foreign' if fault == 'uuid' else 'pinned'}},
        'script_digest': 'old' if fault == 'script' else 'current', 'guest': guest,
        'proof': dict(proof, disk={'id': '2'}, creation_time=456 if fault == 'proof' else 123)}
    monkeypatch.setattr(controller.system.baseline, 'Capture', Mock(return_value=capture))
    monkeypatch.setattr(controller.system.baseline, 'snapshot_proof', Mock(return_value=proof))
    if fault:
        with pytest.raises(controller.system.Error):
            controller.preparation_format(source, Mock())
    else:
        assert controller.preparation_format(source, Mock()) == expected
    source.shutdown.assert_not_called()
    assert source.domain.mock_calls == []
