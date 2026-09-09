#!/usr/bin/python3
"""Guarded SSH transport for the existing, identity-recorded test VM."""

import io
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shlex
import stat
import tarfile
import sys
import threading
import time

from owned_commands import Commands, require, CommandError as Error

BOOT_SHA256_PROBE = '''import hashlib,pathlib,re
value=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text()
assert re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\n',value)
print(hashlib.sha256(value.encode()).hexdigest())
'''


@contextmanager
def readiness_events():
    """Use the controller's running libvirt event loop for bounded probe ticks."""
    import libvirt
    event = threading.Event()
    timer = libvirt.virEventAddTimeout(500, lambda *_: event.set(), None)
    try:
        yield event
    finally:
        libvirt.virEventRemoveTimeout(timer)


def ssh(config, *, attempts=1):
    directory = config['directory']
    return ['ssh', '-F', '/dev/null', '-i', directory + '/ssh-key',
            '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + directory + '/known-hosts',
            '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=5',
            '-o', f'ConnectionAttempts={attempts}', '-o', 'ServerAliveInterval=10',
            '-o', 'ServerAliveCountMax=3', 'root@' + config['hostname']]


def guard_host(config):
    import libvirt
    import xml.etree.ElementTree as ET
    connection = libvirt.open('qemu:///system')
    try:
        domain = connection.lookupByUUIDString(config['domain_uuid'])
        root = ET.fromstring(domain.XMLDesc(0))
        require(domain.ID() == config['domain_id'] and domain.name() == 'ubuntu26.04' and
                root.findtext('description') == 'onpc-system-run:' + config['run'] and
                not root.findall('devices/filesystem') and not root.findall('devices/hostdev') and
                not root.findall('devices/channel') and not root.findall('devices/redirdev'),
                'transport:domain-replaced-or-shared')
    finally:
        connection.close()


def guest_prefix(config):
    # The marker is root-private and pinned to the Lease-created guest instance.
    program = (
        'import json,os,pathlib,stat; '
        'p=pathlib.Path("/etc/onpc-system-test.json"); s=p.lstat(); '
        'assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and stat.S_IMODE(s.st_mode)==384; '
        'm=json.loads(p.read_text()); '
        f'assert m["run"]=={config["run"]!r} and m["domain_uuid"]=={config["domain_uuid"]!r}; '
        'assert pathlib.Path("/sys/class/dmi/id/product_uuid").read_text().strip().lower()==m["domain_uuid"]; '
        'assert pathlib.Path("/etc/machine-id").read_text().strip()==m["machine_id"]!=m["host_machine_id"]; '
        'assert not any(x.split(" - ")[1].split()[0] in '
        '{"virtiofs","9p","nfs","nfs4","cifs","fuse.sshfs"} '
        'for x in pathlib.Path("/proc/self/mountinfo").read_text().splitlines())'
    )
    return shlex.join(['/usr/bin/python3', '-c', program]) + ' && '


def remote(config, argv):
    return guest_prefix(config) + 'exec ' + shlex.join(argv)


def local_path(config, value):
    path = Path(value)
    directory = Path(config['directory'])
    require(path.is_absolute() and '..' not in path.parts and directory in path.parents and
            path == path.resolve(strict=False), 'transport:host-path')
    return path


