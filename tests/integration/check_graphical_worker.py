#!/usr/bin/python3
"""Fixed non-VM qualification: byte bridge, normal exit and forced interruption.

Run the isolated graphical-worker cleanup tests first. This privileged command
creates only private temporary test sockets/directories and contained fixture
processes. It cannot open libvirt, boot a VM, or run an arbitrary user command.
Raw worker output stays in its root-private evidence directory.
"""

import array
import json
import os
from pathlib import Path
import select
import signal
import socket
import sys
import tempfile
import time

from graphical_lease import CallbackServer
from graphical_worker import Worker
from owned_commands import CommandError, require


RUN = 'a' * 32  # Public fixture identity, never a real lease token.


class DisplayFixture:
    """Declared socket echo double; provides no graphical/VM acceptance."""

    def __init__(self):
        self.display = None
        self.echo = None
        self.pending = bytearray()

    def revalidate(self):
        pass

    def request(self, action, run):
        require(action == 'graphics' and run == RUN and self.display is None,
                'qualification:unexpected-callback')
        self.display, self.echo = socket.socketpair()
        self.echo.setblocking(False)
        return self.display

    def pump(self):
        if self.echo is None:
            return
        try:
            self.pending.extend(self.echo.recv(65536))
        except BlockingIOError:
            pass
        if self.pending:
            try:
                count = self.echo.send(self.pending)
                del self.pending[:count]
            except BlockingIOError:
                pass

    def close_display(self):
        for endpoint in (self.display, self.echo):
            if endpoint is not None:
                endpoint.close()
        self.display = self.echo = None


def wait_exited(descriptors, timeout):
    """select wakes for any exit; success needs every recorded process exited."""
    pending = set(descriptors)
    deadline = time.monotonic() + timeout
    while pending:
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'qualification:descendant-survived')
        ready, _, _ = select.select(list(pending), [], [], remaining)
        pending.difference_update(ready)


def attempt(directory, mode):
    directory.mkdir(mode=0o700)
    adapter = DisplayFixture()
    server = CallbackServer(adapter, directory)
    server.listener.settimeout(0.01)
    proof = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    proof.bind(str(directory / 'proof.sock'))
    proof.listen(1)
    proof.setblocking(False)
    handle = None
    peer = None
    pinned = array.array('i')
    started = time.monotonic()
    try:
        handle = Worker(directory, server.path, RUN,
                        ['/usr/bin/python3', '-B', str(Path(__file__).with_name('graphical_worker_fixture.py').resolve()), str(directory / 'proof.sock'), mode])
        deadline = started + 30
        while peer is None and time.monotonic() < deadline:
            require(handle.poll() is None, 'qualification:fixture-exited-early')
            server.serve_once()
            adapter.pump()
            try:
                peer, _ = proof.accept()
            except BlockingIOError:
                pass
        require(peer is not None, 'qualification:proof-timeout')
        peer.settimeout(5)
        packet, ancillary, flags, _ = peer.recvmsg(64, socket.CMSG_SPACE(8), socket.MSG_CMSG_CLOEXEC)
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                pinned.frombytes(data)
        require(packet == b'roundtrip-ok\n' and not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC)
                and len(pinned) == 2,
                'qualification:invalid-proof')
        require(not select.select(list(pinned), [], [], 0)[0], 'qualification:fixture-not-alive')
        peer.sendall(b'continue\n')
        if mode == 'interrupt':
            # Deliberately kill only the recorded supervisor. This exercises
            # unshare parent-death and kernel namespace descendant cleanup.
            signal.pidfd_send_signal(handle.pidfd, signal.SIGKILL)
        elif mode == 'success':
            handle.run(server, timeout=10)
        handle.close()
        wait_exited(pinned, timeout=5)
        return {'mode': mode, 'outcome': 'passed', 'bytes_roundtrip': 1048576,
                'owned_processes_exited': 2,
                'duration_seconds': round(time.monotonic() - started, 3)}
    finally:
        if handle is not None:
            handle.close()
        for descriptor in pinned:
            os.close(descriptor)
        if peer is not None:
            peer.close()
        proof.close()
        server.close()


def main():
    require(os.geteuid() == 0, 'qualification:root-required')
    require(len(sys.argv) == 1, 'qualification:invalid-arguments')
    os.umask(0o077)
    directory = Path(tempfile.mkdtemp(prefix='onpc-graphical-worker-'))
    results = []
    try:
        for mode in ('success', 'disconnect', 'interrupt'):
            results.append(attempt(directory / mode, mode))
        result = {'scope': 'non-vm-worker-fixture', 'outcome': 'passed', 'vm_access': False,
                  'attempts': results, 'evidence_directory': str(directory)}
    except (Exception, KeyboardInterrupt) as error:
        result = {'scope': 'non-vm-worker-fixture', 'outcome': 'failed', 'vm_access': False,
                  'attempts': results, 'evidence_directory': str(directory),
                  'category': str(error) if isinstance(error, CommandError) else 'qualification:failed'}
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
