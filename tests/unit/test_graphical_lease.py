"""Host-safe adapter checks: mocked VM, real display socket ownership."""

import array
import socket
import stat
import struct
from unittest.mock import MagicMock, Mock, patch
import xml.etree.ElementTree as ET

import pytest

from test_system_runner import lease_rig, rig, runner, xml, UUID, RUN

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
import graphical_lease as graphical
sys.path.pop(0)


@pytest.fixture
def prepared(lease_rig):
    lease, current = lease_rig
    graphics = lease.source.api.open.return_value
    graphics.getURI.return_value = graphical.URI
    domain = graphics.lookupByUUIDString.return_value
    domain.UUIDString.return_value = lease.source.uuid
    domain.ID.side_effect = lambda: current['id']
    domain.XMLDesc.side_effect = lambda *_: current['xml']
    lease.view.graphics_type = 'vnc'
    with lease:
        lease.prepare()
        yield lease, current


def test_vnc_isolation_removes_all_host_listeners_and_shares():
    root = ET.fromstring(runner.isolated_xml(xml(), UUID, RUN, graphics_type='vnc'))
    runner.validate_private_vnc(root)
    assert root.find('devices/graphics').attrib == {'type': 'vnc'}
    assert root.find('devices/disk/source').get('file') == '/image'
    for name in ('filesystem', 'channel', 'redirdev', 'hostdev'):
        assert not root.findall('devices/' + name)


@pytest.mark.parametrize('display', [
    '<graphics type="vnc"><listen type="none"/></graphics>',
    '<graphics type="vnc" port="-1" autoport="no"><listen type="none"/></graphics>',
])
def test_accepts_only_documented_non_listening_vnc_normalization(display):
    runner.validate_private_vnc(ET.fromstring('<domain><devices>' + display + '</devices></domain>'))


@pytest.mark.parametrize('display', [
    '', '<graphics type="spice"><listen type="none"/></graphics>',
    '<graphics type="vnc" port="5900"><listen type="none"/></graphics>',
    '<graphics type="vnc" autoport="yes"><listen type="none"/></graphics>',
    '<graphics type="vnc" socket="/tmp/public"><listen type="none"/></graphics>',
    '<graphics type="vnc" listen="127.0.0.1"><listen type="none"/></graphics>',
    '<graphics type="vnc"><listen type="address" address="127.0.0.1"/></graphics>',
    '<graphics type="vnc"><listen type="none"/><listen type="socket"/></graphics>',
    '<graphics type="vnc"><listen type="none"/><clipboard copypaste="yes"/></graphics>',
    '<graphics type="vnc"><listen type="none" address="127.0.0.1"/></graphics>',
    '<graphics type="vnc"><listen type="none"/></graphics>' * 2,
])
def test_changed_or_exposed_endpoint_is_refused(display):
    with pytest.raises(runner.Error, match='guard:graphics-'):
        runner.validate_private_vnc(ET.fromstring('<domain><devices>' + display + '</devices></domain>'))


def test_unsupported_graphics_refuses_before_lease_mutation(lease_rig):
    lease, _ = lease_rig
    lease.view.graphics_type = 'other'
    with pytest.raises(runner.Error, match='graphics-type'):
        lease.__enter__()
    lease.source.domain.create.assert_not_called()
    lease.source.domain.revertToSnapshot.assert_not_called()
    assert lease.fd is None


def test_backend_off_on_off_sequence_never_restores_within_attempt(prepared):
    lease, _ = prepared
    adapter = graphical.Adapter(lease)
    initial_restores = lease.source.domain.revertToSnapshot.call_count
    assert adapter.request('off', adapter.run) == 'ok'
    assert adapter.request('status', adapter.run) == 'off'
    assert adapter.request('on', adapter.run) == 'ok'
    assert adapter.request('status', adapter.run) == 'on'
    assert adapter.request('off', adapter.run) == 'ok'
    assert adapter.request('off', adapter.run) == 'ok'
    assert adapter.request('status', adapter.run) == 'off'
    assert lease.source.domain.revertToSnapshot.call_count == initial_restores
    assert adapter.events == ['initial-off', 'status-off', 'poweron', 'status-on',
                              'poweroff', 'poweroff', 'status-off']
    lease.source.domain.create.assert_called_once()
    assert lease.state['phase'] != 'complete'  # Outer lease still owns cleanup.
    with pytest.raises(RuntimeError, match='unexpected-poweron'):
        adapter.request('on', adapter.run)


