"""VM maintenance uses real lease files/locks with exclusively mocked VM calls."""
from tests.support.vm_registry import vm_name
import json
import hashlib
from pathlib import Path
import runpy
import os
import time
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import system_runner as runner
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig, UUID

import vm_control as control

VM_ARGS = ['--vm', vm_name()]


def reopened(lease):
    result = runner.Lease(lease.source, lease.commands, lease.inspect,
                          directory=lease.directory, anchor=lease.capture.anchor, graphics_type='vnc')
    return result


def start(lease):
    lease.view.graphics_type = 'vnc'
    control.operate(lease, 'start', [])
    lease.release()


@pytest.mark.parametrize('phase', [
    'validated', 'shutdown-requested', 'restore-requested', 'isolated', 'start-requested', 'cleanup-requested'])
@pytest.mark.parametrize('fault', [None, 'running', 'owner', 'configuration'])
def test_preparation_recovers_never_started_owned_maintenance_without_booting(
        lease_rig, phase, fault):
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    lease.__enter__()
    control.save_owner(lease)
    if phase in ('isolated', 'start-requested', 'cleanup-requested'):
        lease.prepare()
    lease.save(phase)
    lease.release()
    before = lease.journal.read_bytes()
    if fault == 'running':
        current['id'] = 71
        lease.source.off = False
        lease.source.domain.listAllSnapshots.return_value = []
    elif fault == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    elif fault == 'configuration':
        current['xml'] = current['xml'].replace('</domain>', '<description>unrelated</description></domain>')
    held = reopened(lease)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    try:
        if fault:
            with pytest.raises(RuntimeError):
                control.recover_preparation(held)
            assert lease.journal.read_bytes() == before
            assert lease.source.domain.revertToSnapshot.call_count == snapshots
        else:
            control.recover_preparation(held)
            assert held.state['phase'] == 'complete'
            assert current['id'] == -1
    finally:
        held.release()
    lease.source.domain.create.assert_not_called()


def test_start_reboot_input_stop_share_one_attempt_and_restore_only_at_edges(lease_rig, monkeypatch):
    lease, current = lease_rig
    monkeypatch.setattr(runner.baseline, 'digest', Mock(side_effect=AssertionError('image hash')))
    lease.commands.check = Mock(side_effect=AssertionError('image scan'))
    original = current['xml']
    start(lease)
    assert lease.state['phase'] == 'running'
    run = lease.state['run']
    for action, keys in [('reboot', []), ('send-key', [28])]:
        resumed = reopened(lease)
        try:
            control.operate(resumed, action, keys)
            assert resumed.state['run'] == run
            assert resumed.capture.verification_totals['bytes_read'] == 0
        finally:
            resumed.release()
    assert lease.source.domain.revertToSnapshot.call_count == 1
    lease.source.domain.sendKey.assert_called_once_with(
        lease.source.api.VIR_KEYCODE_SET_LINUX, 100, [28], 1, 0)
    resumed = reopened(lease)
    try:
        control.operate(resumed, 'stop', [])
    finally:
        resumed.release()
    assert lease.source.domain.revertToSnapshot.call_count == 2
    assert current['xml'] == original
    assert resumed.state['phase'] == 'complete'
    assert resumed.capture.verification_totals['bytes_read'] == 0
    assert lease.source.off


@pytest.mark.parametrize('phase', ['running', 'cleanup-requested'])
@pytest.mark.parametrize('restored', [False, True])
def test_off_maintenance_recovery_audits_restored_guest_or_restores_owned_isolation(
        lease_rig, phase, restored):
    lease, current = lease_rig
    start(lease)
    lease.state['phase'] = phase
    lease.journal.write_bytes(runner.baseline.encode(lease.state))
    if restored:
        lease.source.domain.revertToSnapshot(None, 0)
    else:
        lease.source.off, current['id'] = True, -1
    held = reopened(lease)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    definitions = lease.source.connection.defineXML.call_count
    shutdowns = lease.source.shutdown_calls
    try:
        control.recover_preparation(held)
        assert held.state['phase'] == 'complete'
        assert current['id'] == -1
        assert lease.source.domain.revertToSnapshot.call_count == snapshots + int(not restored)
        assert lease.source.connection.defineXML.call_count == definitions + int(not restored)
        assert lease.source.shutdown_calls == shutdowns
    finally:
        held.release()
    lease.source.domain.create.assert_called_once()
    lease.source.domain.destroyFlags.assert_not_called()


@pytest.mark.parametrize('fault', [
    'guest', 'audit-interrupted', 'restarted', 'configuration', 'split-configuration',
    'owner', 'snapshot', 'busy'])
