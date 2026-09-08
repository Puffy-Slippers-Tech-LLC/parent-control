#!/usr/bin/python3
"""generalhw lifecycle callbacks delegated to one already-prepared VM lease.

This is controller plumbing, not a graphical runner. The future worker must
keep its TCP-to-FD bridge in a private network namespace and qualify its owned
subprocess cleanup before using it with os-autoinst. No host TCP listener is
created here. All libvirt calls stay in the lease owner's service loop.
"""

import argparse
import array
import os
from pathlib import Path
import re
import socket
import stat
import struct
import sys

from owned_commands import require
from prepare_host import URI


def log(event):
    # Never include socket paths, run tokens, XML, or backend output.
    print('graphical-lease: [' + event + ']', file=sys.stderr, flush=True)


class Adapter:
    """Accept one generalhw off/on/off attempt; never restore within it."""

    def __init__(self, lease):
        require(lease.fd is not None and lease.state['phase'] == 'isolated' and
                lease.view.run == lease.state['run'] and
                lease.view.graphics_type == 'vnc', 'graphics:unprepared-lease')
        lease.guard(off=True)
        self.lease = lease
        self.run = lease.state['run']
        self.phase = 'initial'
        self.events = []
        self.display = None
        self.serial = None

    def revalidate(self):
        try:
            require(self.lease.fd is not None and self.lease.view.run == self.run and
                    self.lease.state['run'] == self.run, 'graphics:expired-lease')
            self.lease.guard()
        except BaseException:
            try:
                self.close_serial()
            finally:
                self.close_display()
            raise

    def close_serial(self):
        if self.serial is not None:
            self.serial.close()

    def close_display(self):
        if self.display is not None:
            display, self.display = self.display, None
            try:
                # Revoke SCM_RIGHTS duplicates held by the owned bridge too.
                try:
                    display.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            finally:
                display.close()
            log('display-closed')

    def open_display(self):
        """Public graphics FD API on a disposable graphics connection.

        A failed FD RPC can close its libvirt connection. Never issue it on
        the lease's lifecycle connection, which must remain usable for cleanup.
        The second connection grants no new ownership: compare its exact domain
        instance and XML against the guarded lease before attaching anything.
        """
        connection = self.lease.source.api.open(URI)
        require(connection is not None, 'graphics:connection')
        display = None
        try:
            require(connection.getURI() == URI, 'graphics:connection')
            domain = connection.lookupByUUIDString(self.lease.source.uuid)
            self.revalidate()
            require(domain.UUIDString() == self.lease.source.uuid and
                    domain.ID() == self.lease.view.domain_id and
                    domain.XMLDesc(0) == self.lease.source.domain.XMLDesc(0),
                    'graphics:domain-identity')
            log('display-attach-requested')
            # Let libvirt create/label the pair for its confined QEMU process.
            # flags=0 retains authentication. No direct QEMU socket access.
            descriptor = domain.openGraphicsFD(0, 0)
            try:
                display = socket.socket(fileno=descriptor)
            except BaseException:
                os.close(descriptor)
                raise
            self.revalidate()
            require(domain.ID() == self.lease.view.domain_id and
                    domain.XMLDesc(0) == self.lease.source.domain.XMLDesc(0),
                    'graphics:domain-identity')
        except BaseException:
            if display is not None:
                try:
                    display.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                display.close()
            log('display-attach-failed')
            raise
        finally:
            original = sys.exception()
            try:
                connection.close()
            except BaseException:
                if display is not None:
                    try:
                        display.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    display.close()
                if original is None:
                    raise
                log('graphics-connection-close-failed')
        return display

    def request(self, action, run):
        require(run == self.run, 'graphics:wrong-run')
        require(action in ('on', 'off', 'status', 'graphics'), 'graphics:unknown-action')
        self.revalidate()
        if action == 'status':
            state = 'off' if self.lease.view.snapshot()[1] else 'on'
            self.events.append('status-' + state)
            log('status-' + state)
            return state
        if action == 'off':
            # generalhw begins with an off-state assertion before power-on.
            # Preserve the prepared pipes until the actual running shutdown.
            if self.phase not in ('initial', 'ready'):
                self.close_serial()
            self.close_display()
            # Initial poweroff is an asserted, guarded off state. Subsequent
            # poweroff stops only the instance the lease recorded at start.
            if self.phase in ('initial', 'ready'):
                self.lease.guard(off=True)
                self.phase = 'ready'
                self.events.append('initial-off')
            else:
                self.lease.stop()
                self.phase = 'stopped'
                self.events.append('poweroff')
            log('poweroff-complete')
            return 'ok'
        if action == 'on':
            require(self.phase == 'ready', 'graphics:unexpected-poweron')
            # Mark first: a failed start must never permit a second create.
            self.phase = 'starting'
            self.lease.start()
            self.phase = 'running'
            self.events.append('poweron')
            log('poweron-complete')
            return 'ok'
        require(self.phase == 'running' and not self.lease.view.snapshot()[1],
                'graphics:not-running')
        self.close_display()
        display = self.open_display()
        self.display = display
        # Recheck after acquiring the FD; do not return a replaced endpoint.
        self.revalidate()
        log('display-opened')
        return display


