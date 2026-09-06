#!/usr/bin/python3
"""Private attachment-only child; the parent holds the guarded VM lease."""

import json
import os
import signal
import socket
import sys
import time

from owned_commands import require
from prepare_host import URI


def attach(api, expected, mode):
    connection = api.open(URI)
    display = None
    try:
        require(connection.getURI() == URI, 'attachment:uri')
        domain = connection.lookupByUUIDString(expected['uuid'])

        def guard():
            require(domain.UUIDString() == expected['uuid'] and
                    domain.ID() == expected['id'] and expected['id'] >= 0 and
                    domain.XMLDesc(0) == expected['xml'], 'attachment:identity')

        guard()
        if mode == 'daemon':
            descriptor = domain.openGraphicsFD(0, 0)
            try:
                display = socket.socket(fileno=descriptor)
            except BaseException:
                os.close(descriptor)
                raise
        else:
            require(mode == 'caller', 'attachment:mode')
            display, peer = socket.socketpair()
            with peer:
                domain.openGraphics(0, peer.fileno(), 0)
        guard()
        display.settimeout(10)
        greeting = bytearray()
        while len(greeting) < 12:
            data = display.recv(12 - len(greeting))
            require(data, 'attachment:eof')
            greeting.extend(data)
        require(bytes(greeting) == b'RFB 003.008\n', 'attachment:rfb-greeting')
        guard()
        return {'mode': mode, 'outcome': 'passed', 'rfb_greeting': True}
    finally:
        if display is not None:
            display.close()
        connection.close()


def main():
    require(len(sys.argv) == 1 and os.geteuid() == 0, 'attachment:invocation')
    # A stopped tracer cannot leave an unbounded attachment child behind.
    signal.alarm(45)
    import libvirt
    expected = json.load(sys.stdin)
    results = []
    for mode in ('daemon', 'caller'):
        # Profile loads during VM startup exhaust the kernel audit burst. Give
        # each diagnostic RPC its own quiet window so denials are retained.
        # This is diagnostic collection, not product readiness or a daily wait.
        time.sleep(6)
        try:
            results.append(attach(libvirt, expected, mode))
        except Exception as error:
            results.append({'mode': mode, 'outcome': 'failed',
                            'exception_type': type(error).__name__,
                            'libvirt_error_code': error.get_error_code()
                            if isinstance(error, libvirt.libvirtError) else None})
    print(json.dumps(results), flush=True)
    return 0 if any(r['outcome'] == 'passed' for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
