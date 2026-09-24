"""FD transport diagnostic cannot start a guest or attach a usable display."""

import sys
import os
import array
import socket
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import check_graphical_transport as transport


class RPCError(Exception):
    def get_error_code(self):
        return 55


@pytest.mark.parametrize('off,alive', [(False, True), (True, True), (True, False)])
def test_probe_refuses_active_vm_and_only_sends_impossible_index(off, alive):
    api = Mock(libvirtError=RPCError, VIR_ERR_OPERATION_INVALID=55)
    source = Mock()
    source.snapshot.return_value = ({}, off)
    source.connection.isAlive.return_value = int(alive)
    source.domain.openGraphics.side_effect = RPCError()
    with patch.object(transport.host, 'LibvirtSource', return_value=source):
        if not off:
            with pytest.raises(RuntimeError, match='domain-must-be-off'):
                transport.probe(api)
            source.domain.openGraphics.assert_not_called()
        else:
            result = transport.probe(api)
            assert result['outcome'] == ('passed' if alive else 'failed')
            index, descriptor, flags = source.domain.openGraphics.call_args.args
            assert index == 0xffffffff and flags == 0
            with pytest.raises(OSError):
                transport.os.fstat(descriptor)
    source.domain.create.assert_not_called()
    source.domain.destroyFlags.assert_not_called()
    source.domain.revertToSnapshot.assert_not_called()
    source.close.assert_called_once()


@pytest.mark.parametrize('args,uid', [(['check', 'extra'], 0), (['check'], 1000)])
def test_invalid_entrypoint_refuses_before_libvirt(args, uid):
    with patch.object(sys, 'argv', args), patch.object(transport.os, 'geteuid', return_value=uid), \
            patch.object(transport, 'probe') as probe:
        with pytest.raises(RuntimeError, match='graphics-probe:'):
            transport.main()
    probe.assert_not_called()


@pytest.mark.parametrize('send_fd', [False, True])
def test_receive_probe_detects_missing_rights_and_closes_received_socket(tmp_path, send_fd):
    evidence = tmp_path / ('long-evidence-' * 12)
    evidence.mkdir()
    paths = []
    local, remote = socket.socketpair()
    with local, remote:
        def fixture(args, **kwargs):
            assert args[:3] == ['/usr/bin/aa-exec', '--profile=libvirtd', '--']
            assert kwargs['timeout'] == 15
            paths.append(Path(args[-1]))
            assert len(os.fsencode(paths[-1])) < 108
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.connect(args[-1])
                remote.sendall(b'graphics-fd-fixture')
                peer.sendmsg([b'F'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                    array.array('i', [local.fileno()]))] if send_fd else [])
        result = transport.receive_probe(evidence, Mock(run=fixture))
        assert result['outcome'] == ('passed' if send_fd else 'failed')
        assert result['descriptor_count'] == int(send_fd)
        assert not paths[0].parent.exists()
        assert evidence.is_dir()
        local.close()
        remote.settimeout(1)
        try:
            assert remote.recv(1) == b''
        except ConnectionResetError:
            assert not send_fd  # Unread fixture bytes when no FD was exported.


def test_receive_probe_removes_runtime_socket_on_fixture_failure(tmp_path):
    paths = []

    def fail(args, **kwargs):
        paths.append(Path(args[-1]))
        raise RuntimeError('fixture failure')

    with pytest.raises(RuntimeError, match='fixture failure'):
        transport.receive_probe(tmp_path, Mock(run=fail))
    assert not paths[0].parent.exists()
