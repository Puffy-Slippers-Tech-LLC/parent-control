"""Authenticate one child bus connection without changing the broker's identity.

The short-lived child authenticates with Gio, but does not send Hello. After
its authenticated socket is transferred and the child is reaped, the broker
owns the stream and completes Hello on its existing private GLib context.
"""

import array
import errno
import os
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

from gi.repository import Gio, GLib


HELPER_PATH = "/usr/lib/oh-no-parent-control/broker/oh_no_parent_control/child_bus.py"
_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8", "HOME": "/nonexistent"}
# The helper may return only these fixed statuses, never exception text or
# addresses. Recreate public Gio identities so existing diagnostic projection
# preserves the failure category at the broker's reviewed source location.
_HELPER_ERRORS = {
    b"A": (Gio.dbus_error_quark, Gio.DBusError.AUTH_FAILED),
    b"T": (Gio.io_error_quark, Gio.IOErrorEnum.TIMED_OUT),
    b"D": (Gio.io_error_quark, Gio.IOErrorEnum.CLOSED),
    b"N": (Gio.io_error_quark, Gio.IOErrorEnum.NOT_FOUND),
    b"I": (Gio.io_error_quark, Gio.IOErrorEnum.INVALID_ARGUMENT),
    b"R": (Gio.io_error_quark, Gio.IOErrorEnum.NO_SPACE),
    b"W": (Gio.io_error_quark, Gio.IOErrorEnum.READ_ONLY),
    b"F": (Gio.dbus_error_quark, Gio.DBusError.FAILED),
}


def _address_path(address):
    # Only a single, literal local Unix socket; never autolaunch, TCP, escaped
    # paths or a fallback address list. The manager owns the fixed runtime path.
    match = re.fullmatch(r"unix:path=(/[^,;%\x00]+)(?:,guid=[0-9a-f]{32})?", address)
    if match is None:
        raise ValueError("invalid child bus address")
    return match[1]


def _validate_target(account, address):
    if (type(account.pw_uid) is not int or account.pw_uid <= 0 or
            type(account.pw_gid) is not int or account.pw_gid < 0):
        raise ValueError("invalid child bus identity")
    path = _address_path(address)
    status = os.lstat(path)
    if not stat.S_ISSOCK(status.st_mode) or status.st_uid != account.pw_uid:
        raise ValueError("unsafe child bus socket")
    return path


def _receive_descriptor(channel):
    descriptors = []
    try:
        payload, ancillary, flags, _address = channel.recvmsg(
            2, socket.CMSG_SPACE(4 * array.array("i").itemsize), socket.MSG_CMSG_CLOEXEC)
        valid = len(ancillary) == 1
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                received = array.array("i")
                received.frombytes(data[:len(data) - len(data) % received.itemsize])
                descriptors.extend(received)
                valid &= len(data) == received.itemsize
            else:
                valid = False
        truncated = flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC)
        if not ancillary and not truncated:
            if payload[:1] == b"E" and payload[1:] in _HELPER_ERRORS:
                domain, code = _HELPER_ERRORS[payload[1:]]
                raise GLib.Error.new_literal(domain(), "child bus authentication failed", code)
            if not payload:
                raise RuntimeError("child bus helper exited without a status")
        if (not valid or payload != b"S" or len(descriptors) != 1 or
                truncated):
            raise ValueError("invalid child bus descriptor message")
        return descriptors.pop()
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


