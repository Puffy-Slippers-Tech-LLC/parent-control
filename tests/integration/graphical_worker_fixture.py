#!/usr/bin/python3
"""Internal byte/descendant fixture; only the namespace worker invokes it."""

import array
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

from graphical_worker import PORT
from owned_commands import require


def fixture(proof_path, mode):
    """Only called by the namespace worker, never directly on the host."""
    require(os.getpid() != 1 and os.getppid() == 1, 'qualification:not-contained')
    require(os.path.samefile('/proc/1/exe', '/proc/self/exe'), 'qualification:wrong-init')
    with socket.create_connection(('127.0.0.1', PORT), timeout=10) as display:
        chunk = bytes(range(256)) * 128
        for _ in range(32):
            display.sendall(chunk)
            received = bytearray()
            while len(received) < len(chunk):
                data = display.recv(len(chunk) - len(received))
                require(data, 'qualification:early-eof')
                received.extend(data)
            require(received == chunk, 'qualification:bytes-changed')
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as proof:
        proof.connect(str(proof_path))
        child = subprocess.Popen(['/usr/bin/python3', '-B', str(Path(__file__).resolve()),
                                  '--linger'], stdin=subprocess.DEVNULL)
        pinned = array.array('i', [os.pidfd_open(os.getpid()), os.pidfd_open(child.pid)])
        try:
            proof.sendmsg([b'roundtrip-ok\n'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, pinned)])
        finally:
            for descriptor in pinned:
                os.close(descriptor)
        # The host confirms receipt of both identities before normal exit or
        # interruption; inherited PIDs/names are never used for cleanup.
        require(proof.recv(16) == b'continue\n', 'qualification:proof-refused')
        if mode in ('interrupt', 'disconnect'):
            select.select([proof], [], [], 30)
    return 0


def main():
    require(os.geteuid() == 0 and os.getpid() > 1 and
            os.path.samefile('/proc/1/exe', '/proc/self/exe'), 'qualification:not-contained')
    if sys.argv[1:] == ['--linger']:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
        return 0
    require(len(sys.argv) == 3 and sys.argv[2] in ('success', 'interrupt', 'disconnect'),
            'qualification:invalid-arguments')
    return fixture(Path(sys.argv[1]), sys.argv[2])


if __name__ == '__main__':
    sys.exit(main())
