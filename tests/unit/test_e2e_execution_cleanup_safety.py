"""Public controller, real recorder/collector/lease exit; VM operations substituted."""

import copy
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.e2e_evidence import attempt as evidence_attempt

from tests.support.paths import ROOT
from tests.support.vm_baseline import local_preparation_source
from tests.support.vm_runner import bootstrap_guest
import evidence
import execution
import e2e_worker
import suite_lease
from private_artifacts import EvidenceError, PrivateCollector
REAL_BOOTSTRAP = execution.system.bootstrap


@pytest.fixture(autouse=True)
def fixture_password(monkeypatch):
    monkeypatch.setattr('test_account_password.read_password', lambda *args: 'fixture-password')
    monkeypatch.setattr('fixture_credentials.read_password', lambda *args: 'fixture-password')

CALLBACK = '''
def execute(recorder, context):
    context.run_worker(observe=lambda: None, validate=lambda: None)
    case = recorder.contract.plan['cases'][0]
    for phase, steps in case['phases'].items():
        if phase == 'cleanup':
            continue
        for step in steps:
            with recorder.step(step['id']):
                recorder.continuity(boot='private-canary-boot')
                checks = [(kind, check) for kind, entries in case['assertions'].items()
                          for check in entries if check['step_id'] == step['id']]
                if checks:
                    for kind in case['expected_evidence']:
                        recorder.artifact(kind, kind, ('reviewed ' + kind).encode(), reviewed=True)
                    for kind, check in checks:
                        recorder.assertion(check['id'], artifact_ids=[
                            {'visible': 'screen', 'backend': 'backend', 'other_user': 'other-user'}[kind]])
E2E_CASES = {'synthetic-smoke': execute}
'''