class _ConnectionAttempt:
    def __init__(self, account, address, context, callback, timeout):
        self.account, self.address = account, address
        self.context, self.callback = context, callback
        self.deadline = time.monotonic() + timeout
        self.process = self.channel = self.guardian = self.stream = None
        self.descriptor = None
        self.cancellable = Gio.Cancellable()
        self.done = False
        self.pending = True
        self._hello_pending = False
        self._kill_sent = False
        self._cleanup_error_recorded = False
        self.result = None
        self.error = None
        # Defer even validation errors so the caller can record our identity
        # before receiving a completion callback.
        self.source = GLib.timeout_source_new(10)
        self.source.set_callback(self._poll)
        self.source.attach(context)

    def _poll(self, *_args):
        if self.done:
            return self._settle()
        try:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("child bus connection timed out")
            if self.process is None:
                self.path = _validate_target(self.account, self.address)
                self.channel, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                self.channel.setblocking(False)
                try:
                    self.process = subprocess.Popen(
                        ["/usr/bin/python3", "-I", HELPER_PATH, str(child.fileno()),
                         str(self.account.pw_uid), str(self.account.pw_gid), self.address],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        close_fds=True, pass_fds=(child.fileno(),),
                        user=self.account.pw_uid, group=self.account.pw_gid, extra_groups=(),
                        env=_ENVIRONMENT)
                finally:
                    child.close()
            if self.stream is not None:
                return GLib.SOURCE_CONTINUE
            if self.descriptor is None:
                try:
                    self.descriptor = _receive_descriptor(self.channel)
                except BlockingIOError:
                    if self.process.poll() is None:
                        return GLib.SOURCE_CONTINUE
                    # The helper can send its status between recvmsg and
                    # poll. Read that last queued packet before falling back
                    # to a missing-status error.
                    try:
                        self.descriptor = _receive_descriptor(self.channel)
                    except BlockingIOError:
                        raise RuntimeError("child bus helper exited without a status") from None
            # Never let two Gio worker threads consume the same endpoint.
            status = self.process.poll()
            if status is None:
                return GLib.SOURCE_CONTINUE
            if status != 0:
                raise RuntimeError("child bus authentication failed")
            self.channel.close()
            self.channel = None
            if not stat.S_ISSOCK(os.fstat(self.descriptor).st_mode):
                raise ValueError("invalid child bus descriptor")
            self.guardian = socket.socket(fileno=os.dup(self.descriptor))
            peer_uid = struct.unpack("3i", self.guardian.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]
            if (self.guardian.family != socket.AF_UNIX or
                    self.guardian.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM or
                    self.guardian.getpeername() != self.path or peer_uid != self.account.pw_uid):
                raise ValueError("invalid child bus transport")
            native_socket = Gio.Socket.new_from_fd(self.descriptor)
            self.descriptor = None  # Gio now owns this descriptor.
            self.stream = native_socket.connection_factory_create_connection()
            self._hello_pending = True
            try:
                Gio.DBusConnection.new(self.stream, None, Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                                       None, self.cancellable, self._connected)
            except Exception:
                self._hello_pending = False
                raise
        except Exception as error:
            self._finish(None, error)
            return GLib.SOURCE_CONTINUE if self.pending else GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _connected(self, _source, result, *_args):
        connection = None
        try:
            connection = Gio.DBusConnection.new_finish(result)
            connection.set_exit_on_close(False)
            if self.done:
                connection.close(None, None, None)
            elif time.monotonic() >= self.deadline:
                self._finish(None, TimeoutError("child bus connection timed out"))
                connection.close(None, None, None)
            else:
                self._finish(connection, None)
        except Exception as error:
            if not self.done:
                self._finish(None, error)
        finally:
            self._hello_pending = False
            self.stream = None
            if self.done:
                self._settle()

    def cancel(self):
        """Cancel on the owning context; completion waits for owned cleanup."""
        if not self.done:
            self._finish(None, InterruptedError("child bus connection was cancelled"))

    def _finish(self, connection, error):
        if self.done:
            return
        self.done = True
        self.result, self.error = connection, error
        if error is not None:
            self.cancellable.cancel()
        if self.guardian is not None:
            if error is not None:
                # Gio's implicit Hello does not honor its constructor's
                # cancellable. Interrupt via a separate owned socket, without
                # concurrently closing/mutating Gio objects or reusing its fd.
                try:
                    self.guardian.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        for name in ("guardian", "channel"):
            resource = getattr(self, name)
            setattr(self, name, None)
            if resource is not None:
                try:
                    resource.close()
                except OSError as cleanup_error:
                    self._cleanup_failed(cleanup_error)
        if self.descriptor is not None:
            descriptor, self.descriptor = self.descriptor, None
            try:
                os.close(descriptor)
            except OSError as cleanup_error:
                self._cleanup_failed(cleanup_error)
        self._settle()

    def _cleanup_failed(self, error):
        if not self._cleanup_error_recorded:
            self._cleanup_error_recorded = True
            # The isolated helper never calls this broker-only cleanup path.
            from common.oh_no_parent_control_ui.diagnostic_events import record_exception
            record_exception(error)

    def _settle(self):
        # Never block the private GLib context in wait(). Preserve the exact
        # Popen owner until poll() has reaped it, including after a failed kill
        # or waitpid. The helper also has its own three-second hard alarm.
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    if not self._kill_sent:
                        self.process.kill()
                        self._kill_sent = True
                    return GLib.SOURCE_CONTINUE
                self.process = None
            except (OSError, subprocess.TimeoutExpired) as error:
                self._cleanup_failed(error)
                return GLib.SOURCE_CONTINUE
        if self._hello_pending:
            return GLib.SOURCE_CONTINUE
        self.stream = None
        self.source.destroy()
        self.pending = False
        self._deliver()
        return GLib.SOURCE_REMOVE

    def _deliver(self):
        callback, self.callback = self.callback, None
        if callback is not None:
            callback(self.result, self.error)