@pytest.mark.parametrize('action,run,category', [
    ('on', None, 'unexpected-poweron'), ('graphics', None, 'not-running'),
    ('restore', None, 'unknown-action'), ('off', 'b' * 32, 'wrong-run'),
])
def test_invalid_callback_does_not_start_or_restore(prepared, action, run, category):
    lease, _ = prepared
    adapter = graphical.Adapter(lease)
    restores = lease.source.domain.revertToSnapshot.call_count
    with pytest.raises(RuntimeError, match=category):
        adapter.request(action, adapter.run if run is None else run)
    lease.source.domain.create.assert_not_called()
    assert lease.source.domain.revertToSnapshot.call_count == restores


def start_adapter(lease):
    adapter = graphical.Adapter(lease)
    adapter.request('off', adapter.run)
    adapter.request('on', adapter.run)
    return adapter


def test_serial_pipes_survive_initial_off_and_close_before_actual_stop(prepared):
    lease, _ = prepared
    adapter = graphical.Adapter(lease)
    adapter.serial = Mock()
    adapter.request('off', adapter.run)
    adapter.request('off', adapter.run)
    adapter.serial.close.assert_not_called()
    adapter.request('on', adapter.run)
    def closed():
        assert not lease.view.snapshot()[1]
    adapter.serial.close.side_effect = closed
    adapter.request('off', adapter.run)
    adapter.serial.close.assert_called_once()


def test_graphics_uses_public_fd_and_stop_revokes_transferred_duplicate(prepared):
    lease, _ = prepared
    adapter = start_adapter(lease)
    connection = lease.source.api.open.return_value
    domain = connection.lookupByUUIDString.return_value
    peers = []
    def attach(index, flags):
        assert (index, flags) == (0, 0)
        local, remote = socket.socketpair()
        peers.append(remote)
        return local.detach()
    domain.openGraphicsFD.side_effect = attach
    display = adapter.request('graphics', adapter.run)
    with peers[0] as remote:
        connection.close.assert_called_once()
        lease.source.connection.close.assert_not_called()
        lease.source.domain.openGraphicsFD.assert_not_called()
        sender, receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        with sender, receiver:
            sender.sendmsg([b'ok\n'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                        array.array('i', [display.fileno()]))])
            data, ancillary, flags, _ = receiver.recvmsg(16, socket.CMSG_SPACE(array.array('i').itemsize))
            assert data == b'ok\n' and flags == 0
            descriptors = array.array('i')
            descriptors.frombytes(ancillary[0][2])
            assert len(descriptors) == 1
        with socket.socket(fileno=descriptors[0]) as transferred:
            transferred.sendall(b'framebuffer')
            assert remote.recv(32) == b'framebuffer'
            adapter.request('off', adapter.run)
            remote.settimeout(1)
            assert remote.recv(32) == b''
            with pytest.raises(BrokenPipeError):
                transferred.sendall(b'late input')
        assert display.fileno() == -1


@pytest.mark.parametrize('change', ['domain', 'marker', 'listener', 'disk'])
@pytest.mark.parametrize('action', ['off', 'graphics'])
def test_replaced_identity_refuses_controls_and_display(prepared, change, action):
    lease, current = prepared
    adapter = start_adapter(lease)
    original = dict(current)
    if change == 'domain':
        current['id'] += 1
    elif change == 'marker':
        current['xml'] = current['xml'].replace(adapter.run, 'b' * 32)
    elif change == 'listener':
        current['xml'] = current['xml'].replace('type="none"', 'type="address"')
    else:
        lease.source.layout['disk'] += '-replacement'
    shutdowns = lease.source.shutdown_calls
    try:
        with pytest.raises((runner.Error, FileNotFoundError)):
            adapter.request(action, adapter.run)
        lease.source.domain.openGraphicsFD.assert_not_called()
        lease.source.domain.destroyFlags.assert_not_called()
        assert lease.source.shutdown_calls == shutdowns
    finally:
        current.update(original)
        if change == 'disk':
            lease.source.layout['disk'] = lease.source.layout['disk'].removesuffix('-replacement')


def test_replacement_during_fd_acquisition_closes_fd_before_return(prepared):
    lease, current = prepared
    adapter = start_adapter(lease)
    peers = []
    original_id = current['id']
    def replaced(index, flags):
        local, remote = socket.socketpair()
        peers.append(remote)
        current['id'] += 1
        return local.detach()
    lease.source.api.open.return_value.lookupByUUIDString.return_value.openGraphicsFD.side_effect = replaced
    try:
        with pytest.raises(runner.Error, match='domain-replaced'):
            adapter.request('graphics', adapter.run)
        assert adapter.display is None
        with peers[0] as remote:
            remote.settimeout(1)
            assert remote.recv(32) == b''
    finally:
        current['id'] = original_id