@pytest.fixture
def harness(evidence_attempt, tmp_path, monkeypatch, local_preparation_source, request):
    _, _, _, inventory_path, inputs = evidence_attempt
    path = tmp_path / 'tests/e2e/scenarios.json'
    path.write_bytes(inventory_path.read_bytes())
    callback = tmp_path / 'tests/e2e/synthetic.py'
    callback.write_text(CALLBACK)
    for relative in ('tests/e2e/inventory.py', 'tests/e2e/runner.py'):
        (tmp_path / relative).write_bytes((ROOT / relative).read_bytes())
    run_directory = tmp_path / 'raw'
    run_directory.mkdir(mode=0o700)
    # Keep the real collector's allocator independent of the raw directory.
    monkeypatch.setattr(execution, 'tempfile', SimpleNamespace(mkdtemp=Mock(return_value=str(run_directory))))
    collectors = []
    def collect(**kwargs):
        collector = PrivateCollector(**kwargs, parent=tmp_path)
        collectors.append(collector)
        return collector
    monkeypatch.setattr(execution, 'PrivateCollector', collect)
    monkeypatch.setattr(execution, 'Commands', Mock(return_value=Mock()))
    monkeypatch.setattr(execution.graphical_backend, 'check', Mock())
    monkeypatch.setattr(execution.system, 'artifact_source', Mock(return_value=tmp_path))
    monkeypatch.setattr(execution.system, 'stage_assets',
                        Mock(side_effect=lambda _source, target, _commands: target.mkdir()))
    monkeypatch.setattr(execution, 'preflight_source', Mock(return_value={'source_sha256': 'a' * 64}))
    fingerprint = Mock(return_value='host-before')
    monkeypatch.setattr(execution.system, 'host_fingerprint', fingerprint)
    source = Mock()
    monkeypatch.setattr(execution, 'open_source', Mock(return_value=(source, Mock())))
    monkeypatch.setattr(execution.system, 'bootstrap', Mock(return_value='private-canary-key'))
    events, leases = [], []
    real_lease = execution.system.Lease
    def lease_factory(source, commands, inspect, *, ledger, graphics_type, verify_backing_bytes):
        lease = real_lease(source, commands, inspect, ledger=ledger, graphics_type=graphics_type,
                           verify_backing_bytes=verify_backing_bytes)
        lease.state = {'phase': 'isolated', 'domain_id': None, 'run': 'a' * 32,
                       'domain_uuid': 'fixed-domain'}
        lease.prepare = Mock()
        lease.guard = Mock()
        lease.save = Mock(side_effect=lambda phase: lease.state.update(phase=phase))
        def finish():
            events.append('restore')
            lease.state['phase'] = 'complete'
        def release():
            events.append('release')
            lease.fd = None
        lease.finish = Mock(side_effect=finish)
        lease.release = Mock(side_effect=release)
        leases.append(lease)
        return lease
    def enter(lease):
        events.append('enter')
        lease.fd = 42
        return lease
    monkeypatch.setattr(real_lease, '__enter__', enter)
    monkeypatch.setattr(execution.system, 'Lease', lease_factory)
    class Verified:
        def __init__(self, *, lease, assets, root):
            self.lease, self.root = lease, root
            self.inputs = copy.deepcopy(inputs)
            self.source_files = {'tests/e2e/synthetic.py': hashlib.sha256(callback.read_bytes()).hexdigest()}
            self.recheck = Mock()
            self.recheck_contract = Mock()
        def contract(self, *, run_id, selector):
            return evidence.EvidenceContract(inventory_path=path, root=self.root,
                                            run_id=run_id, selector=selector, inputs=self.inputs)
        def validate(self, contract, records, collector):
            assert self.lease.fd == 42 and self.lease.state['phase'] == 'complete'
            events.append('validate')
            return contract.validate(records, collector)
    monkeypatch.setattr(execution, 'VerifiedInputs', Verified)
    worker = Mock(return_value={'outcome': 'passed', 'worker_stopped': True,
                              'callback_closed': True, 'shutdown_verified': True})
    monkeypatch.setattr(e2e_worker, 'run_distribution', worker)
    runner = runpy.run_path(str(tmp_path / 'tests/e2e/runner.py'))
    # Public preflight accepts project artifact roots under /tmp or /var/tmp.
    # Keep that path shape, with an explicit fixture lifetime.
    assets_parent = tempfile.TemporaryDirectory(prefix='onpc-e2e-assets-', dir='/var/tmp')
    request.addfinalizer(assets_parent.cleanup)
    assets = PrivateCollector(run_id='assets', secrets=[], parent=Path(assets_parent.name))
    request.addfinalizer(assets.close)
    plan = runner['preflight'](['--artifacts=' + str(assets.path)], root=tmp_path)
    yield SimpleNamespace(root=tmp_path, plan=plan, case=plan['cases'][0], callback=callback,
                          events=events, leases=leases, source=source, collectors=collectors,
                          worker=worker, fingerprint=fingerprint, runner=runner)


def run(harness, **kwargs):
    return execution.attempt(harness.plan, harness.case, root=harness.root, **kwargs)


def documents(harness):
    return [json.loads(path.read_text()) for collector in harness.collectors
            for path in sorted(collector.path.glob('*.json'))]


def test_installed_case_without_suite_refuses_before_vm_acquisition(harness):
    harness.case['preconditions'].append('installed-digest-verified-product')
    result = run(harness)
    assert result['outcome'] == 'failed'
    assert result['first_failure']['code'] == 'execution:installed-snapshot-suite-required'
    execution.open_source.assert_not_called()
    execution.system.bootstrap.assert_not_called()
    harness.worker.assert_not_called()