def extract(data, destination):
    """Only ordinary files/directories can be returned by a testbed."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        for member in archive:
            require(member.isdir() or member.isfile(), 'transport:archive-special-file')
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts, 'transport:archive-path')
            target = destination / path
            require(target.resolve(strict=False).is_relative_to(destination.resolve()), 'transport:archive-escape')
        archive.extractall(destination, filter='data')


class Transport:
    def __init__(self, config, commands=None, guard=guard_host):
        self.config = config
        self.commands = commands or Commands()
        self.guard = guard

    def call(self, argv, *, input=None, timeout=120, check=True, attempts=1):
        self.guard(self.config)
        return self.commands.run([*ssh(self.config, attempts=attempts), remote(self.config, argv)],
                                 input=input, timeout=timeout, check=check, merge_stderr=False)

    def ready(self):
        self.probe_ready()

    def probe_ready(self, *, boot_id=False, timeout=330):
        return self._probe_ready(boot_id=boot_id, timeout=timeout)

    def wait_boot_change(self, previous_boot_sha256, *, on_diagnostic=None):
        """Observe a customer-requested reboot; never issue a lifecycle command.

        The old boot may still answer SSH after input submission. Only this
        transition waits through that valid old identity, using the same bounded
        readiness loop. Guest guard errors and malformed identities are final.
        Hash the complete boot-id file in the guest, matching E2E observations.
        """
        require(isinstance(previous_boot_sha256, str)
                and re.fullmatch(r'[0-9a-f]{64}', previous_boot_sha256),
                'transport:invalid-previous-boot')
        diagnostic = {'old_boot': 0, 'ssh_unavailable': 0, 'changed_boot': 0,
                      'outcome': 'unknown-error'}
        try:
            result = self._probe_ready(boot_id=True, timeout=330,
                previous_boot_sha256=previous_boot_sha256, diagnostic=diagnostic)
            diagnostic['outcome'] = 'changed-boot'
            return result
        except BaseException as error:
            codes = {'transport:' + code: code for code in (
                'readiness-timeout', 'configuration-changed', 'invalid-boot-output',
                'guest-probe-failed', 'domain-replaced-or-shared')}
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                diagnostic['outcome'] = 'interrupted'
            elif isinstance(error, Error) and str(error) in codes:
                diagnostic['outcome'] = codes[str(error)]
            raise
        finally:
            # Fixed categories and counts only: never SSH output or exception text.
            if on_diagnostic is not None:
                on_diagnostic(dict(diagnostic))

    def _probe_ready(self, *, boot_id, timeout, previous_boot_sha256=None, diagnostic=None):
        # ConnectionAttempts only retries TCP establishment. A reboot can also
        # reset an already connected SSH handshake. Only these fixed read-only
        # probes may repeat after SSH's transport-error exit status (255).
        # Guest guard failures and successful-but-wrong assertions are terminal.
        argv = ['cat', '/proc/sys/kernel/random/boot_id'] if boot_id else ['true']
        if previous_boot_sha256 is not None:
            argv = ['/usr/bin/python3', '-c', BOOT_SHA256_PROBE]
        deadline = time.monotonic() + timeout
        waiting = False
        config = dict(self.config)
        with readiness_events() as event:
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'transport:readiness-timeout')
                if previous_boot_sha256 is not None:
                    require(self.config == config, 'transport:configuration-changed')
                result = self.call(argv, timeout=min(30, remaining), check=False)
                # Lease guards also execute qemu-img through this Commands
                # instance. Preserve SSH's status before the post-probe guard
                # replaces last_returncode with its own successful result.
                probe_returncode = self.commands.last_returncode
                if previous_boot_sha256 is not None:
                    require(self.config == config, 'transport:configuration-changed')
                    self.guard(config)
                if probe_returncode == 0:
                    changed = True
                    if previous_boot_sha256 is not None:
                        require(isinstance(result, bytes) and re.fullmatch(rb'[0-9a-f]{64}\n', result),
                            'transport:invalid-boot-output')
                        changed = result.decode('ascii').strip() != previous_boot_sha256
                        diagnostic['changed_boot' if changed else 'old_boot'] += 1
                    if changed:
                        if waiting:
                            print('check-system: [transport:ssh-ready]', file=sys.stderr, flush=True)
                        return result
                else:
                    require(probe_returncode == 255, 'transport:guest-probe-failed')
                    if diagnostic is not None:
                        diagnostic['ssh_unavailable'] += 1
                if not waiting:
                    label = 'waiting-for-boot-change' if previous_boot_sha256 is not None else 'waiting-for-ssh'
                    print('check-system: [transport:' + label + ']', file=sys.stderr, flush=True)
                    waiting = True
                event.wait(max(0, deadline - time.monotonic()))
                event.clear()

    def reboot(self):
        before = self.call(['/usr/bin/python3', '-c', BOOT_SHA256_PROBE])
        require(isinstance(before, bytes) and re.fullmatch(rb'[0-9a-f]{64}\n', before),
                'transport:invalid-boot-output')
        # Wait for connection closure caused by this reboot; the host deadline
        # bounds failure. No sleeps and no discovery of signal targets.
        program = 'import signal,subprocess; subprocess.run(["systemctl","reboot"],check=True); signal.pause()'
        self.call(['python3', '-c', program], timeout=180, check=False)
        require(self.commands.last_returncode in (0, 255), 'transport:reboot-command-failed')
        # The SSH session can close before sshd stops accepting new connections.
        # Reuse the bounded transition observer: a valid old boot is pending,
        # while malformed replies, guard errors and ownership loss still fail.
        self.wait_boot_change(before.decode('ascii').strip())

    def copy(self, up, source, destination):
        require(source.endswith('/') == destination.endswith('/'), 'transport:copy-type')
        is_dir = source.endswith('/')
        local = local_path(self.config, destination if up else source)
        guest = source if up else destination
        require(guest.startswith('/') and '..' not in Path(guest).parts and guest != '/', 'transport:guest-path')
        if up:
            if is_dir:
                extract(self.call(['tar', '-C', guest, '-cf', '-', '.'], timeout=300), local)
            else:
                raw = self.call(['cat', '--', guest], timeout=300)
                local.parent.mkdir(parents=True, exist_ok=True)
                require(not local.is_symlink(), 'transport:host-symlink')
                local.write_bytes(raw)
        elif is_dir:
            from system_runner import check_tree
            check_tree(local)
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as archive:
                archive.add(local, arcname='.')
            self.call(['mkdir', '-p', '--', guest])
            self.call(['tar', '-C', guest, '-xf', '-'], input=stream.getvalue(), timeout=300)
        else:
            require(local.is_file() and not local.is_symlink(), 'transport:source-file')
            program = ('import os,pathlib,sys; p=pathlib.Path(sys.argv[1]); '
                       'p.parent.mkdir(parents=True,exist_ok=True); '
                       'f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,384); '
                       's=os.fdopen(f,"wb"); s.write(sys.stdin.buffer.read()); s.close(); '
                       'os.chmod(p,int(sys.argv[2]))')
            self.call(['python3', '-c', program, guest, str(stat.S_IMODE(local.stat().st_mode))],
                      input=local.read_bytes(), timeout=300)