@pytest.mark.parametrize('close_fails', [False, True])
def test_graphics_rpc_disconnect_preserves_lifecycle_cleanup(prepared, close_fails):
    lease, _ = prepared
    adapter = start_adapter(lease)
    connection = lease.source.api.open.return_value
    domain = connection.lookupByUUIDString.return_value
    failure = RuntimeError('fixture RPC disconnected')
    domain.openGraphicsFD.side_effect = failure
    if close_fails:
        connection.close.side_effect = RuntimeError('fixture close failed')
    with pytest.raises(RuntimeError) as caught:
        adapter.request('graphics', adapter.run)
    assert caught.value is failure
    assert adapter.display is None
    lease.source.connection.close.assert_not_called()
    adapter.request('off', adapter.run)
    assert lease.source.off


@pytest.mark.parametrize('fault', ['uri', 'uuid', 'id', 'xml'])
def test_separate_graphics_connection_identity_checked_before_attach(prepared, fault):
    lease, _ = prepared
    adapter = start_adapter(lease)
    connection = lease.source.api.open.return_value
    domain = connection.lookupByUUIDString.return_value
    if fault == 'uri':
        connection.getURI.return_value = 'qemu:///session'
    elif fault == 'uuid':
        domain.UUIDString.return_value = 'replacement'
    elif fault == 'id':
        domain.ID.side_effect = lambda: lease.view.domain_id + 1
    else:
        domain.XMLDesc.side_effect = lambda *_: '<replacement/>'
    with pytest.raises(RuntimeError, match='graphics:'):
        adapter.request('graphics', adapter.run)
    domain.openGraphicsFD.assert_not_called()
    connection.close.assert_called_once()
    lease.source.connection.close.assert_not_called()


def test_released_lease_refuses_callback_before_libvirt(prepared):
    lease, _ = prepared
    adapter = graphical.Adapter(lease)
    descriptor = lease.fd
    lease.fd = None
    try:
        with patch.object(lease, 'guard') as guard:
            with pytest.raises(RuntimeError, match='expired-lease'):
                adapter.request('off', adapter.run)
            guard.assert_not_called()
    finally:
        lease.fd = descriptor


def test_server_refuses_unprivileged_use_before_opening_socket(tmp_path):
    with patch.object(graphical.os, 'geteuid', return_value=1000), \
            patch.object(graphical.socket, 'socket') as create:
        with pytest.raises(RuntimeError, match='root-required'):
            graphical.CallbackServer(Mock(), tmp_path)
    create.assert_not_called()


def test_callback_failure_does_not_export_paths_or_exceptions(capsys):
    with patch.object(graphical, 'callback', side_effect=RuntimeError('sensitive backend text')):
        assert graphical.main(['--socket', '/private/path', '--run', RUN, 'off']) == 2
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == 'graphical-lease: [callback-failed]\n'


@pytest.fixture
def rpc(tmp_path):
    """Service logic with kernel peer/packet delivery mocked; no privileged bind."""
    server = object.__new__(graphical.CallbackServer)
    server.directory = tmp_path
    metadata = tmp_path.stat()
    server.identity = (metadata.st_dev, metadata.st_ino)
    server.adapter = Mock()
    server.adapter.request.return_value = 'ok'
    server.listener = Mock()
    peer = MagicMock()
    peer.__enter__.return_value = peer
    peer.getsockopt.return_value = struct.pack('3i', 1234, 0, 0)
    peer.recvmsg.return_value = (f'off {RUN}\n'.encode(), [], 0, None)
    server.listener.accept.return_value = (peer, None)
    root_metadata = Mock(st_mode=stat.S_IFDIR | 0o700, st_uid=0,
                         st_dev=metadata.st_dev, st_ino=metadata.st_ino)
    with patch.object(Path, 'lstat', return_value=root_metadata):
        yield server, peer, root_metadata


def test_callback_transport_dispatches_exact_request(rpc):
    server, peer, _ = rpc
    assert server.serve_once()
    server.adapter.request.assert_called_once_with('off', RUN)
    peer.sendall.assert_called_once_with(b'ok\n')
    peer.settimeout.assert_called_once_with(2)


