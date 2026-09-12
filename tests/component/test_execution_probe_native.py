"""Real local gate/exec protocol; no systemd or policy-receipt qualification."""

from array import array
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import os
from pathlib import Path
import select
import shutil
import socket
import struct
import tempfile

import pytest

from oh_no_parent_control import probe_channel
from tests.support.paths import ROOT
from tests.support.terminal import capture


TOKEN = "1" * 32
INVOCATION = "2" * 32


def frame(stage, invocation=INVOCATION):
    return b"ONP1" + stage + b"\0" * 3 + invocation.encode("ascii")


def receive_to_eof(peer):
    data = b""
    while True:
        part = peer.recv(256)
        if not part:
            return data
        data += part
        assert len(data) <= 256, "unexpected oversized native output"


@pytest.fixture(scope="module")
def native_probe():
    # Keep sockaddr_un paths short; TemporaryDirectory removes only this fixture.
    with tempfile.TemporaryDirectory(prefix="onpc-admit-") as temporary:
        root = Path(temporary)
        runtime = root / "runtime"
        runtime.mkdir(mode=0o700)
        for kind in ("gate", "witness"):
            result, output = capture([
                "/usr/bin/cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                "-D_FORTIFY_SOURCE=3", "-fstack-protector-strong",
                f'-DPROBE_RUNTIME_ROOT="{runtime}"',
                str(ROOT / "tools" / f"execution_probe_{kind}.c"),
                "-o", str(root / kind),
            ], os.environ, None, timeout=30)
            assert result.returncode == 0, output
        yield root, runtime


@contextmanager
def broker_channel(directory):
    adapter = probe_channel.ProbeChannel()
    try:
        adapter.open(directory)
        yield adapter
    finally:
        assert adapter.close(), "owned channel cleanup incomplete"


def binding(hello):
    # Synthetic manager coordinates: these tests qualify only the local channel.
    return probe_channel.AdmissionBinding(hello, ":1.50", "probe.service", "/job/1")


@pytest.mark.parametrize("denied", [False, True], ids=["exec", "denied-exec"])
def test_broker_channel_admits_native_once_and_retains_result(native_probe, denied):
    root, runtime = native_probe
    directory = runtime / TOKEN
    directory.mkdir(mode=0o700)
    target = directory / "witness"
    shutil.copyfile(root / "witness", target)
    target.chmod(0o500)
    try:
        with broker_channel(directory) as adapter:
            with ThreadPoolExecutor(max_workers=1) as executor:
                process = executor.submit(capture, [str(root / "gate"), TOKEN],
                                          {"INVOCATION_ID": INVOCATION}, None, timeout=5)
                try:
                    hello = adapter.select()
                    assert Path(f"/proc/{hello.pid}/exe").resolve() == root / "gate"
                    if denied:
                        target.chmod(0o400)
                    adapter.admit(binding(hello))
                    assert adapter.binding.peer == hello and adapter.consumed
                    expected = "exec-failed" if denied else "executed"
                    assert adapter.collect() == expected
                    assert adapter.collect() == expected  # retained after native exit
                    assert process.result(timeout=5)[0].returncode == (70 if denied else 23)
                    with pytest.raises(RuntimeError):
                        adapter.admit(binding(hello))
                    assert adapter.result == expected  # failure cannot overwrite evidence
                finally:
                    adapter.close()
                    process.result(timeout=6)
        assert not (directory / "channel").exists() and target.exists()
    finally:
        shutil.rmtree(directory)


@contextmanager
def synthetic_peer(tmp_path):
    tmp_path.chmod(0o700)
    with broker_channel(tmp_path) as adapter:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(3)
            peer.connect(str(tmp_path / "channel"))
            yield adapter, peer


@pytest.mark.parametrize("payload", [b"", frame(b"H")[:-1], frame(b"X"),
                                    frame(b"H") * 2, b"x" * 8192,
                                    frame(b"H", "0" * 32), frame(b"H", "G" * 32)])
def test_broker_rejects_malformed_hello_without_admission(tmp_path, payload):
    with synthetic_peer(tmp_path) as (adapter, peer):
        peer.sendall(payload)
        peer.shutdown(socket.SHUT_WR)
        with pytest.raises(probe_channel.ChannelRefused):
            adapter.select()
        assert not adapter.consumed and adapter.binding is None


@pytest.mark.parametrize("payload", [b"", frame(b"X")[:-1], frame(b"H"),
                                    frame(b"X") * 2, b"x" * 8192,
                                    frame(b"X", "3" * 32)])
def test_broker_rejects_malformed_result_without_promotion(tmp_path, payload):
    with synthetic_peer(tmp_path) as (adapter, peer):
        peer.sendall(frame(b"H"))
        adapter.admit(binding(adapter.select()))
        assert receive_to_eof(peer) == frame(b"A")
        peer.sendall(payload)
        peer.shutdown(socket.SHUT_WR)
        with pytest.raises(probe_channel.ChannelRefused):
            adapter.collect()
        assert adapter.result is None and adapter.failure == "result-refused"
        with pytest.raises(RuntimeError):
            adapter.collect()