@pytest.mark.parametrize('verify_backing_bytes', [True, False])
def test_public_ready_plan_executes_real_callback_and_finalizes_after_lease_exit(harness, verify_backing_bytes):
    args = ['--artifacts=' + harness.plan['artifacts']]
    if not verify_backing_bytes:
        args.append('--skip-backing-verification')
    harness.plan = harness.runner['preflight'](args, root=harness.root)
    result = run(harness)
    assert result['outcome'] == 'passed', result
    assert result['acceptance_candidate']['case_ids'] == [harness.case['case_id']]
    assert harness.events == ['enter', 'restore', 'validate', 'validate', 'release']
    assert result['first_failure'] is None
    assert all(value['outcome'] == 'passed' for value in result['outcomes'].values())
    harness.source.close.assert_called_once()
    assert all(c._fd is None for c in harness.collectors)
    assert 'private-canary' not in json.dumps(documents(harness))
    assert harness.leases[0].capture.verify_backing_bytes is verify_backing_bytes
    policy = 'full' if verify_backing_bytes else 'metadata-only'
    assert result['baseline_verification']['policy'] == policy


@pytest.mark.parametrize('preparation_fails', [False, True])
def test_retained_attempt_screens_support_guarded_export(harness, monkeypatch, preparation_fails):
    helper = runpy.run_path(str(ROOT / 'tools/onpc-export-screenshot'))
    with ExitStack() as owned:
        def allocate(**kwargs):
            return owned.enter_context(tempfile.TemporaryDirectory(**kwargs))
        monkeypatch.setattr(execution, 'tempfile', SimpleNamespace(mkdtemp=allocate))
        # Export has a fixed /tmp scope, independent of the process temp default.
        monkeypatch.setattr(tempfile, 'tempdir', str(harness.root))
        if preparation_fails:
            execution.graphical_backend.check.side_effect = RuntimeError('private-canary')
        result = run(harness)
        assert result['outcome'] == ('failed' if preparation_fails else 'passed')
        raw = Path(result['raw_directory'])
        assert raw.stat().st_mode & 0o777 == 0o700
        assert raw.stat().st_uid == os.getuid()
        assert (raw / 'private').stat().st_mode & 0o777 == 0o700
        results = raw / 'testresults'
        results.mkdir(mode=0o700)
        source = results / 'smoke-1.png'
        payload = helper['PNG_SIGNATURE'] + b'synthetic screen'
        source.write_bytes(payload)
        source.chmod(0o600)
        destination = Path('/tmp') / (raw.name + '-export.png')
        try:
            helper['export'](str(source), str(destination), os.getuid(), os.getgid())
            assert destination.read_bytes() == payload
            assert destination.stat().st_mode & 0o777 == 0o600
            assert destination.stat().st_uid == os.getuid()
            assert source.read_bytes() == payload
        finally:
            if destination.exists():
                destination.unlink()
        assert all(c._fd is None for c in harness.collectors)
        if preparation_fails:
            assert not harness.leases
            execution.open_source.assert_not_called()
        else:
            assert result['lease_phase'] == 'complete'
            harness.source.close.assert_called_once()


def test_public_preparation_satisfies_real_bootstrap_input_contract(harness, monkeypatch):
    # Execute the actual bootstrap composition. Only offline guest access and
    # external commands are substituted, so a missing selected-input file fails.
    monkeypatch.setattr(execution.system, 'bootstrap', REAL_BOOTSTRAP)
    harness.source.uuid = 'fixed-domain'
    factory = execution.system.Lease
    def prepared(*args, **kwargs):
        lease = factory(*args, **kwargs)
        lease.state['baseline_sha256'] = 'b' * 64
        lease.capture = Mock(verification_totals={}, state={'source': {'layout': {'disk': '/guarded-image'}},
                                   'guest': {'preparation_record_sha256': 'c' * 64}})
        return lease
    monkeypatch.setattr(execution.system, 'Lease', prepared)
    guest, files = bootstrap_guest()
    @contextmanager
    def mounted(*args, **kwargs):
        (Path(args[1].commands.directory).parent / 'ssh-key.pub').write_bytes(b'ssh-ed25519 QUFB fixture\n')
        yield guest
    monkeypatch.setattr(execution.system, 'mounted_guest', mounted)
    result = run(harness)
    assert result['outcome'] == 'passed', result
    path = Path(result['raw_directory']) / 'input/selected-inputs.json'
    data = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(data) == {'schema_version': 1, 'scope': 'e2e-observation',
        'source_sha256': 'a' * 64, 'inventory_sha256': harness.plan['inventory_sha256'],
        'case': harness.case}
    marker = next(json.loads(call.args[1]) for call in guest.write.call_args_list
                  if call.args[0] == '/etc/onpc-system-test.json')
    assert marker['selected_inputs_sha256'] == hashlib.sha256(data).hexdigest()
    assert marker['scope'] == 'graphical-observation-only'
    assert 'private-guest-identity' not in json.dumps(documents(harness))


