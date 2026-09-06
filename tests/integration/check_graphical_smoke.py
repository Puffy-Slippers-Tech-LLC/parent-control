#!/usr/bin/python3
"""Fixed credential-free generalhw smoke on the existing exclusively leased VM.

Invoke only through the project test dispatcher. No arguments, product install,
authentication input, arbitrary guest command, or public raw capture export.
"""

import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import sys
import tempfile
import threading
import time

import graphical_backend
from graphical_lease import Adapter, CallbackServer, lifecycle_variables
from graphical_worker import Worker
from owned_commands import Commands, require
import system_runner as runner
from vm_transport import Transport


ROOT = Path(__file__).resolve().parents[2]
STAGES = ('ready', 'gdm', 'menu', 'dismissed')
# All session names and identifiers stay inside this guest process. This is a
# read-only corroboration, never a replacement for graphical input/screens.
OBSERVATION = '''import subprocess,time
def call(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=10).stdout
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    active = call('systemctl', 'is-active', 'display-manager').strip() == 'active'
    classes = []
    greeter = False
    for row in call('loginctl', 'list-sessions', '--no-legend', '--no-pager').splitlines():
        session = row.split()[0]
        props = dict(line.split('=', 1) for line in call(
            'loginctl', 'show-session', session, '-p', 'Class', '-p', 'Active', '-p', 'Type').splitlines())
        classes.append(props.get('Class'))
        greeter |= props.get('Class') == 'greeter' and props.get('Active') == 'yes' and props.get('Type') in ('wayland', 'x11')
    if active and greeter and not any(c in ('user', 'user-early') for c in classes):
        print('greeter-ready')
        break
    time.sleep(0.5)
else:
    raise SystemExit(1)
'''


def inputs():
    paths = [*sorted((ROOT / 'tests/integration').glob('*.py')),
             *sorted((ROOT / 'tests/integration/graphical_smoke').rglob('*.pm')),
             ROOT / 'tests/test-tools-ubuntu-26.04.txt']
    return {str(p.relative_to(ROOT)): runner.baseline.digest(p) for p in paths}


def variables(directory, server, run):
    return {
        'BACKEND': 'generalhw', 'DISTRI': 'onpc-smoke',
        'CASEDIR': str(directory / 'distribution'),
        'WORKER_HOSTNAME': '127.0.0.1', 'GENERAL_HW_VNC_IP': '127.0.0.1',
        'GENERAL_HW_VNC_PORT': 5900, 'GENERAL_HW_NO_SERIAL': 1,
        'NOVIDEO': 1,
        **lifecycle_variables(server.path, run),
    }


def schedule_preflight(directory, commands):
    """Public schedule-only option: no backend constructed or lease acquired."""
    target = directory / 'schedule-preflight'
    target.mkdir(mode=0o700)
    raw = commands.run(['/usr/bin/isotovideo', '--workdir=' + str(target),
                        '_EXIT_AFTER_SCHEDULE=1',
                        'CASEDIR=' + str(Path(__file__).with_name('graphical_smoke')),
                        'DISTRI=onpc-smoke'], timeout=30, check=False)
    # The pinned CLI's END block overrides the documented early exit(0) with
    # its initial status 1. Require the exact completed schedule diagnostics;
    # an ordinary status-1 compile failure cannot satisfy this preflight.
    require(commands.last_returncode in (0, 1) and
            raw.count(b'scheduling smoke tests/smoke.pm') == 1 and
            raw.count(b'Early exit has been requested with _EXIT_AFTER_SCHEDULE. Only evaluating test schedule.') == 1,
            'smoke:schedule-preflight-failed')


def module_result(directory):
    result = json.loads((directory / 'testresults/result-smoke.json').read_text())
    require(result.get('result') == 'ok' and not result.get('dents') and
            all(d.get('result') not in ('fail', 'softfail') for d in result.get('details', [])),
            'smoke:module-not-passed')


def screenshot(directory, name):
    require(isinstance(name, str) and re.fullmatch(r'smoke-[0-9]+\.png', name),
            'smoke:invalid-screenshot-name')
    path = directory / 'testresults' / name
    require(not path.is_symlink() and path.resolve().parent == (directory / 'testresults').resolve(),
            'smoke:screenshot-path')
    raw = path.read_bytes()
    require(24 <= len(raw) <= 32 * 1024 * 1024 and raw[:16] == b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR',
            'smoke:invalid-png')
    width, height = struct.unpack('!II', raw[16:24])
    require(640 <= width <= 4096 and 480 <= height <= 2160, 'smoke:screen-size')
    return {'width': width, 'height': height, 'sha256': hashlib.sha256(raw).hexdigest()}


