#!/usr/bin/python3
"""Private generalhw TCP bridge and namespace-owned backend lifetime.

Internal plumbing: the controller still owns the lease and services callbacks.
The namespace is containment for trusted test tools, not a sandbox for hostile
root code. No VM APIs, process discovery, or host TCP listeners live here.
"""

import argparse
import array
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

from owned_commands import Commands, require


PORT = 5900
LIMIT = 256 * 1024
NAMESPACES = ('net', 'pid', 'mnt')


def log(event):
    # Only fixed categories; backend output belongs in the private working dir.
    print('graphical-worker: [' + event + ']', file=sys.stderr, flush=True)


def namespace_ids():
    # These are our own namespace identities, never a process ownership scan.
    return tuple(os.stat('/proc/self/ns/' + name).st_ino for name in NAMESPACES)


def require_private_namespace(original):
    require(os.geteuid() == 0 and os.getpid() == 1,
            'worker:namespace-init-required')
    require(len(original) == 3 and all(a != b for a, b in zip(original, namespace_ids())),
            'worker:namespace-not-isolated')
    require(os.stat('/proc/1/ns/pid').st_ino == namespace_ids()[1],
            'worker:proc-not-isolated')


def graphics_fd(path, run):
    """Receive exactly one revocable display FD from the lease controller."""
    require(re.fullmatch(r'[0-9a-f]{32}', run) is not None, 'worker:invalid-run')
    descriptors = array.array('i')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
            peer.settimeout(5)
            peer.connect(str(path))
            _, uid, _ = struct.unpack('3i', peer.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
            require(uid == 0, 'worker:controller-peer')
            peer.sendall(f'graphics {run}\n'.encode('ascii'))
            packet, ancillary, flags, _ = peer.recvmsg(
                16, socket.CMSG_SPACE(16 * descriptors.itemsize), socket.MSG_CMSG_CLOEXEC)
            for level, kind, data in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    descriptors.frombytes(data[:len(data) - len(data) % descriptors.itemsize])
            require(packet == b'ok\n' and not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC)
                    and len(descriptors) == 1, 'worker:graphics-refused')
        descriptor = descriptors.pop()
        try:
            display = socket.socket(fileno=descriptor)
        except BaseException:
            os.close(descriptor)
            raise
        try:
            require(display.type == socket.SOCK_STREAM, 'worker:graphics-not-stream')
            display.getpeername()
            return display
        except BaseException:
            display.close()
            raise
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


class Bridge:
    """One VNC connection, bounded buffers, no interpretation or capture."""

    def __init__(self, original, path, run):
        require_private_namespace(original)  # Must precede even socket creation.
        self.path, self.run = path, run
        self.ends = []
        self.pending = [bytearray(), bytearray()]
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.listener.bind(('127.0.0.1', PORT))
            self.listener.listen(1)
            self.listener.setblocking(False)
        except BaseException:
            self.listener.close()
            raise

    def disconnect(self):
        for endpoint in self.ends:
            endpoint.close()
        self.ends = []
        self.pending = [bytearray(), bytearray()]

    def step(self, control):
        reads = [control, self.listener]
        writes = []
        for index, endpoint in enumerate(self.ends):
            if len(self.pending[1 - index]) < LIMIT:
                reads.append(endpoint)
            if self.pending[index]:
                writes.append(endpoint)
        readable, writable, _ = select.select(reads, writes, [], 0.1)
        if control in readable:
            # EOF, stop, or any unexpected controller packet ends containment.
            return False
        if self.listener in readable:
            incoming, _ = self.listener.accept()
            if self.ends:
                incoming.close()
            else:
                try:
                    display = graphics_fd(self.path, self.run)
                except BaseException:
                    incoming.close()
                    raise
                self.ends = [incoming, display]
                for endpoint in self.ends:
                    endpoint.setblocking(False)
                log('display-connected')
        try:
            for index, endpoint in enumerate(self.ends):
                if endpoint in readable:
                    data = endpoint.recv(min(65536, LIMIT - len(self.pending[1 - index])))
                    if not data:
                        self.disconnect()
                        log('display-disconnected')
                        break
                    self.pending[1 - index].extend(data)
                if endpoint in writable:
                    sent = endpoint.send(self.pending[index])
                    del self.pending[index][:sent]
        except (ConnectionError, BrokenPipeError):
            self.disconnect()
            log('display-disconnected')
        return True

    def close(self):
        self.disconnect()
        self.listener.close()


