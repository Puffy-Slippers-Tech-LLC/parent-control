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
import signal
import struct
import sys
import tempfile
import threading
import time
import uuid

import graphical_backend
from owned_commands import Commands, require
import system_runner as runner
from vm_transport import Transport


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import e2e_worker
from private_artifacts import EvidenceError, PrivateCollector
from provenance import VerifiedInputs
from recording import save_checkpoint
sys.path.pop(0)
STAGES = ('ready', 'gdm', 'selected', 'dismissed')
# All session names and identifiers stay inside this guest process. This is a
# read-only corroboration, never a replacement for graphical input/screens.
OBSERVATION = '''import json,subprocess,time
def call(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=10).stdout
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    active = call('systemctl', 'is-active', 'display-manager').strip() == 'active'
    user_session = False
    greeter = False
    for row in call('loginctl', 'list-sessions', '--no-legend', '--no-pager').splitlines():
        session = row.split()[0]
        props = dict(line.split('=', 1) for line in call(
            'loginctl', 'show-session', session, '-p', 'Class', '-p', 'Active', '-p', 'Type',
            '-p', 'Remote', '-p', 'Service', '-p', 'User').splitlines())
        # Our root SSH observation creates its own logind user session. Only
        # that non-graphical observation identity is excluded from this gate.
        observer = (props.get('User') == '0' and props.get('Service') == 'sshd' and
                    props.get('Remote') == 'yes' and props.get('Type') not in ('wayland', 'x11'))
        user_session |= props.get('Class') in ('user', 'user-early') and not observer
        greeter |= props.get('Class') == 'greeter' and props.get('Active') == 'yes' and props.get('Type') in ('wayland', 'x11')
    if active and greeter and not user_session:
        print('greeter-ready')
        break
    time.sleep(0.5)
else:
    print(json.dumps({'display_manager_active': active, 'active_graphical_greeter': greeter,
                      'unexpected_user_session': user_session}, sort_keys=True))
    raise SystemExit(1)
'''


def inputs():
    paths = [*sorted((ROOT / 'tests/integration').glob('*.py')),
             *sorted((ROOT / 'tests/integration/graphical_smoke').rglob('*.pm')),
             *sorted((ROOT / 'tests/e2e').glob('*.py')),
             ROOT / 'tests/e2e/scenarios.json', ROOT / 'tests/requirements.json',
             ROOT / 'tests/test-tools-ubuntu-26.04.txt']
    return {str(p.relative_to(ROOT)): runner.baseline.digest(p) for p in paths}


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
    def __init__(self, directory, lease, commands, host_key, progress=None):
        self.directory, self.lease, self.commands = directory, lease, commands
        self.host_key = host_key
        self.steps = []
        self.vm = None
        self.progress = progress

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
        if self.progress is not None:
            self.progress(stage, None)
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
        if self.progress is not None:
            # Persist the actual corroboration before acknowledging the next
            # guest action. Raw screenshots/SSH identities never enter reports.
            self.progress(stage, self.steps[-1])
        pending = self.directory / f'{stage}.reply.tmp'
        pending.write_text(json.dumps(reply))
        pending.rename(self.directory / f'{stage}.reply.json')
        runner.log('graphical:' + stage + '-observed')


def run_backend(directory, lease, commands, host_key, ledger, expected_inputs,
                *, progress=None, on_failure=None):
    smoke = Smoke(directory, lease, commands, host_key, progress)
    def validate():
        require(len(smoke.steps) == len(STAGES), 'smoke:missing-stages')
        module_result(directory)
    try:
        worker_result = e2e_worker.run_distribution(
            directory, lease, ledger, expected_inputs=expected_inputs,
            observe=smoke.step, validate=validate, on_failure=on_failure)
        return {'steps': smoke.steps, 'worker_evidence': worker_result}
    finally:
        original = sys.exception()
        try:
            (directory / 'steps.json').write_text(json.dumps(smoke.steps, indent=2) + '\n')
        except BaseException:
            ledger.fail_outcome('collection', 'smoke:step-report-failed')
            if original is None:
                raise