class Smoke:
    def __init__(self, directory, lease, commands, host_key):
        self.directory, self.lease, self.commands = directory, lease, commands
        self.host_key = host_key
        self.steps = []
        self.vm = None

    def step(self):
        if len(self.steps) == len(STAGES):
            return
        stage = STAGES[len(self.steps)]
        path = self.directory / f'{stage}.request.json'
        if not path.exists():
            return
        require(not path.is_symlink() and path.stat().st_size <= 1024, 'smoke:request-file')
        request = json.loads(path.read_text())
        require(set(request) == {'stage', 'screenshot'} and request['stage'] == stage,
                'smoke:stage-request')
        self.lease.guard()
        if stage == 'ready':
            require(request['screenshot'] is None, 'smoke:early-screenshot')
            hostname = runner.address(self.lease.source, timeout=90)
            (self.directory / 'known-hosts').write_text(f'{hostname} {self.host_key}\n')
            config = {'directory': str(self.directory), 'hostname': hostname,
                      'domain_uuid': self.lease.source.uuid,
                      'domain_id': self.lease.view.domain_id, 'run': self.lease.state['run']}
            self.vm = Transport(config, self.commands, guard=lambda _: self.lease.guard())
            self.vm.probe_ready(timeout=180)
            reply = {'observation': 'active-greeter-no-user-session'}
        else:
            reply = screenshot(self.directory, request['screenshot'])
            if stage != 'gdm':
                previous = self.steps[-1]
                require((reply['width'], reply['height']) == (previous['width'], previous['height'])
                        and reply['sha256'] != previous['sha256'], 'smoke:unchanged-screen')
        # Corroborate each captured stage, not just SSH availability at boot.
        require(self.vm.call(['/usr/bin/python3', '-c', OBSERVATION], timeout=110) == b'greeter-ready\n',
                'smoke:greeter-observation-failed')
        self.steps.append({'stage': stage, **reply})
        pending = self.directory / f'{stage}.reply.tmp'
        pending.write_text(json.dumps(reply))
        pending.rename(self.directory / f'{stage}.reply.json')
        runner.log('graphical:' + stage + '-observed')


def close_backend(worker, server, ledger):
    original = sys.exception()
    failure = None
    with ledger.measure('cleanup'):
        for resource in (worker, server):
            if resource is None:
                continue
            try:
                resource.close()
            except BaseException as error:
                failure = failure or error
                ledger.fail_outcome('cleanup', 'smoke:backend-cleanup-failed')
    if failure is not None and original is None:
        raise failure


def run_backend(directory, lease, commands, host_key, ledger):
    server = CallbackServer(Adapter(lease), directory)
    worker = None
    smoke = Smoke(directory, lease, commands, host_key)
    try:
        shutil.copytree(Path(__file__).with_name('graphical_smoke'), directory / 'distribution')
        (directory / 'distribution/needles').mkdir()
        (directory / 'vars.json').write_text(json.dumps(variables(directory, server, lease.state['run'])))
        worker = Worker(directory, server.path, lease.state['run'],
                        ['/usr/bin/isotovideo', '--exit-status-from-test-results'])
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            result = worker.poll()
            if result is not None:
                require(result == 0, 'smoke:backend-failed')
                require(len(smoke.steps) == len(STAGES), 'smoke:missing-stages')
                module_result(directory)
                return smoke.steps
            server.serve_once()
            smoke.step()
        require(False, 'smoke:timeout')
    finally:
        try:
            (directory / 'steps.json').write_text(json.dumps(smoke.steps, indent=2) + '\n')
        finally:
            close_backend(worker, server, ledger)


def main():
    require(len(sys.argv) == 1, 'smoke:invalid-arguments')
    require(os.geteuid() == os.getegid() == 0, 'smoke:root-required')
    require(Path.cwd() == ROOT == runner.baseline.guest_contract.CHECKOUT, 'smoke:checkout')
    os.umask(0o077)
    directory = Path(tempfile.mkdtemp(prefix='onpc-graphical-smoke-'))
    commands, ledger = Commands(), runner.RunLedger()
    private = directory / 'private'
    private.mkdir(mode=0o700)
    commands.directory = private
    source = lease = host_before = None
    result = {'scope': 'credential-free-graphical-feasibility', 'outcome': 'failed',
              'raw_capture': 'root-private-not-approved-for-export',
              'evidence_directory': str(directory), 'steps': []}
    started = time.monotonic()
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ledger.measure('preparation'):
            result['inputs_sha256'] = inputs()
            result['backend'] = graphical_backend.check(commands)
            schedule_preflight(directory, commands)
            (directory / 'input').mkdir(mode=0o700)
            (directory / 'input/selected-inputs.json').write_text(json.dumps(result['inputs_sha256'], sort_keys=True))
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
                host_key = runner.bootstrap(commands, lease, directory, guestfs, observation_only=True)
                lease.guard(off=True)
                lease.save('isolated')
            with ledger.measure('test'):
                result['steps'] = run_backend(directory, lease, commands, host_key, ledger)
                require(inputs() == result['inputs_sha256'], 'smoke:source-inputs-changed')
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
                    require(runner.host_fingerprint(commands) == host_before, 'smoke:host-state-changed')
            except BaseException:
                ledger.fail_outcome('cleanup', 'smoke:host-state-unverifiable')
                result['outcome'] = 'failed'
            finally:
                if source is not None:
                    try:
                        source.close()
                    except BaseException:
                        ledger.fail_outcome('cleanup', 'smoke:connection-close-failed')
                        result['outcome'] = 'failed'
        if any(v['outcome'] == 'failed' for v in ledger.outcomes.values()):
            result['outcome'] = 'failed'
        result.update(ledger.data())
        result['duration_seconds'] = round(time.monotonic() - started, 3)
        result['lease_phase'] = lease.state['phase'] if lease and lease.state else None
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, sort_keys=True))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