def test_restored_off_maintenance_refusals_preserve_journal_without_vm_mutation(
        lease_rig, fault):
    lease, current = lease_rig
    start(lease)
    lease.source.domain.revertToSnapshot(None, 0)
    before = lease.journal.read_bytes()
    held = reopened(lease)
    competitor = reopened(lease)
    original = current['xml']
    if fault == 'guest':
        held.inspect = Mock(return_value={})
    elif fault == 'audit-interrupted':
        held.inspect = Mock(side_effect=KeyboardInterrupt())
    elif fault == 'restarted':
        def restart(*args):
            lease.source.off, current['id'] = False, 72
            return lease.capture.state['guest']
        held.inspect = restart
    elif fault == 'configuration':
        current['xml'] = original.replace('</domain>', '<description>unrelated</description></domain>')
    elif fault == 'split-configuration':
        lease.source.domain.XMLDesc.side_effect = lambda flags=0: (
            original if flags else original.replace('</domain>', '<description>unrelated</description></domain>'))
    elif fault == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    elif fault == 'snapshot':
        lease.source.baseline_xml += ' '
    else:
        control.resume(competitor, stopping=True)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    definitions = lease.source.connection.defineXML.call_count
    shutdowns = lease.source.shutdown_calls
    try:
        with pytest.raises(KeyboardInterrupt if fault == 'audit-interrupted' else RuntimeError):
            control.recover_preparation(held)
        assert lease.journal.read_bytes() == before
        assert lease.source.domain.revertToSnapshot.call_count == snapshots
        assert lease.source.connection.defineXML.call_count == definitions
        assert lease.source.shutdown_calls == shutdowns
        lease.source.domain.destroyFlags.assert_not_called()
        lease.source.domain.create.assert_called_once()
    finally:
        held.release()
        competitor.release()


@pytest.mark.parametrize('fault', [None, 'instance', 'owner', 'busy'])
def test_automatic_preparation_recovery_stops_only_proven_maintenance(
        lease_rig, tmp_path, monkeypatch, fault):
    import check_graphical_recovery as recovery
    lease, current = lease_rig
    start(lease)
    before = lease.journal.read_bytes()
    if fault == 'instance':
        current['id'] += 1
    elif fault == 'owner':
        owner = json.loads((lease.directory / 'vm-control.json').read_bytes())
        owner['baseline_sha256'] = 'f' * 64
        (lease.directory / 'vm-control.json').write_text(json.dumps(owner))
    evidence = tmp_path / 'recovery-evidence'
    evidence.mkdir()
    recovered = reopened(lease)
    monkeypatch.setattr(recovery, 'allocate', lambda *a, **kw: str(evidence))
    monkeypatch.setattr(recovery.os, 'umask', Mock())
    monkeypatch.setattr(recovery.threading, 'Thread', Mock())
    monkeypatch.setattr(recovery.importlib, 'import_module', lambda _: Mock())
    monkeypatch.setattr(recovery.runner.baseline, 'LibvirtSource', lambda _: lease.source)
    monkeypatch.setattr(recovery.runner, 'Commands', lambda: lease.commands)
    monkeypatch.setattr(recovery.runner, 'Lease', lambda *a, **kw: recovered)
    # Online maintenance has SPICE first and private VNC beside its observer.
    monkeypatch.setattr(recovery, 'recorded_graphics_type', lambda _: 'spice')
    lease.source.close = Mock()
    competitor = reopened(lease)
    if fault == 'busy':
        control.resume(competitor)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    try:
        assert recovery.recover(None, maintenance=True) == int(fault is not None)
    finally:
        competitor.release()
    result = json.loads((evidence / 'result.json').read_bytes())
    assert result['scope'] == 'recorded-maintenance-cleanup-only'
    if fault:
        assert lease.journal.read_bytes() == before
        assert lease.source.domain.revertToSnapshot.call_count == snapshots
    else:
        assert json.loads(lease.journal.read_bytes())['phase'] == 'complete'
        assert current['id'] == -1
    assert recovered.fd is None


@pytest.mark.parametrize('phase', ['running', 'isolated', 'cleanup-requested'])
@pytest.mark.parametrize('fault', [None, 'owner', 'snapshot', 'busy', 'interrupted'])
def test_auto_baseline_recovers_off_maintenance_and_preserves_refused_attempts(
        lease_rig, monkeypatch, phase, fault):
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    lease.__enter__()
    control.save_owner(lease)
    lease.prepare()
    if phase == 'running':
        lease.start()
        lease.source.off, current['id'] = True, -1
    lease.save(phase)
    lease.release()
    before = lease.journal.read_bytes()
    owner_path = lease.directory / 'vm-control.json'
    if fault == 'owner':
        owner = json.loads(owner_path.read_bytes())
        owner['baseline_sha256'] = 'f' * 64
        owner_path.write_bytes(runner.baseline.encode(owner))
    elif fault == 'snapshot':
        lease.source.baseline_xml += ' '
    owner_before = owner_path.read_bytes()
    held, competitor = reopened(lease), reopened(lease)
    if fault == 'busy':
        control.resume(competitor, stopping=True)
    elif fault == 'interrupted':
        held.inspect = Mock(side_effect=KeyboardInterrupt())
    monkeypatch.setattr(runner.baseline.guest_contract.vm_config, 'selected',
                        lambda **_: SimpleNamespace(baseline_directory=lease.directory, clipboard=False))
    monkeypatch.setattr(runner, 'Lease', lambda *a, **kw: held)
    snapshots = lease.source.domain.revertToSnapshot.call_count
    starts = lease.source.domain.create.call_count
    try:
        if fault:
            with pytest.raises(KeyboardInterrupt if fault == 'interrupted' else runner.Error):
                runner.baseline.recover_off_attempt(
                    lease.source, lease.commands, lease.inspect, mode='auto')
            if fault != 'interrupted':
                assert lease.journal.read_bytes() == before
                assert lease.source.domain.revertToSnapshot.call_count == snapshots
            else:
                assert json.loads(lease.journal.read_bytes())['phase'] == 'cleanup-requested'
        else:
            assert runner.baseline.recover_off_attempt(
                lease.source, lease.commands, lease.inspect, mode='auto') is True
            completed = lease.journal.read_bytes()
            assert json.loads(completed)['phase'] == 'complete'
            assert current['id'] == -1
            assert lease.source.domain.revertToSnapshot.call_count == snapshots + 1
            assert runner.baseline.recover_off_attempt(
                lease.source, lease.commands, lease.inspect, mode='auto') is None
            assert lease.journal.read_bytes() == completed
            assert lease.source.domain.revertToSnapshot.call_count == snapshots + 1
        assert owner_path.read_bytes() == owner_before
        assert lease.source.domain.create.call_count == starts
        assert held.fd is held.compatibility_fd is None
    finally:
        held.release()
        competitor.release()