def connect_child_bus(account, address, context, callback, *, timeout=2):
    """Start a bounded connection; callback(connection, error) runs on context.

    The caller supplies its validated child account and live-session address.
    It must push context as thread-default while dispatching, and cancel the
    returned attempt on that context during shutdown. Continue dispatching until
    attempt.pending is false before releasing the context. It remains true until
    the helper is reaped and any pending Gio Hello has completed. Cancellation
    closes the handoff fds and interrupts Hello via socket shutdown; cleanup and
    the final callback continue on the supplied context without a blocking wait.
    """
    if not 0 < timeout <= 10:
        raise ValueError("invalid child bus connection timeout")
    return _ConnectionAttempt(account, address, context, callback, timeout)


def _authenticate():
    # This file is the fixed installed helper, invoked with isolated Python.
    # No product imports, user configuration, arbitrary code or shell commands.
    signal.alarm(3)
    descriptor, uid, gid = map(int, sys.argv[1:4])
    channel = socket.socket(fileno=descriptor)
    try:
        if os.getuid() != uid or os.geteuid() != uid or os.getgid() != gid or uid <= 0:
            raise ValueError("invalid child bus helper identity")
        account = type("Account", (), {"pw_uid": uid, "pw_gid": gid})
        _validate_target(account, sys.argv[4])
        observer = Gio.DBusAuthObserver()
        observer.connect("allow-mechanism", lambda _observer, mechanism: mechanism == "EXTERNAL")
        connection = Gio.DBusConnection.new_for_address_sync(
            sys.argv[4], Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT, observer, None)
        connection.set_exit_on_close(False)
        channel.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
            array.array("i", [connection.get_stream().get_socket().get_fd()]))])
    except BaseException as error:
        try:
            channel.send(b"E" + _authentication_status(error))
        except OSError:
            pass
        os._exit(1)
    # Destructors would close/shutdown the shared endpoint after the handoff.
    os._exit(0)


def _authentication_status(error):
    if isinstance(error, ValueError):
        return b"I"
    if isinstance(error, GLib.Error):
        if (error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.PERMISSION_DENIED) or
                error.matches(Gio.dbus_error_quark(), Gio.DBusError.ACCESS_DENIED)):
            return b"A"
        if (error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CONNECTION_CLOSED) or
                error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CONNECTION_REFUSED) or
                error.matches(Gio.dbus_error_quark(), Gio.DBusError.DISCONNECTED)):
            return b"D"
        for status, (domain, code) in _HELPER_ERRORS.items():
            if error.matches(domain(), code):
                return status
    if isinstance(error, OSError):
        return {errno.EACCES: b"A", errno.EPERM: b"A", errno.ENOENT: b"N",
                errno.ETIMEDOUT: b"T", errno.ECONNREFUSED: b"D"}.get(error.errno, b"F")
    return b"F"


if __name__ == "__main__":
    try:
        _authenticate()
    except BaseException:
        os._exit(1)
