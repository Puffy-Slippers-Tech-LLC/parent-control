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
from qualification_storage import allocate, session as storage_session

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
import installed_setup
from guest_observations import GREETER as OBSERVATION
from observation_transport import ReadOnlyObservations
from fixture_credentials import (FixtureCredentials, preflight as credential_preflight,
                                 provision_vt6_login_window)
from graphical_serial import provision_getty
from ui_observations import UiObservations
from installation_boundary import InstallationBoundary
import installation_observations
from vt6_authentication import (Authentication as VT6Authentication, STAGES as VT6_LOGIN_STAGES,
                                REFUSALS as VT6_AUTH_REFUSALS)
sys.path.pop(0)
STAGES = ('ready', 'gdm', 'selected', 'dismissed')
VT6_PROMPT_STAGES = (*STAGES, 'vt6-ready', 'vt6-login-screen', 'vt6-prompt-ready', 'vt6-prompt-screen')
VT6_AUTH_STAGES = (*STAGES, *VT6_LOGIN_STAGES)
AUTH_STAGES = (*STAGES, 'authenticated')
SERIAL_STAGES = (*STAGES, 'serial-password', 'serial-authenticated', 'serial-command', 'serial-logout',
                 'gdm-return')
FUNCTIONAL_SERIAL_STAGES = ('ready', 'gdm', 'focused', *SERIAL_STAGES[2:])
FUNCTIONAL_GDM_OPERATIONS = {
    'gdm': 'gdm-product-free-list',
    'focused': 'gdm-product-free-focused',
    'selected': 'gdm-product-free-select-parent',
    'dismissed': 'gdm-product-free-returned',
    'gdm-return': 'gdm-product-free-returned',
}
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


def harness_observation(observer, projection):
    """HAR03's closed harness bindings; the observer owns guards/schema/latch."""
    require(projection in ('boot', 'greeter', 'serial-password', 'serial-session'),
            'smoke:harness-projection')
    return observer.read(projection)


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


def matched_serial_screens(directory):
    """Retained legacy pixel qualification; case 1 uses functional UI evidence."""
    module_result(directory)
    details = json.loads((directory / 'testresults/result-smoke.json').read_text())['details']
    matches = [(i, d) for i, d in enumerate(details) if 'needle' in d]
    account, prompt = 'onpc-gdm-parent-account', 'onpc-gdm-parent-masked-password'
    require([d['needle'] for _, d in matches] == [account, account, account, prompt, account, account],
            'qualification:match-sequence')
    logout = [i for i, d in enumerate(details) if d.get('title') == 'serial-logout' and d.get('result') == 'ok']
    returned = [i for i, d in enumerate(details) if d.get('title') == 'gdm-return' and d.get('result') == 'ok']
    require(len(logout) == len(returned) == 1
            and matches[-2][0] < logout[0] < matches[-1][0] < returned[0],
            'qualification:return-order')
    result = []
    for (index, match), stage in zip(matches, ('initial', 'select-ready', 'click', 'prompt', 'dismissed', 'returned')):
        require(match.get('result') == 'ok' and match.get('area')
                and all(a.get('result') == 'ok' and a.get('similarity') == 100 for a in match['area']),
                'qualification:match-quality')
        result.append({'stage': stage, 'detail_index': index, 'needle': match['needle'],
                       **screenshot(directory, match.get('screenshot'))})
    return result


class Smoke:
    def __init__(self, directory, lease, commands, host_key, progress=None, transfer=None,
                 authenticate=False, serial=False, installation=None, vt6_prompt=False,
                 vt6_auth=False, verified=None, functional=False):
        self.directory, self.lease, self.commands = directory, lease, commands
        self.host_key = host_key
        self.steps = []
        self.vm = None
        self.progress = progress
        self.transfer = transfer
        require(type(functional) is bool and (not functional or
                (serial and authenticate and installation is None and not vt6_auth and not vt6_prompt)),
                'smoke:functional-prerequisites')
        self.functional, self.ui = functional, None
        require(type(vt6_prompt) is bool and (not vt6_prompt or
                (not authenticate and not serial and installation is None and transfer is None)),
                'smoke:vt6-prompt-prerequisites')
        self._vt6_boot = None
        require(type(vt6_auth) is bool and (not vt6_auth or (authenticate and not serial
                and not vt6_prompt and installation is None and transfer is None
                and verified is not None and progress is not None)), 'smoke:vt6-auth-prerequisites')
        self.vt6_auth, self.verified = vt6_auth, verified
        self._vt6_authentication = None
        self._worker_guard = None
        require(installation is None or (serial and authenticate and transfer is not None
                and installation.transfer is transfer), 'smoke:installation-prerequisites')
        self.installation = installation
        self._failed = False
        self._reboot_boot = None
        self._reboot_password_verified = False
        self.stages = (FUNCTIONAL_SERIAL_STAGES if functional else
                       VT6_AUTH_STAGES if vt6_auth else VT6_PROMPT_STAGES if vt6_prompt else
                       INSTALL_REFUSAL_STAGES if installation is not None and installation.refusal else
                       INSTALL_STAGES if installation is not None else
                       SERIAL_STAGES if serial else AUTH_STAGES if authenticate else STAGES)

    def step(self, serial_console=None):
        require(not self._failed, 'smoke:previous-failure')
        try:
            self._step(serial_console)
        except BaseException:
            self._failed = True
            raise

    def guarded_step(self, guard):
        self._worker_guard = guard
        self.step()

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
        pending = self.directory / f'{stage}.reply.tmp'
        require(not os.path.lexists(pending) and not os.path.lexists(
            self.directory / f'{stage}.reply.json'), 'smoke:reply-replay')
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
        if self.vt6_auth:
            require(callable(self._worker_guard), 'smoke:worker-guard-required')
            self._worker_guard()
        if stage == 'ready':
            require(request['screenshot'] is None, 'smoke:early-screenshot')
            hostname = runner.address(self.lease.source, timeout=90)
            (self.directory / 'known-hosts').write_text(f'{hostname} {self.host_key}\n')
            config = {'directory': str(self.directory), 'hostname': hostname,
                      'domain_uuid': self.lease.source.uuid,
                      'domain_id': self.lease.view.domain_id, 'run': self.lease.state['run']}
            transport = Transport(config, self.commands, guard=lambda _: self.lease.guard())
            transport.probe_ready(timeout=180)
            if self.functional:
                self.ui = UiObservations(transport,
                    progress=getattr(self.lease, 'watch_progress', None))
            self.vm = ReadOnlyObservations(transport, on_diagnostic=(
                lambda condition: self.progress(self.stages[len(self.steps)],
                    {'recipient_refusal': condition})) if self.progress is not None else None)
            reply = {'observation': 'active-greeter-no-user-session'}
            reply['authenticate'] = self.stages == AUTH_STAGES
            reply['serial'] = self.functional or self.stages == SERIAL_STAGES
            if self.functional:
                reply['functional_smoke'] = True
            reply['install'] = self.installation is not None
            reply['install_refusal'] = self.installation is not None and self.installation.refusal
            reply['vt6_prompt'] = self.stages == VT6_PROMPT_STAGES
            reply['vt6_auth'] = self.vt6_auth
            if self.vt6_auth:
                self._vt6_authentication = VT6Authentication(self.directory, self.vm, self.verified,
                    on_diagnostic=lambda name, report: self.progress(name, {'vt6_diagnostic': report}))
            if reply['vt6_prompt']:
                self._vt6_boot = self.vm.read('boot')['boot_sha256']
            if self.transfer is not None:
                reply['assets'] = self.transfer.observe(self.vm)
        elif self.vt6_auth and stage in VT6_LOGIN_STAGES:
            try:
                reply = self._vt6_authentication.observe(stage, request['screenshot'], self._worker_guard)
            except Exception:
                self.progress(stage, {'vt6_refusal': self._vt6_authentication.refusal})
                raise
        elif stage.startswith('vt6-'):
            require(self._vt6_boot is not None and
                    self.vm.read('boot')['boot_sha256'] == self._vt6_boot, 'smoke:vt6-boot-changed')
            probe = 'vt6-getty' if stage in ('vt6-ready', 'vt6-login-screen') else 'vt6-password'
            if stage.endswith('-screen'):
                reply = screenshot(self.directory, request['screenshot'])
                reply.update(self.vm.read(probe))
            else:
                require(request['screenshot'] is None, 'smoke:early-screenshot')
                reply = self.vm.read(probe)
            require(self.vm.read('boot')['boot_sha256'] == self._vt6_boot, 'smoke:vt6-boot-changed')
            reply['boot_sha256'] = self._vt6_boot
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
            reply = harness_observation(self.vm, 'greeter')
            if self.functional:
                reply['ui'] = self.ui.observe(FUNCTIONAL_GDM_OPERATIONS[stage])
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
                reply = harness_observation(self.vm, 'serial-password')
            elif stage == 'serial-logout':
                reply = harness_observation(self.vm, 'greeter')
            else:
                reply = harness_observation(self.vm, 'serial-session')
                if stage == 'serial-command':
                    reply['command_marker_verified'] = True
        elif stage == 'authenticated':
            # No post-password screenshot may cross the explicit capture route.
            require(request['screenshot'] is None, 'smoke:authentication-capture-refused')
            reply = self.vm.read('parent-session')
        elif self.functional and stage in ('gdm', 'focused', 'selected', 'dismissed'):
            require(request['screenshot'] is None, 'smoke:functional-capture-refused')
            operation = FUNCTIONAL_GDM_OPERATIONS[stage]
            reply = {'ui': self.ui.observe(operation)}
            if stage == 'gdm':
                require(reply['ui'].get('focused') is True
                        and 'navigation' not in reply['ui'],
                        'smoke:functional-focus-unverified')
                reply['ui_focused'] = True
        else:
            reply = screenshot(self.directory, request['screenshot'])
            if stage != 'gdm':
                previous = self.steps[-1]
                require((reply['width'], reply['height']) == (previous['width'], previous['height'])
                        and reply['sha256'] != previous['sha256'], 'smoke:unchanged-screen')
        # Corroborate each captured stage, not just SSH availability at boot.
        if stage not in ('authenticated', 'gdm-return') and not stage.startswith(('serial-', 'install-', 'reboot-', 'vt6-')):
            harness_observation(self.vm, 'greeter')
        self.steps.append({'stage': stage, **reply})
        if self.vt6_auth:
            self.steps[-1]['input_provenance'] = {
                'worker_run': self.lease.state['run'],
                'source_sha256': self.verified.inputs['source_sha256']}
            if stage == 'vt6-password-screen':
                self.steps[-1]['input_provenance'].update(self._vt6_authentication.capture_evidence)
        if self.progress is not None:
            # Persist the actual corroboration before acknowledging the next
            # guest action. Raw screenshots/SSH identities never enter reports.
            self.progress(stage, self.steps[-1])
        self.lease.guard()
        if self.vt6_auth:
            # A durable checkpoint failure above prevents input. Recheck the
            # owned worker after persistence, immediately before publication.
            self._worker_guard()
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(json.dumps(reply))
            stream.flush()
            os.fsync(stream.fileno())
        pending.rename(self.directory / f'{stage}.reply.json')
        runner.log('graphical:' + stage + '-observed')