@pytest.mark.parametrize("phase", ["hello", "result"])
@pytest.mark.parametrize("count", [1, 40])
def test_broker_rejects_ancillary_and_closes_received_descriptors(tmp_path, phase, count):
    read_fd, write_fd = os.pipe()
    try:
        with synthetic_peer(tmp_path) as (adapter, peer):
            if phase == "result":
                peer.sendall(frame(b"H"))
                adapter.admit(binding(adapter.select()))
                assert receive_to_eof(peer) == frame(b"A")
            peer.sendmsg([frame(b"H" if phase == "hello" else b"X")], [
                (socket.SOL_SOCKET, socket.SCM_RIGHTS, array("i", [write_fd] * count))])
            os.close(write_fd)
            write_fd = None
            with pytest.raises(probe_channel.ChannelRefused):
                (adapter.select if phase == "hello" else adapter.collect)()
            assert select.select([read_fd], [], [], 1)[0] == [read_fd]
            assert os.read(read_fd, 1) == b""
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)


def test_broker_candidate_loss_or_duplicate_never_selects_replacement(tmp_path):
    with synthetic_peer(tmp_path) as (adapter, peer):
        peer.sendall(frame(b"H"))
        hello = adapter.select()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as replacement:
            with pytest.raises(ConnectionRefusedError):
                replacement.connect(str(tmp_path / "channel"))
        peer.shutdown(socket.SHUT_WR)
        with pytest.raises(probe_channel.ChannelRefused):
            adapter.admit(binding(hello))
        with pytest.raises(RuntimeError):
            adapter.select()
        assert not adapter.consumed


@pytest.mark.parametrize("phase", ["select", "hello", "admit", "result"])
def test_broker_deadlines_fail_closed(tmp_path, monkeypatch, phase):
    monkeypatch.setattr(probe_channel, "TIMEOUT", 0.02)
    if phase == "select":
        tmp_path.chmod(0o700)
        with broker_channel(tmp_path) as adapter:
            with pytest.raises(probe_channel.ChannelRefused):
                adapter.select()
        return
    with synthetic_peer(tmp_path) as (adapter, peer):
        if phase != "hello":
            peer.sendall(frame(b"H"))
            hello = adapter.select()
            if phase == "admit":
                adapter._admission_deadline = 0
            else:
                adapter.admit(binding(hello))
        with pytest.raises(probe_channel.ChannelRefused):
            if phase == "hello":
                adapter.select()
            elif phase == "admit":
                adapter.admit(binding(hello))
            else:
                adapter.collect()
        assert adapter.result is None


def test_channel_cleanup_preserves_replaced_socket_and_retries(tmp_path):
    tmp_path.chmod(0o700)
    with broker_channel(tmp_path) as adapter:
        path = tmp_path / "channel"
        original = tmp_path / "original"
        path.rename(original)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as replacement:
            replacement.bind(str(path))
            inode = path.stat().st_ino
            assert not adapter.close()
            assert path.stat().st_ino == inode
        path.unlink()  # this test owns the replacement
        original.rename(path)
        assert adapter.close() and adapter.close()


def test_channel_cleanup_uses_pinned_directory_after_path_replacement(tmp_path):
    directory = tmp_path / "attempt"
    directory.mkdir(mode=0o700)
    with broker_channel(directory) as adapter:
        directory.rename(tmp_path / "old")
        directory.mkdir(mode=0o700)
        replacement = directory / "channel"
        replacement.write_text("foreign")
        assert adapter.close()
        assert replacement.read_text() == "foreign"
        assert not (tmp_path / "old" / "channel").exists()


def test_existing_socket_is_never_claimed_or_removed(tmp_path):
    tmp_path.chmod(0o700)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        path = tmp_path / "channel"
        listener.bind(str(path))
        inode = path.stat().st_ino
        adapter = probe_channel.ProbeChannel()
        try:
            with pytest.raises(OSError):
                adapter.open(tmp_path)
        finally:
            assert adapter.close()
        assert path.stat().st_ino == inode


