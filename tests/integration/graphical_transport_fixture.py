#!/usr/bin/python3
"""Internal non-VM fixture: send one socket under libvirtd's AppArmor label."""

import array
from pathlib import Path
import socket
import sys

from owned_commands import require


def main():
    require(len(sys.argv) == 2, 'fd-fixture:arguments')
    require(Path('/proc/self/attr/current').read_text().strip() == 'libvirtd (enforce)',
            'fd-fixture:wrong-profile')
    local, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    with local, remote, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(5)
        peer.connect(sys.argv[1])
        remote.sendall(b'graphics-fd-fixture')
        peer.sendmsg([b'F'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                              array.array('i', [local.fileno()]))])


if __name__ == '__main__':
    main()
