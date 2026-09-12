"""Single-use native probe channel; never a systemd or policy receipt.

The generation owner supplies a private directory and retains it and the
immutable witness until unit settlement. A future manager adapter must verify
the binding before admit(), and terminal identity/exit after collect(). This
module compares peer credentials; it does not authenticate systemd metadata.
"""

from array import array
from dataclasses import dataclass
import logging
import os
import re
import select
import socket
import stat
import struct
import threading
import time


LOG = logging.getLogger("oh-no-parent-control.execution-probe")
FRAME_SIZE = 40
TIMEOUT = 2.0


@dataclass(frozen=True)
class PeerHello:
    pid: int
    uid: int
    gid: int
    invocation: str


@dataclass(frozen=True)
class AdmissionBinding:
    """Caller-verified manager coordinates, retained before any admission byte."""

    peer: PeerHello
    manager: str
    unit: str
    job: str


class ChannelRefused(Exception):
    """Fixed diagnostic only; never include wire bytes or paths."""


def _identity(info):
    return info.st_dev, info.st_ino


def _frame(stage, invocation):
    return b"ONP1" + stage + b"\0" * 3 + invocation.encode("ascii")


def _decode(data, stages):
    if (len(data) != FRAME_SIZE or data[:4] != b"ONP1" or
            data[4:5] not in stages or data[5:8] != b"\0" * 3 or
            re.fullmatch(rb"[0-9a-f]{32}", data[8:]) is None or
            data[8:] == b"0" * 32):
        raise ChannelRefused("invalid-frame")
    return data[4:5], data[8:].decode("ascii")