@pytest.mark.parametrize('mutation', ['instance', 'run', 'owner', 'baseline', 'symlink'])
def test_replacement_or_unowned_attempt_never_receives_vm_actions(lease_rig, mutation):
    lease, current = lease_rig
    start(lease)
    if mutation == 'instance':
        current['id'] += 1
    elif mutation == 'run':
        current['xml'] = current['xml'].replace(lease.state['run'], 'f' * 32)
    elif mutation == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    elif mutation == 'baseline':
        lease.source.baseline_xml += ' '
    else:
        owner = lease.directory / 'vm-control.json'
        owner.rename(lease.directory / 'old-owner.json')
        owner.symlink_to('old-owner.json')
    resumed = reopened(lease)
    before = lease.source.shutdown_calls
    try:
        with pytest.raises(runner.Error):
            control.operate(resumed, 'stop', [])
    finally:
        resumed.release()
    assert lease.source.shutdown_calls == before
    lease.source.domain.destroyFlags.assert_not_called()
    assert lease.source.domain.revertToSnapshot.call_count == 1


def test_busy_controller_lock_refuses_even_with_valid_identity(lease_rig):
    lease, _ = lease_rig
    lease.view.graphics_type = 'vnc'
    control.operate(lease, 'start', [])
    concurrent = reopened(lease)
    try:
        with pytest.raises(runner.Error, match='busy-controller'):
            control.operate(concurrent, 'stop', [])
    finally:
        concurrent.release()
        lease.release()
    assert lease.source.domain.revertToSnapshot.call_count == 1


def test_wrong_vm_uuid_or_connection_refuses_before_leasing():
    source = Mock(uuid=UUID)
    source.connection.getURI.return_value = 'qemu:///system'
    source.domain.UUIDString.return_value = UUID
    source.domain.name.return_value = runner.baseline.DOMAIN
    control.check_identity(source, UUID)
    for uri, expected, name in [('qemu:///session', UUID, runner.baseline.DOMAIN),
                                 ('qemu:///system', 'f' * 36, runner.baseline.DOMAIN),
                                 ('qemu:///system', UUID, 'other-vm')]:
        source.connection.getURI.return_value = uri
        source.domain.name.return_value = name
        with pytest.raises(runner.Error):
            control.check_identity(source, expected)


@pytest.mark.parametrize('argv', [['vm', 'destroy', 'other'], ['vm', 'start', '1'],
                                 ['vm', '--domain=other', 'start'], ['vm', 'send-key'],
                                 ['vm', 'send-key', '256'], ['vm', 'send-key', '-1']])
def test_dispatcher_refuses_arbitrary_vm_selection_and_actions(argv):
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    with pytest.raises(ValueError):
        dispatcher['selection'](root, [*argv, *VM_ARGS])


def test_dispatcher_supplies_installed_uuid_and_no_caller_uri():
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    select = dispatcher['selection']
    with pytest.raises(ValueError, match='refresh'):
        select(root, ['vm', 'start', *VM_ARGS])
    select.__globals__['VM_UUIDS'] = {vm_name(): UUID}
    command = select(root, ['vm', 'send-key', '28', *VM_ARGS])
    assert command[3:] == [*VM_ARGS, '--expected-uuid', UUID, 'send-key', '28']


@pytest.mark.parametrize('fault', [None, 'uri', 'uuid', 'name'])
def test_snapshot_inventory_uses_only_pinned_read_only_connection(monkeypatch, capsys, fault):
    api = Mock()
    connection = api.openReadOnly.return_value
    domain = connection.lookupByUUIDString.return_value
    connection.getURI.return_value = 'qemu:///system' if fault != 'uri' else 'qemu:///session'
    domain.UUIDString.return_value = UUID if fault != 'uuid' else 'f' * 36
    domain.name.return_value = runner.baseline.DOMAIN if fault != 'name' else 'other'
    snapshot = Mock()
    snapshot.getName.return_value = '1 - Clean'
    snapshot.getXMLDesc.return_value = '<domainsnapshot/>'
    domain.listAllSnapshots.return_value = [snapshot]
    monkeypatch.setattr(control.importlib, 'import_module', lambda name: api)
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.os, 'getegid', lambda: 0)
    monkeypatch.setattr(control.os, 'umask', lambda value: 0)
    assert control.main([*VM_ARGS, '--expected-uuid', UUID, 'snapshots']) == (2 if fault else 0)
    connection.lookupByUUIDString.assert_called_once_with(UUID)
    connection.close.assert_called_once()
    api.open.assert_not_called()
    api.virEventRegisterDefaultImpl.assert_not_called()
    domain.revertToSnapshot.assert_not_called()
    if fault:
        domain.listAllSnapshots.assert_not_called()
    else:
        assert json.loads(capsys.readouterr().out) == [{'name': '1 - Clean', 'xml': '<domainsnapshot/>'}]