def run_backend(directory, lease, commands, host_key, ledger, expected_inputs,
                *, progress=None, on_failure=None, transfer=None, credentials=None, serial=False,
                installation=None, vt6_prompt=False, vt6_auth=False, verified=None):
    smoke = Smoke(directory, lease, commands, host_key, progress, transfer,
                  authenticate=credentials is not None, serial=serial, installation=installation,
                  vt6_prompt=vt6_prompt, vt6_auth=vt6_auth, verified=verified)
    def validate():
        require(len(smoke.steps) == len(smoke.stages), 'smoke:missing-stages')
        module_result(directory)
    # VT6 authentication performs ten mandatory full baseline rechecks (802s
    # measured in attempt 10). Reserve 1200s for those checks plus the existing
    # 600s smoke allowance after readiness, plus bounded online-snapshot
    # power-on preparation and synchronous off restore/backend exit.
    # This is one finite total budget; no callback or retry renews it.
    timeout = 1800 if vt6_auth else (
        1500 if installation is not None and not installation.refusal else 1200)
    try:
        worker_result = e2e_worker.run_distribution(
            directory, lease, ledger, expected_inputs=expected_inputs,
            observe=smoke.step, validate=validate, on_failure=on_failure, credentials=credentials,
            **({'guarded_observe': smoke.guarded_step} if vt6_auth else {}),
            serial=serial, timeout=timeout)
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
                 credentials=None, serial=False, install=False, install_refusal=False, vt6_prompt=False,
                 vt6_auth=False):
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
        self.vt6_prompt = vt6_prompt
        self.vt6_auth = vt6_auth

    def checkpoint(self, event):
        self.sequence += 1
        try:
            save_checkpoint(self.collector, self.sequence, event, {
                'scope': ('installed-parent-setup-qualification'
                          if self.result.get('scope') == 'installed-parent-setup-qualification' else
                          'authenticated-vt6-shell-qualification' if self.vt6_auth else
                          'credential-free-vt6-prompt-qualification' if self.vt6_prompt else
                          'deliberate-installation-refusal-qualification' if self.install_refusal else
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
        require(stage in (VT6_AUTH_STAGES if self.vt6_auth else VT6_PROMPT_STAGES if self.vt6_prompt else
                          INSTALL_REFUSAL_STAGES if self.install_refusal else
                          INSTALL_STAGES if self.install else SERIAL_STAGES if self.serial else
                          AUTH_STAGES if self.credentials is not None else STAGES),
                'smoke:stage-request')
        self.active_stage = stage
        if observed is None:
            self.checkpoint('stage-started')
        elif self.vt6_auth and stage in VT6_LOGIN_STAGES and set(observed) == {'vt6_refusal'}:
            require(type(observed['vt6_refusal']) is str
                    and observed['vt6_refusal'] in VT6_AUTH_REFUSALS,
                    'smoke:diagnostic-condition')
            self.result['vt6_refusal'] = {'stage': stage, 'code': observed['vt6_refusal']}
            self.checkpoint('stage-rejected')
        elif self.vt6_auth and stage in VT6_LOGIN_STAGES and set(observed) == {'vt6_diagnostic'}:
            report = observed['vt6_diagnostic']
            require(type(report) is dict and set(report) == {'phase', 'recipient', 'recheck_ms'}
                    and report['phase'] in ('before-inputs', 'after-inputs', 'inputs-before', 'inputs-after'),
                    'smoke:diagnostic-condition')
            timings, recipient = report['recheck_ms'], report['recipient']
            require(type(timings) is dict and set(timings) <= {'source', 'assets', 'baseline'}
                    and all(type(value) is int and 0 <= value <= 3600000 for value in timings.values()),
                    'smoke:diagnostic-condition')
            require(type(recipient) is dict and (not recipient or (
                set(recipient) == {'executable', 'login_timeout_seconds', 'timeout_source',
                                  'login_version', 'matches_pinned_recipient'}
                and recipient['executable'] in ('login', 'agetty', 'other')
                and type(recipient['login_timeout_seconds']) is int
                and 0 <= recipient['login_timeout_seconds'] <= 86400
                and recipient['timeout_source'] in ('login.defs', 'default')
                and type(recipient['login_version']) is str
                and re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,3}){1,2}', recipient['login_version'])
                and type(recipient['matches_pinned_recipient']) is bool)), 'smoke:diagnostic-condition')
            self.result.setdefault('vt6_diagnostics', []).append({'stage': stage, **report})
            self.checkpoint('terminal-diagnostic')
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
                if self.vt6_auth:
                    self.checkpoint('login-window-preparation-started')
                    self.result['vt6_login_window'] = provision_vt6_login_window(
                        lease, self.verified, guestfs)
                    self.checkpoint('login-window-preparation-verified')
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
                    installation=installation, vt6_prompt=self.vt6_prompt,
                    **({'vt6_auth': True, 'verified': self.verified} if self.vt6_auth else {})))
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
         install_refusal=False, vt6_prompt=False, vt6_auth=False, parent_setup=False,
         parent_input=False, parent_standard_input=False, parent_about=False,
         parent_access=False, desktop_session_logout=False, desktop_session_switch=False,
         gdm_navigation=False, gdm_recipient=False, gdm_product_free=False,
         kiosk_entry=False, request_exit=False, parent_toggle=False,
         fresh_desktop=None, shell_search_results=False, parent_search_launch=False,
         shell_search=False, parent_terminal_provider=False,
         license_viewer_provider=False, information_link='license',
         kiosk_eligible_choices=False, request_choices=False,
         kiosk_no_child=False, kiosk_no_approver=False, repeated_operations=False,
         challenges=False, challenge_profile='parent', product_free_entry=False, package_authority=False,
         package_install=False, customer_reboot=False, app_row_observations=False, native_fixtures=False,
         catalogue_search=False, catalogue_filters=False, policy_legend=False, match_save_cancel=False,
         match_editor=False, access_choices=False, policy_edit=False, rejected_parent_rule=False,
         feedback_read=False, text_qualification=False, allowance_presets=False, allowance=False,
         time_explanation=False, set_allowance=False, app_restart=False,
         allowance_boundaries=False, kiosk_valid_duration=False, request_duration=False,
         request_flow=False, mate_prompt=False, kiosk_approval=False, kiosk_rejection=False,
         auth_result=False, kiosk_approved_flow=False, approval_flow=None, kiosk_multiple=False,
         kiosk_ineligible=False, restricted_station_about=False, fresh_thirty_allowance=False,
         fresh_thirty_child='child',
         feedback_privacy=False, feedback_states=False, format_qualification=False,
         trace_stable_state=False, trace_transition=False, compose_observation=False,
         accessibility_input_trace=False, parent_save_trace=False, custom_save_trace=False,
         named_child_custom_saves=False, feedback_collection=False,
         window_switch=False, feedback_rejection=False, feedback_length=False,
         synthetic_files=False, document_open=False, archive_open=False, source_change=False,
         file_chooser=False, save_chooser=False, diagnostic_export=False, attachment_items=False, attachment_preview=False,
         attachment_boundaries=False, feedback_reset=False, feedback_block_semantics=False,
         feedback_formats=False, feedback_link_semantics=False, real_interval=False,
         independent_network=False, public_connectivity_controls=False, native_grid_usable=False,
         native_app=False, app_activity=False):
    require(type(app_activity) is bool and (not app_activity or (
        assets is not None and provision_credentials and fresh_desktop is None
        and approval_flow is None and not any(value for name, value in locals().items()
            if name not in ('assets', 'provision_credentials', 'app_activity')
            and isinstance(value, bool)))), 'smoke:app-activity-prerequisites')
    require(type(native_app) is bool and (not native_app or (
        assets is not None and provision_credentials and fresh_desktop is None
        and approval_flow is None and not any(value for name, value in locals().items()
            if name not in ('assets', 'provision_credentials', 'native_app')
            and isinstance(value, bool)))), 'smoke:native-app-prerequisites')
    require(type(native_grid_usable) is bool and (not native_grid_usable or (
        assets is not None and provision_credentials and fresh_desktop is None
        and approval_flow is None and not any(value for name, value in locals().items()
            if name not in ('assets', 'provision_credentials', 'native_grid_usable')
            and isinstance(value, bool)))), 'smoke:native-grid-prerequisites')
    require(type(rejected_parent_rule) is bool and (not rejected_parent_rule or
            (native_fixtures and not catalogue_search and not catalogue_filters
             and not policy_legend and not match_save_cancel and not match_editor
             and not access_choices and not policy_edit)), 'smoke:rejected-parent-rule-prerequisites')
    require(type(policy_edit) is bool and (not policy_edit or
            (native_fixtures and not catalogue_search and not catalogue_filters
             and not policy_legend and not match_save_cancel and not match_editor
             and not access_choices)), 'smoke:policy-prerequisites')
    require(type(access_choices) is bool and (not access_choices or
            (native_fixtures and not catalogue_search and not catalogue_filters
             and not policy_legend and not match_save_cancel and not match_editor)),
            'smoke:access-choices-prerequisites')
    require(type(match_editor) is bool and (not match_editor or
            (native_fixtures and not catalogue_search and not catalogue_filters
             and not policy_legend and not match_save_cancel and not access_choices)), 'smoke:match-editor-prerequisites')
    require(type(match_save_cancel) is bool and (not match_save_cancel or
            (native_fixtures and not catalogue_search and not catalogue_filters and not policy_legend)),
            'smoke:match-save-cancel-prerequisites')
    require(type(catalogue_search) is bool and (not catalogue_search or native_fixtures),
            'smoke:catalogue-search-prerequisites')
    require(type(catalogue_filters) is bool and (not catalogue_filters or
            (native_fixtures and not catalogue_search)), 'smoke:catalogue-filter-prerequisites')
    require(type(policy_legend) is bool and (not policy_legend or
            (native_fixtures and not catalogue_search and not catalogue_filters)),
            'smoke:policy-legend-prerequisites')
    require(type(native_fixtures) is bool and (not native_fixtures or (
        app_row_observations and assets is not None and provision_credentials
        and fresh_desktop is None and approval_flow is None
        and not any(value for name, value in locals().items()
                    if name not in ('assets', 'provision_credentials', 'app_row_observations',
                                    'native_fixtures', 'catalogue_search', 'catalogue_filters', 'policy_legend', 'match_save_cancel', 'match_editor', 'access_choices', 'policy_edit', 'rejected_parent_rule') and isinstance(value, bool)))),
        'smoke:native-fixtures-prerequisites')
    require(type(public_connectivity_controls) is bool and (not public_connectivity_controls or (
        assets is not None and provision_credentials and parent_toggle
        and fresh_desktop is None and approval_flow is None
        and not any(value for name, value in locals().items()
            if name not in ('assets', 'provision_credentials', 'parent_toggle',
                            'public_connectivity_controls') and isinstance(value, bool)))),
        'smoke:public-connectivity-controls-prerequisites')
    require(type(independent_network) is bool and (not independent_network or (
        assets is not None and provision_credentials and fresh_desktop == 'parent'
        and approval_flow is None and not any(value for name, value in locals().items()
            if name not in ('assets', 'provision_credentials', 'independent_network')
            and isinstance(value, bool)))), 'smoke:independent-network-prerequisites')
    require(type(real_interval) is bool and (not real_interval or (
        assets is not None and provision_credentials and fresh_desktop is None and approval_flow is None
        and not any(value for name, value in locals().items()
                    if name not in ('assets', 'provision_credentials', 'real_interval')
                    and isinstance(value, bool)))), 'smoke:real-interval-prerequisites')
    require(type(diagnostic_export) is bool and not (diagnostic_export and save_chooser),
            'smoke:diagnostic-export-prerequisites')
    require(type(save_chooser) is bool and not ((save_chooser or diagnostic_export) and (
        file_chooser or attachment_items or attachment_preview or attachment_boundaries
        or feedback_read or feedback_states or feedback_collection or feedback_privacy
        or format_qualification or window_switch or feedback_rejection or feedback_length
        or trace_stable_state or trace_transition or compose_observation
        or accessibility_input_trace or parent_save_trace or custom_save_trace
        or feedback_reset or feedback_block_semantics or feedback_formats or feedback_link_semantics
        or synthetic_files or document_open or archive_open or source_change)),
        'smoke:save-chooser-prerequisites')
    require(type(named_child_custom_saves) is bool and
            (not named_child_custom_saves or custom_save_trace), 'smoke:trace-prerequisites')
    require(type(feedback_collection) is bool and type(custom_save_trace) is bool and type(parent_save_trace) is bool and type(accessibility_input_trace) is bool and
            sum((parent_save_trace, accessibility_input_trace, custom_save_trace, feedback_collection)) <= 1 and
            not ((accessibility_input_trace or parent_save_trace or custom_save_trace or feedback_collection) and
            (compose_observation or trace_transition or trace_stable_state)), 'smoke:trace-prerequisites')
    require(type(compose_observation) is bool and not (compose_observation and
            (trace_transition or trace_stable_state)), 'smoke:trace-prerequisites')
    require(type(trace_transition) is bool and not (trace_transition and trace_stable_state),
            'smoke:trace-prerequisites')
    require(type(trace_stable_state) is bool and not ((trace_stable_state or trace_transition or compose_observation or accessibility_input_trace or parent_save_trace or custom_save_trace or feedback_collection) and (
        feedback_states or feedback_read or feedback_privacy or format_qualification
        or feedback_reset or window_switch or feedback_rejection or feedback_length
        or file_chooser or attachment_items or attachment_preview or attachment_boundaries
        or feedback_formats or feedback_block_semantics or feedback_link_semantics)),
        'smoke:trace-prerequisites')
    feedback_states = feedback_states or trace_stable_state or trace_transition or compose_observation or accessibility_input_trace or parent_save_trace or custom_save_trace or feedback_collection
    require(type(feedback_link_semantics) is bool and not (feedback_link_semantics and (
        feedback_formats or feedback_block_semantics or format_qualification)),
        'smoke:linked-prerequisites')
    require(type(feedback_formats) is bool and not (feedback_formats and (
        feedback_block_semantics or format_qualification)), 'smoke:formats-prerequisites')
    require(type(feedback_block_semantics) is bool and not (
        feedback_block_semantics and format_qualification), 'smoke:block-prerequisites')
    format_qualification = (format_qualification or feedback_block_semantics or feedback_formats
                            or feedback_link_semantics)
    require(type(feedback_reset) is bool and not (feedback_reset and (
        feedback_read or feedback_privacy or feedback_states or format_qualification
        or window_switch or feedback_rejection or feedback_length or file_chooser
        or attachment_items or attachment_preview or attachment_boundaries or app_restart)),
        'smoke:feedback-reset-prerequisites')
    feedback_read = feedback_read or feedback_reset
    require(type(attachment_boundaries) is bool and not (attachment_boundaries and (
        attachment_preview or attachment_items or file_chooser)), 'smoke:attachment-boundaries-prerequisites')
    require(type(attachment_preview) is bool and not (attachment_preview and (attachment_items or file_chooser)),
            'smoke:attachment-preview-prerequisites')
    require(type(attachment_items) is bool and not (attachment_items and file_chooser),
            'smoke:attachment-items-prerequisites')
    file_chooser = file_chooser or attachment_items or attachment_preview or attachment_boundaries
    require(type(file_chooser) is bool and not (file_chooser and (
        feedback_read or feedback_privacy or feedback_states or format_qualification
        or window_switch or feedback_rejection or feedback_length or synthetic_files
        or document_open or archive_open or source_change)),
        'smoke:file-chooser-prerequisites')
    require(type(synthetic_files) is bool and (not synthetic_files or fresh_desktop == 'parent'),
            'smoke:synthetic-files-prerequisites')
    require(type(document_open) is bool and (not document_open or
            (fresh_desktop == 'parent' and not synthetic_files)),
            'smoke:document-open-prerequisites')
    require(type(archive_open) is bool and (not archive_open or
            (fresh_desktop == 'parent' and not synthetic_files and not document_open)),
            'smoke:archive-open-prerequisites')
    require(type(source_change) is bool and (not source_change or
            (fresh_desktop == 'parent' and not synthetic_files and not document_open
             and not archive_open)), 'smoke:source-change-prerequisites')
    require(type(feedback_length) is bool and not (feedback_length and (
        feedback_read or feedback_privacy or feedback_states or format_qualification
        or window_switch or feedback_rejection)), 'smoke:feedback-length-prerequisites')
    require(type(feedback_rejection) is bool and not (feedback_rejection and (
        feedback_read or feedback_privacy or feedback_states or format_qualification or window_switch)),
        'smoke:feedback-rejection-prerequisites')
    require(type(window_switch) is bool and not (window_switch and (
        feedback_privacy or feedback_states or format_qualification or feedback_read)),
        'smoke:window-switch-prerequisites')
    require(type(format_qualification) is bool
            and not (format_qualification and (feedback_privacy or feedback_states or feedback_read)),
            'smoke:format-prerequisites')
    require(type(feedback_states) is bool
            and not (feedback_states and (feedback_privacy or feedback_read)),
            'smoke:feedback-states-prerequisites')
    require(type(feedback_privacy) is bool and not (feedback_privacy and feedback_read),
            'smoke:feedback-privacy-prerequisites')
    feedback_read = feedback_read or feedback_privacy or feedback_states or format_qualification or window_switch or feedback_rejection or feedback_length or file_chooser or save_chooser or diagnostic_export
    require(type(fresh_thirty_allowance) is bool and type(set_allowance) is bool
            and not (fresh_thirty_allowance and set_allowance),
            'smoke:fresh-thirty-allowance-prerequisites')
    require(fresh_thirty_child in ('child', 'existing') and
            (fresh_thirty_allowance or fresh_thirty_child == 'child'),
            'smoke:fresh-thirty-child-prerequisites')
    set_allowance = set_allowance or fresh_thirty_allowance
    require(type(restricted_station_about) is bool and not (restricted_station_about and (
        kiosk_ineligible or kiosk_multiple or kiosk_valid_duration or request_duration
        or request_flow or mate_prompt or kiosk_approval or kiosk_rejection or auth_result
        or kiosk_approved_flow or approval_flow)), 'smoke:restricted-station-about-prerequisites')
    require(type(kiosk_ineligible) is bool and not (kiosk_ineligible and kiosk_multiple),
            'smoke:kiosk-ineligible-prerequisites')
    kiosk_multiple = kiosk_multiple or kiosk_ineligible
    require(type(kiosk_multiple) is bool and not (kiosk_multiple and (
        kiosk_valid_duration or request_duration or request_flow or mate_prompt or kiosk_approval
        or kiosk_rejection or auth_result or kiosk_approved_flow or approval_flow)),
        'smoke:kiosk-multiple-prerequisites')
    require(approval_flow in (None, 'rejection', 'cancel') and not (approval_flow and (
        kiosk_approved_flow or auth_result or kiosk_approval or kiosk_rejection or mate_prompt
        or request_flow or request_duration or kiosk_valid_duration)), 'smoke:approval-flow-prerequisites')
    require(type(kiosk_approved_flow) is bool and not (kiosk_approved_flow and (
        auth_result or kiosk_approval or kiosk_rejection or mate_prompt or request_flow
        or request_duration or kiosk_valid_duration)), 'smoke:kiosk-approved-flow-prerequisites')
    require(type(auth_result) is bool and not (auth_result and (
        kiosk_approval or kiosk_rejection or mate_prompt or request_flow or request_duration
        or kiosk_valid_duration)), 'smoke:auth-result-prerequisites')
    require(type(kiosk_rejection) is bool and not (kiosk_rejection and (
        kiosk_approval or mate_prompt or request_flow or request_duration or kiosk_valid_duration)),
        'smoke:kiosk-rejection-prerequisites')
    require(type(kiosk_approval) is bool and not (kiosk_approval and (
        mate_prompt or request_flow or request_duration or kiosk_valid_duration)),
        'smoke:kiosk-approval-prerequisites')
    require(type(mate_prompt) is bool and not (mate_prompt and (
        request_flow or request_duration or kiosk_valid_duration)), 'smoke:mate-prompt-prerequisites')
    require(type(request_flow) is bool and not (request_flow and (
        kiosk_valid_duration or request_duration)), 'smoke:request-flow-prerequisites')
    require(type(request_duration) is bool and not (request_duration and kiosk_valid_duration),
            'smoke:request-duration-prerequisites')
    kiosk_valid_duration = (kiosk_valid_duration or request_duration or request_flow or mate_prompt
                            or kiosk_approval or kiosk_rejection or auth_result or kiosk_approved_flow
                            or approval_flow is not None or kiosk_multiple or restricted_station_about)
    require(type(kiosk_valid_duration) is bool and (not kiosk_valid_duration or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification, allowance_presets, allowance, time_explanation,
                     set_allowance, app_restart, allowance_boundaries)))),
            'smoke:kiosk-valid-duration-prerequisites')
    require(type(allowance_boundaries) is bool and (not allowance_boundaries or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification, allowance_presets, allowance, time_explanation,
                     set_allowance, app_restart)))), 'smoke:allowance-boundaries-prerequisites')
    require(type(app_restart) is bool and (not app_restart or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification, allowance_presets, allowance, time_explanation,
                     set_allowance)))), 'smoke:app-restart-prerequisites')
    require(type(set_allowance) is bool and (not set_allowance or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification, allowance_presets, allowance, time_explanation)))),
            'smoke:set-allowance-prerequisites')
    require(type(time_explanation) is bool and (not time_explanation or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification, allowance_presets, allowance)))), 'smoke:time-explanation-prerequisites')
    require(type(allowance) is bool and (not allowance or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification, allowance_presets)))), 'smoke:allowance-prerequisites')
    require(type(allowance_presets) is bool and (not allowance_presets or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read,
                     text_qualification)))), 'smoke:allowance-presets-prerequisites')
    require(type(text_qualification) is bool and (not text_qualification or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations, feedback_read)))),
            'smoke:text-prerequisites')
    require(type(kiosk_no_approver) is bool and (not kiosk_no_approver or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider,
                         kiosk_eligible_choices, request_choices, kiosk_no_child,
                         repeated_operations, challenges, product_free_entry,
                         package_authority, package_install, customer_reboot,
                         app_row_observations, feedback_read)))),
            'smoke:kiosk-no-approver-prerequisites')
    require(type(feedback_read) is bool and (not feedback_read or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot, app_row_observations)))),
            'smoke:feedback-read-prerequisites')
    require(type(app_row_observations) is bool and (not app_row_observations or (
        assets is not None and provision_credentials and fresh_desktop is None
        and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                     parent_setup, parent_input, parent_standard_input, parent_about,
                     parent_access, desktop_session_logout, desktop_session_switch,
                     gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry,
                     request_exit, parent_toggle, shell_search_results, parent_search_launch,
                     shell_search, parent_terminal_provider, license_viewer_provider,
                     kiosk_eligible_choices, request_choices, kiosk_no_child, kiosk_no_approver,
                     repeated_operations, challenges, product_free_entry, package_authority,
                     package_install, customer_reboot)))), 'smoke:app-rows-prerequisites')
    require(type(customer_reboot) is bool and not (customer_reboot and
            (package_install or package_authority or product_free_entry)),
            'smoke:customer-reboot-prerequisites')
    require(type(package_install) is bool and not (package_install and
            (package_authority or product_free_entry)), 'smoke:package-install-prerequisites')
    require(type(package_authority) is bool and not (package_authority and product_free_entry),
            'smoke:package-authority-prerequisites')
    # Reuse the exact product-free prerequisite gate, preparation and envelope.
    product_free_entry = product_free_entry or package_authority or package_install or customer_reboot
    require(type(product_free_entry) is bool and (not product_free_entry or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider,
                         kiosk_eligible_choices, request_choices, kiosk_no_child,
                         kiosk_no_approver, repeated_operations, challenges)))),
            'smoke:product-free-entry-prerequisites')
    require(challenge_profile in ('parent', 'fresh-child', 'fresh-child-denied',
                                  'countdown-enabled', 'countdown-off', 'shell-panel',
                                  'overlay-valid-choices', 'overlay-choices', 'overlay-license',
                                  'overlay-browser-links') and
            (challenge_profile == 'parent' or challenges is True), 'smoke:challenge-profile')
    require(type(challenges) is bool and (not challenges or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider,
                         kiosk_eligible_choices, request_choices, kiosk_no_child,
                         kiosk_no_approver, repeated_operations)))), 'smoke:challenges-prerequisites')
    require(type(repeated_operations) is bool and (not repeated_operations or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider,
                         kiosk_eligible_choices, request_choices, kiosk_no_child,
                         kiosk_no_approver)))), 'smoke:repeated-operations-prerequisites')
    require(type(kiosk_no_child) is bool and (not kiosk_no_child or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider,
                         kiosk_eligible_choices, request_choices)))),
            'smoke:kiosk-no-child-prerequisites')
    require(type(request_choices) is bool and (not request_choices or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider,
                         kiosk_eligible_choices)))), 'smoke:request-choices-prerequisites')
    require(type(kiosk_eligible_choices) is bool and (not kiosk_eligible_choices or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider, license_viewer_provider)))),
            'smoke:kiosk-eligible-choices-prerequisites')
    require(information_link in ('license', 'website', 'privacy', 'support', 'information')
            and (information_link == 'license' or license_viewer_provider),
            'smoke:information-link-binding')
    require(type(license_viewer_provider) is bool and (not license_viewer_provider or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search,
                         parent_terminal_provider)))),
            'smoke:license-viewer-provider-prerequisites')
    require(type(parent_terminal_provider) is bool and (not parent_terminal_provider or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch, shell_search)))),
            'smoke:parent-terminal-provider-prerequisites')
    require(type(shell_search) is bool and (not shell_search or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results, parent_search_launch)))),
            'smoke:standard-search-prerequisites')
    require(type(parent_search_launch) is bool and (not parent_search_launch or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results)))), 'smoke:parent-search-prerequisites')
    require(fresh_desktop is None or (
            fresh_desktop in ('parent', 'standard', 'standard-keyring')
            and assets is not None and provision_credentials
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle,
                         shell_search_results))),
            'smoke:fresh-desktop-prerequisites')
    require(type(shell_search_results) is bool and (not shell_search_results or (
            assets is not None and provision_credentials and fresh_desktop is None
            and not any((serial, install, install_refusal, vt6_prompt, vt6_auth,
                         parent_setup, parent_input, parent_standard_input,
                         parent_about, parent_access, desktop_session_logout,
                         desktop_session_switch, gdm_navigation, gdm_recipient,
                         gdm_product_free, kiosk_entry, request_exit, parent_toggle)))),
            'smoke:shell-search-prerequisites')
    require(type(parent_toggle) is bool and (not parent_toggle or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, gdm_navigation, gdm_recipient,
                gdm_product_free, kiosk_entry, request_exit)))),
            'smoke:parent-toggle-prerequisites')
    require(type(kiosk_entry) is bool and (not kiosk_entry or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, gdm_navigation, gdm_recipient,
                gdm_product_free, request_exit, parent_toggle)))),
            'smoke:kiosk-entry-prerequisites')
    require(type(request_exit) is bool and (not request_exit or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, gdm_navigation, gdm_recipient,
                gdm_product_free, kiosk_entry, parent_toggle)))),
            'smoke:request-exit-prerequisites')
    require(type(desktop_session_logout) is bool and (not desktop_session_logout or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_switch, gdm_navigation, gdm_recipient, gdm_product_free,
                kiosk_entry, request_exit, parent_toggle)))),
            'smoke:desktop-session-logout-prerequisites')
    require(type(desktop_session_switch) is bool and (not desktop_session_switch or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, gdm_navigation, gdm_recipient, gdm_product_free,
                kiosk_entry, request_exit, parent_toggle)))),
            'smoke:desktop-session-switch-prerequisites')
    require(type(gdm_navigation) is bool and (not gdm_navigation or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, kiosk_entry,
                request_exit, parent_toggle, gdm_recipient, gdm_product_free)))),
            'smoke:gdm-navigation-prerequisites')
    require(type(gdm_recipient) is bool and (not gdm_recipient or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, gdm_navigation,
                gdm_product_free, kiosk_entry, request_exit, parent_toggle)))),
            'smoke:gdm-recipient-prerequisites')
    require(type(gdm_product_free) is bool and (not gdm_product_free or (
            assets is not None and provision_credentials and not any((
                serial, install, install_refusal, vt6_prompt, vt6_auth, parent_setup,
                parent_input, parent_standard_input, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, gdm_navigation, gdm_recipient,
                kiosk_entry, request_exit, parent_toggle)))),
            'smoke:gdm-product-free-prerequisites')
    require(type(parent_access) is bool and (not parent_access or (assets is not None
            and provision_credentials and not any((serial, install, install_refusal,
                vt6_prompt, vt6_auth, parent_setup, parent_input, parent_standard_input,
                parent_about, desktop_session_logout, desktop_session_switch, gdm_navigation,
                gdm_recipient, gdm_product_free,
                kiosk_entry,
                request_exit, parent_toggle)))),
            'smoke:parent-access-prerequisites')
    require(type(parent_about) is bool and (not parent_about or (assets is not None
            and provision_credentials and not any((serial, install, install_refusal,
                vt6_prompt, vt6_auth, parent_setup, parent_input,
                parent_standard_input, desktop_session_logout, desktop_session_switch,
                gdm_navigation, gdm_recipient, gdm_product_free, kiosk_entry, request_exit,
                parent_toggle)))),
            'smoke:parent-about-prerequisites')
    require(type(parent_input) is bool and (not parent_input or parent_setup),
            'smoke:parent-input-prerequisites')
    require(type(parent_standard_input) is bool
            and (not parent_standard_input or parent_setup)
            and not (parent_standard_input and parent_input),
            'smoke:parent-standard-input-prerequisites')
    require(type(parent_setup) is bool and (not parent_setup or (assets is not None
            and provision_credentials and not any((serial, install, install_refusal,
                vt6_prompt, vt6_auth, parent_about, parent_access,
                desktop_session_logout, desktop_session_switch, gdm_navigation, gdm_recipient,
                gdm_product_free, kiosk_entry,
                request_exit, parent_toggle)))),
            'smoke:parent-setup-prerequisites')
    require(type(vt6_auth) is bool and (not vt6_auth or (provision_credentials
            and assets is None and not serial and not install and not install_refusal
            and not vt6_prompt)), 'smoke:vt6-auth-prerequisites')
    require(type(vt6_prompt) is bool and (not vt6_prompt or
            (assets is None and not provision_credentials and not serial and not install
             and not install_refusal)), 'smoke:vt6-prompt-prerequisites')
    require(type(install) is bool and type(install_refusal) is bool
            and not (install and install_refusal)
            and (not (install or install_refusal) or (assets is not None and serial
            and provision_credentials)), 'smoke:installation-prerequisites')
    require(type(serial) is bool and (not serial or provision_credentials), 'smoke:serial-credentials')
    credentials = FixtureCredentials() if provision_credentials else None
    require(assets is not None or len(sys.argv) == 1, 'smoke:invalid-arguments')
    require(os.geteuid() == os.getegid() == 0, 'smoke:root-required')
    require(Path.cwd() == ROOT == runner.baseline.guest_contract.CHECKOUT, 'smoke:checkout')
    os.umask(0o077)
    with storage_session():
        directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-graphical-smoke-', dir='/tmp'))
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
        if credentials is not None:
            result['scope'] = 'fixture-authentication-qualification'
        if serial:
            result['scope'] = 'fixture-serial-command-qualification'
        if install:
            result['scope'] = 'authenticated-installation-qualification'
        if install_refusal:
            result['scope'] = 'deliberate-installation-refusal-qualification'
        if vt6_prompt:
            result['scope'] = 'credential-free-vt6-prompt-qualification'
        if vt6_auth:
            result['scope'] = 'authenticated-vt6-shell-qualification'
        if parent_setup:
            result['scope'] = 'installed-parent-setup-qualification'
        if parent_input:
            result['scope'] = 'installed-parent-input-qualification'
        if parent_standard_input:
            result['scope'] = 'installed-standard-input-qualification'
        if parent_about:
            result['scope'] = 'installed-parent-about-qualification'
        if parent_access:
            result['scope'] = 'installed-parent-access-qualification'
        if desktop_session_logout:
            result['scope'] = 'installed-desktop-logout-qualification'
        if desktop_session_switch:
            result['scope'] = 'installed-desktop-switch-qualification'
        if gdm_navigation:
            result['scope'] = 'installed-gdm-navigation-qualification'
        if gdm_recipient:
            result['scope'] = 'installed-gdm-recipient-qualification'
        if gdm_product_free:
            result['scope'] = 'product-free-gdm-qualification'
        if fresh_desktop is not None:
            result['scope'] = 'fresh-' + fresh_desktop + '-desktop-qualification'
        if synthetic_files:
            result['scope'] = 'synthetic-files-qualification'
        if document_open:
            result['scope'] = 'document-open-qualification'
        if archive_open:
            result['scope'] = 'archive-open-qualification'
        if source_change:
            result['scope'] = 'source-change-qualification'
        if shell_search_results:
            result['scope'] = 'installed-shell-search-results-qualification'
        if parent_search_launch:
            result['scope'] = 'installed-parent-search-launch-qualification'
        if shell_search:
            result['scope'] = 'installed-standard-search-qualification'
        if parent_terminal_provider:
            result['scope'] = 'installed-parent-terminal-provider-qualification'
        if license_viewer_provider:
            result['scope'] = (f'installed-parent-{information_link}-qualification' if information_link != 'license'
                               else 'installed-license-viewer-provider-qualification')
        if kiosk_entry:
            result['scope'] = 'installed-kiosk-entry-qualification'
        if kiosk_eligible_choices:
            result['scope'] = 'installed-kiosk-eligible-choices-qualification'
        if request_choices:
            result['scope'] = 'installed-request-choices-qualification'
        if kiosk_no_child:
            result['scope'] = 'installed-kiosk-no-child-qualification'
        if kiosk_no_approver:
            result['scope'] = 'installed-kiosk-no-approver-qualification'
        if request_exit:
            result['scope'] = 'installed-request-exit-qualification'
        if parent_toggle:
            result['scope'] = 'installed-parent-toggle-qualification'
        if public_connectivity_controls:
            result['scope'] = 'installed-public-connectivity-controls-qualification'
        if app_row_observations:
            result['scope'] = 'installed-app-row-observations-qualification'
        if native_fixtures:
            result['scope'] = 'installed-native-fixtures-qualification'
        if native_grid_usable:
            result['scope'] = 'installed-native-grid-usable-qualification'
        if native_app:
            result['scope'] = 'installed-native-app-qualification'
        if app_activity:
            result['scope'] = 'installed-app-activity-qualification'
        if catalogue_search:
            result['scope'] = 'installed-catalogue-search-qualification'
        if catalogue_filters:
            result['scope'] = 'installed-catalogue-filter-qualification'
        if policy_legend:
            result['scope'] = 'installed-policy-legend-qualification'
        if match_save_cancel:
            result['scope'] = 'installed-match-save-cancel-qualification'
        if match_editor:
            result['scope'] = 'installed-match-editor-qualification'
        if rejected_parent_rule:
            result['scope'] = 'installed-rejected-parent-rule-qualification'
        if access_choices:
            result['scope'] = 'installed-access-choices-qualification'
        if policy_edit:
            result['scope'] = 'installed-policy-qualification'
        if feedback_read:
            result['scope'] = 'installed-feedback-read-qualification'
        if file_chooser:
            result['scope'] = 'installed-file-chooser-qualification'
        if save_chooser:
            result['scope'] = 'installed-save-chooser-qualification'
        if diagnostic_export:
            result['scope'] = 'installed-diagnostic-export-qualification'
        if attachment_items:
            result['scope'] = 'installed-attachment-items-qualification'
        if attachment_preview:
            result['scope'] = 'installed-attachment-preview-qualification'
        if attachment_boundaries:
            result['scope'] = 'installed-attachment-boundaries-qualification'
        if feedback_privacy:
            result['scope'] = 'installed-feedback-privacy-qualification'
        if feedback_reset:
            result['scope'] = 'installed-feedback-reset-qualification'
        if feedback_states:
            result['scope'] = 'installed-feedback-states-qualification'
        if trace_stable_state:
            result['scope'] = 'installed-trace-stable-state-qualification'
        if trace_transition:
            result['scope'] = 'installed-trace-transition-qualification'
        if compose_observation:
            result['scope'] = 'installed-compose-observation-qualification'
        if accessibility_input_trace:
            result['scope'] = 'installed-accessibility-input-trace-qualification'
        if parent_save_trace:
            result['scope'] = 'installed-parent-save-trace-qualification'
        if feedback_collection:
            result['scope'] = 'installed-feedback-collection-qualification'
        if custom_save_trace:
            result['scope'] = 'installed-custom-save-trace-qualification'
        if named_child_custom_saves:
            result['scope'] = 'installed-named-child-custom-saves-qualification'
        if format_qualification:
            result['scope'] = 'installed-format-qualification'
        if feedback_block_semantics:
            result['scope'] = 'installed-feedback-block-semantics-qualification'
        if feedback_formats:
            result['scope'] = 'installed-feedback-formats-qualification'
        if feedback_link_semantics:
            result['scope'] = 'installed-feedback-link-semantics-qualification'
        if window_switch:
            result['scope'] = 'installed-window-switch-qualification'
        if feedback_rejection:
            result['scope'] = 'installed-feedback-rejection-qualification'
        if feedback_length:
            result['scope'] = 'installed-feedback-length-qualification'
        if text_qualification:
            result['scope'] = 'installed-text-qualification'
        if allowance_presets:
            result['scope'] = 'installed-allowance-presets-qualification'
        if allowance:
            result['scope'] = 'installed-allowance-qualification'
        if allowance_boundaries:
            result['scope'] = 'installed-allowance-boundaries-qualification'
        if kiosk_valid_duration:
            result['scope'] = 'installed-kiosk-valid-duration-qualification'
        if request_duration:
            result['scope'] = 'installed-request-duration-qualification'
        if request_flow:
            result['scope'] = 'installed-request-flow-qualification'
        if restricted_station_about:
            result['scope'] = 'installed-restricted-station-about-qualification'
        if mate_prompt:
            result['scope'] = 'installed-mate-prompt-qualification'
        if kiosk_multiple:
            result['scope'] = 'installed-kiosk-multiple-qualification'
        if kiosk_ineligible:
            result['scope'] = 'installed-kiosk-ineligible-qualification'
        if kiosk_approval:
            result['scope'] = 'installed-kiosk-approval-qualification'
        if auth_result:
            result['scope'] = 'installed-auth-result-qualification'
        if kiosk_approved_flow:
            result['scope'] = 'installed-kiosk-approved-flow-qualification'
        if approval_flow:
            result['scope'] = 'installed-approval-flow-' + approval_flow + '-qualification'
        if kiosk_rejection:
            result['scope'] = 'installed-kiosk-rejection-qualification'
        if time_explanation:
            result['scope'] = 'installed-time-explanation-qualification'
        if set_allowance:
            result['scope'] = 'installed-set-allowance-qualification'
        if fresh_thirty_allowance:
            result['scope'] = ('installed-fresh-thirty-allowance-qualification'
                               if fresh_thirty_child == 'child' else
                               'installed-jordan-thirty-allowance-qualification')
        if app_restart:
            result['scope'] = 'installed-app-restart-qualification'
        if real_interval:
            result['scope'] = 'installed-real-interval-qualification'
        if independent_network:
            result['scope'] = 'installed-independent-network-qualification'
        if repeated_operations:
            result['scope'] = 'installed-repeated-operations-qualification'
        if challenges:
            result['scope'] = {'parent': 'installed-challenges-qualification',
                'fresh-child': 'installed-fresh-child-allowed-qualification',
                'fresh-child-denied': 'installed-fresh-child-denied-qualification',
                'countdown-enabled': 'installed-countdown-enabled-qualification',
                'countdown-off': 'installed-countdown-off-qualification',
                'shell-panel': 'installed-shell-panel-qualification',
                'overlay-valid-choices': 'installed-overlay-valid-choices-qualification',
                'overlay-choices': 'installed-overlay-choices-qualification',
                'overlay-license': 'installed-overlay-license-qualification',
                'overlay-browser-links': 'installed-overlay-browser-links-qualification'}[challenge_profile]
        if product_free_entry:
            result['scope'] = 'product-free-entry-qualification'
        if package_authority:
            result['scope'] = 'package-authority-qualification'
        if package_install:
            result['scope'] = 'package-install-qualification'
        if customer_reboot:
            result['scope'] = 'customer-reboot-qualification'
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
                if (parent_setup or parent_about or parent_access or desktop_session_logout
                        or desktop_session_switch or gdm_navigation or gdm_recipient or kiosk_entry
                        or fresh_desktop is not None or shell_search_results or parent_search_launch or native_grid_usable or native_app or app_activity
                        or shell_search or parent_terminal_provider or license_viewer_provider
                        or request_exit or parent_toggle or app_row_observations or feedback_read or text_qualification or allowance_presets or allowance or time_explanation or set_allowance or kiosk_eligible_choices or request_choices
                        or kiosk_no_child or kiosk_no_approver or repeated_operations or challenges or app_restart or allowance_boundaries or kiosk_valid_duration or real_interval):
                    installed_setup.stage(directory, staged, result['inputs_sha256'])
                    staged = directory / 'input'
                else:
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
                qualification_class = Qualification
                if parent_setup:
                    from parent_setup_qualification import ParentSetupQualification
                    qualification_class = ParentSetupQualification
                if parent_about:
                    from parent_setup_qualification import ParentAboutQualification
                    qualification_class = ParentAboutQualification
                if parent_access:
                    from parent_setup_qualification import ParentAccessQualification
                    qualification_class = ParentAccessQualification
                if desktop_session_logout:
                    from parent_setup_qualification import DesktopLogoutQualification
                    qualification_class = DesktopLogoutQualification
                if desktop_session_switch:
                    from parent_setup_qualification import DesktopSwitchQualification
                    qualification_class = DesktopSwitchQualification
                if gdm_navigation:
                    from parent_setup_qualification import GdmNavigationQualification
                    qualification_class = GdmNavigationQualification
                if gdm_recipient:
                    from parent_setup_qualification import GdmRecipientQualification
                    qualification_class = GdmRecipientQualification
                if fresh_desktop == 'parent':
                    from parent_setup_qualification import FreshParentDesktopQualification
                    qualification_class = FreshParentDesktopQualification
                    if synthetic_files:
                        from parent_setup_qualification import SyntheticFilesQualification
                        qualification_class = SyntheticFilesQualification
                    if document_open:
                        from parent_setup_qualification import DocumentOpenQualification
                        qualification_class = DocumentOpenQualification
                    if archive_open:
                        from parent_setup_qualification import ArchiveOpenQualification
                        qualification_class = ArchiveOpenQualification
                    if source_change:
                        from parent_setup_qualification import SourceChangeQualification
                        qualification_class = SourceChangeQualification
                    if independent_network:
                        from parent_setup_qualification import IndependentNetworkQualification
                        qualification_class = IndependentNetworkQualification
                if fresh_desktop == 'standard':
                    from parent_setup_qualification import FreshStandardDesktopQualification
                    qualification_class = FreshStandardDesktopQualification
                if fresh_desktop == 'standard-keyring':
                    from parent_setup_qualification import KeyringStandardDesktopQualification
                    qualification_class = KeyringStandardDesktopQualification
                if shell_search_results:
                    from parent_setup_qualification import ShellSearchResultsQualification
                    qualification_class = ShellSearchResultsQualification
                if parent_search_launch:
                    from parent_setup_qualification import ParentSearchLaunchQualification
                    qualification_class = ParentSearchLaunchQualification
                if shell_search:
                    from parent_setup_qualification import ShellSearchQualification
                    qualification_class = ShellSearchQualification
                if parent_terminal_provider:
                    from parent_setup_qualification import ParentTerminalProviderQualification
                    qualification_class = ParentTerminalProviderQualification
                if license_viewer_provider:
                    from parent_setup_qualification import (
                        LicenseViewerProviderQualification, ParentWebsiteQualification,
                        ParentPrivacyQualification, ParentSupportQualification,
                        ParentInformationQualification)
                    qualification_class = {
                        'license': LicenseViewerProviderQualification,
                        'website': ParentWebsiteQualification,
                        'privacy': ParentPrivacyQualification,
                        'support': ParentSupportQualification,
                        'information': ParentInformationQualification,
                    }[information_link]
                if repeated_operations:
                    from parent_setup_qualification import RepeatedOperationsQualification
                    qualification_class = RepeatedOperationsQualification
                if challenges:
                    from parent_setup_qualification import (ChallengesQualification,
                        FreshChildAllowedQualification, FreshChildDeniedQualification,
                        CountdownQualification, CountdownOffQualification, ShellPanelQualification,
                        OverlayValidChoicesQualification, OverlayChoicesQualification, OverlayLicenseQualification,
                        OverlayBrowserLinksQualification)
                    qualification_class = {'parent': ChallengesQualification,
                        'fresh-child': FreshChildAllowedQualification,
                        'fresh-child-denied': FreshChildDeniedQualification,
                        'countdown-enabled': CountdownQualification,
                        'countdown-off': CountdownOffQualification,
                        'shell-panel': ShellPanelQualification,
                        'overlay-valid-choices': OverlayValidChoicesQualification,
                        'overlay-choices': OverlayChoicesQualification,
                        'overlay-license': OverlayLicenseQualification,
                        'overlay-browser-links': OverlayBrowserLinksQualification}[challenge_profile]
                if gdm_product_free:
                    from parent_setup_qualification import GdmProductFreeQualification
                    qualification_class = GdmProductFreeQualification
                if product_free_entry:
                    from parent_setup_qualification import ProductFreeEntryQualification
                    qualification_class = ProductFreeEntryQualification
                if package_authority:
                    from parent_setup_qualification import PackageAuthorityQualification
                    qualification_class = PackageAuthorityQualification
                if package_install:
                    from parent_setup_qualification import PackageInstallQualification
                    qualification_class = PackageInstallQualification
                if customer_reboot:
                    from parent_setup_qualification import CustomerRebootQualification
                    qualification_class = CustomerRebootQualification
                if kiosk_entry:
                    from parent_setup_qualification import KioskEntryQualification
                    qualification_class = KioskEntryQualification
                if kiosk_eligible_choices:
                    from parent_setup_qualification import KioskEligibleChoicesQualification
                    qualification_class = KioskEligibleChoicesQualification
                if request_choices:
                    from parent_setup_qualification import RequestChoicesQualification
                    qualification_class = RequestChoicesQualification
                if kiosk_no_child:
                    from parent_setup_qualification import KioskNoChildQualification
                    qualification_class = KioskNoChildQualification
                if kiosk_no_approver:
                    from parent_setup_qualification import KioskNoApproverQualification
                    qualification_class = KioskNoApproverQualification
                if request_exit:
                    from parent_setup_qualification import RequestExitQualification
                    qualification_class = RequestExitQualification
                if parent_toggle:
                    from parent_setup_qualification import ParentToggleQualification
                    qualification_class = ParentToggleQualification
                    if public_connectivity_controls:
                        from parent_setup_qualification import PublicConnectivityControlsQualification
                        qualification_class = PublicConnectivityControlsQualification
                if app_row_observations:
                    from parent_setup_qualification import AppRowQualification
                    qualification_class = AppRowQualification
                if native_fixtures:
                    from parent_setup_qualification import NativeFixtureQualification
                    qualification_class = NativeFixtureQualification
                if native_grid_usable:
                    from parent_setup_qualification import NativeGridQualification
                    qualification_class = NativeGridQualification
                if native_app:
                    from parent_setup_qualification import NativeAppQualification
                    qualification_class = NativeAppQualification
                if app_activity:
                    from parent_setup_qualification import NativeActivityQualification
                    qualification_class = NativeActivityQualification
                if catalogue_search:
                    from parent_setup_qualification import CatalogueSearchQualification
                    qualification_class = CatalogueSearchQualification
                if catalogue_filters:
                    from parent_setup_qualification import CatalogueQualification
                    qualification_class = CatalogueQualification
                if policy_legend:
                    from parent_setup_qualification import PolicyLegendQualification
                    qualification_class = PolicyLegendQualification
                if match_save_cancel:
                    from parent_setup_qualification import MatchSaveCancelQualification
                    qualification_class = MatchSaveCancelQualification
                if match_editor:
                    from parent_setup_qualification import MatchEditorQualification
                    qualification_class = MatchEditorQualification
                if rejected_parent_rule:
                    from parent_setup_qualification import RejectedParentRuleQualification
                    qualification_class = RejectedParentRuleQualification
                if access_choices:
                    from parent_setup_qualification import AccessChoicesQualification
                    qualification_class = AccessChoicesQualification
                if policy_edit:
                    from parent_setup_qualification import PolicyQualification
                    qualification_class = PolicyQualification
                if feedback_read:
                    from parent_setup_qualification import FeedbackReadQualification
                    qualification_class = FeedbackReadQualification
                if file_chooser:
                    from parent_setup_qualification import FileChooserQualification
                    qualification_class = FileChooserQualification
                if save_chooser:
                    from parent_setup_qualification import SaveChooserQualification
                    qualification_class = SaveChooserQualification
                if diagnostic_export:
                    from parent_setup_qualification import DiagnosticExportQualification
                    qualification_class = DiagnosticExportQualification
                if attachment_items:
                    from parent_setup_qualification import AttachmentItemsQualification
                    qualification_class = AttachmentItemsQualification
                if attachment_preview:
                    from parent_setup_qualification import AttachmentPreviewQualification
                    qualification_class = AttachmentPreviewQualification
                if attachment_boundaries:
                    from parent_setup_qualification import AttachmentBoundariesQualification
                    qualification_class = AttachmentBoundariesQualification
                if feedback_privacy:
                    from parent_setup_qualification import FeedbackPrivacyQualification
                    qualification_class = FeedbackPrivacyQualification
                if feedback_reset:
                    from parent_setup_qualification import FeedbackResetQualification
                    qualification_class = FeedbackResetQualification
                if feedback_states:
                    from parent_setup_qualification import FeedbackStatesQualification
                    qualification_class = FeedbackStatesQualification
                if trace_stable_state:
                    from parent_setup_qualification import TraceStableStateQualification
                    qualification_class = TraceStableStateQualification
                if trace_transition:
                    from parent_setup_qualification import TraceTransitionQualification
                    qualification_class = TraceTransitionQualification
                if compose_observation:
                    from parent_setup_qualification import ComposeObservationQualification
                    qualification_class = ComposeObservationQualification
                if accessibility_input_trace:
                    from parent_setup_qualification import AccessibilityInputTraceQualification
                    qualification_class = AccessibilityInputTraceQualification
                if parent_save_trace:
                    from parent_setup_qualification import ParentSaveTraceQualification
                    qualification_class = ParentSaveTraceQualification
                if feedback_collection:
                    from parent_setup_qualification import FeedbackCollectionQualification
                    qualification_class = FeedbackCollectionQualification
                if custom_save_trace:
                    from parent_setup_qualification import CustomSaveTraceQualification
                    qualification_class = CustomSaveTraceQualification
                if named_child_custom_saves:
                    from parent_setup_qualification import NamedChildCustomSavesQualification
                    qualification_class = NamedChildCustomSavesQualification
                if format_qualification:
                    from parent_setup_qualification import FormatQualification
                    qualification_class = FormatQualification
                if feedback_block_semantics:
                    from parent_setup_qualification import BlockSemanticsQualification
                    qualification_class = BlockSemanticsQualification
                if feedback_formats:
                    from parent_setup_qualification import FeedbackFormatsQualification
                    qualification_class = FeedbackFormatsQualification
                if feedback_link_semantics:
                    from parent_setup_qualification import FeedbackLinkQualification
                    qualification_class = FeedbackLinkQualification
                if window_switch:
                    from parent_setup_qualification import WindowSwitchQualification
                    qualification_class = WindowSwitchQualification
                if feedback_rejection:
                    from parent_setup_qualification import FeedbackRejectionQualification
                    qualification_class = FeedbackRejectionQualification
                if feedback_length:
                    from parent_setup_qualification import FeedbackLengthQualification
                    qualification_class = FeedbackLengthQualification
                if text_qualification:
                    from parent_setup_qualification import TextQualification
                    qualification_class = TextQualification
                if allowance_presets:
                    from parent_setup_qualification import AllowancePresetsQualification
                    qualification_class = AllowancePresetsQualification
                if allowance:
                    from parent_setup_qualification import AllowanceQualification
                    qualification_class = AllowanceQualification
                if allowance_boundaries:
                    from parent_setup_qualification import AllowanceBoundariesQualification
                    qualification_class = AllowanceBoundariesQualification
                if kiosk_valid_duration:
                    from parent_setup_qualification import KioskValidDurationQualification
                    qualification_class = KioskValidDurationQualification
                if request_duration:
                    from parent_setup_qualification import RequestDurationQualification
                    qualification_class = RequestDurationQualification
                if request_flow:
                    from parent_setup_qualification import RequestFlowQualification
                    qualification_class = RequestFlowQualification
                if restricted_station_about:
                    from parent_setup_qualification import RestrictedStationAboutQualification
                    qualification_class = RestrictedStationAboutQualification
                if mate_prompt:
                    from parent_setup_qualification import MatePromptQualification
                    qualification_class = MatePromptQualification
                if kiosk_multiple:
                    from parent_setup_qualification import KioskMultipleQualification
                    qualification_class = KioskMultipleQualification
                if kiosk_ineligible:
                    from parent_setup_qualification import KioskIneligibleQualification
                    qualification_class = KioskIneligibleQualification
                if kiosk_approval:
                    from parent_setup_qualification import KioskApprovalQualification
                    qualification_class = KioskApprovalQualification
                if kiosk_rejection:
                    from parent_setup_qualification import KioskRejectionQualification
                    qualification_class = KioskRejectionQualification
                if auth_result:
                    from parent_setup_qualification import AuthResultQualification
                    qualification_class = AuthResultQualification
                if kiosk_approved_flow:
                    from parent_setup_qualification import KioskApprovedFlowQualification
                    qualification_class = KioskApprovedFlowQualification
                if approval_flow:
                    from parent_setup_qualification import ApprovalFlowRejectionQualification, ApprovalFlowCancelQualification
                    qualification_class = (ApprovalFlowRejectionQualification if approval_flow == 'rejection'
                                           else ApprovalFlowCancelQualification)
                if time_explanation:
                    from parent_setup_qualification import TimeExplanationQualification
                    qualification_class = TimeExplanationQualification
                if set_allowance:
                    from parent_setup_qualification import SetAllowanceQualification
                    qualification_class = SetAllowanceQualification
                if fresh_thirty_allowance:
                    from parent_setup_qualification import FreshThirtyAllowanceQualification, JordanThirtyAllowanceQualification
                    qualification_class = (FreshThirtyAllowanceQualification if fresh_thirty_child == 'child'
                                           else JordanThirtyAllowanceQualification)
                if app_restart:
                    from parent_setup_qualification import AppRestartQualification
                    qualification_class = AppRestartQualification
                if real_interval:
                    from parent_setup_qualification import RealIntervalQualification
                    qualification_class = RealIntervalQualification
                qualification = qualification_class(directory, commands, ledger, collector, result, host_before,
                                              staged, credentials, serial, install, install_refusal, vt6_prompt,
                                              vt6_auth)
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