@pytest.mark.parametrize('category', ['customer-journey', 'runner-smoke', 'fault-recovery'])
@pytest.mark.parametrize('installed', [True, False])
def test_installed_preparation_uses_customer_prerequisites_without_a_case_id_switch(
        harness, monkeypatch, category, installed):
    import installed_setup
    stage = Mock()
    monkeypatch.setattr(installed_setup, 'stage', stage)
    harness.case['category'] = category
    harness.case['preconditions'] = ['installed-digest-verified-product'] if installed else []
    execution.system.bootstrap.side_effect = RuntimeError('stop after inspecting bootstrap inputs')
    suite = SimpleNamespace(commands=execution.Commands(), backend_checked=False,
                            credentials_checked=False, prepare_case=Mock())
    def acquire(ledger):
        source, guestfs = execution.open_source()
        lease = execution.system.Lease(source, suite.commands, Mock(), ledger=ledger,
                                       graphics_type='vnc', verify_backing_bytes=True)
        return source, guestfs, lease
    suite.acquire = acquire
    result = run(harness, suite=suite)
    assert result['outcome'] == 'failed'
    expected = installed
    assert execution.system.bootstrap.call_args.kwargs['observation_only'] is not expected
    assert stage.call_count == int(expected)
    suite.prepare_case.assert_called_once()
    if expected:
        assert stage.call_args.args[2]['case'] == harness.case
    harness.leases[0].finish.assert_called_once()
    harness.leases[0].release.assert_called_once()


def test_credential_tool_pin_refuses_before_vm_acquisition(harness, monkeypatch):
    harness.case['preconditions'].append('fixture-credentials-via-secret-api')
    check = Mock(side_effect=RuntimeError('private-canary'))
    monkeypatch.setattr(execution, 'credential_preflight', check)
    result = run(harness)
    assert result['outcome'] == 'failed'
    assert not harness.leases
    execution.open_source.assert_not_called()
    check.assert_called_once()
    assert 'private-canary' not in json.dumps(documents(harness))


@pytest.mark.parametrize('boundary', ['backend', 'source', 'open-source', 'prepare', 'bootstrap', 'capture'])
def test_preparation_failure_retains_diagnostics_and_only_owned_cleanup(harness, monkeypatch, boundary):
    error = RuntimeError('private-canary')
    if boundary == 'backend': execution.graphical_backend.check.side_effect = error
    elif boundary == 'source': execution.preflight_source.side_effect = error
    elif boundary == 'open-source': execution.open_source.side_effect = error
    elif boundary == 'bootstrap': execution.system.bootstrap.side_effect = error
    elif boundary == 'capture': monkeypatch.setattr(execution, 'VerifiedInputs', Mock(side_effect=error))
    else:
        factory = execution.system.Lease
        def broken(*args, **kwargs):
            lease = factory(*args, **kwargs)
            lease.prepare.side_effect = error
            return lease
        monkeypatch.setattr(execution.system, 'Lease', broken)
    result = run(harness)
    assert result['outcome'] == 'failed'
    assert result['acceptance_candidate'] is None
    harness.worker.assert_not_called()
    assert not any(d.get('event') == 'case-started' for d in documents(harness))
    if harness.leases:
        lease = harness.leases[0]
        lease.finish.assert_called_once()
        lease.release.assert_called_once()
        assert 'before-lease-cleanup' in [d.get('event') for d in documents(harness)]
        harness.source.close.assert_called_once()
    else:
        harness.source.close.assert_not_called()
    assert 'private-canary' not in json.dumps(documents(harness))


