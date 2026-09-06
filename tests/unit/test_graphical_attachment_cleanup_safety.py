"""Attachment diagnostic preserves the lease owner and closes its own sockets."""

import json
import socket
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
import check_graphical_attachment as check
import graphical_attachment_probe as child
sys.path.pop(0)


@pytest.mark.parametrize('mode', ['daemon', 'caller'])
@pytest.mark.parametrize('fault', [None, 'identity', 'rpc', 'replacement', 'greeting'])
def test_attachment_checks_instance_and_closes_sockets(mode, fault):
    api = Mock()
    connection = api.open.return_value
    connection.getURI.return_value = child.URI
    domain = connection.lookupByUUIDString.return_value
    expected = {'uuid': 'fixture', 'id': 3, 'xml': '<fixture/>'}
    domain.UUIDString.return_value = expected['uuid']
    domain.ID.return_value = 4 if fault == 'identity' else 3
    domain.XMLDesc.return_value = expected['xml']
    peers = []

    def attach(index, *args):
        assert index == 0 and args[-1] == 0
        if fault == 'rpc':
            raise RuntimeError('fixture-rpc')
        if mode == 'daemon':
            local, remote = socket.socketpair()
            result = local.detach()
        else:
            remote = socket.fromfd(args[0], socket.AF_UNIX, socket.SOCK_STREAM)
            result = 0
        peers.append(remote)
        remote.sendall(b'bad greeting' if fault == 'greeting' else b'RFB 003.008\n')
        if fault == 'replacement':
            domain.ID.return_value = 4
        return result

    domain.openGraphicsFD.side_effect = domain.openGraphics.side_effect = attach
    try:
        if fault:
            with pytest.raises(RuntimeError):
                child.attach(api, expected, mode)
        else:
            assert child.attach(api, expected, mode)['rfb_greeting'] is True
        if fault == 'identity':
            domain.openGraphicsFD.assert_not_called()
            domain.openGraphics.assert_not_called()
        connection.close.assert_called_once()
        for peer in peers:
            peer.settimeout(1)
            try:
                assert peer.recv(1) == b''
            except ConnectionResetError:
                assert fault == 'replacement'
    finally:
        for peer in peers:
            peer.close()


def test_tracer_only_launches_fixed_child_with_kill_on_exit(tmp_path):
    lease, commands = Mock(), Mock()
    lease.source.uuid, lease.view.domain_id = 'fixture', 3
    lease.source.domain.XMLDesc.return_value = '<fixture/>'
    commands.run.return_value = json.dumps([
        {'mode': 'daemon', 'outcome': 'failed'}, {'mode': 'caller', 'outcome': 'passed'}]).encode()
    check.probe(lease, commands, tmp_path)
    args, = commands.run.call_args.args
    assert args[:4] == ['/usr/bin/strace', '--kill-on-exit', '-e', 'trace=recvmsg']
    assert args[6:8] == ['/usr/bin/python3', '-B']
    assert Path(args[8]).name == 'graphical_attachment_probe.py'
    assert len(args) == 9 and '-p' not in args
    assert commands.run.call_args.kwargs['timeout'] == 55
    assert lease.guard.call_count == 2
    lease.stop.assert_not_called()


def test_refused_guard_never_launches_tracer(tmp_path):
    lease, commands = Mock(), Mock()
    lease.guard.side_effect = RuntimeError('unowned')
    with pytest.raises(RuntimeError, match='unowned'):
        check.probe(lease, commands, tmp_path)
    commands.run.assert_not_called()


@pytest.mark.parametrize('argv,uid', [(['check', 'extra'], 0), (['check'], 1000)])
def test_invalid_invocation_refuses_before_creating_evidence(argv, uid):
    with patch.object(sys, 'argv', argv), patch.object(check.os, 'geteuid', return_value=uid), \
            patch.object(check.tempfile, 'mkdtemp') as create:
        with pytest.raises(RuntimeError, match='attachment:'):
            check.main()
    create.assert_not_called()
