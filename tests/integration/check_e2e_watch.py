#!/usr/bin/python3
"""Guarded spectator qualification: client churn and collector failure."""

import importlib
import json
import os
from pathlib import Path
import signal
import struct
import sys
import tempfile
import threading
import time

from graphical_lease import Adapter
from owned_commands import Commands, require
import system_runner as runner


class RFBProbe:
    """Minimal RFB 3.8 raw 1-pixel request, on the automation's own endpoint."""

    def __init__(self, peer):
        self.peer = peer
        peer.settimeout(5)
        require(self.read(12) == b'RFB 003.008\n', 'watch-rfb:greeting')
        peer.sendall(b'RFB 003.008\n')
        types = self.read(self.read(1)[0])
        require(1 in types, 'watch-rfb:authentication')
        peer.sendall(b'\x01')
        require(self.read(4) == b'\0' * 4, 'watch-rfb:authentication')
        peer.sendall(b'\x01')  # Shared automation connection.
        header = self.read(24)
        length = struct.unpack('>I', header[20:24])[0]
        require(length < 4096, 'watch-rfb:name-size')
        self.read(length)
        # Fixed little-endian RGB32, then raw encoding only.
        peer.sendall(struct.pack('>BBBBBBBBHHHBBBxxx', 0, 0, 0, 0, 32, 24, 0, 1,
                                 255, 255, 255, 16, 8, 0))
        peer.sendall(struct.pack('>BBHi', 2, 0, 1, 0))

    def read(self, count):
        data = b''
        while len(data) < count:
            part = self.peer.recv(count - len(data))
            require(part, 'watch-rfb:eof')
            data += part
        return data

    def frame(self):
        started = time.monotonic()
        self.peer.sendall(struct.pack('>BBHHHH', 3, 0, 0, 0, 1, 1))
        header = self.read(4)
        require(header[:2] == b'\0\0', 'watch-rfb:update')
        for _ in range(struct.unpack('>H', header[2:])[0]):
            x, y, width, height, encoding = struct.unpack('>HHHHi', self.read(12))
            # QEMU rounds damage to tiles, including for a one-pixel request.
            require(encoding == 0 and x >= 0 and y >= 0 and
                    0 < width <= 2048 and 0 < height <= 2048, 'watch-rfb:rectangle')
            self.read(width * height * 4)
        return round((time.monotonic() - started) * 1000, 2)