@pytest.mark.parametrize('boundary', ['preflight', 'capture', 'contract'])
@pytest.mark.parametrize('code', [
    'provenance:source-changed', 'provenance:assets-changed', 'provenance:baseline-changed',
])
def test_pre_recorder_provenance_refusal_survives_owned_cleanup(harness, monkeypatch, boundary, code):
    error = EvidenceError(code)
    if boundary == 'preflight':
        execution.preflight_source.side_effect = error
    elif boundary == 'capture':
        monkeypatch.setattr(execution, 'VerifiedInputs', Mock(side_effect=error))
    else:
        monkeypatch.setattr(execution.VerifiedInputs, 'contract', Mock(side_effect=error))
    # Later connection cleanup cannot replace the first, specific refusal.
    harness.source.close.side_effect = RuntimeError('private-canary-close')
    result = run(harness)
    expected = {'category': 'infrastructure', 'code': code}
    assert result['outcome'] == 'failed'
    assert result['first_failure'] == expected
    assert result['outcomes']['infrastructure']['category'] == code
    assert result['acceptance_candidate'] is None
    harness.worker.assert_not_called()
    records = documents(harness)
    assert not any(d.get('event') == 'case-started' for d in records)
    if boundary == 'preflight':
        assert not harness.leases
        execution.open_source.assert_not_called()
    else:
        assert next(d for d in records if d.get('event') == 'before-lease-cleanup')['first_failure'] == expected
        harness.leases[0].finish.assert_called_once()
        harness.leases[0].release.assert_called_once()
        harness.source.close.assert_called_once()
        assert result['outcomes']['cleanup']['outcome'] == 'failed'
    assert records[-1]['first_failure'] == expected
    assert 'private-canary' not in json.dumps([result, records])


@pytest.mark.parametrize('error', [
    EvidenceError('provenance:private-canary'),
    EvidenceError('provenance:source-changed private-canary'),
    EvidenceError('provenance:source-changed', 'private-canary'),
    EvidenceError({'private-canary': 'value'}),
    RuntimeError('provenance:source-changed'),
])
def test_pre_recorder_exception_text_is_never_exported(harness, monkeypatch, error):
    monkeypatch.setattr(execution.VerifiedInputs, 'contract', Mock(side_effect=error))
    result = run(harness)
    assert result['first_failure'] == {'category': 'infrastructure', 'code': 'execution:attempt-failed'}
    assert 'private-canary' not in json.dumps([result, documents(harness)])
    harness.worker.assert_not_called()
    harness.leases[0].finish.assert_called_once()
    harness.leases[0].release.assert_called_once()


@pytest.mark.parametrize('interrupt', [False, True])
def test_first_callback_failure_survives_cleanup_and_close_failures(harness, monkeypatch, interrupt):
    harness.worker.side_effect = KeyboardInterrupt('private-canary') if interrupt else RuntimeError('private-canary')
    factory = execution.system.Lease
    def broken(*args, **kwargs):
        lease = factory(*args, **kwargs)
        lease.finish.side_effect = RuntimeError('private-canary-cleanup')
        return lease
    monkeypatch.setattr(execution.system, 'Lease', broken)
    harness.source.close.side_effect = RuntimeError('private-canary-close')
    result = run(harness)
    assert result['outcome'] == 'failed'
    assert result['first_failure']['code'] == ('worker-interrupted' if interrupt else 'worker-execution-failed')
    harness.leases[0].release.assert_called_once()
    assert result['outcomes']['cleanup']['outcome'] == 'failed'
    assert 'private-canary' not in json.dumps(documents(harness))


