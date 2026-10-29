#!/usr/bin/python3
"""Guarded SSH transport for the existing, identity-recorded test VM."""

import io
import hashlib
from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tarfile
import sys
import threading
import time

from owned_commands import Commands, require, CommandError as Error
import vm_config
from watch_activity import observed

BOOT_SHA256_PROBE = '''import hashlib,pathlib,re
value=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text()
assert re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\n',value)
print(hashlib.sha256(value.encode()).hexdigest())
'''

# The retained fixture timeout shows wait_log_commit in sshd, with a Btrfs
# transaction waiting for extent-buffer I/O and a worker in rq_qos_wait.
# Capture their dependencies and disk progress, rather than just the login
# waiter. Keep only kernel symbols, numeric counters and fixed role labels.
BOOT_STORAGE_DIAGNOSTIC = r'''import itertools,json,pathlib,re,time
rows=[];unavailable=0
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdecimal():continue
 try:
  status=dict(line.split(':',1) for line in (proc/'status').read_text().splitlines() if ':' in line)
  if status.get('Uid','').split()!=['0']*4 or status.get('State','').split()[:1]!=['D']:continue
  identity=(proc/'stat').read_text().rsplit(')',1)[1].split()
  if status.get('Name','').strip()=='sshd-session':role='root-ssh'
  elif identity[1]=='2':role='kernel-worker'
  else:continue
  with (proc/'stack').open() as stream:stack=stream.read(8192)
  frames=re.findall(r'\] ([A-Za-z0-9_.]+)\+',stack)[:24]
  if (proc/'stat').read_text().rsplit(')',1)[1].split()[19]!=identity[19]:
   unavailable+=1;continue
  rows.append({'pid':int(proc.name),'role':role,'kernel_frames':frames})
  if len(rows)==32:break
 except (OSError,ValueError,IndexError):unavailable+=1
disks=list(itertools.islice((p for p in pathlib.Path('/sys/block').iterdir()
 if re.fullmatch(r'vd[a-z]+',p.name)),4))
def sample():
 result=[]
 for disk in disks:
  values={}
  for field in ('stat','inflight','queue/wbt_lat_usec'):
   try:
    raw=(disk/field).read_text()
    if len(raw)<=4096 and re.fullmatch(r'\s*\d+(?:\s+\d+)*\s*',raw):
     values[field]=[int(value) for value in raw.split()]
   except OSError:pass
  result.append({'device':disk.name,'counters':values})
 return {'monotonic_ns':time.monotonic_ns(),'disks':result}
first=sample();time.sleep(1);second=sample()
print(json.dumps({'event':'boot-storage-timeout','blocked_tasks':rows,
 'unavailable':unavailable,'samples':[first,second]},sort_keys=True))
'''


@contextmanager
def package_operation(transport, label, *, lease=None):
    """Keep admission through owned shutdown when SSH completion is uncertain."""
    from tools.host_disk import operation
    with operation(label):
        try:
            yield
            status = transport.commands.last_returncode
            if type(status) is int and (status == 255 or status < 0):
                raise Error('package:transport-completion-uncertain')
        except BaseException as error:
            status = getattr(transport.commands, 'last_returncode', None)
            if status is None or (type(status) is int and (status == 255 or status < 0)):
                owner = lease if lease is not None else getattr(transport, 'lease', None)
                if owner is None:
                    error.add_note('package:owned-shutdown-unavailable')
                else:
                    try:
                        owner.stop()
                    except BaseException as cleanup:
                        error.add_note('package:owned-shutdown-failed:' + type(cleanup).__name__)
                    finally:
                        transport.commands.last_returncode = status
            raise


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
    import system_runner
    import xml.etree.ElementTree as ET
    configured = vm_config.selected()
    connection = libvirt.open(vm_config.URI)
    try:
        domain = connection.lookupByUUIDString(config['domain_uuid'])
        root = ET.fromstring(domain.XMLDesc(0))
        require(connection.getURI() == vm_config.URI and
                domain.ID() == config['domain_id'] and domain.name() == configured.name and
                root.findtext('description') == 'onpc-system-run:' + config['run'],
                'transport:domain-replaced-or-shared')
        try:
            system_runner.validate_host_sharing(root)
        except system_runner.Error as error:
            raise Error('transport:domain-replaced-or-shared') from error
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
        'assert pathlib.Path("/etc/machine-id").read_text().strip()==m["machine_id"]!=m["host_machine_id"]'
    )
    return shlex.join(['/usr/bin/python3', '-c', program]) + ' && '


