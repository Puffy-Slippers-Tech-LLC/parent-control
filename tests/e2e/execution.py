"""Public selected attempts using the existing VM lease and evidence gate.

Scenario modules are trusted checkout code, loaded only after independent input
capture. Cases start from the baseline; multi-case runs retain one suite lease.
"""

import copy
from functools import cache
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import uuid

from fixture_credentials import FixtureCredentials, preflight as credential_preflight
from leased_recording import LeasedScenario
from private_artifacts import EvidenceError, PrivateCollector, require
from provenance import VerifiedInputs, preflight_source
from recording import ScenarioRecorder
from tools.e2e_progress import Progress

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
import graphical_backend
from owned_commands import Commands
import system_runner as system
sys.path.pop(0)


def attempt_failure(error):
    """Retain reviewed provenance refusals even before a recorder exists.

    Do not serialize arbitrary exception text, including code-shaped account
    names or secrets. Unknown failures keep the generic infrastructure code.
    """
    if isinstance(error, KeyboardInterrupt):
        return 'execution:interrupted'
    codes = {
        'provenance:source-changed', 'provenance:assets-changed',
        'provenance:baseline-changed', 'provenance:package-source-mismatch',
        'provenance:baseline-state-changed', 'provenance:baseline-proof-changed',
        'provenance:baseline-identity-changed', 'provenance:file-changed',
        'provenance:file-replaced', 'provenance:tree-changed',
        'provenance:source-preflight-failed', 'provenance:capture-failed',
        'provenance:recheck-failed',
    }
    if isinstance(error, EvidenceError) and len(error.args) == 1:
        code = error.args[0]
        if type(code) is str and code in codes:
            return code
    return 'execution:attempt-failed'


@cache
def event_api():
    """One public libvirt event loop per controller process, across cases."""
    api = importlib.import_module('libvirt')
    api.virEventRegisterDefaultImpl()
    def events():
        while True:
            api.virEventRunDefaultImpl()
    threading.Thread(target=events, daemon=True, name='libvirt-events').start()
    return api


def open_source():
    """Each independent attempt owns and closes its separate connection."""
    guestfs = importlib.import_module('guestfs')
    api = event_api()
    return system.baseline.LibvirtSource(api), guestfs


def load_callback(case, verified):
    """Execute frozen, digest-checked Python bytes, never a caller command."""
    relative = case['executable']['path']
    path = verified.root / relative
    require(path.suffix == '.py' and path.resolve() == path and path.is_file(),
            'execution:unsafe-callback')
    verified.recheck()
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == verified.source_files.get(relative),
            'execution:callback-inputs-changed')
    namespace = {'__file__': str(path), '__name__': 'onpc_e2e_scenario'}
    exec(compile(data, str(path), 'exec'), namespace)
    callbacks = namespace.get('E2E_CASES')
    require(type(callbacks) is dict, 'execution:callback-registry-required')
    callback = callbacks.get(case['executable']['test_id'])
    require(callable(callback), 'execution:callback-missing')
    verified.recheck()
    return callback


class ScenarioContext:
    """Prepared inputs for trusted callbacks; the lease remains the only owner.

    Use run_worker once to retain its actual cleanup proof. Provisioning helpers
    use credentials/guestfs within declared setup steps, before worker startup.
    No arbitrary guest command, checkpoint or alternate VM selector is exposed.
    """

    def __init__(self, recorder, verified, directory, commands, guestfs, host_key, credentials):
        self.recorder, self.verified = recorder, verified
        self.directory, self.commands = directory, commands
        self.guestfs, self.host_key, self.credentials = guestfs, host_key, credentials
        self.lease = verified.lease
        self.worker = None
        self._worker_started = False

    def run_worker(self, *, observe, validate, authenticate=False, serial=False, timeout=600,
                   guarded_observe=None):
        require(not self._worker_started, 'execution:worker-already-attempted')
        self._worker_started = True
        try:
            self.worker = self.recorder.run_worker(
                self.verified, self.directory, self.lease, self.lease.ledger,
                observe=observe, validate=validate, timeout=timeout,
                credentials=self.credentials if authenticate else None, serial=serial,
                **({'guarded_observe': guarded_observe} if guarded_observe is not None else {}))
        except BaseException as error:
            retained = getattr(error, 'onpc_worker_result', None)
            if isinstance(retained, dict):
                self.worker = copy.deepcopy(retained)
            raise
        return copy.deepcopy(self.worker)