def test_root_guest_dispatch_keeps_arbitrary_command_inside_the_fixed_controller():
    root = Path(__file__).resolve().parents[2]
    dispatch = runpy.run_path(str(root / 'tools/onpc-test-runner'))['selection']
    dispatch.__globals__['VM_UUIDS'] = {vm_name(): UUID}
    guest = ['sh', '-c', 'journalctl; id -u', '--vm', 'unknown-vm', '--help', '--list']
    command = dispatch(root, ['vm', 'exec', *VM_ARGS, '--timeout', '600', '--', *guest])
    assert command == ['/usr/bin/python3', '-B', str(root / 'tests/integration/vm_control.py'),
                       *VM_ARGS, '--expected-uuid', UUID, 'exec', '--timeout', '600', '--', *guest]
    with pytest.raises(ValueError, match='--vm'):
        dispatch(root, ['vm', 'exec', '--', *guest])


def test_public_probe_launcher_keeps_host_selector_before_guest_arguments(monkeypatch):
    import dev_privileges
    import sys
    root = Path(__file__).resolve().parents[2]
    guest = ['printf', '--vm', 'unknown-vm', '--help', '--list']
    launch = Mock()
    monkeypatch.setattr(dev_privileges, 'launch', launch)
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(sys, 'argv', [str(root / 'tools/test-vm'), *VM_ARGS, 'exec', '--', *guest])
    runpy.run_path(str(root / 'tools/test-vm'), run_name='__main__')
    launch.assert_called_once_with('/usr/local/libexec/onpc-test-runner',
                                  ['vm', *VM_ARGS, 'exec', '--', *guest])


def test_probe_input_is_opened_unprivileged_and_not_forwarded_as_a_host_path(tmp_path):
    source = tmp_path / 'payload.rpm'
    source.write_bytes(b'RPM\0payload')
    root = Path(__file__).resolve().parents[2]
    prepare = runpy.run_path(str(root / 'tools/test-vm'))['input_arguments']
    guest = ['cat', '--input-file', '/guest-only']
    args, fd = prepare(['exec', '--input-file', str(source), '--', *guest])
    try:
        assert args == ['exec', '--stdin', '--', *guest]
        assert os.read(fd, 100) == b'RPM\0payload'
        assert str(source) not in args
    finally:
        os.close(fd)


@pytest.mark.parametrize('fault', ['symlink', 'directory', 'fifo', 'oversize', 'missing', 'wrong-action'])
def test_probe_input_refuses_invalid_files_and_actions(tmp_path, fault):
    root = Path(__file__).resolve().parents[2]
    prepare = runpy.run_path(str(root / 'tools/test-vm'))['input_arguments']
    source = tmp_path / 'payload'
    if fault == 'symlink':
        source.symlink_to(tmp_path)
    elif fault == 'directory':
        source.mkdir()
    elif fault == 'fifo':
        os.mkfifo(source)
    elif fault == 'oversize':
        with source.open('wb') as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
    args = ['status' if fault == 'wrong-action' else 'exec', '--input-file', str(source), '--', 'cat']
    with pytest.raises(ValueError, match='vm-probe:'):
        prepare(args)


def test_dispatcher_passes_input_marker_without_a_privileged_host_path():
    root = Path(__file__).resolve().parents[2]
    dispatch = runpy.run_path(str(root / 'tools/onpc-test-runner'))['selection']
    dispatch.__globals__['VM_UUIDS'] = {vm_name(): UUID}
    command = dispatch(root, ['vm', 'exec', *VM_ARGS, '--stdin', '--', 'cat'])
    assert command[-3:] == ['--stdin', '--', 'cat']


@pytest.mark.parametrize('args', [[], ['id'], ['--'], ['--host', 'other', '--', 'id']])
def test_root_guest_dispatch_refuses_invalid_host_controls(args):
    root = Path(__file__).resolve().parents[2]
    dispatch = runpy.run_path(str(root / 'tools/onpc-test-runner'))['selection']
    with pytest.raises(ValueError, match='vm-probe:'):
        dispatch(root, ['vm', 'exec', *VM_ARGS, *args])


def probe_snapshot(held, current):
    """Current snapshot identity double, backed only by a private lease fixture."""
    tree = ET.Element('domainsnapshot')
    ET.SubElement(tree, 'state').text = 'running'
    ET.SubElement(tree, 'memory', snapshot='internal')
    ET.SubElement(tree, 'description').text = json.dumps({'baseline_sha256': held.state['baseline_sha256']})
    tree.append(ET.fromstring(current['xml']))
    snapshot = Mock()
    snapshot.getName.return_value = 'onpc-v1.1'
    snapshot.getXMLDesc.side_effect = lambda _: ET.tostring(tree, encoding='unicode')
    held.source.domain.snapshotCurrent.return_value = snapshot
    record = {'run': held.state['run'], 'private_key': 'private-key-canary'}
    return tree, snapshot, record


