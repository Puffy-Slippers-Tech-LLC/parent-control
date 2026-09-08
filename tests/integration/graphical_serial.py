"""Lease-owned serial stream and private pipes for public virtio_terminal.

The console name is historical: os-autoinst documents non-virtio transports
through its pipe interface too. Only libvirt opens the existing serial device;
no raw host PTY, second lifecycle owner, thread or child process is used.
"""

import os
from pathlib import Path
import stat
import sys
import xml.etree.ElementTree as ET

from owned_commands import require
from prepare_host import URI

LIMIT = 65536


def serial_device(xml):
    root = ET.fromstring(xml)
    ports = root.findall('devices/serial')
    consoles = root.findall('devices/console')
    require(len(ports) == len(consoles) == 1, 'serial:device-count')
    port, console = ports[0], consoles[0]
    require(port.get('type') == console.get('type') == 'pty'
            and port.find('target') is not None
            and port.find('target').attrib == {'type': 'isa-serial', 'port': '0'}
            and console.find('target') is not None
            and console.find('target').attrib == {'type': 'serial', 'port': '0'},
            'serial:device-type')
    alias = port.find('alias')
    require(alias is not None and alias.attrib == {'name': 'serial0'}, 'serial:device-alias')
    return 'serial0'


class SerialConsole:
    def __init__(self, adapter, directory):
        self.adapter = adapter
        self.directory = Path(directory)
        self.connection = self.stream = None
        self.fds = []
        self.identities = []
        self.pending_in = bytearray()
        self.pending_out = bytearray()
        self.closed = False
        self.attached = False
        info = self.directory.lstat()
        require(self.directory.is_absolute() and self.directory.resolve() == self.directory
                and stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o700, 'serial:private-directory')
        self.identity = (info.st_dev, info.st_ino)
        adapter.revalidate()
        try:
            for suffix in ('in', 'out'):
                path = self.directory / ('serial-console.' + suffix)
                os.mkfifo(path, 0o600)
                fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_NOFOLLOW)
                self.fds.append(fd)
                info = os.fstat(fd)
                self.identities.append((info.st_dev, info.st_ino))
            self.guard()
        except BaseException:
            self.close()
            raise

    def guard(self):
        require(not self.closed, 'serial:closed')
        self.adapter.revalidate()
        info = self.directory.lstat()
        require(self.directory.resolve() == self.directory
                and (info.st_dev, info.st_ino) == self.identity
                and stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.geteuid(),
                'serial:directory-replaced')
        for suffix, identity in zip(('in', 'out'), self.identities, strict=True):
            info = (self.directory / ('serial-console.' + suffix)).lstat()
            require(stat.S_ISFIFO(info.st_mode) and info.st_uid == os.geteuid()
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                    and (info.st_dev, info.st_ino) == identity, 'serial:pipe-replaced')

    def attach(self):
        require(not self.attached and self.adapter.phase == 'running', 'serial:attach-state')
        self.guard()
        lease = self.adapter.lease
        self.connection = lease.source.api.open(URI)
        require(self.connection is not None and self.connection.getURI() == URI,
                'serial:connection')
        domain = self.connection.lookupByUUIDString(lease.source.uuid)
        def identity():
            self.guard()
            require(domain.UUIDString() == lease.source.uuid
                    and domain.ID() == lease.view.domain_id
                    and domain.XMLDesc(0) == lease.source.domain.XMLDesc(0),
                    'serial:domain-replaced')
            return serial_device(domain.XMLDesc(0))
        name = identity()
        self.stream = self.connection.newStream(lease.source.api.VIR_STREAM_NONBLOCK)
        # SAFE refuses unsupported exclusivity and busy consoles. Never FORCE.
        domain.openConsole(name, self.stream, lease.source.api.VIR_DOMAIN_CONSOLE_SAFE)
        identity()
        self.attached = True
        print('graphical-serial: [attached-exclusive]', file=sys.stderr, flush=True)

    def step(self):
        if self.closed:
            require(self.adapter.phase != 'running', 'serial:unexpected-close')
            return
        try:
            self.guard()
            if self.adapter.phase != 'running':
                return
            if not self.attached:
                self.attach()
            if len(self.pending_in) < LIMIT:
                try:
                    self.pending_in.extend(os.read(self.fds[0], LIMIT - len(self.pending_in)))
                except BlockingIOError:
                    pass
            if self.pending_in:
                self.guard()
                count = self.stream.send(bytes(self.pending_in))
                require(count == -2 or 0 < count <= len(self.pending_in), 'serial:send-failed')
                if count != -2:
                    del self.pending_in[:count]
            if len(self.pending_out) < LIMIT:
                data = self.stream.recv(LIMIT - len(self.pending_out))
                require(data == -2 or isinstance(data, bytes) and 0 < len(data)
                        <= LIMIT - len(self.pending_out), 'serial:stream-ended')
                if data != -2:
                    self.pending_out.extend(data)
            if self.pending_out:
                self.guard()
                try:
                    count = os.write(self.fds[1], self.pending_out)
                    del self.pending_out[:count]
                except BlockingIOError:
                    pass
        except BaseException:
            self.close()
            raise

    def close(self):
        self.closed = True
        first = None
        stream, self.stream = self.stream, None
        connection, self.connection = self.connection, None
        for resource, action in ((stream, 'abort'), (connection, 'close')):
            try:
                if resource is not None:
                    getattr(resource, action)()
            except BaseException as error:
                first = first or error
        for fd in self.fds:
            try:
                os.close(fd)
            except BaseException as error:
                first = first or error
        self.fds = []
        self.pending_in.clear()
        self.pending_out.clear()
        if first is not None:
            raise first


def provision_getty(lease, guestfs):
    """Enable the stock password-authenticated getty only in offline preparation."""
    from system_runner import mounted_guest
    require(lease.fd is not None and lease.state['phase'] == 'isolated'
            and lease.state['domain_id'] is None, 'serial:outside-provisioning')
    lease.guard(off=True)
    with mounted_guest(guestfs, lease) as g:
        target = '/usr/lib/systemd/system/serial-getty@.service'
        require(g.is_file(target) and g.realpath(target) == target, 'serial:getty-prerequisite')
        wants = '/etc/systemd/system/getty.target.wants'
        require(g.is_dir(wants) and g.realpath(wants) == wants, 'serial:getty-directory')
        path = wants + '/serial-getty@ttyS0.service'
        if g.is_symlink(path):
            require(g.realpath(path) == target, 'serial:getty-conflict')
        else:
            require(not g.exists(path), 'serial:getty-conflict')
            g.ln_s(target, path)
        require(g.realpath(path) == target, 'serial:getty-enable-failed')
    lease.guard(off=True)