@pytest.mark.parametrize('boundary', ['close', 'report', 'verify', 'collector-close', 'release', 'host'])
def test_late_failure_revokes_earlier_acceptance(harness, monkeypatch, boundary):
    if boundary == 'close': harness.source.close.side_effect = RuntimeError('private-canary')
    elif boundary == 'host': harness.fingerprint.side_effect = ['host-before', 'host-before', 'changed']
    elif boundary == 'release':
        factory = execution.system.Lease
        def broken(*args, **kwargs):
            lease = factory(*args, **kwargs)
            release = lease.release.side_effect
            def fail():
                release()
                raise RuntimeError('private-canary')
            lease.release.side_effect = fail
            return lease
        monkeypatch.setattr(execution.system, 'Lease', broken)
    else:
        collect = execution.PrivateCollector
        def broken(**kwargs):
            collector = collect(**kwargs)
            if boundary == 'report':
                save = collector.save_report
                def fail(name, value):
                    if value.get('event') == 'attempt-terminal-candidate':
                        raise OSError('private-canary')
                    return save(name, value)
                collector.save_report = fail
            elif boundary == 'verify':
                verify = collector.verify
                def fail(records):
                    if harness.leases and harness.leases[0].fd is None:
                        raise OSError('private-canary')
                    return verify(records)
                collector.verify = fail
            else:
                close = collector.close
                def fail():
                    close()
                    raise OSError('private-canary')
                collector.close = fail
            return collector
        monkeypatch.setattr(execution, 'PrivateCollector', broken)
    result = run(harness)
    assert result['outcome'] == 'failed'
    assert result['first_failure'] is not None
    harness.leases[0].release.assert_called_once()
    harness.source.close.assert_called_once()
    assert 'private-canary' not in json.dumps(result)


@pytest.mark.parametrize('mutation', ['missing-callback', 'no-records', 'no-worker', 'wrong-inputs'])
def test_declaration_or_worker_success_alone_cannot_pass(harness, mutation):
    kwargs = {}
    if mutation == 'missing-callback': harness.callback.write_text('E2E_CASES = {}\n')
    elif mutation == 'no-records': harness.callback.write_text("E2E_CASES = {'synthetic-smoke': lambda r, c: {'outcome': 'passed'}}\n")
    elif mutation == 'no-worker': harness.callback.write_text(CALLBACK.replace('    context.run_worker(observe=lambda: None, validate=lambda: None)\n', ''))
    else: kwargs['expected_inputs'] = {'source_sha256': 'changed'}
    result = run(harness, **kwargs)
    assert result['outcome'] == 'failed'
    assert result['acceptance_candidate'] is None
    harness.leases[0].finish.assert_called_once()
    harness.leases[0].release.assert_called_once()


@pytest.fixture
def public(harness, monkeypatch):
    # The fake controller belongs to this test checkout, including executable
    # copies used for local validation. Keep the production path guard intact.
    monkeypatch.setattr(execution.system.baseline.guest_contract, 'CHECKOUT', execution.ROOT)
    # Substitute this entry point's privilege check, preserving real ownership
    # metadata checks inside PrivateCollector and the rest of the process.
    monkeypatch.setattr(execution, 'os', SimpleNamespace(**(vars(execution.os) | {
        'geteuid': lambda: 0, 'getegid': lambda: 0, 'umask': Mock()})))
    # Substitute suite VM operations using this fixture's existing fake lease.
    # The real suite lifecycle is exercised with real locks in suite tests.
    def suite_factory(opener, *, verify_backing_bytes):
        suite = Mock(lease=None, backend_checked=False, credentials_checked=False,
                     commands=execution.Commands())
        def acquire(ledger):
            source, guestfs = opener()
            suite.lease = execution.system.Lease(source, suite.commands, Mock(),
                ledger=ledger, graphics_type='vnc', verify_backing_bytes=verify_backing_bytes)
            return source, guestfs, suite.lease
        suite.acquire.side_effect = acquire
        suite.prepare_case.side_effect = lambda *args, **kwargs: suite.lease.prepare()
        return suite
    monkeypatch.setattr(suite_lease, 'Suite', suite_factory)
    original = execution.attempt
    monkeypatch.setattr(execution, 'attempt',
        lambda plan, case, **kwargs: original(plan, case, root=harness.root, **kwargs))
    return harness