@pytest.mark.parametrize('status', [0, 1, 127, 255])
@pytest.mark.parametrize('input_stream', [False, True])
def test_root_probe_preserves_guest_state_and_exit_status(lease_rig, monkeypatch, capsys, status, input_stream):
    import online_snapshot
    import vm_probe
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held)
    held.commands.directory = lease.directory / 'probe-scratch'
    held.commands.directory.mkdir()
    _, _, record = probe_snapshot(held, current)
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=record))
    monkeypatch.setattr(vm_probe.system, 'address', Mock(return_value='192.168.122.20'))
    transport = Mock()
    if input_stream:
        import io
        from types import SimpleNamespace
        original_stat, original_seek = os.fstat, os.lseek
        monkeypatch.setattr(vm_probe.os, 'fstat', lambda fd: SimpleNamespace(st_mode=0o100600, st_size=7)
                            if fd == 0 else original_stat(fd))
        monkeypatch.setattr(vm_probe.os, 'lseek', lambda fd, offset, whence: 0
                            if fd == 0 else original_seek(fd, offset, whence))
        monkeypatch.setattr(vm_probe.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'payload')))
    def run(command, **kwargs):
        assert command == ['journalctl', '--no-pager']
        assert kwargs['check'] is False and kwargs['timeout'] == 120
        assert kwargs.get('input') == (b'payload' if input_stream else None)
        kwargs['on_stream'](b'guest stdout\n', 'stdout')
        kwargs['on_stream'](b'guest stderr\n', 'stderr')
        transport.commands.last_returncode = status
    transport.call.side_effect = run
    connect = Mock(return_value=transport)
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', connect)
    journal, owner = held.journal.read_bytes(), (held.directory / 'vm-control.json').read_bytes()
    restores = held.source.domain.revertToSnapshot.call_count
    guard = held.guard
    def checked_guard():
        guard()
        transport.commands.last_returncode = 0
    held.guard = checked_guard
    try:
        assert vm_probe.execute(held, ['journalctl', '--no-pager'], 120, input_stream=input_stream) == status
        connect.assert_called_once_with(held, held.commands.directory, record, '192.168.122.20')
        assert held.journal.read_bytes() == journal
        assert (held.directory / 'vm-control.json').read_bytes() == owner
        assert held.source.domain.revertToSnapshot.call_count == restores
        assert current['id'] == 71
        out = capsys.readouterr()
        assert 'guest stdout' in out.out and 'guest stderr' in out.err
        assert 'private-key-canary' not in out.out + out.err
    finally:
        held.release()


@pytest.mark.parametrize('fault', ['credentials', 'name', 'memory', 'uuid', 'run', 'baseline'])
def test_root_probe_refuses_unbound_snapshot_credentials_before_connecting(lease_rig, monkeypatch, fault):
    import online_snapshot
    import vm_probe
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held)
    tree, snapshot, record = probe_snapshot(held, current)
    if fault == 'credentials':
        record = None
    elif fault == 'name':
        snapshot.getName.return_value = 'onpc_baseline'
    elif fault == 'memory':
        tree.find('memory').set('snapshot', 'no')
    elif fault == 'uuid':
        tree.find('domain/uuid').text = '0' * 36
    elif fault == 'run':
        record['run'] = 'f' * 32
    elif fault == 'baseline':
        tree.find('description').text = json.dumps({'baseline_sha256': 'f' * 64})
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=record))
    connect = Mock()
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', connect)
    address = Mock()
    monkeypatch.setattr(vm_probe.system, 'address', address)
    journal = held.journal.read_bytes()
    restores = held.source.domain.revertToSnapshot.call_count
    try:
        with pytest.raises(RuntimeError):
            vm_probe.execute(held, ['id', '-u'], 120)
        connect.assert_not_called()
        address.assert_not_called()
        assert held.journal.read_bytes() == journal
        assert held.source.domain.revertToSnapshot.call_count == restores
    finally:
        held.release()


@pytest.mark.parametrize('fault', ['pipe', 'oversize', 'offset', 'changed'])
def test_root_probe_refuses_invalid_input_before_ssh(lease_rig, monkeypatch, fault):
    import io
    from types import SimpleNamespace
    import online_snapshot
    import vm_probe
    lease, current = lease_rig
    start(lease)
    held = reopened(lease)
    control.resume(held)
    _, _, record = probe_snapshot(held, current)
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=record))
    monkeypatch.setattr(vm_probe.system, 'address', Mock(return_value='192.168.122.20'))
    connect = Mock()
    monkeypatch.setattr(online_snapshot, 'connect_saved_transport', connect)
    original_stat, original_seek = os.fstat, os.lseek
    info = SimpleNamespace(st_mode=0o010600 if fault == 'pipe' else 0o100600,
                           st_size=64 * 1024 * 1024 + 1 if fault == 'oversize' else 7)
    monkeypatch.setattr(vm_probe.os, 'fstat', lambda fd: info if fd == 0 else original_stat(fd))
    monkeypatch.setattr(vm_probe.os, 'lseek', lambda fd, offset, whence:
                        (1 if fault == 'offset' else 0) if fd == 0 else original_seek(fd, offset, whence))
    monkeypatch.setattr(vm_probe.sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'short')))
    journal = held.journal.read_bytes()
    try:
        with pytest.raises(RuntimeError, match='vm-probe:'):
            vm_probe.execute(held, ['cat'], 120, input_stream=True)
        connect.assert_not_called()
        assert held.journal.read_bytes() == journal
    finally:
        held.release()


@pytest.mark.parametrize('fault', ['owner', 'busy', 'instance'])
def test_root_probe_refuses_foreign_or_active_controller_before_ssh(lease_rig, monkeypatch, fault):
    import vm_probe
    lease, current = lease_rig
    if fault == 'busy':
        lease.view.graphics_type = 'vnc'
        control.operate(lease, 'start', [])
    else:
        start(lease)
        if fault == 'owner':
            (lease.directory / 'vm-control.json').write_text('{}')
        else:
            current['id'] += 1
    execute = Mock()
    monkeypatch.setattr(vm_probe, 'execute', execute)
    held = reopened(lease)
    try:
        with pytest.raises(RuntimeError):
            control.resume(held)
        execute.assert_not_called()
    finally:
        held.release()
        lease.release()