def probe(lease, commands, directory, host_key):
    from e2e_progress import Progress
    lease.watch_progress = Progress([dict(case_id='spectator-harness', coverage_id=1,
                                         title='Spectator harness')])
    lease.watch_progress.case('spectator-harness')
    lease.watch_progress.step('Observe VM frames and command output')
    adapter = Adapter(lease)
    try:
        adapter.request('off', adapter.run)
        adapter.request('on', adapter.run)
        observer = adapter.observer
        require(observer is not None and observer.ready.is_set(), 'watch:collector-unavailable')
        vnc = RFBProbe(adapter.request('graphics', adapter.run))
        before = vnc.frame()
        from vm_transport import Transport
        hostname = runner.address(lease.source)
        (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
        vm = Transport(dict(directory=str(directory), hostname=hostname,
            run=lease.state['run'], domain_uuid=lease.source.uuid,
            domain_id=lease.view.domain_id), commands, guard=lambda _: lease.guard())
        vm.ready()
        require(vm.call(['printf', 'ONPC-WATCH-SSH-STDOUT\\n']) == b'ONPC-WATCH-SSH-STDOUT\n',
                'watch:ssh-stdout')
        vm.call(['ls', '--', '/onpc-watch-missing-entry'], check=False)
        require(commands.last_returncode != 0, 'watch:ssh-stderr')
        result = json.loads(commands.run(['/usr/bin/python3', '-B',
            str(Path(__file__).with_name('e2e_watch_probe.py'))], timeout=40))
        result['rfb_before_ms'] = before
        result['rfb_after_client_churn_ms'] = vnc.frame()
        # Harness fault only; never injected into customer E2E scenarios.
        signal.pidfd_send_signal(observer.pidfd, signal.SIGSTOP)
        require(observer.finished.wait(8), 'watch:watchdog-failed')
        require(observer.child is None and observer.pidfd is None, 'watch:collector-not-reaped')
        result['rfb_after_collector_stall_ms'] = vnc.frame()
        adapter.revalidate()
        result['watchdog_reaped_collector'] = True
        adapter.request('off', adapter.run)
        return result
    finally:
        adapter.close_display()
        adapter.close_observer()


def maintenance_probe(lease, commands, directory, host_key, *, detached=True):
    """Exercise automatic observation and handoff with no graphical/E2E owner."""
    from vm_transport import Transport
    from watch_activity import operation
    lease.watch_detached = detached
    lease.start()
    require(lease.watch is not None, 'watch:maintenance-collector-unavailable')
    # The short-lived maintenance launcher closes precisely these handles on
    # return. The keeper must retain its feed without holding the VM lease.
    if detached:
        lease.watch.detach()
        lease.watch = None
    hostname = runner.address(lease.source)
    (directory / 'known-hosts').write_text(f'{hostname} {host_key}\n')
    vm = Transport(dict(directory=str(directory), hostname=hostname,
        run=lease.state['run'], domain_uuid=lease.source.uuid,
        domain_id=lease.view.domain_id), commands, guard=lambda _: lease.guard())
    vm.ready()
    vm.call(['printf', 'ONPC-WATCH-SSH-STDOUT\\n'])
    vm.call(['ls', '--', '/onpc-watch-missing-entry'], check=False)
    reader = ['/usr/bin/python3', '-B', str(Path(__file__).with_name('e2e_watch_probe.py'))]
    with operation('Qualifying VM maintenance observation'):
        result = json.loads(commands.run([*reader, '--experiment'], timeout=40))
    lease.stop()
    result.update(json.loads(commands.run([*reader, '--stopped'], timeout=20)))
    return result


def system_probe(lease, commands, directory, host_key):
    return maintenance_probe(lease, commands, directory, host_key, detached=False)


def main():
    require(len(sys.argv) == 1 and os.geteuid() == os.getegid() == 0, 'watch:invocation')
    require(Path.cwd() == runner.ROOT == runner.baseline.guest_contract.CHECKOUT, 'watch:checkout')
    os.umask(0o077)
    directory = Path(tempfile.mkdtemp(prefix='onpc-e2e-watch-check-'))
    print('watch-check: evidence=' + str(directory), flush=True)
    commands, ledger = Commands(), runner.RunLedger()
    commands.directory = directory
    source = lease = host_before = None
    result = {'scope': 'spectator-harness', 'outcome': 'failed', 'evidence_directory': str(directory)}
    started = time.monotonic()
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        host_before = runner.host_fingerprint(commands)
        api, guestfs = importlib.import_module('libvirt'), importlib.import_module('guestfs')
        api.virEventRegisterDefaultImpl()
        def events():
            while True:
                api.virEventRunDefaultImpl()
        threading.Thread(target=events, daemon=True, name='libvirt-events').start()
        source = runner.baseline.LibvirtSource(api)
        for name, graphics, run_probe in (('maintenance', 'vnc', maintenance_probe),
                                         ('system', 'spice', system_probe),
                                         ('probe', 'vnc', probe)):
            attempt = directory / name
            attempt.mkdir(mode=0o700)
            commands.directory = attempt
            lease = runner.Lease(source, commands,
                lambda disk, digest: runner.baseline.inspect_guest(guestfs, disk, digest),
                ledger=ledger, graphics_type=graphics)
            with lease:
                lease.prepare()
                inputs = attempt / 'input'
                inputs.mkdir(mode=0o700)
                (inputs / 'selected-inputs.json').write_text(json.dumps({'scope': 'spectator-harness'}))
                host_key = runner.bootstrap(commands, lease, attempt, guestfs, observation_only=True)
                lease.save('isolated')
                result[name] = run_probe(lease, commands, attempt, host_key)
                ledger.pass_outcome('infrastructure')
                ledger.pass_outcome('collection')
        result['outcome'] = 'passed'
    except (Exception, KeyboardInterrupt) as error:
        result['category'] = runner.record_caught_failure(ledger, error)
        result['exception_type'] = type(error).__name__
    finally:
        try:
            if host_before is not None:
                require(runner.host_fingerprint(commands) == host_before, 'watch:host-state-changed')
        except BaseException:
            ledger.fail_outcome('cleanup', 'watch:host-state-unverifiable')
        finally:
            if source is not None:
                source.close()
        result.update(ledger.data())
        if any(v['outcome'] == 'failed' for v in ledger.outcomes.values()):
            result['outcome'] = 'failed'
        result['duration_seconds'] = round(time.monotonic() - started, 3)
        result['lease_phase'] = lease.state['phase'] if lease and lease.state else None
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