def attempt(plan, case, *, root=ROOT, expected_inputs=None, progress=None, suite=None):
    """Retain preparation failures even when no ScenarioRecorder can exist yet."""
    run_id = 'scenario-' + uuid.uuid4().hex
    ledger = system.RunLedger()
    source = lease = collector = context = host_before = bridge = None
    commands = suite.commands if suite is not None else Commands()
    report = {'schema_version': 1, 'run_id': run_id, 'case_id': case['case_id'],
              'outcome': 'failed', 'acceptance_candidate': None, 'inputs': None,
              'first_failure': None, 'lease_phase': None,
              'scope': 'independent-scenario-attempt'}
    if suite is not None:
        report['verification_scope'] = 'suite-boundaries'
    sequence = 0
    progress = progress if progress is not None else Progress(plan['cases'])
    progress.prepare(case['case_id'])

    def fail(category, code):
        ledger.fail_outcome(category, code)
        report['outcome'] = 'failed'
        if report['first_failure'] is None:
            report['first_failure'] = {'category': category, 'code': code}

    def checkpoint(event):
        nonlocal sequence
        sequence += 1
        try:
            collector.save_report(f'invocation-{sequence:06d}', {
                **report, **ledger.data(), 'event': event})
        except BaseException:
            fail('collection', 'execution:report-failed')
            raise

    try:
        credentials = FixtureCredentials()
        collector = PrivateCollector(run_id=run_id,
                                     secrets=credentials.variables.registered_secrets)
        report['evidence_directory'] = str(collector.path)
        checkpoint('preparation-started')
        with ledger.measure('preparation'):
            # Keep retained worker PNGs inside the existing guarded export
            # scope, including when the caller has configured another TMPDIR.
            from tools.test_retention import allocate
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-graphical-smoke-', dir='/tmp'))
            directory.chmod(0o700)
            report['raw_directory'] = str(directory)
            private = directory / 'private'
            private.mkdir(mode=0o700)
            commands.directory = private
            if suite is None or not suite.backend_checked:
                graphical_backend.check(commands)
                if suite is not None:
                    suite.backend_checked = True
            if ('fixture-credentials-via-secret-api' in case['preconditions'] and
                    (suite is None or not suite.credentials_checked)):
                credential_preflight(commands)
                if suite is not None:
                    suite.credentials_checked = True
            staged = directory / 'assets'
            system.stage_assets(system.artifact_source(Path(plan['artifacts'])), staged, commands)
            staged.chmod(0o700)
            source_check = preflight_source(staged, root=root)
            # bootstrap binds the guest's observation marker to this exact
            # selected input document. Stage it before acquiring the VM; a
            # ready callback cannot substitute for this preparation input.
            bootstrap_inputs = {'schema_version': 1, 'scope': 'e2e-observation',
                'source_sha256': source_check['source_sha256'],
                'inventory_sha256': plan['inventory_sha256'], 'case': case}
            input_directory = directory / 'input'
            installed_consumer = (case['category'] == 'customer-journey'
                                  and 'installed-digest-verified-product' in case['preconditions'])
            if installed_consumer:
                from installed_setup import stage
                stage(directory, staged, bootstrap_inputs)
            else:
                input_directory.mkdir(mode=0o700)
                with (input_directory / 'selected-inputs.json').open('xb') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(system.baseline.encode(bootstrap_inputs))
                    stream.flush()
                    os.fsync(stream.fileno())
            print('e2e:bootstrap-inputs-staged', file=sys.stderr, flush=True)
            if suite is None:
                host_before = system.host_fingerprint(commands)
                source, guestfs = open_source()
                lease = system.Lease(source, commands,
                    lambda disk, digest: system.baseline.inspect_guest(guestfs, disk, digest),
                    ledger=ledger, graphics_type='vnc',
                    verify_backing_bytes=plan.get('verify_backing_bytes', True))
            else:
                source, guestfs, lease = suite.acquire(ledger)
        with lease:
            try:
                with ledger.measure('preparation'):
                    lease.prepare()
                    host_key = system.bootstrap(commands, lease, directory, guestfs,
                                                observation_only=not installed_consumer)
                    lease.guard(off=True)
                    lease.save('isolated')
                    verified = VerifiedInputs(lease=lease, assets=staged, root=root)
                    if suite is not None:
                        suite.verified = verified
                    report['inputs'] = verified.inputs
                    require(verified.inputs['inventory_sha256'] == plan['inventory_sha256'],
                            'execution:selection-inputs-changed')
                    require(expected_inputs is None or verified.inputs == expected_inputs,
                            'execution:invocation-inputs-changed')
                    contract = verified.contract(run_id=run_id, selector=case['case_id'])
                    require(contract.plan['cases'] == [case], 'execution:selection-changed')
                    recorder = ScenarioRecorder(contract, collector, progress=progress)
                    lease.watch_progress = recorder.progress
                    context = ScenarioContext(recorder, verified, directory, commands,
                                              guestfs, host_key, credentials)

                    def cleanup(_recorder, held):
                        if suite is None:
                            require(system.host_fingerprint(commands) == host_before,
                                    'execution:host-changed')
                        worker = context.worker or {}
                        return {'lease_phase': held.state['phase'], 'vm_off': True,
                                'baseline_restored': held.state['phase'] == 'complete',
                                'host_preserved': True, 'source_preserved': True,
                                'owned_processes_stopped': worker.get('worker_stopped') is True
                                    and worker.get('callback_closed') is True}

                    bridge = LeasedScenario(recorder, verified, cleanup=cleanup)
                    checkpoint('preparation-complete')
                with ledger.measure('test'):
                    bridge.execute(lambda r: load_callback(case, verified)(r, context))
                    progress.prepare_next()
            except BaseException as error:
                # Persist before Lease.__exit__ starts restoration, including
                # preparation failures before a recorder or finalizer exists.
                if context is not None and context.recorder.records:
                    failures = context.recorder.records[-1]['failures']
                    for failure in failures:
                        fail(failure['category'], failure['code'])
                if report['first_failure'] is None:
                    fail('infrastructure', attempt_failure(error))
                try:
                    checkpoint('before-lease-cleanup')
                except BaseException:
                    pass
                raise
        report['acceptance_candidate'] = bridge.result()
        for category in ledger.outcomes:
            ledger.pass_outcome(category)
        report['outcome'] = 'passed'
    except BaseException as error:
        # Lease restoration/finalization/release may have failed after the
        # callback returned. Keep those domains instead of blaming the product.
        if context is not None and context.recorder.records:
            for failure in context.recorder.records[-1]['failures']:
                fail(failure['category'], failure['code'])
        if report['first_failure'] is None and ledger.first_failure_category is not None:
            for category, value in ledger.outcomes.items():
                if value['category'] == ledger.first_failure_category:
                    report['first_failure'] = {'category': category, 'code': value['category']}
                    break
        if report['first_failure'] is None:
            fail('infrastructure', attempt_failure(error))
    finally:
        with ledger.measure('cleanup'):
            if host_before is not None:
                try:
                    require(system.host_fingerprint(commands) == host_before,
                            'execution:host-changed')
                except BaseException:
                    fail('cleanup', 'execution:host-preservation-failed')
            if source is not None and suite is None:
                try:
                    source.close()
                except BaseException:
                    fail('cleanup', 'execution:connection-close-failed')
        report['lease_phase'] = lease.state['phase'] if lease and lease.state else None
        if lease is not None:
            report['baseline_verification'] = dict(lease.capture.verification_totals)
        if any(v['outcome'] == 'failed' for v in ledger.outcomes.values()):
            report['outcome'] = 'failed'
        if collector is not None:
            try:
                checkpoint('attempt-terminal-candidate')
                collector.verify([artifact for record in context.recorder.records
                                  for artifact in record['artifacts']] if context else [])
            except BaseException:
                fail('collection', 'execution:final-report-failed')
            finally:
                try:
                    collector.close()
                except BaseException:
                    fail('collection', 'execution:collector-close-failed')
        report.update(ledger.data())
    return report