@pytest.mark.parametrize('argv', [
    ['vm', 'rename'], ['vm', 'rename', '--new-name', '../another'],
    ['vm', 'rename', '--new-name', '-flag'],
    ['vm', 'start', '--new-name', 'another'],
    ['vm', 'rename', '1', '--new-name', 'another'],
])
def test_dispatcher_refuses_invalid_rename_destinations(argv):
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['selection'].__globals__['VM_UUIDS'] = {vm_name(): UUID}
    with pytest.raises(ValueError):
        dispatcher['selection'](Path(__file__).resolve().parents[2], [*argv, *VM_ARGS])


def test_dispatcher_rename_keeps_uuid_pin_and_only_accepts_destination_label():
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    dispatcher['selection'].__globals__['VM_UUIDS'] = {vm_name(): UUID}
    assert dispatcher['selection'](root, ['vm', 'rename', '--new-name', 'custom-Ubuntu26.04', *VM_ARGS])[3:] == [
        *VM_ARGS, '--expected-uuid', UUID, 'rename', '--new-name', 'custom-Ubuntu26.04']


def rename_rig(lease, current, monkeypatch):
    """Private named and legacy leases; no real libvirt access."""
    import vm_config
    root = lease.directory.parent
    (root / '.lock').touch(mode=0o600)
    monkeypatch.setattr(vm_config, 'STATE_ROOT', root)
    monkeypatch.setattr(runner.baseline, 'DOMAIN', runner.baseline.DOMAIN)
    source = lease.source
    source.api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE = 1
    source.api.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT = 2
    source.domain.UUIDString.return_value = UUID
    source.domain.name.side_effect = lambda: ET.fromstring(current['xml']).findtext('name')
    source.connection.lookupByUUIDString.return_value = source.domain
    snapshots = {runner.baseline.SNAPSHOT: source.baseline_xml,
                 'onpc-v9.9': source.baseline_xml.replace(
                     '<name>' + runner.baseline.SNAPSHOT + '</name>', '<name>onpc-v9.9</name>')}
    def snapshot(name):
        value = Mock()
        value.getName.return_value = name
        value.getXMLDesc.side_effect = lambda *_: snapshots[name]
        return value
    source.domain.listAllSnapshots.side_effect = lambda *_: [snapshot(name) for name in snapshots]
    source.domain.snapshotLookupByName.side_effect = lambda name, *_: snapshot(name)
    source.domain.hasCurrentSnapshot.return_value = True
    source.domain.snapshotCurrent.return_value = snapshot(runner.baseline.SNAPSHOT)
    def renamed(name, *_):
        tree = ET.fromstring(current['xml'])
        tree.find('name').text = name
        current['xml'] = ET.tostring(tree, encoding='unicode')
    source.domain.rename.side_effect = renamed
    def redefine(xml, flags):
        name = ET.fromstring(xml).findtext('name')
        assert flags & source.api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE
        snapshots[name] = xml
        source.baseline_xml = snapshots[runner.baseline.SNAPSHOT]
        return snapshot(name)
    source.domain.snapshotCreateXML.side_effect = redefine
    return snapshots, redefine


def test_rename_preserves_disks_uuid_snapshot_contents_and_provenance(lease_rig, monkeypatch):
    lease, current = lease_rig
    snapshots, _ = rename_rig(lease, current, monkeypatch)
    old_name = runner.baseline.DOMAIN
    directory = lease.directory
    identity = directory.stat().st_ino
    original = current['xml']
    originals = snapshots.copy()
    state = (directory / 'phase.json').read_bytes()
    before = {item['path']: Path(item['path']).read_bytes()
              for item in json.loads(state)['source']['chain']}
    try:
        control.rename(lease, 'custom-Ubuntu26.04')
        assert not directory.exists()
        assert lease.directory.name == 'custom-Ubuntu26.04'
        assert lease.directory.stat().st_ino == identity
        assert (lease.directory / 'phase.json').read_bytes() == state
        assert control.same_xml(current['xml'], control.renamed_xml(original, old_name, 'custom-Ubuntu26.04', UUID))
        assert snapshots == originals
        lease.source.domain.snapshotCreateXML.assert_not_called()
        assert all(Path(path).read_bytes() == content for path, content in before.items())
        assert lease.source.domain.ID() == -1
        assert json.loads(next(lease.directory.glob('rename-*.json')).read_bytes())['phase'] == 'complete'
        assert lease.capture.verify_snapshot() == lease.capture.state['proof']
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
        assert lease.source.creations == [lease.capture.description()]
    finally:
        lease.release()


@pytest.mark.parametrize('fault', ['metadata', 'record-uuid', 'record-name', 'missing-record', 'pending'])
def test_historical_snapshot_name_requires_exact_owned_rename_proof(lease_rig, monkeypatch, fault):
    lease, current = lease_rig
    rename_rig(lease, current, monkeypatch)
    try:
        control.rename(lease, 'custom-Ubuntu26.04')
        record_path = next(lease.directory.glob('rename-*.json'))
        record = json.loads(record_path.read_bytes())
        if fault == 'metadata':
            lease.source.baseline_xml += ' '
        elif fault == 'missing-record':
            record_path.rename(lease.directory / 'preserved-record.json')
        else:
            if fault == 'record-uuid':
                record['domain_uuid'] = 'f' * 36
            elif fault == 'record-name':
                record['new_name'] = 'unrelated-vm'
            else:
                record['phase'] = 'requested'
            record_path.write_text(json.dumps(record))
        with pytest.raises(runner.Error, match='domain-identity'):
            lease.capture.verify_snapshot()
        lease.source.domain.snapshotCreateXML.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
    finally:
        lease.release()


