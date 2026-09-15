"""Lease-owned display collector. It never owns or launches a viewer window."""

import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import BASE, require


def log(event):
    print('e2e-watch: [' + event + ']', file=sys.stderr, flush=True)


class Publication:
    """Root-owned registry and socket; only the invoking user receives frames."""

    def __init__(self, uid, run):
        require(os.geteuid() == 0 and type(uid) is int and uid > 0
                and re.fullmatch('[0-9a-f]{32}', run), 'publication-context')
        self.run = run
        self.directory = BASE / str(uid)
        for directory in (BASE, self.directory):
            try:
                directory.mkdir(mode=0o755)
                directory.chmod(0o755)
            except FileExistsError:
                pass
            info = directory.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                    and stat.S_IMODE(info.st_mode) == 0o755
                    and directory.resolve() == directory, 'registry-owner')
        self.path = self.directory / (run + '.sock')
        self.current = self.directory / 'current.json'
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            self.server.bind(str(self.path))
            self.identity = self.path.lstat().st_ino
            self.path.chmod(0o666)
            self.server.listen(8)
        except BaseException:
            self.server.close()
            raise

    def publish(self):
        temporary = self.directory / (self.run + '.json')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'run': self.run}, stream)
            os.fchmod(stream.fileno(), 0o644)
        temporary.replace(self.current)

    def close(self):
        self.server.close()
        try:
            if self.path.lstat().st_ino == self.identity:
                self.path.unlink()
        except FileNotFoundError:
            pass
        try:
            if json.loads(self.current.read_text()) == {'run': self.run}:
                self.current.unlink()
        except FileNotFoundError:
            pass


class Observer:
    """Independent watchdog revokes only the collector's owned QEMU sockets.

    The user only receives shared memory. No viewer socket, process or window
    is involved in VM lifetime or cleanup. A stalled collector is disconnected
    after three seconds, including while the controller waits on guest work.
    """

    def __init__(self, display, uid, run):
        self.display = display
        self.child = self.pidfd = self.publication = self.thread = None
        self.control = self.listener = None
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.finished = threading.Event()
        self.cleanup_error = None
        remote_control = remote_listener = None
        try:
            self.publication = Publication(uid, run)
            self.control, remote_control = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.listener, remote_listener = socket.socketpair()
            descriptors = [remote_control.fileno(), display.fileno(), self.listener.fileno(),
                           remote_listener.fileno(), self.publication.server.fileno()]
            command = ['/usr/bin/python3', '-B', str(Path(__file__).with_name('e2e_watch_collector.py'))]
            for name, fd in zip(('control', 'display', 'listener', 'remote', 'server'), descriptors):
                command.extend(['--' + name, str(fd)])
            command.extend(['--uid', str(uid), '--run', run])
            self.child = subprocess.Popen(command, pass_fds=tuple(descriptors),
                stdin=subprocess.DEVNULL, env={'PATH': '/usr/bin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'})
            self.pidfd = os.pidfd_open(self.child.pid)
            self.control.sendall(b'start')
            self.control.settimeout(.25)
            self.thread = threading.Thread(target=self._monitor, name='e2e-watch', daemon=True)
            self.thread.start()
        except BaseException:
            self._reap()
            raise
        finally:
            for peer in (remote_control, remote_listener):
                if peer is not None:
                    peer.close()

    def _monitor(self):
        deadline = time.monotonic() + 5
        try:
            while not self.stop.is_set():
                try:
                    message = self.control.recv(16)
                except TimeoutError:
                    message = None
                if message in (b'ready', b'beat'):
                    deadline = time.monotonic() + 3
                    if message == b'ready':
                        self.publication.publish()
                        self.ready.set()
                        log('available')
                elif message == b'':
                    break
                if time.monotonic() > deadline:
                    log('collector-timeout')
                    break
        except Exception:
            log('collector-unavailable')
        finally:
            try:
                self._reap()
            except Exception as error:
                self.cleanup_error = error
                log('collector-cleanup-failed')
            finally:
                self.finished.set()

    def _reap(self):
        # Shutdown affects all duplicates, including an unresponsive child.
        # These sockets belong solely to D-Bus, never the automation VNC stream.
        for name in ('display', 'listener', 'control'):
            peer = getattr(self, name)
            if peer is not None:
                try:
                    peer.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                peer.close()
                setattr(self, name, None)
        if self.child is not None:
            try:
                self.child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                require(self.pidfd is not None, 'unrecorded-collector')
                try:
                    signal.pidfd_send_signal(self.pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.child.wait(timeout=2)
            self.child = None
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None
        if self.publication is not None:
            self.publication.close()
            self.publication = None

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=6)
            require(not self.thread.is_alive(), 'collector-cleanup-timeout')
            if self.cleanup_error is not None:
                # Preserve the pinned identity after an incomplete reap and
                # retry only that cleanup at the owning adapter boundary.
                self._reap()
                self.cleanup_error = None
        else:
            self._reap()


def start(adapter):
    """Optional feed failure disables viewing; never starts a user window."""
    uid = os.environ.get('PKEXEC_UID', '')
    if not uid.isdecimal() or int(uid) <= 0:
        return None
    observer = None
    try:
        observer = Observer(adapter.open_display(index=1), int(uid), adapter.run)
        if not observer.ready.wait(6) or observer.finished.is_set():
            observer.close()
            log('disabled')
            return None
        return observer
    except Exception:
        if observer is not None:
            observer.close()
        log('disabled')
        return None
    except BaseException:
        if observer is not None:
            observer.close()
        raise
