"""VM maintenance uses real lease files/locks with exclusively mocked VM calls."""
import json
from pathlib import Path
import runpy
from unittest.mock import Mock

import pytest
import system_runner as runner
from tests.support.vm_baseline import rig
from tests.support.vm_runner import lease_rig, UUID

import vm_control as control


def reopened(lease):
    result = runner.Lease(lease.source, lease.commands, lease.inspect,
                          directory=lease.directory, anchor=lease.capture.anchor, graphics_type='vnc')
    return result


def start(lease):
    lease.view.graphics_type = 'vnc'
    control.operate(lease, 'start', [])
    lease.release()


def test_start_reboot_input_stop_share_one_attempt_and_restore_only_at_edges(lease_rig):
    lease, current = lease_rig
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
    source.domain.name.return_value = 'ubuntu26.04'
    control.check_identity(source, UUID)
    for uri, expected, name in [('qemu:///session', UUID, 'ubuntu26.04'),
                                 ('qemu:///system', 'f' * 36, 'ubuntu26.04'),
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
        dispatcher['selection'](root, argv)


def test_dispatcher_supplies_installed_uuid_and_no_caller_uri():
    root = Path(__file__).resolve().parents[2]
    dispatcher = runpy.run_path(str(root / 'tools/onpc-test-runner'))
    select = dispatcher['selection']
    with pytest.raises(ValueError, match='refresh'):
        select(root, ['vm', 'start'])
    select.__globals__['VM_UUID'] = UUID
    command = select(root, ['vm', 'send-key', '28'])
    assert command[3:] == ['--expected-uuid', UUID, 'send-key', '28']


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
