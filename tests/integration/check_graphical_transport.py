#!/usr/bin/python3
"""Fixed, non-booting probe of libvirt's graphics FD RPC rejection boundary."""

import importlib
import array
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

from owned_commands import Commands, require
import prepare_host as host


def receive_probe(directory, commands):
    """Real SCM_RIGHTS from a confined owned fixture; no daemon or VM mutation."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        path = directory / 'receive.sock'
        listener.bind(str(path))
        listener.listen(1)
        listener.settimeout(5)
        commands.run(['/usr/bin/aa-exec', '--profile=libvirtd', '--', '/usr/bin/python3', '-B',
                      str(Path(__file__).with_name('graphical_transport_fixture.py')), str(path)], timeout=15)
        peer, _ = listener.accept()
        descriptors = array.array('i')
        try:
            with peer:
                peer.settimeout(5)
                data, ancillary, flags, _ = peer.recvmsg(
                    1, socket.CMSG_SPACE(descriptors.itemsize), socket.MSG_CMSG_CLOEXEC)
                for level, kind, raw in ancillary:
                    if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                        descriptors.frombytes(raw[:len(raw) - len(raw) % descriptors.itemsize])
            result = {'payload_received': data == b'F', 'descriptor_count': len(descriptors),
                      'control_truncated': bool(flags & socket.MSG_CTRUNC)}
            if len(descriptors) == 1:
                descriptor = descriptors.pop()
                try:
                    display = socket.socket(fileno=descriptor)
                except BaseException:
                    os.close(descriptor)
                    raise
                with display:
                    display.settimeout(5)
                    result['socket_usable'] = display.recv(64) == b'graphics-fd-fixture'
            result['outcome'] = 'passed' if (result['payload_received'] and
                not result['control_truncated'] and result.get('socket_usable')) else 'failed'
            return result
        finally:
            for descriptor in descriptors:
                os.close(descriptor)


def probe(api):
    source = host.LibvirtSource(api)
    try:
        require(source.snapshot()[1], 'graphics-probe:domain-must-be-off')
        local, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        with local, peer:
            try:
                # Impossible graphics index; even a concurrent external boot
                # cannot turn this fixed request into an attached display.
                source.domain.openGraphics(0xffffffff, peer.fileno(), 0)
            except api.libvirtError as error:
                alive = source.connection.isAlive() == 1
                code = error.get_error_code()
                return {'scope': 'non-booting-invalid-graphics-index',
                        'outcome': 'passed' if alive and code in (
                            api.VIR_ERR_OPERATION_INVALID, api.VIR_ERR_INTERNAL_ERROR,
                            api.VIR_ERR_INVALID_ARG) else 'failed',
                        'connection_alive': alive, 'libvirt_error_code': code}
            require(False, 'graphics-probe:invalid-index-accepted')
    finally:
        source.close()


def main():
    require(len(sys.argv) == 1, 'graphics-probe:invalid-arguments')
    require(os.geteuid() == os.getegid() == 0, 'graphics-probe:root-required')
    require(Path.cwd() == host.guest_contract.CHECKOUT, 'graphics-probe:checkout')
    os.umask(0o077)
    directory = Path(tempfile.mkdtemp(prefix='onpc-graphics-transport-'))
    commands = Commands()
    commands.directory = directory
    result = probe(importlib.import_module('libvirt'))
    try:
        result['receive_fixture'] = receive_probe(directory, commands)
    except Exception as error:
        # Raw fixture stderr remains private; retain a useful failed summary.
        result['receive_fixture'] = {'outcome': 'failed', 'category': 'receive-fixture-failed',
                                     'exception_type': type(error).__name__}
    if result['receive_fixture']['outcome'] != 'passed':
        result['outcome'] = 'failed'
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    result['evidence_directory'] = str(directory)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