class Worker:
    """Controller handle; pin the spawned supervisor before authorizing work.

    Close before closing CallbackServer / finishing Lease. Control EOF normally
    exits namespace init. A bounded fallback signals only the pinned unshare
    supervisor; --kill-child=KILL then ends its namespace, including descendants.
    The backend never inherits the controller socket or lease lock descriptor.
    """

    def __init__(self, directory, callback_path, run, command):
        require(os.geteuid() == 0, 'worker:root-required')
        directory = Path(directory)
        metadata = directory.lstat()
        require(directory.is_absolute() and directory.resolve() == directory and
                stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == 0 and
                stat.S_IMODE(metadata.st_mode) == 0o700, 'worker:private-directory')
        require(Path(callback_path).is_absolute() and
                re.fullmatch(r'[0-9a-f]{32}', run) is not None and command and
                Path(command[0]).is_absolute(), 'worker:invalid-arguments')
        self.child = None
        self.pidfd = None
        self.control, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.ready = False
        self.result = None
        try:
            args = ['/usr/bin/unshare', '--mount', '--net', '--pid', '--fork',
                    '--kill-child=KILL', '--mount-proc', '--propagation', 'private',
                    '/usr/bin/python3', '-B', str(Path(__file__).resolve()),
                    '--control-fd', str(remote.fileno()), '--original',
                    *(str(value) for value in namespace_ids()),
                    '--socket', str(callback_path), '--run', run, '--', *command]
            fd = os.open(directory / 'worker-private.log',
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as output:
                self.child = subprocess.Popen(args, cwd=directory, stdin=subprocess.DEVNULL,
                                              stdout=output, stderr=output,
                                              pass_fds=(remote.fileno(),),
                                              env={'PATH': '/usr/bin:/usr/sbin:/bin',
                                                   'HOME': str(directory), 'LANG': 'C.UTF-8'})
                self.pidfd = os.pidfd_open(self.child.pid)
            self.control.sendall(b'start\n')
            self.control.setblocking(False)
            log('spawned')
        except BaseException:
            remote.close()
            self.close()
            raise
        finally:
            remote.close()

    def poll(self):
        # Observe exit first, then drain packets: a fast backend may queue ready
        # and exit together. Do not race its final send against waitpid.
        status = self.child.poll()
        while True:
            try:
                packet = self.control.recv(64)
            except BlockingIOError:
                break
            if not packet:
                break
            if packet == b'ready\n':
                require(not self.ready, 'worker:duplicate-ready')
                self.ready = True
                log('ready')
                continue
            match = re.fullmatch(rb'exit ([0-9]{1,3})\n', packet)
            if match:
                require(self.ready and self.result is None, 'worker:unexpected-result')
                self.result = int(match.group(1))
            else:
                require(False, 'worker:invalid-reply')
        if status is not None:
            require(self.ready and self.result is not None and status == 0,
                    'worker:unexpected-exit')
            return self.result
        return None

    def run(self, server, timeout=300):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.poll()
            if result is not None:
                require(result == 0, 'worker:backend-failed')
                return
            server.serve_once()
        require(False, 'worker:timeout')

    def close(self):
        if self.control is not None:
            self.control.close()
            self.control = None
        if self.child is None:
            return
        try:
            self.child.wait(timeout=7)
        except subprocess.TimeoutExpired:
            # If pinning failed, the start gate was never released. EOF or
            # the startup deadline ends init without any backend spawned.
            require(self.pidfd is not None, 'worker:unrecorded-supervisor')
            try:
                signal.pidfd_send_signal(self.pidfd, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.child.wait(timeout=10)
        # Keep the recorded identity if waiting failed, allowing owned recovery.
        if self.pidfd is not None:
            os.close(self.pidfd)
            self.pidfd = None
        self.child = None
        log('cleanup-complete')


def namespace_main(args):
    require_private_namespace(args.original)
    os.umask(0o077)
    with socket.socket(fileno=args.control_fd) as control:
        control.settimeout(5)
        require(control.recv(16) == b'start\n', 'worker:start-refused')
        control.settimeout(None)
        Commands().run(['/usr/sbin/ip', 'link', 'set', 'dev', 'lo', 'up'], timeout=5)
        bridge = Bridge(args.original, args.socket, args.run)
        try:
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            require(command and Path(command[0]).is_absolute(), 'worker:invalid-command')
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, close_fds=True)
            control.sendall(b'ready\n')
            while child.poll() is None:
                if not bridge.step(control):
                    log('controller-closed')
                    return 0
            control.sendall(f'exit {child.returncode if child.returncode >= 0 else 128 - child.returncode}\n'.encode())
            return 0
        finally:
            bridge.close()
            # Returning from PID 1 makes the kernel terminate all namespace
            # members, including backend-created orphaned grandchildren.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-fd', type=int, required=True)
    parser.add_argument('--original', type=int, nargs=3, required=True)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        return namespace_main(args)
    except (Exception, KeyboardInterrupt):
        log('failed')
        return 2


if __name__ == '__main__':
    sys.exit(main())