@pytest.mark.parametrize('fault', ['peer', 'oversize', 'malformed', 'directory', 'ownership'])
def test_callback_transport_refuses_before_dispatch_and_revokes_display(rpc, fault):
    server, peer, metadata = rpc
    if fault == 'peer':
        peer.getsockopt.return_value = struct.pack('3i', 1234, 1000, 1000)
    elif fault == 'oversize':
        peer.recvmsg.return_value = (b'x' * 128, [], socket.MSG_TRUNC, None)
    elif fault == 'malformed':
        peer.recvmsg.return_value = (f'off {RUN}\nextra'.encode(), [], 0, None)
    elif fault == 'directory':
        metadata.st_ino += 1
    else:
        server.adapter.revalidate.side_effect = RuntimeError('graphics:expired-lease')
    with pytest.raises(RuntimeError):
        server.serve_once()
    server.adapter.request.assert_not_called()
    server.adapter.close_display.assert_called_once()


def test_idle_service_still_checks_ownership(rpc):
    server, _, _ = rpc
    server.listener.accept.side_effect = TimeoutError
    assert server.serve_once() is False
    server.adapter.revalidate.assert_called_once()


def test_disconnected_callback_revokes_display_and_retains_original_failure(rpc):
    server, peer, _ = rpc
    failure = BrokenPipeError('private peer detail')
    peer.sendall.side_effect = failure
    with pytest.raises(BrokenPipeError) as caught:
        server.serve_once()
    assert caught.value is failure
    server.adapter.close_display.assert_called_once()


def test_server_close_revokes_display_without_signalling_processes(rpc):
    server, _, _ = rpc
    server.close()
    server.adapter.close_display.assert_called_once()
    server.listener.close.assert_called_once()


@pytest.mark.parametrize('field,value', [('st_uid', 1000), ('st_mode', stat.S_IFDIR | 0o755),
                                       ('st_mode', stat.S_IFLNK | 0o700)])
def test_server_refuses_unsafe_directory_before_binding(tmp_path, field, value):
    metadata = Mock(st_uid=0, st_mode=stat.S_IFDIR | 0o700)
    setattr(metadata, field, value)
    with patch.object(graphical.os, 'geteuid', return_value=0), \
            patch.object(Path, 'lstat', return_value=metadata), \
            patch.object(graphical.socket, 'socket') as create:
        with pytest.raises(RuntimeError, match='private-directory'):
            graphical.CallbackServer(Mock(), tmp_path)
    create.assert_not_called()


def test_graphics_reply_transfers_only_opened_descriptor(rpc):
    server, peer, _ = rpc
    peer.recvmsg.return_value = (f'graphics {RUN}\n'.encode(), [], 0, None)
    display, remote = socket.socketpair()
    with display, remote:
        server.adapter.request.return_value = display
        assert server.serve_once()
        data, ancillary = peer.sendmsg.call_args.args
        assert data == [b'ok\n']
        level, kind, descriptors = ancillary[0]
        assert (level, kind) == (socket.SOL_SOCKET, socket.SCM_RIGHTS)
        assert list(descriptors) == [display.fileno()]
        assert display.fileno() >= 0  # Controller keeps a revocable original.


@pytest.mark.parametrize('action,result,code', [
    ('on', b'ok\n', 0), ('off', b'ok\n', 0),
    ('status', b'on\n', 1), ('status', b'off\n', 0),
])
def test_public_callback_exit_status_matches_generalhw(action, result, code):
    with patch.object(graphical.socket, 'socket') as create:
        peer = create.return_value.__enter__.return_value
        peer.recv.return_value = result
        assert graphical.callback('/private/generalhw.sock', RUN, action) == code
        peer.sendall.assert_called_once_with(f'{action} {RUN}\n'.encode())
        peer.settimeout.assert_called_once_with(240)


@pytest.mark.parametrize('path', ['/tmp/with space/socket', '/tmp/a;echo', 'relative'])
def test_backend_command_arguments_refuse_ambiguous_paths(path):
    with pytest.raises(RuntimeError, match='invalid-command-arguments'):
        graphical.lifecycle_variables(path, RUN)


def test_public_command_variables_use_only_lifecycle_callback_cli():
    variables = graphical.lifecycle_variables('/tmp/private/generalhw.sock', RUN)
    assert variables['GENERAL_HW_CMD_DIR'] == '/usr/bin'
    for command, action in (('POWERON', 'on'), ('POWEROFF', 'off'), ('IS_SHUTDOWN', 'status')):
        assert variables[f'GENERAL_HW_{command}_CMD'] == 'python3'
        arguments = variables[f'GENERAL_HW_{command}_ARGS'].split(' ')
        assert arguments[:2] == ['-B', str(Path(graphical.__file__).resolve())]
        assert arguments[2:] == ['--socket', '/tmp/private/generalhw.sock', '--run', RUN, action]