def test_socket_identity_capture_failure_retains_cleanup_uncertainty(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    adapter = probe_channel.ProbeChannel()
    real_stat = os.stat

    def failed_capture(path, *args, **kwargs):
        if path == "channel":
            raise OSError("identity read failed")
        return real_stat(path, *args, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(probe_channel.os, "stat", failed_capture)
            with pytest.raises(OSError):
                adapter.open(tmp_path)
        assert not adapter.close()
        assert (tmp_path / "channel").is_socket()
    finally:
        # The test owns this entire fresh fixture; production needs its outer
        # generation owner to reconcile an unrecorded socket, never adopt it.
        (tmp_path / "channel").unlink()
        assert adapter.close()


@pytest.mark.parametrize("mode", [0o755, 0o777])
def test_broker_refuses_shared_attempt_directory(tmp_path, mode):
    tmp_path.chmod(mode)
    adapter = probe_channel.ProbeChannel()
    try:
        with pytest.raises(probe_channel.ChannelRefused):
            adapter.open(tmp_path)
    finally:
        assert adapter.close()
    assert not (tmp_path / "channel").exists()


def test_broker_drops_already_queued_duplicate_without_admission(tmp_path):
    with synthetic_peer(tmp_path) as (adapter, peer):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as duplicate:
            duplicate.settimeout(2)
            duplicate.connect(str(tmp_path / "channel"))
            duplicate.sendall(frame(b"H"))
            peer.sendall(frame(b"H"))
            adapter.admit(binding(adapter.select()))
            assert receive_to_eof(peer) == frame(b"A")
            try:
                assert duplicate.recv(40) == b""
            except ConnectionResetError:
                pass
            peer.sendall(frame(b"X"))
            peer.shutdown(socket.SHUT_WR)
            assert adapter.collect() == "executed"


@contextmanager
def attempt(native_probe, *, invocation=INVOCATION, token=TOKEN, prepare=None):
    root, runtime = native_probe
    directory = runtime / TOKEN
    directory.mkdir(mode=0o700)
    target = directory / "witness"
    shutil.copyfile(root / "witness", target)
    target.chmod(0o500)
    try:
        if prepare is not None:
            prepare(target)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(directory / "channel"))
            listener.listen(2)
            listener.settimeout(4)
            with ThreadPoolExecutor(max_workers=1) as executor:
                process = executor.submit(
                    capture, [str(root / "gate"), token],
                    {"INVOCATION_ID": invocation}, None, timeout=5)
                try:
                    yield listener, process, target
                finally:
                    # Every started native child is joined by capture, including
                    # refusal/assertion failures. Never discover or signal by PID.
                    process.result(timeout=6)
    finally:
        shutil.rmtree(directory)


@contextmanager
def waiting_gate(listener):
    peer, _ = listener.accept()
    with peer:
        peer.settimeout(4)
        hello = b""
        while len(hello) < 40:
            part = peer.recv(40 - len(hello))
            assert part, "gate closed before hello"
            hello += part
        assert hello == frame(b"H")
        # Before authorization the gate is waiting, not running the witness.
        assert select.select([peer], [], [], 0.05)[0] == []
        yield peer


def admit(peer, payload=None):
    peer.sendall(frame(b"A") if payload is None else payload)
    peer.shutdown(socket.SHUT_WR)


def test_waiting_gate_execs_separate_witness_on_same_connection(native_probe):
    """ADMIT-01 native portion: hello, no target before A, real exec and EOF."""
    with attempt(native_probe) as (listener, process, _target):
        with waiting_gate(listener) as peer:
            pid, uid, _gid = struct.unpack("3i", peer.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            assert pid > 0 and uid == os.geteuid()
            assert Path(f"/proc/{pid}/exe").resolve() == native_probe[0] / "gate"
            admit(peer)
            assert receive_to_eof(peer) == frame(b"X")
        result, output = process.result(timeout=5)
        assert result.returncode == 23 and output == ""


@pytest.mark.parametrize("payload", [
    b"", frame(b"A")[:-1], frame(b"A") + b"extra", frame(b"A") * 2,
    frame(b"H"), frame(b"X"), frame(b"F"), frame(b"A", "3" * 32),
    b"ONP2" + frame(b"A")[4:], frame(b"A")[:5] + b"bad" + frame(b"A")[8:],
    b"x" * 8192,
], ids=["eof", "truncated", "extra", "duplicate", "hello", "execution",
        "failure", "invocation", "version", "reserved", "oversized"])
def test_bad_admission_never_reaches_witness(native_probe, payload):
    """ADMIT-08 native input refusal, including exact version/stage/framing."""
    with attempt(native_probe) as (listener, process, _target):
        with waiting_gate(listener) as peer:
            admit(peer, payload)
            # Oversized unread input may produce ECONNRESET on process exit.
            try:
                assert receive_to_eof(peer) == b""
            except ConnectionResetError:
                pass
        result, output = process.result(timeout=5)
        assert result.returncode == 70
        assert output == "execution-probe: gate-refused\n"


@pytest.mark.parametrize("mode", ["silence", "partial", "missing-eof"])
def test_admission_deadline_never_execs_or_replays(native_probe, mode):
    """ADMIT-06/09 native portion: incomplete admission expires in the gate."""
    with attempt(native_probe) as (listener, process, _target):
        with waiting_gate(listener) as peer:
            if mode != "silence":
                peer.sendall(frame(b"A")[:12] if mode == "partial" else frame(b"A"))
            assert receive_to_eof(peer) == b""
        result, output = process.result(timeout=5)
        assert result.returncode == 70
        assert output == "execution-probe: gate-refused\n"


@pytest.mark.parametrize("count", [1, 40], ids=["rights", "truncated-rights"])
def test_ancillary_descriptors_are_refused(native_probe, count):
    """ADMIT-08 native ancillary rejection, including a truncated control buffer."""
    read_fd, write_fd = os.pipe()
    try:
        with attempt(native_probe) as (listener, process, _target):
            with waiting_gate(listener) as peer:
                peer.sendmsg([frame(b"A")], [
                    (socket.SOL_SOCKET, socket.SCM_RIGHTS, array("i", [write_fd] * count))])
                os.close(write_fd)
                write_fd = None
                peer.shutdown(socket.SHUT_WR)
                assert receive_to_eof(peer) == b""
            result, _output = process.result(timeout=5)
            assert result.returncode == 70
            assert select.select([read_fd], [], [], 1)[0] == [read_fd]
            assert os.read(read_fd, 1) == b""  # No received pipe writer survives.
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)


def test_denied_exec_emits_failure_then_new_gate_still_waits(native_probe):
    """ADMIT-04 native portion; a replacement has no old connected capability."""
    with attempt(native_probe) as (listener, process, target):
        with waiting_gate(listener) as peer:
            target.chmod(0o400)  # Real pathname exec failure after preflight/hello.
            admit(peer)
            assert receive_to_eof(peer) == frame(b"F")
        result, _output = process.result(timeout=5)
        assert result.returncode == 70
    with attempt(native_probe) as (listener, process, _target):
        with waiting_gate(listener) as peer:
            peer.shutdown(socket.SHUT_WR)  # Never admit the replacement.
            assert receive_to_eof(peer) == b""
        assert process.result(timeout=5)[0].returncode == 70


@pytest.mark.parametrize("invocation", ["", "0" * 32, "a" * 31, "a" * 33,
                                         "G" * 32, "private-input"])
def test_invalid_invocation_refuses_before_connect_without_disclosure(native_probe, invocation):
    with attempt(native_probe, invocation=invocation) as (listener, process, _target):
        result, output = process.result(timeout=5)
        assert result.returncode == 70
        assert output == "execution-probe: gate-refused\n"
        assert select.select([listener], [], [], 0)[0] == []


def test_gate_does_not_reconnect_after_selected_connection_loss(native_probe):
    """ADMIT-12 native portion: EOF cannot replay admission or create a new peer."""
    with attempt(native_probe) as (listener, process, _target):
        with waiting_gate(listener):
            pass
        assert process.result(timeout=5)[0].returncode == 70
        assert select.select([listener], [], [], 0)[0] == []


def test_witness_refuses_without_inherited_socket(native_probe):
    result, output = capture([str(native_probe[0] / "witness"), INVOCATION],
                             {}, None, timeout=5)
    assert result.returncode == 70
    assert output == "execution-probe: witness-refused\n"


@pytest.mark.parametrize("token", ["../witness", "0" * 32, "a" * 33, "A" * 32])
def test_gate_cannot_dispatch_arbitrary_paths(native_probe, token):
    with attempt(native_probe, token=token) as (listener, process, _target):
        result, output = process.result(timeout=5)
        assert result.returncode == 70
        assert output == "execution-probe: gate-refused\n"
        assert select.select([listener], [], [], 0)[0] == []


@pytest.mark.parametrize("kind", ["writable-target", "non-executable", "symlink",
                                  "shared-directory"])
def test_unsafe_path_preflight_refuses_before_hello(native_probe, kind):
    def prepare(target):
        if kind == "writable-target":
            target.chmod(0o700)
        elif kind == "non-executable":
            target.chmod(0o400)
        elif kind == "symlink":
            target.unlink()
            target.symlink_to(native_probe[0] / "witness")
        else:
            target.parent.chmod(0o755)

    with attempt(native_probe, prepare=prepare) as (listener, process, _target):
        assert process.result(timeout=5)[0].returncode == 70
        assert select.select([listener], [], [], 0)[0] == []


def test_fragmented_admission_is_accepted_only_after_write_eof(native_probe):
    with attempt(native_probe) as (listener, process, _target):
        with waiting_gate(listener) as peer:
            admission = frame(b"A")
            peer.sendall(admission[:7])
            assert select.select([peer], [], [], 0.05)[0] == []
            peer.sendall(admission[7:])
            assert select.select([peer], [], [], 0.05)[0] == []
            peer.shutdown(socket.SHUT_WR)
            assert receive_to_eof(peer) == frame(b"X")
        assert process.result(timeout=5)[0].returncode == 23
