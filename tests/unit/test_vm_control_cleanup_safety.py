"""VM maintenance uses real lease files/locks with exclusively mocked VM calls."""
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

VM_ARGS = ['--vm', 'onpc-Ubuntu26.04']


def reopened(lease):
    result = runner.Lease(lease.source, lease.commands, lease.inspect,
                          directory=lease.directory, anchor=lease.capture.anchor, graphics_type='vnc')
    return result


def start(lease):
    lease.view.graphics_type = 'vnc'
    control.operate(lease, 'start', [])
    lease.release()


def test_start_reboot_input_stop_share_one_attempt_and_restore_only_at_edges(lease_rig, monkeypatch):
    lease, current = lease_rig
    monkeypatch.setattr(runner.baseline, 'digest', Mock(side_effect=AssertionError('image hash')))
    lease.commands.check = Mock(side_effect=AssertionError('image scan'))
    original = current['xml']
    start(lease)
    assert lease.state['phase'] == 'running'
    assert not lease.source.layout['source_shares']
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
    select.__globals__['VM_UUIDS'] = {'onpc-Ubuntu26.04': UUID}
    command = select(root, ['vm', 'send-key', '28', *VM_ARGS])
    assert command[3:] == [*VM_ARGS, '--expected-uuid', UUID, 'send-key', '28']


@pytest.mark.parametrize('argv', [
    ['vm', 'rename'], ['vm', 'rename', '--new-name', '../another'],
    ['vm', 'rename', '--new-name', '-flag'],
    ['vm', 'start', '--new-name', 'another'],
    ['vm', 'rename', '1', '--new-name', 'another'],
])
def test_dispatcher_refuses_invalid_rename_destinations(argv):
    dispatcher = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-test-runner'))
    dispatcher['selection'].__globals__['VM_UUIDS'] = {'onpc-Ubuntu26.04': UUID}
    with pytest.raises(ValueError):
        dispatcher['selection'](Path(__file__).resolve().parents[2], [*argv, *VM_ARGS])


def test_dispatcher_rename_keeps_uuid_pin_and_only_accepts_destination_label():
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    dispatcher['selection'].__globals__['VM_UUIDS'] = {'onpc-Ubuntu26.04': UUID}
    assert dispatcher['selection'](root, ['vm', 'rename', '--new-name', 'custom-Ubuntu26.04', *VM_ARGS])[3:] == [
        *VM_ARGS, '--expected-uuid', UUID, 'rename', '--new-name', 'custom-Ubuntu26.04']


def rename_rig(lease, current, monkeypatch):
    """Private shared lock and snapshot metadata, with no real libvirt access."""
    import vm_config
    root = lease.directory.parent
    lease.capture.lock_path.rename(root / '.lock')
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
def test_explicit_interrupted_online_recovery_is_bound_and_cleanup_only(lease_rig, monkeypatch, fault):
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
    try:
        if fault:
            with pytest.raises(RuntimeError):
                control.operate(resumed, 'recover-online', [72 if fault == 'instance' else 71])
            assert lease.source.domain.revertToSnapshot.call_count == calls
        else:
            control.operate(resumed, 'recover-online', [71])
            assert resumed.state['phase'] == 'complete'
            assert lease.source.off
            assert lease.source.domain.revertToSnapshot.call_count == calls + 1
        assert lease.source.domain.create.call_count == 1
    finally:
        resumed.release()
