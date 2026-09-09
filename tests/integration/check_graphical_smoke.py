#!/usr/bin/python3
"""Fixed generalhw qualifications on the existing exclusively leased VM.

Invoke only through the project test dispatcher. The credential entry point
adds fixture GDM authentication. No arbitrary guest command or raw capture export.
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
from provenance import VerifiedInputs, preflight_source, refusal_code
from recording import save_checkpoint
from asset_transfer import AssetTransfer
from guest_observations import GREETER as OBSERVATION
from observation_transport import ReadOnlyObservations
from fixture_credentials import FixtureCredentials, preflight as credential_preflight
from graphical_serial import provision_getty
from installation_boundary import InstallationBoundary
import installation_observations
sys.path.pop(0)
STAGES = ('ready', 'gdm', 'selected', 'dismissed')
AUTH_STAGES = (*STAGES, 'authenticated')
SERIAL_STAGES = (*STAGES, 'serial-password', 'serial-authenticated', 'serial-command', 'serial-logout',
                 'gdm-return')
INSTALL_STAGES = (*STAGES, 'serial-password', 'serial-authenticated',
                  *InstallationBoundary.STAGES, 'reboot-ready', 'reboot-password',
                  'reboot-observed', 'gdm-return')
INSTALL_REFUSAL_STAGES = (*STAGES, 'serial-password', 'serial-authenticated',
                          *InstallationBoundary.REFUSAL_STAGES, 'serial-logout', 'gdm-return')


def inputs():
    paths = [*sorted((ROOT / 'tests/integration').glob('*.py')),
             *sorted((ROOT / 'tests/e2e').glob('*.py')),
             ROOT / 'tests/e2e/scenarios.json', ROOT / 'tests/requirements.json',
             ROOT / 'tests/test-tools-ubuntu-26.04.txt']
    result = {str(p.relative_to(ROOT)): runner.baseline.digest(p) for p in paths}
    prefix = e2e_worker.DISTRIBUTION.relative_to(ROOT).as_posix() + '/'
    result.update({prefix + name: hashlib.sha256(data).hexdigest()
                   for name, data in e2e_worker.distribution_inputs().items()})
    return result


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
    def __init__(self, directory, lease, commands, host_key, progress=None, transfer=None,
                 authenticate=False, serial=False, installation=None):
        self.directory, self.lease, self.commands = directory, lease, commands
        self.host_key = host_key
        self.steps = []
        self.vm = None
        self.progress = progress
        self.transfer = transfer
        require(installation is None or (serial and authenticate and transfer is not None
                and installation.transfer is transfer), 'smoke:installation-prerequisites')
        self.installation = installation
        self._failed = False
        self._reboot_boot = None
        self._reboot_password_verified = False
        self.stages = (INSTALL_REFUSAL_STAGES if installation is not None and installation.refusal else
                       INSTALL_STAGES if installation is not None else
                       SERIAL_STAGES if serial else AUTH_STAGES if authenticate else STAGES)

    def step(self, serial_console=None):
        require(not self._failed, 'smoke:previous-failure')
        try:
            self._step(serial_console)
        except BaseException:
            self._failed = True
            raise

    def _step(self, serial_console):
        if len(self.steps) == len(self.stages):
            return
        stage = self.stages[len(self.steps)]
        path = self.directory / f'{stage}.request.json'
        if not path.exists():
            return
        require(not path.is_symlink() and path.stat().st_size <= 1024, 'smoke:request-file')
        request = json.loads(path.read_text())
        require(set(request) == {'stage', 'screenshot'} and request['stage'] == stage,
                'smoke:stage-request')
        if stage.startswith(('serial-', 'install-', 'reboot-')):
            # The stage request is published after the worker's input. Drain
            # those bytes before a blocking SSH observation; otherwise the
            # observer could wait for input still buffered in our own pipe.
            require(serial_console is not None, 'smoke:serial-transport-required')
            serial_console.step()
            if serial_console.pending_in:
                return
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
            transport = Transport(config, self.commands, guard=lambda _: self.lease.guard())
            transport.probe_ready(timeout=180)
            self.vm = ReadOnlyObservations(transport, on_diagnostic=(
                lambda condition: self.progress(self.stages[len(self.steps)],
                    {'recipient_refusal': condition})) if self.progress is not None else None)
            reply = {'observation': 'active-greeter-no-user-session'}
            reply['authenticate'] = self.stages == AUTH_STAGES
            reply['serial'] = self.stages == SERIAL_STAGES
            reply['install'] = self.installation is not None
            reply['install_refusal'] = self.installation is not None and self.installation.refusal
            if self.transfer is not None:
                reply['assets'] = self.transfer.observe(self.vm)
        elif stage.startswith('install-'):
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            self.installation.observer = self.vm
            reply = self.installation.observe(stage)
        elif stage == 'reboot-ready':
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            installed = self.steps[-1]
            require(installed['stage'] == 'install-complete'
                    and installed.get('verified_package_digest') is True
                    and installed.get('installed_identity_verified') is True
                    and installed.get('product_reboot_required') is True,
                    'smoke:reboot-before-installation')
            boot = self.vm.read('boot')['boot_sha256']
            require(boot == installed['boot_sha256'], 'smoke:premature-reboot')
            session = self.vm.read('serial-session')
            require(self.vm.read('boot')['boot_sha256'] == boot, 'smoke:premature-reboot')
            self._reboot_boot = boot
            reply = {**session, 'boot_sha256': boot, 'customer_reboot_authorized': True}
        elif stage == 'reboot-password':
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            require(self._reboot_boot is not None, 'smoke:reboot-not-authorized')
            self.installation.verified.recheck()
            require(self.vm.read('boot')['boot_sha256'] == self._reboot_boot,
                    'smoke:premature-reboot')
            reply = self.vm.read('reboot-password')
            require(reply.get('sudo_reboot_process_verified') is True
                    and reply.get('terminal_echo_disabled') is True,
                    'smoke:reboot-password-unverified')
            require(self.vm.read('boot')['boot_sha256'] == self._reboot_boot,
                    'smoke:premature-reboot')
            self.installation.verified.recheck()
            self._reboot_password_verified = True
            reply = {**reply, 'boot_sha256': self._reboot_boot}
        elif stage == 'reboot-observed':
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            require(self._reboot_boot is not None and self._reboot_password_verified,
                    'smoke:reboot-not-authorized')
            if self.progress is not None:
                self.progress(stage, {'serial_input_drained': True})
            reply = self.vm.wait_boot_change(self._reboot_boot, on_diagnostic=(
                lambda report: self.progress(stage, {'reboot_diagnostic': report}))
                if self.progress is not None else None)
        elif stage == 'gdm-return':
            # The match's automatic screenshot stays private. The callback
            # reconciles it from the completed module, never reopening capture.
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            reply = self.vm.read('greeter')
            if self._reboot_boot is not None:
                boot = self.vm.read('boot')['boot_sha256']
                require(boot == self.steps[-1]['boot_sha256'], 'smoke:boot-changed-again')
                enforcement = self.vm.read('startup-enforcement')
                broker = self.vm.read('startup-broker')
                layout = self.installation.observe_installed_layout()
                require(enforcement['boot_sha256'] == boot and broker['boot_sha256'] == boot
                        and self.vm.read('boot')['boot_sha256'] == boot,
                        'smoke:boot-changed-again')
                reply = {**reply, 'boot_sha256': boot, 'customer_reboot_verified': True,
                         'startup_enforcement': enforcement, 'startup_broker': broker,
                         'installed_layout': layout}
        elif stage.startswith('serial-'):
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            if stage == 'serial-password':
                reply = self.vm.read('serial-password')
            elif stage == 'serial-logout':
                reply = self.vm.read('greeter')
            else:
                reply = self.vm.read('serial-session')
                if stage == 'serial-command':
                    reply['command_marker_verified'] = True
        elif stage == 'authenticated':
            # No post-password screenshot may cross the explicit capture route.
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            reply = self.vm.read('parent-session')
        else:
            reply = screenshot(self.directory, request['screenshot'])
            if stage != 'gdm':
                previous = self.steps[-1]
                require((reply['width'], reply['height']) == (previous['width'], previous['height'])
                        and reply['sha256'] != previous['sha256'], 'smoke:unchanged-screen')
        # Corroborate each captured stage, not just SSH availability at boot.
        if stage not in ('authenticated', 'gdm-return') and not stage.startswith(('serial-', 'install-', 'reboot-')):
            self.vm.read('greeter')
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
                *, progress=None, on_failure=None, transfer=None, credentials=None, serial=False,
                installation=None):
    smoke = Smoke(directory, lease, commands, host_key, progress, transfer,
                  authenticate=credentials is not None, serial=serial, installation=installation)
    def validate():
        require(len(smoke.steps) == len(smoke.stages), 'smoke:missing-stages')
        module_result(directory)
    try:
        worker_result = e2e_worker.run_distribution(
            directory, lease, ledger, expected_inputs=expected_inputs,
            observe=smoke.step, validate=validate, on_failure=on_failure, credentials=credentials,
            serial=serial, timeout=960 if installation is not None and not installation.refusal else 600)
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

    def __init__(self, directory, commands, ledger, collector, result, host_before, assets=None,
                 credentials=None, serial=False, install=False, install_refusal=False):
        self.directory, self.commands, self.ledger = directory, commands, ledger
        self.collector, self.result, self.host_before = collector, result, host_before
        self.verified = None
        self.sequence = 0
        self.started = time.monotonic()
        self.active_stage = None
        self.assets = assets
        self.transfer = None
        self.credentials = credentials
        self.serial = serial
        self.install = install
        self.install_refusal = install_refusal

    def checkpoint(self, event):
        self.sequence += 1
        try:
            save_checkpoint(self.collector, self.sequence, event, {
                'scope': ('deliberate-installation-refusal-qualification' if self.install_refusal else
                          'authenticated-installation-qualification' if self.install else
                          'fixture-credential-qualification' if self.credentials is not None
                          else 'credential-free-worker-qualification'),
                'active_stage': self.active_stage,
                'monotonic_seconds': time.monotonic() - self.started,
                'result': self.result, **self.ledger.data(),
            })
        except BaseException:
            self.ledger.fail_outcome('collection', 'smoke:checkpoint-failed')
            raise

    def progress(self, stage, observed):
        require(stage in (INSTALL_REFUSAL_STAGES if self.install_refusal else
                          INSTALL_STAGES if self.install else SERIAL_STAGES if self.serial else
                          AUTH_STAGES if self.credentials is not None else STAGES),
                'smoke:stage-request')
        self.active_stage = stage
        if observed is None:
            self.checkpoint('stage-started')
        elif stage == 'reboot-observed' and set(observed) == {'serial_input_drained'}:
            require(observed['serial_input_drained'] is True, 'smoke:diagnostic-condition')
            self.result['reboot_input_drained'] = True
            self.checkpoint('reboot-input-drained')
        elif stage == 'reboot-observed' and set(observed) == {'reboot_diagnostic'}:
            report = observed['reboot_diagnostic']
            require(isinstance(report, dict) and set(report) == {
                'old_boot', 'ssh_unavailable', 'changed_boot', 'outcome'}
                and all(type(report[key]) is int and report[key] >= 0
                        for key in ('old_boot', 'ssh_unavailable', 'changed_boot'))
                and report['outcome'] in ('changed-boot', 'unknown-error', 'interrupted',
                    'readiness-timeout', 'configuration-changed', 'invalid-boot-output',
                    'guest-probe-failed', 'domain-replaced-or-shared'),
                'smoke:diagnostic-condition')
            self.result['reboot_diagnostic'] = dict(report)
            self.checkpoint('reboot-probe-finished')
        elif stage in ('install-password', 'reboot-password') and set(observed) == {'recipient_refusal'}:
            # Refusal is diagnostic evidence, never a completed proof step.
            require(observed['recipient_refusal'] in
                    installation_observations.SUDO_PASSWORD_STAGES, 'smoke:diagnostic-condition')
            key = 'installation_diagnostic' if stage == 'install-password' else 'reboot_authentication_diagnostic'
            self.result[key] = dict(observed)
            self.checkpoint('stage-rejected')
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
                self.verified = VerifiedInputs(lease=lease, assets=self.assets)
                self.result['provenance'] = self.verified.inputs
                self.checkpoint('inputs-captured')
                if self.credentials is not None:
                    self.checkpoint('credential-provisioning-started')
                    self.result['fixture_credentials'] = self.credentials.provision(
                        lease, self.verified, self.directory, guestfs, self.commands)
                    self.checkpoint('credential-provisioning-verified')
                if self.serial:
                    provision_getty(lease, guestfs)
                    self.result['serial_getty'] = 'stock-password-authentication'
                    self.checkpoint('serial-getty-provisioned')
                if self.assets is not None:
                    self.transfer = AssetTransfer(self.verified)
                    self.checkpoint('asset-transfer-started')
                    self.result['asset_transfer'] = self.transfer.provision(lease, guestfs)
                    self.checkpoint('asset-transfer-verified')
                installation = (InstallationBoundary(None, self.verified, self.transfer,
                                                     refusal=self.install_refusal)
                                if self.install or self.install_refusal else None)
            with self.ledger.measure('test'):
                self.verified.recheck()
                self.result.update(run_backend(
                    self.directory, lease, self.commands, host_key, self.ledger,
                    self.verified.source_files, progress=self.progress, on_failure=self.failure,
                    transfer=self.transfer, credentials=self.credentials, serial=self.serial,
                    installation=installation))
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

    def _recheck_final_inputs(self):
        try:
            self.verified.recheck()
        except BaseException as error:
            self.result.setdefault('final_provenance_refusal', refusal_code(error))
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
            self._recheck_final_inputs()
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
                self._recheck_final_inputs()
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


def main(*, assets=None, provision_credentials=False, serial=False, install=False,
         install_refusal=False):
    require(type(install) is bool and type(install_refusal) is bool
            and not (install and install_refusal)
            and (not (install or install_refusal) or (assets is not None and serial
            and provision_credentials)), 'smoke:installation-prerequisites')
    require(type(serial) is bool and (not serial or provision_credentials), 'smoke:serial-credentials')
    require(assets is not None or len(sys.argv) == 1, 'smoke:invalid-arguments')
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
    if assets is not None:
        result['scope'] = 'credential-free-asset-transfer-qualification'
    credentials = FixtureCredentials() if provision_credentials else None
    if credentials is not None:
        result['scope'] = 'fixture-authentication-qualification'
    if serial:
        result['scope'] = 'fixture-serial-command-qualification'
    if install:
        result['scope'] = 'authenticated-installation-qualification'
    if install_refusal:
        result['scope'] = 'deliberate-installation-refusal-qualification'
    started = time.monotonic()
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ledger.measure('preparation'):
            result['inputs_sha256'] = inputs()
            result['backend'] = graphical_backend.check(commands)
            if credentials is not None:
                credential_preflight(commands)
            schedule_preflight(directory, commands)
            staged = None
            if assets is not None:
                staged = directory / 'assets'
                runner.stage_assets(runner.artifact_source(assets), staged, commands)
                staged.chmod(0o700)
                result['source_preflight'] = preflight_source(staged)
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
        with PrivateCollector(run_id='qualification-' + uuid.uuid4().hex,
                              secrets=credentials.variables.registered_secrets
                              if credentials is not None else []) as collector:
            result['qualification_evidence'] = str(collector.path)
            qualification = Qualification(directory, commands, ledger, collector, result, host_before,
                                          staged, credentials, serial, install, install_refusal)
            lease.finalize = qualification.finalize
            with lease:
                result['baseline_sha256'] = lease.state['baseline_sha256']
                qualification.execute(lease, guestfs)
    except (Exception, KeyboardInterrupt) as error:
        result['outcome'] = 'failed'
        if isinstance(error, EvidenceError) and not any(
                value['outcome'] == 'failed' for value in ledger.outcomes.values()):
            ledger.fail_outcome('infrastructure', str(error))
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
