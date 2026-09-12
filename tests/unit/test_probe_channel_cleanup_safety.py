"""Admission interruptions and cleanup failures cannot replay or lose ownership."""

from dataclasses import replace
import os
import socket
from unittest.mock import Mock

import pytest

from oh_no_parent_control import probe_channel as channel


def selected(monkeypatch):
    adapter = channel.ProbeChannel()
    adapter._hello = channel.PeerHello(42, os.geteuid(), os.getegid(), "2" * 32)
    adapter._peer = Mock()
    adapter._admission_deadline = channel.time.monotonic() + 2
    monkeypatch.setattr(channel.select, "select", lambda *args: ([], [], []))
    return adapter, channel.AdmissionBinding(adapter._hello, ":1.5", "probe.service", "/job/1")


@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt])
@pytest.mark.parametrize("offset", [0, 7, 40])
def test_interrupted_admission_is_bound_consumed_and_never_replayed(monkeypatch, error, offset):
    adapter, binding = selected(monkeypatch)
    peer = adapter._peer
    sent = bytearray()

    def interrupted(payload):
        assert adapter.binding == binding and adapter.consumed
        sent.extend(payload[:offset])
        raise error("private transport detail")

    monkeypatch.setattr(adapter, "_send_admission", interrupted)
    with pytest.raises(error):
        adapter.admit(binding)
    assert adapter.failure == "admission-refused"
    assert adapter.binding == binding and adapter.consumed
    with pytest.raises(RuntimeError):
        adapter.admit(binding)
    with pytest.raises(RuntimeError):
        adapter.collect()
    assert len(sent) == offset
    assert adapter.close() and adapter.close()
    peer.close.assert_called_once()


def test_partial_send_continues_offset_and_half_closes_once(monkeypatch):
    adapter, binding = selected(monkeypatch)
    monkeypatch.setattr(adapter, "_wait", lambda *args, **kwargs: None)
    peer = adapter._peer
    peer.send.side_effect = [7, InterruptedError(), 33]
    adapter.admit(binding)
    payloads = [call.args[0] for call in peer.send.call_args_list]
    assert payloads == [channel._frame(b"A", binding.peer.invocation),
                        channel._frame(b"A", binding.peer.invocation)[7:]] + [payloads[1]]
    peer.shutdown.assert_called_once_with(socket.SHUT_WR)
    assert adapter.close()


@pytest.mark.parametrize("field,value", [("pid", 43), ("uid", 99999),
                                         ("invocation", "3" * 32)])
def test_wrong_or_stale_identity_closes_candidate_without_sending(monkeypatch, field, value):
    adapter, binding = selected(monkeypatch)
    peer = adapter._peer
    with pytest.raises(channel.ChannelRefused):
        adapter.admit(replace(binding, peer=replace(binding.peer, **{field: value})))
    assert adapter.binding is None and not adapter.consumed
    peer.send.assert_not_called()
    peer.close.assert_called_once()
    assert adapter.close()


def test_concurrent_operation_refuses_without_touching_owner(monkeypatch):
    adapter, binding = selected(monkeypatch)
    peer = adapter._peer
    with adapter._lock:
        for operation in (adapter.select, lambda: adapter.admit(binding), adapter.collect, adapter.close):
            with pytest.raises(RuntimeError, match="already running"):
                operation()
    assert adapter.failure is None and not adapter.consumed
    peer.close.assert_not_called()
    assert adapter.close()


def test_unlink_failure_retains_directory_for_scoped_retry(tmp_path, monkeypatch):
    adapter = channel.ProbeChannel()
    adapter._directory = os.open(tmp_path, os.O_DIRECTORY)
    adapter._socket_identity = (1, 2)
    adapter._socket_created = True
    info = Mock(st_dev=1, st_ino=2, st_mode=0o140700)
    monkeypatch.setattr(channel.os, "stat", lambda *args, **kwargs: info)
    unlink = Mock(side_effect=[PermissionError("private path"), None])
    monkeypatch.setattr(channel.os, "unlink", unlink)
    descriptor = adapter._directory
    assert not adapter.close()
    os.fstat(descriptor)
    assert adapter.close() and adapter.close()
    assert adapter._directory is None
    assert [call.kwargs for call in unlink.call_args_list] == [{"dir_fd": descriptor}] * 2