def test_public_main_runs_selected_callback_and_emits_post_close_result(public, capsys):
    assert public.runner['main'](['--artifacts=' + public.plan['artifacts']]) == 0
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result['outcome'] == 'passed'
    assert result['expected_cases'] == [public.case['case_id']]
    assert result['attempts'][0]['case_id'] == public.case['case_id']
    assert result['attempts'][0]['outcome'] == 'passed'
    assert all(c._fd is None for c in public.collectors)
    assert 'private-canary' not in json.dumps(result)


@pytest.mark.parametrize('failure', ['action', 'preparation', 'terminal-write', 'collector-close'])
def test_public_failure_is_terminal_and_retains_original_attempt(public, monkeypatch, capsys, failure):
    if failure == 'action': public.worker.side_effect = RuntimeError('private-canary')
    elif failure == 'preparation': execution.preflight_source.side_effect = RuntimeError('private-canary')
    else:
        collect = execution.PrivateCollector
        def broken(**kwargs):
            collector = collect(**kwargs)
            if kwargs['run_id'].startswith('invocation-'):
                if failure == 'terminal-write':
                    save = collector.save_report
                    def fail(name, value):
                        if name == 'invocation-terminal-candidate':
                            raise OSError('private-canary')
                        return save(name, value)
                    collector.save_report = fail
                else:
                    close = collector.close
                    def fail():
                        close()
                        raise OSError('private-canary')
                    collector.close = fail
            return collector
        monkeypatch.setattr(execution, 'PrivateCollector', broken)
    assert public.runner['main'](['--artifacts=' + public.plan['artifacts']]) == 1
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result['outcome'] == 'failed'
    assert result['attempts'][0]['outcome'] == (
        'failed' if failure in ('action', 'preparation') else 'passed')
    assert 'private-canary' not in json.dumps(result)
    if failure != 'terminal-write':
        terminal = json.loads((public.collectors[0].path / 'invocation-terminal-candidate.json').read_text())
        assert terminal['outcome'] == ('passed' if failure == 'collector-close' else 'failed')


@pytest.mark.parametrize('failure', [None, 1])
def test_ready_cases_use_independent_attempts_and_stop_after_first_failure(public, monkeypatch, capsys, failure):
    plan = copy.deepcopy(public.plan)
    plan.update(scope='partial', ready_only=True, excluded_pending_cases=['E2E-004/pending'])
    plan['cases'] = [dict(public.case, case_id=f'E2E-00{i}/synthetic') for i in range(1, 4)]
    results = [dict(case_id=c['case_id'], outcome='failed' if i == failure else 'passed',
                    inputs={'source_sha256': 'frozen'}) for i, c in enumerate(plan['cases'])]
    execute = Mock(side_effect=results)
    monkeypatch.setattr(execution, 'attempt', execute)
    assert execution.main(plan) == (0 if failure is None else 1)
    output = capsys.readouterr().out.splitlines()
    result = json.loads(output[-1])
    events = [json.loads(line.removeprefix('ONPC-TEST-EVENT '))
              for line in output if line.startswith('ONPC-TEST-EVENT ')]
    assert events[0] == dict(kind='collection', total=3,
                             nodeids=[case['case_id'] for case in plan['cases']])
    assert [event['nodeid'] for event in events if event['kind'] == 'finished'] == [
        case['case_id'] for case in plan['cases'][:3 if failure is None else 2]]
    assert [event['nodeid'] for event in events if event['kind'] == 'failure'] == (
        [] if failure is None else [plan['cases'][failure]['case_id']])
    assert len(result['expected_cases']) == 3
    assert len(result['attempts']) == (3 if failure is None else 2)
    assert result['scope'] == 'partial' and result['ready_only'] is True
    assert result['excluded_pending_cases'] == ['E2E-004/pending']
    assert execute.call_args_list[0].kwargs['expected_inputs'] is None
    assert execute.call_args_list[1].kwargs['expected_inputs'] == results[0]['inputs']