def remote(config, argv):
    if tuple(argv) == ('/usr/bin/python3', '-c', BOOT_SHA256_PROBE):
        # Diagnose the intermittent fixture boot-read timeout without retrying
        # it or exposing guest data. These fixed stderr markers distinguish a
        # session that never reaches its shell, a stalled ownership guard and
        # a stalled final boot read in the existing private command artifact.
        return ("printf '%s\\n' 'transport:boot-probe:guest-shell' >&2 && "
                + guest_prefix(config)
                + "printf '%s\\n' 'transport:boot-probe:guard-complete' >&2 && exec "
                + shlex.join(argv))
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


def transfer_diagnostic(raw):
    """Fingerprint transferred bytes; the extracted files own the payload."""
    return f'transfer_bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}\n'.encode('ascii')


class Transport:
    def __init__(self, config, commands=None, guard=guard_host, *, lease=None):
        self.config = config
        self.commands = commands or Commands()
        self.guard = guard
        self.lease = lease
        if lease is not None:
            lease.shutdown_request = self.poweroff

    @observed('Requesting VM shutdown through its owned SSH transport')
    def poweroff(self):
        # Submit once. A disconnect is uncertain; the owning controller must
        # independently observe this exact instance off, never replay input.
        self.call(['systemctl', '--no-ask-password', '--no-block', 'poweroff'],
                  timeout=30, check=False)
        require(self.commands.last_returncode in (0, 255), 'transport:poweroff-command-failed')

    def call(self, argv, *, input=None, timeout=120, check=True, attempts=1, on_output=None,
             on_stream=None, diagnostic_stdout=None):
        require(on_output is None or on_stream is None, 'transport:ambiguous-output-callback')
        from watch_activity import operation, remote_command
        selection = remote_command(argv, input is not None)
        package = any(value == '/var/tmp/onpc-system-input/system_guest.py'
                      and index + 1 < len(argv) and argv[index + 1] in (
                          'install', 'install-previous', 'upgrade', 'install-setup', 'install-suite')
                      for index, value in enumerate(argv))
        with operation(selection[0], priority=1):
            with package_operation(self, 'Installing the guest product package') if package else nullcontext():
                try:
                    return self._call(argv, input=input, timeout=timeout, check=check,
                                      attempts=attempts, on_output=on_output, on_stream=on_stream,
                                      selection=selection, diagnostic_stdout=diagnostic_stdout)
                except subprocess.TimeoutExpired as error:
                    if (check and timeout == 30 and input is None
                            and tuple(argv) == ('/usr/bin/python3', '-c', BOOT_SHA256_PROBE)
                            and error.cmd == [*ssh(self.config, attempts=attempts),
                                              remote(self.config, argv)]):
                        status = self.commands.last_returncode
                        try:
                            self._storage_timeout_sample(error, 'before-guest-diagnostic')
                            # One guarded, read-only exchange. Inline output stays
                            # in the existing private command artifact, off watch.
                            self.call(['/usr/bin/python3', '-c', BOOT_STORAGE_DIAGNOSTIC],
                                      timeout=10, attempts=1, check=False)
                            require(self.commands.last_returncode == 0,
                                    'transport:boot-storage-diagnostic-failed')
                        except Exception:
                            error.add_note('transport:boot-storage-diagnostic-unavailable')
                        finally:
                            self._storage_timeout_sample(error, 'after-guest-diagnostic')
                            self.commands.last_returncode = status
                    raise

    def _storage_timeout_sample(self, error, phase):
        """Distinguish guest writeback stalls from slow host disk completion.

        Sample only after the exact boot probe times out. Reuse the VM owner
        and existing report stream; emit numeric counters without disk paths,
        account names or raw domain XML. A diagnostic failure cannot replace
        the original timeout or authorize another attempt.
        """
        import json
        import xml.etree.ElementTree as ET
        from watch_activity import operation
        try:
            import libvirt
            with operation('Reading disk progress after the test connection stalled'):
                self.guard(self.config)
                connection = libvirt.open(vm_config.URI)
                try:
                    domain = connection.lookupByUUIDString(self.config['domain_uuid'])
                    require(connection.getURI() == vm_config.URI and
                            domain.ID() == self.config['domain_id'],
                            'transport:domain-replaced-or-shared')
                    disks = ET.fromstring(domain.XMLDesc(0)).findall('devices/disk[@device="disk"]')
                    require(len(disks) <= 4, 'transport:storage-diagnostic-disk-count')
                    samples = []
                    for disk in disks:
                        target = disk.find('target').get('dev')
                        stats = domain.blockStatsFlags(target, 0)
                        limits = domain.blockIoTune(target, 0)
                        samples.append({
                            'stats': {key: stats[key] for key in (
                                'rd_operations', 'rd_bytes', 'rd_total_times',
                                'wr_operations', 'wr_bytes', 'wr_total_times',
                                'flush_operations', 'flush_total_times', 'errs')
                                if type(stats.get(key)) is int},
                            'limits': {key: value for key, value in limits.items()
                                       if re.fullmatch(r'[a-z_]{1,64}', key)
                                       and type(value) is int}})
                    self.guard(self.config)
                    print('vm-storage-timeout: ' + json.dumps({
                        'phase': phase, 'monotonic_ns': time.monotonic_ns(),
                        'disks': samples}, sort_keys=True), file=sys.stderr, flush=True)
                finally:
                    connection.close()
        except Exception:
            error.add_note('transport:host-storage-diagnostic-unavailable')

    def _call(self, argv, *, input, timeout, check, attempts, on_output, on_stream, selection,
              diagnostic_stdout):
        started = time.perf_counter()
        command_started = None
        sequence = None
        outcome = 'failed'
        previous_watch = getattr(self.commands, 'watch_command', None)
        try:
            self.guard(self.config)
            command_started = time.perf_counter()
            current_sequence = getattr(self.commands, 'sequence', None)
            if type(current_sequence) is int:
                sequence = current_sequence + 1
            self.commands.watch_command = selection
            def command_output(data, stream):
                if stream == 'stdout':
                    on_output(data)
            result = self.commands.run([*ssh(self.config, attempts=attempts), remote(self.config, argv)],
                                       input=input, timeout=timeout, check=check, merge_stderr=False,
                                       on_output=on_stream if on_stream is not None else
                                       command_output if on_output is not None else None,
                                       **({} if diagnostic_stdout is None else
                                          {'diagnostic_stdout': diagnostic_stdout}))
            outcome = 'finished' if self.commands.last_returncode == 0 else 'failed'
            return result
        finally:
            self.commands.watch_command = previous_watch
            finished = time.perf_counter()
            elapsed = finished - started
            # Keep fast probes quiet. Fixed fields and the existing private
            # command sequence locate slow/failed exchanges without argv,
            # paths, host addresses, credentials or observation contents.
            if elapsed >= 1 or outcome == 'failed':
                guard_elapsed = (command_started if command_started is not None else finished) - started
                command_elapsed = finished - command_started if command_started is not None else 0
                identity = '' if sequence is None else f' sequence={sequence}'
                print(f'vm-transport-timing: operation=ssh-command{identity} state={outcome} '
                      f'duration_seconds={elapsed:.3f} guard_seconds={guard_elapsed:.3f} '
                      f'command_seconds={command_elapsed:.3f}', file=sys.stderr, flush=True)

    def ready(self):
        self.probe_ready()

    @observed('Waiting for the VM SSH connection')
    def probe_ready(self, *, boot_id=False, timeout=330):
        return self._probe_ready(boot_id=boot_id, timeout=timeout)

    @observed('Waiting for system startup to complete')
    def wait_boot_complete(self):
        """Observe systemd's terminal startup state before installed provisioning.

        This is the same boot boundary as system_guest.wait_for_boot. Degraded
        completion leaves every dependency assertion in force. There is one
        read-only command, with no service repair or uncertain-command retry.
        """
        config = dict(self.config)
        raw = self.call(['/usr/bin/systemctl', 'is-system-running', '--wait'],
                        timeout=600, check=False)
        status = self.commands.last_returncode
        require(self.config == config, 'transport:configuration-changed')
        # Lease guards share Commands and may replace last_returncode. Keep
        # systemctl's status before verifying the still-owned instance.
        self.guard(config)
        require(self.config == config, 'transport:configuration-changed')
        require(isinstance(raw, bytes) and (status, raw.strip()) in
                {(0, b'running'), (1, b'degraded')}, 'transport:boot-not-complete')
        return raw.decode('ascii').strip()

    @observed('Waiting for the VM to finish rebooting')
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
        # probes may repeat after SSH's transport-error exit status (255) or
        # after a stalled SSH attempt reaches its per-probe deadline.
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
                try:
                    result = self.call(argv, timeout=min(30, remaining), check=False)
                    # Lease guards also execute qemu-img through this Commands
                    # instance. Preserve SSH's status before the post-probe guard
                    # replaces last_returncode with its own successful result.
                    probe_returncode = self.commands.last_returncode
                except subprocess.TimeoutExpired as error:
                    # Commands has already stopped and waited for its owned
                    # child. Retry only this exact read-only SSH probe; a host
                    # ownership/validation command's timeout remains terminal.
                    if error.cmd != [*ssh(config), remote(config, argv)]:
                        raise
                    result = None
                    probe_returncode = 255
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

    @observed('Rebooting the VM and waiting for its new boot')
    def reboot(self):
        from watch_activity import event
        event('Requesting VM reboot; waiting for a new boot')
        before = self.call(['/usr/bin/python3', '-c', BOOT_SHA256_PROBE])
        require(isinstance(before, bytes) and re.fullmatch(rb'[0-9a-f]{64}\n', before),
                'transport:invalid-boot-output')
        self.request_customer_reboot(before.decode('ascii').strip())
        # The SSH session can close before sshd stops accepting new connections.
        # Reuse the bounded transition observer: a valid old boot is pending,
        # while malformed replies, guard errors and ownership loss still fail.
        self.wait_boot_change(before.decode('ascii').strip())

    @observed('Submitting the planned customer reboot')
    def request_customer_reboot(self, previous_boot_sha256):
        """Submit once on the pinned boot; observation belongs to the caller."""
        require(type(previous_boot_sha256) is str
                and re.fullmatch(r'[0-9a-f]{64}', previous_boot_sha256),
                'transport:invalid-previous-boot')
        program = ('import hashlib,os,pathlib,sys; '
            'assert hashlib.sha256(pathlib.Path("/proc/sys/kernel/random/boot_id").read_bytes())'
            '.hexdigest()==sys.argv[1]; '
            'os.execv("/usr/bin/systemctl", ["systemctl", "--no-ask-password", "reboot"])')
        self.call(['/usr/bin/python3', '-c', program, previous_boot_sha256],
                  timeout=180, check=False)
        require(self.commands.last_returncode in (0, 255), 'transport:reboot-command-failed')

    @observed('Transferring VM files')
    def copy(self, up, source, destination):
        require(source.endswith('/') == destination.endswith('/'), 'transport:copy-type')
        is_dir = source.endswith('/')
        local = local_path(self.config, destination if up else source)
        guest = source if up else destination
        require(guest.startswith('/') and '..' not in Path(guest).parts and guest != '/', 'transport:guest-path')
        if up:
            if is_dir:
                extract(self.call(['tar', '-C', guest, '-cf', '-', '.'], timeout=300,
                                  diagnostic_stdout=transfer_diagnostic), local)
            else:
                raw = self.call(['cat', '--', guest], timeout=300,
                                diagnostic_stdout=transfer_diagnostic)
                local.parent.mkdir(parents=True, exist_ok=True)
                require(not local.is_symlink(), 'transport:host-symlink')
                local.write_bytes(raw)
        elif is_dir:
            from system_runner import check_tree
            check_tree(local)
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as archive:
                archive.add(local, arcname='.')
            # One guarded SSH session owns both preparation and extraction.
            # The destination stays a positional argument, including spaces
            # and shell metacharacters; failed mkdir cannot start tar.
            self.call(['/bin/sh', '-c', 'mkdir -p -- "$1" && exec tar -C "$1" -xf -',
                       'onpc-copy', guest], input=stream.getvalue(), timeout=300)
        else:
            require(local.is_file() and not local.is_symlink(), 'transport:source-file')
            program = ('import os,pathlib,sys; p=pathlib.Path(sys.argv[1]); '
                       'p.parent.mkdir(parents=True,exist_ok=True); '
                       'f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,384); '
                       's=os.fdopen(f,"wb"); s.write(sys.stdin.buffer.read()); s.close(); '
                       'os.chmod(p,int(sys.argv[2]))')
            self.call(['python3', '-c', program, guest, str(stat.S_IMODE(local.stat().st_mode))],
                      input=local.read_bytes(), timeout=300)
