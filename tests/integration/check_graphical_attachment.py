#!/usr/bin/python3
"""One guarded boot comparing public graphics APIs, with private recvmsg trace."""

import importlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time

from owned_commands import Commands, require
import system_runner as runner


def probe(lease, commands, directory):
    lease.guard()
    expected = {'uuid': lease.source.uuid, 'id': lease.view.domain_id,
                'xml': lease.source.domain.XMLDesc(0)}
    raw = commands.run([
        '/usr/bin/strace', '--kill-on-exit', '-e', 'trace=recvmsg',
        '-o', str(directory / 'recvmsg.trace'),
        '/usr/bin/python3', '-B', str(Path(__file__).with_name('graphical_attachment_probe.py')),
    ], input=json.dumps(expected).encode(), timeout=55, check=False, merge_stderr=False)
    lease.guard()
    results = json.loads(raw)
    require(isinstance(results, list) and len(results) == 2 and
            [r['mode'] for r in results] == ['daemon', 'caller'], 'attachment:results')
    return results


def main():
    require(len(sys.argv) == 1, 'attachment:invalid-arguments')
    require(os.geteuid() == os.getegid() == 0, 'attachment:root-required')
    require(Path.cwd() == runner.ROOT == runner.baseline.guest_contract.CHECKOUT,
            'attachment:checkout')
    os.umask(0o077)
    directory = Path(tempfile.mkdtemp(prefix='onpc-graphical-attachment-'))
    commands, ledger = Commands(), runner.RunLedger()
    commands.directory = directory
    source = lease = host_before = None
    result = {'scope': 'guarded-graphics-attachment-diagnostic', 'outcome': 'failed',
              'evidence_directory': str(directory), 'attempts': []}
    started = time.monotonic()

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ledger.measure('preparation'):
            result['inputs_sha256'] = {p.name: runner.baseline.digest(p)
                                      for p in sorted(Path(__file__).parent.glob('*.py'))}
            host_before = runner.host_fingerprint(commands)
            api, guestfs = importlib.import_module('libvirt'), importlib.import_module('guestfs')
            api.virEventRegisterDefaultImpl()

            def events():
                while True:
                    api.virEventRunDefaultImpl()

            threading.Thread(target=events, daemon=True, name='libvirt-events').start()
            source = runner.baseline.LibvirtSource(api)
            lease = runner.Lease(source, commands,
                                 lambda disk, digest: runner.baseline.inspect_guest(guestfs, disk, digest),
                                 ledger=ledger, graphics_type='vnc')
        with lease:
            result['baseline_sha256'] = lease.state['baseline_sha256']
            with ledger.measure('preparation'):
                lease.prepare()
                lease.start()
            with ledger.measure('test'):
                result['attempts'] = probe(lease, commands, directory)
                require(any(r['outcome'] == 'passed' for r in result['attempts']),
                        'attachment:no-working-api')
                ledger.pass_outcome('infrastructure')
                ledger.pass_outcome('collection')
        result['outcome'] = 'passed'
    except (Exception, KeyboardInterrupt) as error:
        result['category'] = runner.record_caught_failure(ledger, error)
        result['exception_type'] = type(error).__name__
    finally:
        with ledger.measure('cleanup'):
            try:
                if host_before is not None:
                    require(runner.host_fingerprint(commands) == host_before, 'attachment:host-state-changed')
            except BaseException:
                ledger.fail_outcome('cleanup', 'attachment:host-state-unverifiable')
            finally:
                if source is not None:
                    try:
                        source.close()
                    except BaseException:
                        ledger.fail_outcome('cleanup', 'attachment:connection-close-failed')
        result.update(ledger.data())
        if any(v['outcome'] == 'failed' for v in ledger.outcomes.values()):
            result['outcome'] = 'failed'
        result['duration_seconds'] = round(time.monotonic() - started, 3)
        result['lease_phase'] = lease.state['phase'] if lease and lease.state else None
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, sort_keys=True))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