@pytest.mark.parametrize('fault', ['running', 'busy', 'destination', 'snapshot-uuid', 'pending'])
def test_rename_refusals_leave_domain_snapshots_and_provenance_untouched(lease_rig, monkeypatch, fault):
    import fcntl
    lease, current = lease_rig
    snapshots, _ = rename_rig(lease, current, monkeypatch)
    destination = lease.directory.parent / 'custom-Ubuntu26.04'
    lock = None
    if fault == 'running':
        current['id'], lease.source.off = 71, False
    elif fault == 'destination':
        destination.mkdir()
    elif fault == 'snapshot-uuid':
        snapshots['onpc-v9.9'] = snapshots['onpc-v9.9'].replace(UUID, 'f' * 36)
    elif fault == 'pending':
        (lease.directory / 'rename-previous.json').write_text('{"phase":"requested"}')
        (lease.directory / 'rename-previous.json').chmod(0o600)
    else:
        lock = lease.capture.lock_path.open('rb')
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    original = current['xml']
    originals = snapshots.copy()
    try:
        with pytest.raises(runner.Error):
            control.rename(lease, destination.name)
        assert current['xml'] == original and snapshots == originals
        assert lease.directory.exists()
        lease.source.domain.rename.assert_not_called()
        lease.source.domain.snapshotCreateXML.assert_not_called()
    finally:
        lease.release()
        if lock is not None:
            lock.close()


@pytest.mark.parametrize('fault', ['api', 'snapshot', 'move', 'interrupt'])
def test_rename_failures_roll_back_only_owned_metadata(lease_rig, monkeypatch, fault):
    lease, current = lease_rig
    snapshots, redefine = rename_rig(lease, current, monkeypatch)
    original, originals = current['xml'], snapshots.copy()
    directory = lease.directory
    if fault == 'api':
        rename_api = lease.source.domain.rename.side_effect
        def fail_rename(name, flags):
            if name == 'custom-Ubuntu26.04':
                raise runner.Error('fixture:rename-failed')
            return rename_api(name, flags)
        lease.source.domain.rename.side_effect = fail_rename
    elif fault in ('snapshot', 'interrupt'):
        reads = 0
        list_snapshots = lease.source.domain.listAllSnapshots.side_effect
        def fail_snapshot(*args):
            nonlocal reads
            reads += 1
            if reads == 3:
                raise KeyboardInterrupt() if fault == 'interrupt' else runner.Error('fixture:snapshot-failed')
            return list_snapshots(*args)
        lease.source.domain.listAllSnapshots.side_effect = fail_snapshot
    else:
        monkeypatch.setattr(control.os, 'rename', Mock(side_effect=OSError('fixture:move-failed')))
    try:
        with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else (runner.Error, OSError)):
            control.rename(lease, 'custom-Ubuntu26.04')
        assert control.same_xml(current['xml'], original)
        assert all(control.same_xml(snapshots[name], xml) for name, xml in originals.items())
        assert directory.exists() and lease.directory == directory
        assert json.loads(next(directory.glob('rename-*.json')).read_bytes())['phase'] == 'rolled-back'
        lease.source.domain.create.assert_not_called()
        lease.source.domain.revertToSnapshot.assert_not_called()
    finally:
        lease.release()


@pytest.mark.parametrize('status', [0, 1, 130])
@pytest.mark.parametrize('argv', [['vm', 'start'], ['vm', 'stop'],
                                 ['integration', 'check_test_recovery']])
def test_foreground_dispatch_runs_only_owned_operation_without_test_gate(tmp_path, monkeypatch, argv, status):
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    dispatcher['run'].__globals__['selection'] = lambda *args: ['selected-operation']
    monkeypatch.setattr(dispatcher['runpy'], 'run_path', lambda _: {
        'safety_command': lambda root: ['shared-qualified-gate']})
    monkeypatch.setattr(dispatcher['os'], 'getgrouplist', lambda *args: [])
    caller = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name='fixture',
                             pw_dir=str(tmp_path))
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert calls == [['selected-operation']]
        assert kwargs['env']['PKEXEC_UID'] == str(caller.pw_uid)
        assert 'user' not in kwargs
        return SimpleNamespace(returncode=status)
    monkeypatch.setattr(dispatcher['subprocess'], 'run', execute)
    assert dispatcher['run'](root, [*argv, *VM_ARGS], caller) == status
    assert len(calls) == 1


def test_reset_leaves_vm_off_and_never_creates_snapshot_or_vm(lease_rig):
    lease, _ = lease_rig
    lease.view.graphics_type = 'vnc'
    snapshots = len(lease.source.creations)
    try:
        control.operate(lease, 'reset', [])
    finally:
        lease.release()
    lease.source.domain.create.assert_not_called()
    assert len(lease.source.creations) == snapshots
    assert lease.source.off


