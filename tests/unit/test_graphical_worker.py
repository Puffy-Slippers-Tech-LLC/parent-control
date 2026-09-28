"""Transport failures and completion protocol, without a VM or namespaces."""

import array
import socket
import struct
from unittest.mock import Mock, MagicMock, patch

import pytest

import graphical_worker as worker
import check_graphical_worker as qualification


def test_descendant_wait_requires_every_recorded_exit():
    with patch.object(qualification.select, 'select', side_effect=[([41], [], []), ([42], [], [])]) as wait:
        qualification.wait_exited([41, 42], 5)
    assert set(wait.call_args_list[0].args[0]) == {41, 42}
    assert wait.call_args_list[1].args[0] == [42]


def test_descendant_timeout_fails_without_signalling_anything():
    with patch.object(qualification.time, 'monotonic', side_effect=[0, 0, 6]), \
            patch.object(qualification.select, 'select', return_value=([], [], [])), \
            patch.object(qualification.signal, 'pidfd_send_signal') as signal:
        with pytest.raises(RuntimeError, match='descendant-survived'):
            qualification.wait_exited([41], 5)
    signal.assert_not_called()


def test_fast_worker_drains_ready_and_exit_before_checking_success():
    handle = worker.Worker.__new__(worker.Worker)
    handle.ready, handle.result = False, None
    handle.child = Mock()
    handle.child.poll.return_value = 0
    handle.control = Mock()
    handle.control.recv.side_effect = [b'ready\n', b'exit 0\n', b'']
    assert handle.poll() == 0


@pytest.mark.parametrize('packets', [
    [b''], [b'ready\n', b''], [b'exit 0\n'],
    [b'ready\n', b'ready\n'], [b'ready\n', b'exit 0\n', b'exit 0\n'], [b'unknown\n'],
])
def test_missing_or_invalid_completion_never_passes(packets):
    handle = worker.Worker.__new__(worker.Worker)
    handle.ready, handle.result = False, None
    handle.child = Mock()
    handle.child.poll.return_value = 0
    handle.control = Mock()
    handle.control.recv.side_effect = packets
    with pytest.raises(RuntimeError, match='worker:'):
        handle.poll()


@pytest.mark.parametrize('packet,descriptors,flags', [
    (b'failed\n', [41], 0), (b'ok\n', [], 0), (b'ok\n', [41, 42], 0),
    (b'ok\n', [41], socket.MSG_CTRUNC), (b'ok\n', [41], socket.MSG_TRUNC),
])
def test_rejected_graphics_reply_closes_all_received_fds(packet, descriptors, flags):
    peer = MagicMock()
    peer.__enter__.return_value = peer
    peer.getsockopt.return_value = struct.pack('3i', 12, 0, 0)
    peer.recvmsg.return_value = (packet, [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                         array.array('i', descriptors).tobytes())], flags, None)
    with patch.object(worker.socket, 'socket', return_value=peer), \
            patch.object(worker.os, 'close') as close:
        with pytest.raises(RuntimeError, match='graphics-refused'):
            worker.graphics_fd('/tmp/callback', 'a' * 32)
    assert [call.args[0] for call in close.call_args_list] == descriptors


def test_graphics_requires_root_controller_before_sending_request():
    peer = MagicMock()
    peer.__enter__.return_value = peer
    peer.getsockopt.return_value = struct.pack('3i', 12, 1000, 1000)
    with patch.object(worker.socket, 'socket', return_value=peer):
        with pytest.raises(RuntimeError, match='controller-peer'):
            worker.graphics_fd('/tmp/callback', 'a' * 32)
    peer.sendall.assert_not_called()


def test_bridge_backpressure_stops_reading_until_pending_bytes_are_sent():
    bridge = worker.Bridge.__new__(worker.Bridge)
    bridge.listener, control = Mock(), Mock()
    sender, receiver = Mock(), Mock()
    bridge.ends = [sender, receiver]
    bridge.pending = [bytearray(), bytearray(b'x' * worker.LIMIT)]
    receiver.send.return_value = 1024
    with patch.object(worker.select, 'select', return_value=([], [receiver], [])) as ready:
        assert bridge.step(control)
    assert sender not in ready.call_args.args[0]
    assert len(bridge.pending[1]) == worker.LIMIT - 1024
    sender.recv.assert_not_called()


def test_controller_loss_precedes_any_new_connection_or_forwarding():
    bridge = worker.Bridge.__new__(worker.Bridge)
    bridge.listener, control = Mock(), Mock()
    bridge.ends = []
    with patch.object(worker.select, 'select', return_value=([control, bridge.listener], [], [])):
        assert not bridge.step(control)
    bridge.listener.accept.assert_not_called()


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('failure', ['eof', 'connection-error'])
def test_bridge_disconnect_identifies_failed_leg_without_payload(index, failure, capsys):
    # Process-local doubles only; retain the existing unit/cleanup scheduling.
    bridge = worker.Bridge.__new__(worker.Bridge)
    bridge.listener, control = Mock(), Mock()
    endpoints = [Mock(), Mock()]
    bridge.ends = endpoints
    bridge.pending = [bytearray(b'private-input'), bytearray(b'private-display')]
    if failure == 'eof':
        endpoints[index].recv.return_value = b''
    else:
        endpoints[index].recv.side_effect = ConnectionResetError('private-error')
    with patch.object(worker.select, 'select', return_value=([endpoints[index]], [], [])):
        assert bridge.step(control)
    assert bridge.ends == [] and bridge.pending == [bytearray(), bytearray()]
    for endpoint in endpoints:
        endpoint.close.assert_called_once()
        endpoint.send.assert_not_called()
    leg = ('backend', 'display')[index]
    assert capsys.readouterr().err == (
        f'graphical-worker: [display-disconnected endpoint={leg} reason={failure}]\n')