class CallbackServer:
    """Bounded root-only local RPC; service from the lease owner's thread.

    The caller creates a fresh private directory. No path cleanup is inferred:
    the controller retains the directory as private evidence after closing.
    A worker receives only the socket path/run and public lifecycle verbs; it
    never opens its own libvirt connection or reads the lease journal.
    """

    def __init__(self, adapter, directory):
        require(os.geteuid() == 0, 'graphics:root-required')
        self.adapter = adapter
        self.directory = Path(directory)
        metadata = self.directory.lstat()
        require(stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == 0 and
                stat.S_IMODE(metadata.st_mode) == 0o700,
                'graphics:private-directory')
        require(self.directory.resolve() == self.directory,
                'graphics:directory-symlink')
        self.identity = (metadata.st_dev, metadata.st_ino)
        self.path = self.directory / 'generalhw.sock'
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            self.listener.bind(str(self.path))
            self.path.chmod(0o600)
            self.listener.listen(1)
            self.listener.settimeout(0.25)
        except BaseException:
            self.listener.close()
            raise

    def serve_once(self):
        """Also revoke the display on idle ownership loss; never spawn a thread."""
        try:
            metadata = self.directory.lstat()
            require((metadata.st_dev, metadata.st_ino) == self.identity and
                    stat.S_ISDIR(metadata.st_mode) and metadata.st_uid == 0 and
                    stat.S_IMODE(metadata.st_mode) == 0o700 and
                    self.directory.resolve() == self.directory,
                    'graphics:directory-changed')
            self.adapter.revalidate()
        except BaseException:
            self.adapter.close_display()
            raise
        try:
            peer, _ = self.listener.accept()
        except TimeoutError:
            return False
        with peer:
            peer.settimeout(2)
            try:
                _, uid, _ = struct.unpack('3i', peer.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
                require(uid == 0, 'graphics:callback-peer')
                packet, _, flags, _ = peer.recvmsg(128)
                require(not flags & socket.MSG_TRUNC, 'graphics:oversize-request')
                match = re.fullmatch(rb'([a-z]+) ([0-9a-f]{32})\n', packet)
                require(match is not None, 'graphics:invalid-request')
                action, run = (value.decode('ascii') for value in match.groups())
                result = self.adapter.request(action, run)
                if isinstance(result, socket.socket):
                    peer.sendmsg([b'ok\n'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                             array.array('i', [result.fileno()]))])
                else:
                    peer.sendall((result + '\n').encode('ascii'))
                return True
            except BaseException:
                self.adapter.close_display()
                log('callback-failed')
                try:
                    peer.sendall(b'failed\n')
                except OSError:
                    pass
                raise

    def close(self):
        try:
            self.adapter.close_serial()
        finally:
            try:
                self.adapter.close_display()
            finally:
                self.listener.close()


def callback(path, run, action):
    """Public generalhw power/status script protocol, with a bounded reply."""
    require(action in ('on', 'off', 'status') and
            re.fullmatch(r'[0-9a-f]{32}', run) is not None,
            'graphics:invalid-callback')
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
        # Lease shutdown currently has a 180-second ACPI deadline. The worker
        # supervisor must allow the controller to finish its bounded cleanup.
        peer.settimeout(240)
        peer.connect(str(path))
        peer.sendall(f'{action} {run}\n'.encode('ascii'))
        result = peer.recv(16)
    require(result in ((b'on\n', b'off\n') if action == 'status' else (b'ok\n',)),
            'graphics:callback-refused')
    return 1 if result == b'on\n' else 0


def lifecycle_variables(path, run):
    """Public generalhw command variables; that backend splits args on spaces."""
    script = Path(__file__).resolve()
    require(Path(path).is_absolute() and
            all(re.fullmatch(r'/[A-Za-z0-9_./-]+', str(item)) for item in (script, path)) and
            re.fullmatch(r'[0-9a-f]{32}', run) is not None,
            'graphics:invalid-command-arguments')
    variables = {'GENERAL_HW_CMD_DIR': '/usr/bin'}
    for name, action in (('POWERON', 'on'), ('POWEROFF', 'off'), ('IS_SHUTDOWN', 'status')):
        variables[f'GENERAL_HW_{name}_CMD'] = 'python3'
        variables[f'GENERAL_HW_{name}_ARGS'] = (
            f'-B {script} --socket {path} --run {run} {action}')
    return variables


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('action', choices=('on', 'off', 'status'))
    args = parser.parse_args(argv)
    try:
        return callback(args.socket, args.run, args.action)
    except (Exception, KeyboardInterrupt):
        log('callback-failed')
        return 2


if __name__ == '__main__':
    sys.exit(main())