class ProbeChannel:
    """Serialized bounded operations, one candidate and no admission recovery.

    open() never replaces a path. close() removes only the recorded socket in
    the pinned private directory, never the caller's directory or witness.
    A mismatched socket remains untouched and cleanup returns False. As with
    the native payload, same-UID privileged mutation is outside the trust
    boundary; identity checks do not claim atomic unlink against hostile root.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._directory = None
        self._socket_identity = None
        self._socket_created = False
        self._listener = None
        self._peer = None
        self._started = False
        self._selected = False
        self._closing = False
        self._hello = None
        self._binding = None
        self._consumed = False
        self._result = None
        self._failure = None
        self._admission_deadline = None

    @property
    def binding(self):
        return self._binding

    @property
    def consumed(self):
        return self._consumed

    @property
    def result(self):
        return self._result

    @property
    def failure(self):
        return self._failure

    def _enter(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("probe channel operation already running")

    def _fail(self, category):
        if self._failure is None:
            self._failure = category
            LOG.info("execution probe channel outcome=%s", category)
        if self._peer is not None:
            self._peer.close()
            self._peer = None

    def open(self, directory):
        """Pin a caller-owned 0700 directory; create only its channel socket."""
        self._enter()
        try:
            if self._started or self._closing:
                raise RuntimeError("probe channel is single-use")
            self._started = True
            self._directory = os.open(directory, os.O_RDONLY | os.O_DIRECTORY |
                                      os.O_NOFOLLOW | os.O_CLOEXEC)
            info = os.fstat(self._directory)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ChannelRefused("unsafe-directory")
            self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener.setblocking(False)
            # Bind relative to the pinned directory without chdir or following
            # a replaced ancestor. Linux procfs fd resolution is kernel-owned.
            self._listener.bind(f"/proc/self/fd/{self._directory}/channel")
            self._socket_created = True
            info = os.stat("channel", dir_fd=self._directory, follow_symlinks=False)
            self._socket_identity = _identity(info)
            self._listener.listen(1)
        except BaseException:
            self._fail("open-refused")
            raise
        finally:
            self._lock.release()

    @staticmethod
    def _wait(peer, *, writing, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ChannelRefused("deadline")
        readable, writable, _ = select.select(
            [] if writing else [peer], [peer] if writing else [], [], remaining)
        if not (writable if writing else readable):
            raise ChannelRefused("deadline")

    def _receive(self, deadline, *, eof):
        data = bytearray()
        while True:
            self._wait(self._peer, writing=False, deadline=deadline)
            try:
                part, ancillary, flags, _ = self._peer.recvmsg(
                    FRAME_SIZE + 1 - len(data), socket.CMSG_SPACE(16 * 4),
                    socket.MSG_CMSG_CLOEXEC)
            except (BlockingIOError, InterruptedError):
                continue
            for level, kind, value in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    descriptors = array("i")
                    descriptors.frombytes(value[:len(value) - len(value) % descriptors.itemsize])
                    for descriptor in descriptors:
                        os.close(descriptor)
            if ancillary or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
                raise ChannelRefused("ancillary-refused")
            if not part:
                if eof and len(data) == FRAME_SIZE:
                    return bytes(data)
                raise ChannelRefused("unexpected-eof")
            data.extend(part)
            if len(data) > FRAME_SIZE:
                raise ChannelRefused("extra-frame-data")
            if not eof and len(data) == FRAME_SIZE:
                return bytes(data)

    def select(self):
        """Return the sole candidate's kernel credentials and parsed hello."""
        self._enter()
        try:
            if (self._listener is None or self._selected or self._closing or
                    self._failure is not None):
                raise RuntimeError("probe candidate unavailable")
            self._selected = True
            self._admission_deadline = time.monotonic() + TIMEOUT
            self._wait(self._listener, writing=False, deadline=self._admission_deadline)
            self._peer, _ = self._listener.accept()
            self._peer.setblocking(False)
            self._listener.close()
            self._listener = None
            pid, uid, gid = struct.unpack("3i", self._peer.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            if pid <= 0 or uid != os.geteuid():
                raise ChannelRefused("peer-refused")
            _, invocation = _decode(self._receive(self._admission_deadline, eof=False), (b"H",))
            self._hello = PeerHello(pid, uid, gid, invocation)
            return self._hello
        except BaseException:
            self._fail("selection-refused")
            raise
        finally:
            self._lock.release()

    def _send_admission(self, payload):
        offset = 0
        while offset < len(payload):
            self._wait(self._peer, writing=True, deadline=self._admission_deadline)
            try:
                count = self._peer.send(payload[offset:], socket.MSG_NOSIGNAL)
            except (BlockingIOError, InterruptedError):
                continue
            if count <= 0:
                raise ChannelRefused("send-refused")
            offset += count
        self._peer.shutdown(socket.SHUT_WR)

    def admit(self, binding):
        """Consume authorization before sending. Caller must verify metadata."""
        self._enter()
        try:
            if (self._hello is None or self._peer is None or self._consumed or
                    self._failure is not None or self._closing):
                raise RuntimeError("probe admission unavailable")
            if (not isinstance(binding, AdmissionBinding) or binding.peer != self._hello or
                    not binding.manager or not binding.unit or not binding.job):
                raise ChannelRefused("binding-refused")
            if select.select([self._peer], [], [], 0)[0]:
                raise ChannelRefused("peer-changed-before-admission")
            self._binding = binding
            self._consumed = True
            self._send_admission(_frame(b"A", self._hello.invocation))
        except BaseException:
            self._fail("admission-refused")
            raise
        finally:
            self._lock.release()

    def collect(self):
        """Retain one bounded result; it is never a terminal/policy receipt."""
        self._enter()
        try:
            if self._failure is not None:
                raise RuntimeError("probe result unavailable")
            if self._result is not None:
                return self._result
            if not self._consumed or self._peer is None or self._failure or self._closing:
                raise RuntimeError("probe result unavailable")
            stage, invocation = _decode(self._receive(time.monotonic() + TIMEOUT, eof=True),
                                        (b"X", b"F"))
            if invocation != self._binding.peer.invocation:
                raise ChannelRefused("invocation-refused")
            self._result = "executed" if stage == b"X" else "exec-failed"
            self._peer.close()
            self._peer = None
            return self._result
        except BaseException:
            self._fail("result-refused")
            raise
        finally:
            self._lock.release()

    def close(self):
        """Close owned descriptors and remove only the recorded socket inode.

        False retains the directory fd/identity for explicit cleanup recovery.
        Never infer process, manager, dispatch or witness settlement from True.
        """
        self._enter()
        try:
            self._closing = True
            for attribute in ("_peer", "_listener"):
                descriptor = getattr(self, attribute)
                if descriptor is not None:
                    descriptor.close()
                    setattr(self, attribute, None)
            if self._directory is not None:
                if self._socket_created:
                    try:
                        info = os.stat("channel", dir_fd=self._directory, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        if (not stat.S_ISSOCK(info.st_mode) or
                                _identity(info) != self._socket_identity):
                            LOG.info("execution probe channel cleanup=path-replaced")
                            return False
                        os.unlink("channel", dir_fd=self._directory)
                    self._socket_identity = None
                    self._socket_created = False
                os.close(self._directory)
                self._directory = None
            return True
        except OSError:
            LOG.info("execution probe channel cleanup=retry-needed")
            return False
        finally:
            self._lock.release()