@pytest.mark.parametrize('running', [False, True])
@pytest.mark.parametrize('fault', ['expired', 'credentials', 'baseline', 'restore'])
def test_online_resume_refusal_preserves_idle_or_running_ownership(
        lease_rig, monkeypatch, tmp_path, running, fault):
    import online_snapshot
    import prepare_snapshot as controller
    from tools import test_retention
    lease, current = lease_rig
    lease.view.graphics_type = 'vnc'
    if running:
        start(lease)
        previous_journal = lease.journal.read_bytes()
        previous_owner = (lease.directory / 'vm-control.json').read_bytes()
        held = reopened(lease)
    else:
        held = lease
    held.capture.directory_identity = held.capture.private_directory()
    baseline_sha256 = hashlib.sha256(runner.baseline.encode(
        held.capture.read_state())).hexdigest()
    root = ET.Element('domainsnapshot')
    ET.SubElement(root, 'memory', snapshot='internal')
    ET.SubElement(root, 'state').text = 'running'
    ET.SubElement(root, 'creationTime').text = str(int(time.time()) - (
        86401 if fault == 'expired' else 0))
    ET.SubElement(root, 'description').text = json.dumps({
        'baseline_sha256': 'f' * 64 if fault == 'baseline' else baseline_sha256})
    root.append(ET.fromstring(runner.isolated_xml(
        current['xml'], UUID, 'e' * 32, graphics_type='vnc')))
    snapshot = Mock()
    snapshot.getXMLDesc.return_value = ET.tostring(root, encoding='unicode')
    lease.source.domain.snapshotLookupByName.return_value = snapshot
    lease.source.close = Mock()
    monkeypatch.setattr(controller, 'open_source', lambda: (lease.source, Mock()))
    monkeypatch.setattr(controller, 'check_identity', Mock())
    monkeypatch.setattr(controller, 'Commands', lambda: lease.commands)
    monkeypatch.setattr(controller.system, 'Lease', lambda *a, **kw: held)
    monkeypatch.setattr(controller, 'current_name', lambda _: 'onpc-v1.1')
    monkeypatch.setattr(test_retention, 'allocate', lambda *a, **kw: str(tmp_path))
    monkeypatch.setattr(online_snapshot, 'load', lambda *a: (
        None if fault == 'credentials' else {'run': 'e' * 32}))
    lease.source.domain.revertToSnapshot.reset_mock()
    lease.source.domain.revertToSnapshot.side_effect = runner.Error('fixture:restore-interrupted')
    with pytest.raises(RuntimeError, match={
            'expired': 'expired-or-invalid', 'credentials': 'credentials-missing',
            'baseline': 'baseline-changed', 'restore': 'restore-interrupted'}[fault]):
        controller.resume(UUID)
    assert held.fd is None
    state = json.loads(lease.journal.read_bytes())
    if fault == 'restore':
        assert state['phase'] == 'start-requested' and state['domain_id'] is None
        lease.source.domain.revertToSnapshot.assert_called_once()
        if running:
            assert state['run'] != json.loads(previous_journal)['run']
    else:
        lease.source.domain.revertToSnapshot.assert_not_called()
        if running:
            assert lease.journal.read_bytes() == previous_journal
            assert (lease.directory / 'vm-control.json').read_bytes() == previous_owner
        else:
            assert state['phase'] == 'complete'


@pytest.mark.parametrize('fault', [None, 'instance', 'owner', 'credentials', 'sharing', 'baseline'])
@pytest.mark.parametrize('automatic', [False, True])
def test_explicit_interrupted_online_recovery_is_bound_and_cleanup_only(
        lease_rig, monkeypatch, fault, automatic):
    import online_snapshot
    lease, current = lease_rig
    start(lease)
    saved_run = lease.state['run']
    tree = ET.Element('domainsnapshot')
    ET.SubElement(tree, 'state').text = 'running'
    ET.SubElement(tree, 'memory', snapshot='internal')
    ET.SubElement(tree, 'description').text = json.dumps({
        'baseline_sha256': lease.state['baseline_sha256'] if fault != 'baseline' else 'f' * 64})
    tree.append(ET.fromstring(current['xml']))
    snapshot = Mock()
    snapshot.getName.return_value = 'onpc-v1.1'
    snapshot.getXMLDesc.return_value = ET.tostring(tree, encoding='unicode')
    lease.source.domain.listAllSnapshots.return_value = [snapshot]
    monkeypatch.setattr(online_snapshot, 'load', Mock(return_value=
        None if fault == 'credentials' else {'run': saved_run}))
    lease.state.update(phase='start-requested', domain_id=None, run='b' * 32)
    lease.journal.write_bytes(runner.baseline.encode(lease.state))
    control.save_owner(lease)
    if fault == 'owner':
        (lease.directory / 'vm-control.json').write_text('{}')
    if fault == 'sharing':
        current['xml'] = current['xml'].replace('</devices>', '<channel/></devices>')
    resumed = reopened(lease)
    calls = lease.source.domain.revertToSnapshot.call_count
    def recover():
        if automatic:
            if fault == 'instance':
                # The observed instance changes before the exclusive lease is
                # acquired. Automation must retain the recorded refusal.
                first = [True]
                def observed_instance():
                    if first:
                        first.pop()
                        return 72
                    return current['id']
                lease.source.domain.ID.side_effect = observed_instance
            control.recover_preparation(resumed)
        else:
            control.operate(resumed, 'recover-online', [72 if fault == 'instance' else 71])
    try:
        if fault:
            with pytest.raises(RuntimeError):
                recover()
            assert lease.source.domain.revertToSnapshot.call_count == calls
        else:
            recover()
            assert resumed.state['phase'] == 'complete'
            assert lease.source.off
            assert lease.source.domain.revertToSnapshot.call_count == calls + 1
        assert lease.source.domain.create.call_count == 1
    finally:
        resumed.release()