def main(plan):
    require(os.geteuid() == os.getegid() == 0, 'execution:root-required')
    require(Path.cwd() == ROOT == system.baseline.guest_contract.CHECKOUT,
            'execution:checkout')
    os.umask(0o077)
    def interrupted(*_):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, interrupted)
    report = {'schema_version': 1, 'scope': plan['scope'], 'outcome': 'failed',
              'inventory_sha256': plan['inventory_sha256'],
              'ready_only': plan.get('ready_only', False),
              'excluded_pending_cases': plan.get('excluded_pending_cases', []),
              'expected_cases': [c['case_id'] for c in plan['cases']], 'attempts': []}
    collector = None
    progress = Progress(plan['cases'])
    from e2e_watch import ProgressPublication
    publication = ProgressPublication(progress)
    from suite_lease import Suite
    suite = (Suite(open_source, verify_backing_bytes=plan.get('verify_backing_bytes', True))
             if len(plan['cases']) > 1 else None)
    previous_progress = system.watch_progress
    system.watch_progress = progress
    try:
        # This final report owns the invocation outcome. Per-case acceptance
        # files are candidates until release, close and report validation pass.
        collector = PrivateCollector(run_id='invocation-' + uuid.uuid4().hex, secrets=[])
        try:
            report['evidence_directory'] = str(collector.path)
            collector.save_report('invocation-started', report)
            expected_inputs = None
            try:
                for case in plan['cases']:
                    result = attempt(plan, case, expected_inputs=expected_inputs, progress=progress,
                                     **({'suite': suite} if suite is not None else {}))
                    report['attempts'].append(result)
                    collector.save_report(f'attempt-{len(report["attempts"]):06d}', result)
                    if result['outcome'] != 'passed':
                        break
                    expected_inputs = result['inputs']
            finally:
                if suite is not None:
                    try:
                        suite.close()
                        report['suite_cleanup'] = {'outcome': 'passed'}
                    except BaseException:
                        report['suite_cleanup'] = {'outcome': 'failed'}
                        raise
                    finally:
                        if suite.lease is not None:
                            report['baseline_verification'] = dict(suite.lease.capture.verification_totals)
            require(report['expected_cases'] and
                    [a['case_id'] for a in report['attempts']] == report['expected_cases'] and
                    all(a['outcome'] == 'passed' for a in report['attempts']),
                    'execution:incomplete-invocation')
            collector.verify([])
            report['outcome'] = 'passed'
        except BaseException:
            report['outcome'] = 'failed'
            report['failure'] = 'execution:invocation-failed'
        finally:
            collector.save_report('invocation-terminal-candidate', report)
            collector.verify([])
    except BaseException:
        report['outcome'] = 'failed'
        report['failure'] = 'execution:invocation-report-failed'
    finally:
        system.watch_progress = previous_progress
        publication.close()
        if collector is not None:
            try:
                collector.close()
            except BaseException:
                report['outcome'] = 'failed'
                report['failure'] = 'execution:invocation-close-failed'
        signal.signal(signal.SIGTERM, previous)
    # Caller exit status and this post-close result are the terminal authority.
    print(json.dumps(report, sort_keys=True))
    return 0 if report['outcome'] == 'passed' else 1