@pytest.mark.parametrize('failure', [None, 'case', 'audit'])
def test_suite_candidates_require_final_audit_before_invocation_acceptance(
        public, monkeypatch, capsys, failure):
    plan = copy.deepcopy(public.plan)
    plan['cases'] = [dict(public.case, case_id=f'E2E-00{i}/synthetic') for i in range(1, 4)]
    suite = Mock(lease=None)
    if failure == 'audit':
        suite.close.side_effect = RuntimeError('private-canary')
    factory = Mock(return_value=suite)
    monkeypatch.setattr(suite_lease, 'Suite', factory)
    def attempt(plan, case, **kwargs):
        assert kwargs['suite'] is suite
        suite.close.assert_not_called()
        return {'case_id': case['case_id'], 'inputs': {'source_sha256': 'frozen'},
                'outcome': 'failed' if failure == 'case' else 'passed'}
    execute = Mock(side_effect=attempt)
    monkeypatch.setattr(execution, 'attempt', execute)
    assert execution.main(plan) == (0 if failure is None else 1)
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    suite.close.assert_called_once()
    assert execute.call_count == (1 if failure == 'case' else 3)
    assert result['suite_cleanup']['outcome'] == ('failed' if failure == 'audit' else 'passed')
    assert result['outcome'] == ('passed' if failure is None else 'failed')
    assert 'private-canary' not in json.dumps(result)


@pytest.mark.parametrize('fault', ['digest', 'symlink', 'edited-while-loading'])
def test_callback_refuses_changed_or_replaced_frozen_code(harness, fault):
    marker = harness.root / 'callback-ran'
    harness.callback.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n" + CALLBACK)
    verified = SimpleNamespace(root=harness.root, recheck=Mock(), source_files={
        'tests/e2e/synthetic.py': hashlib.sha256(harness.callback.read_bytes()).hexdigest()})
    if fault == 'digest': verified.source_files['tests/e2e/synthetic.py'] = '0' * 64
    elif fault == 'symlink':
        original = harness.root / 'original.py'
        harness.callback.rename(original)
        harness.callback.symlink_to(original)
    else:
        verified.recheck.side_effect = RuntimeError('provenance:source-changed')
    with pytest.raises((ValueError, RuntimeError)):
        execution.load_callback(harness.case, verified)
    assert not marker.exists()


def test_independent_connections_share_one_event_loop(monkeypatch):
    api, guestfs, thread = Mock(), Mock(), Mock()
    monkeypatch.setattr(execution.importlib, 'import_module',
                        lambda name: api if name == 'libvirt' else guestfs)
    monkeypatch.setattr(execution.threading, 'Thread', thread)
    connections = [Mock(), Mock()]
    factory = Mock(side_effect=connections)
    monkeypatch.setattr(execution.system.baseline, 'LibvirtSource', factory)
    execution.event_api.cache_clear()
    try:
        assert execution.open_source() == (connections[0], guestfs)
        assert execution.open_source() == (connections[1], guestfs)
        api.virEventRegisterDefaultImpl.assert_called_once()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()
        assert factory.call_count == 2
    finally:
        execution.event_api.cache_clear()


@pytest.mark.parametrize('uid,gid', [(1000, 1000), (0, 1000), (1000, 0)])
def test_unprivileged_entry_refuses_before_artifacts_or_vm(monkeypatch, uid, gid):
    monkeypatch.setattr(execution, 'os', SimpleNamespace(geteuid=lambda: uid, getegid=lambda: gid))
    collector, source = Mock(), Mock()
    monkeypatch.setattr(execution, 'PrivateCollector', collector)
    monkeypatch.setattr(execution, 'open_source', source)
    with pytest.raises(ValueError, match='root-required'):
        execution.main({})
    collector.assert_not_called()
    source.assert_not_called()