class Qualification:
    """Live diagnostic checkpoints, without an inventory or scenario override."""

    def __init__(self, directory, commands, ledger, collector, result, host_before):
        self.directory, self.commands, self.ledger = directory, commands, ledger
        self.collector, self.result, self.host_before = collector, result, host_before
        self.verified = None
        self.sequence = 0
        self.started = time.monotonic()
        self.active_stage = None

    def checkpoint(self, event):
        self.sequence += 1
        try:
            save_checkpoint(self.collector, self.sequence, event, {
                'scope': 'credential-free-worker-qualification',
                'active_stage': self.active_stage,
                'monotonic_seconds': time.monotonic() - self.started,
                'result': self.result, **self.ledger.data(),
            })
        except BaseException:
            self.ledger.fail_outcome('collection', 'smoke:checkpoint-failed')
            raise

    def progress(self, stage, observed):
        require(stage in STAGES, 'smoke:stage-request')
        self.active_stage = stage
        if observed is None:
            self.checkpoint('stage-started')
        else:
            self.result['steps'].append(dict(observed))
            self.active_stage = None
            self.checkpoint('stage-observed')

    def failure(self, category, code):
        # The worker has already put its fixed failure code in the shared ledger.
        self.checkpoint('worker-failed')

    def execute(self, lease, guestfs):
        try:
            self.checkpoint('attempt-started')
            with self.ledger.measure('preparation'):
                lease.prepare()
                host_key = runner.bootstrap(self.commands, lease, self.directory,
                                            guestfs, observation_only=True)
                lease.guard(off=True)
                lease.save('isolated')
                self.verified = VerifiedInputs(lease=lease)
                self.result['provenance'] = self.verified.inputs
                self.checkpoint('inputs-captured')
            with self.ledger.measure('test'):
                self.verified.recheck()
                self.result.update(run_backend(
                    self.directory, lease, self.commands, host_key, self.ledger,
                    self.verified.source_files, progress=self.progress, on_failure=self.failure))
        except BaseException as error:
            code = str(error) if isinstance(error, EvidenceError) else runner.error_category(error)
            if not any(v['outcome'] == 'failed' for v in self.ledger.outcomes.values()):
                self.ledger.fail_outcome('infrastructure', code)
            raise
        finally:
            original = sys.exception()
            try:
                self.checkpoint('before-cleanup')
            except BaseException:
                if original is None:
                    raise

    def finalize(self, lease):
        """Check and report after restoration, before the sole lease release."""
        self.result['lease_phase'] = lease.state['phase']
        self.result['preservation'] = {'source': False, 'host': False}
        first = None
        try:
            require(lease.fd is not None and lease.state['phase'] == 'complete',
                    'smoke:cleanup-lease-required')
            require(self.verified is not None, 'smoke:inputs-not-captured')
            self.verified.recheck()
            self.result['preservation']['source'] = True
        except BaseException as error:
            first = error
            self.ledger.fail_outcome('infrastructure', 'smoke:final-provenance-failed')
        try:
            require(runner.host_fingerprint(self.commands) == self.host_before,
                    'smoke:host-state-changed')
            self.result['preservation']['host'] = True
        except BaseException as error:
            first = first if first is not None else error
            self.ledger.fail_outcome('cleanup', 'smoke:host-state-unverifiable')
        try:
            if first is None and not any(v['outcome'] == 'failed' for v in self.ledger.outcomes.values()):
                require(self.result.get('worker_evidence', {}).get('outcome') == 'passed',
                        'smoke:worker-evidence-missing')
                self.ledger.pass_outcome('infrastructure')
                self.ledger.pass_outcome('collection')
                self.result['outcome'] = 'passed'
            self.checkpoint('after-cleanup')
            self.collector.verify([])
            if self.verified is not None and self.result['preservation']['source']:
                # A late refusal must revoke the earlier successful boundary's
                # preservation flag in the terminal failure checkpoint too.
                self.result['preservation']['source'] = False
                self.verified.recheck()
                self.result['preservation']['source'] = True
        except BaseException as error:
            first = first if first is not None else error
            self.ledger.fail_outcome('collection' if isinstance(error, EvidenceError)
                                     and str(error).startswith('artifact:') else 'infrastructure',
                                     'smoke:final-report-rejected')
        if first is not None:
            self.result['outcome'] = 'failed'
            try:
                self.checkpoint('finalization-rejected')
            except BaseException:
                pass
            raise first
        runner.log('graphical:finalized-with-lease-held')


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
        with PrivateCollector(run_id='qualification-' + uuid.uuid4().hex, secrets=[]) as collector:
            result['qualification_evidence'] = str(collector.path)
            qualification = Qualification(directory, commands, ledger, collector, result, host_before)
            lease.finalize = qualification.finalize
            with lease:
                result['baseline_sha256'] = lease.state['baseline_sha256']
                qualification.execute(lease, guestfs)
    except (Exception, KeyboardInterrupt) as error:
        result['outcome'] = 'failed'
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
