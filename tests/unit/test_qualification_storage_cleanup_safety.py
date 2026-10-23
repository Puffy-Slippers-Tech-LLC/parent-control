"""Qualification rotation and explicit legacy cleanup fail closed."""

import json
import os
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import pytest

import qualification_storage as storage
import check_tmp_storage_cleanup as legacy
from tools import test_retention as retention


def test_standalone_qualifications_rotate_both_work_and_collector(tmp_path, monkeypatch):
    from tools import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'registry')
    store = retention.Store(tmp_path / 'registry')
    monkeypatch.setattr(storage.test_retention, 'Store', lambda path: store)
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    monkeypatch.setattr(storage, 'os', SimpleNamespace(geteuid=lambda: 0, environ=os.environ))
    # Exercise the real ownership/audit operations as the test user.
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    guards = []
    monkeypatch.setattr(storage.runpy, 'run_path', lambda path: {
        'retention_guard': lambda root: guards.append(root)})
    runs = []
    @storage.session()
    def qualify(fail=False):
        from private_artifacts import PrivateCollector
        work = Path(storage.allocate(tempfile.mkdtemp, dir=tmp_path))
        with PrivateCollector(run_id='qualification-test', secrets=[], parent=tmp_path) as collector:
            paths = [work, collector.path]
        for path in paths:
            (path / 'diagnostic.txt').write_text('diagnostics')
        runs.append(paths)
        if fail:
            raise RuntimeError('qualification failed')
        return 7
    for index in range(5):
        if index == 1:
            with pytest.raises(RuntimeError):
                qualify(True)
        else:
            assert qualify() == 7
        assert all(path.exists() for pair in runs[-3:] for path in pair)
        assert all(not path.exists() for pair in runs[:-3] for path in pair)
    assert len(guards) == 10


def test_nested_qualification_joins_existing_run(tmp_path, monkeypatch):
    with retention.Store(tmp_path / 'registry').session() as token:
        @storage.session()
        def qualify():
            assert retention.token() == token
            return storage.allocate(tempfile.mkdtemp, dir=tmp_path)
        path = qualify()
    state = json.loads((tmp_path / 'registry/current.json').read_text())
    assert [record['path'] for record in state['paths']] == [path]


def test_recovery_diagnostics_rotate_without_changing_unfinished_vm_journal(tmp_path, monkeypatch):
    import check_graphical_recovery as recovery
    from tools import test_storage
    monkeypatch.setattr(test_storage, 'ROOT', tmp_path)
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'retention-1000-guest')
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.setattr(storage, 'os', SimpleNamespace(**{**vars(os), 'geteuid': lambda: 0}))
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(umask=lambda _: None))
    def missing_runtime(_):
        raise RuntimeError('injected recovery failure')
    monkeypatch.setattr(recovery, 'importlib', SimpleNamespace(import_module=missing_runtime))
    vm_store = retention.Store(tmp_path / 'retention-1000-guest')
    with vm_store.session():
        retention.preserve_for_recovery()
    original = (vm_store.path / 'current.json').read_bytes()
    journal = tmp_path / 'recovery-diagnostics-1000-guest/current.json'
    paths = []
    for index in range(5):
        with storage.recovery_session():
            assert recovery.recover('vnc') == 1
        state = json.loads(journal.read_text())
        paths.append(Path(state['paths'][0]['path']))
        assert all((path / 'result.json').is_file() for path in paths[-3:])
        assert all(not path.exists() for path in paths[:-3])
        assert (vm_store.path / 'current.json').read_bytes() == original
        assert (vm_store.path / 'recovery-required').exists()
        if index == 0:
            # Abrupt termination of the diagnostic writer is independently
            # recoverable; it never clears the VM's recovery obligation.
            state['finished'] = False
            journal.write_text(json.dumps(state))


@pytest.fixture
def qualification_environment(tmp_path, monkeypatch):
    """Real private storage owners; no VM, display or service."""
    from tools import evidence_bundle, runner_evidence, test_storage
    root = tmp_path / 'checkout'
    root.mkdir(mode=0o700)
    monkeypatch.setattr(test_storage, 'ROOT', root)
    monkeypatch.setattr(test_storage, 'BASE', root / 'output/test-runs')
    monkeypatch.setattr(storage, 'ROOT', root)
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    monkeypatch.delenv(retention.OWNER_VARIABLE, raising=False)
    monkeypatch.delenv('ONPC_RUNNER_INVOCATION', raising=False)
    monkeypatch.delenv('ONPC_TEST_VM', raising=False)
    monkeypatch.setattr(storage, 'os', SimpleNamespace(**{**vars(os), 'geteuid': lambda: 0}))
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid:
        test_storage.directory('state') / ('retention-1000' +
            ('-' + os.environ['ONPC_TEST_VM'] if 'ONPC_TEST_VM' in os.environ else '')))
    monkeypatch.setattr(storage.runpy, 'run_path', lambda path: {'retention_guard': lambda root: None})
    def archive(*args, **kwargs):
        pytest.fail('current qualification must not require archival publication')
    monkeypatch.setattr(runner_evidence, 'ReportEvidence', archive)
    monkeypatch.setattr(runner_evidence, 'recover_pending', archive)
    monkeypatch.setattr(evidence_bundle, 'export', archive)
    return SimpleNamespace(root=root, state=test_storage.directory('state'))


def test_named_qualification_keeps_current_results_and_reuses_owner(qualification_environment):
    env = qualification_environment
    from private_artifacts import PrivateCollector
    outer = retention.Store(env.state / 'outer')
    with outer.session():
        token = retention.token()
        with storage.session(check='standalone-fixture', target='target-a',
                             inputs={'selector': 'one'}):
            work = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-qualification-fixture-'))
            original = b'{"outcome":"failed"}\n'
            (work / 'result.json').write_bytes(original)
            with PrivateCollector(run_id='qualification-fixture', secrets=[]) as collector:
                report = collector.save_report('original', {'outcome': 'failed'})
            assert retention.token() == token
        assert (work / 'result.json').read_bytes() == original
        assert json.loads(Path(report).read_bytes())['outcome'] == 'failed'
    state = json.loads((outer.path / 'current.json').read_bytes())
    assert {item['path'] for item in state['paths']} == {str(work), str(collector.path)}
    assert not state.get('captures')


@pytest.fixture
def diagnostic_guest(qualification_environment, monkeypatch):
    import vm_probe
    import ui_observations
    lease = SimpleNamespace(state={'run': 'a' * 32, 'phase': 'started'},
                            commands=SimpleNamespace(directory=None, sequence=0),
                            guard=lambda **kwargs: None)
    class Observer:
        def __init__(self, transport):
            pass
        def observe(self, name):
            (lease.commands.directory / 'command-0001.txt').write_bytes(b'original command output\x00\n')
            return dict(fallback='guarded', operation=name, outcome='observed')
    def connect(selected):
        assert selected is lease
        (lease.commands.directory / 'ssh-key').write_bytes(b'excluded transport credential')
        return SimpleNamespace(reboot=lambda: None)
    monkeypatch.setattr(vm_probe, 'connect', connect)
    monkeypatch.setattr(vm_probe, 'operation', lambda *args: nullcontext())
    monkeypatch.setattr(ui_observations, 'UiObservations', Observer)
    monkeypatch.setenv('ONPC_TEST_VM', 'target-a')
    return SimpleNamespace(env=qualification_environment, probe=vm_probe, lease=lease,
                           observer=Observer)


def test_actual_probe_keeps_current_observation_without_publication(diagnostic_guest):
    guest = diagnostic_guest
    guest.probe.probe_lock_curtain(guest.lease)
    directory = guest.lease.commands.directory.parent
    observed = json.loads((directory / 'observed.json').read_bytes())
    assert observed == dict(fallback='guarded', operation='child-lock-curtain', outcome='observed')
    assert (guest.lease.commands.directory / 'command-0001.txt').is_file()
    assert guest.lease.state == {'run': 'a' * 32, 'phase': 'started'}
    state = json.loads((guest.env.state / 'recovery-diagnostics-1000-target-a/current.json').read_bytes())
    assert not state.get('captures')


@pytest.mark.parametrize('failure', [RuntimeError, KeyboardInterrupt])
def test_partial_vm_probe_preserves_original_failure_and_private_diagnostics(
        diagnostic_guest, monkeypatch, failure):
    guest = diagnostic_guest
    def observe(observer, name):
        (guest.lease.commands.directory / 'command-0001.txt').write_bytes(b'partial original\n')
        raise failure('original observer failure')
    monkeypatch.setattr(guest.observer, 'observe', observe)
    with pytest.raises(failure, match='original observer failure'):
        guest.probe.probe_revoke_balances(guest.lease)
    assert (guest.lease.commands.directory / 'command-0001.txt').read_bytes() == b'partial original\n'


def test_qualification_command_ledger_keeps_invocations_without_input_or_output(
        qualification_environment):
    from owned_commands import Commands
    with storage.session(check='command-fixture'):
        work = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-command-fixture-'))
        commands = Commands()
        commands.directory = work
        secret = b'private-input-output-canary'
        assert commands.run([sys.executable, '-I', '-c',
            'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'],
            timeout=30, input=secret) == secret
        commands.run([sys.executable, '-I', '-c', 'raise SystemExit(7)'],
                     timeout=30, check=False)
        (work / 'result.json').write_text('{"outcome":"failed"}')
    original = (work / 'producer-commands.jsonl').read_bytes()
    records = [json.loads(line) for line in original.splitlines()]
    assert [item['phase'] for item in records] == ['start', 'end', 'start', 'end']
    assert [item['sequence'] for item in records] == [1, 2, 3, 4]
    assert [item['exit_status'] for item in records] == [None, 0, None, 7]
    assert all(item['timeout'] == 30 for item in records)
    assert records[-1]['check'] is False
    assert records[1]['argv'][0] == sys.executable
    assert secret not in original
    assert (work / 'producer-commands.jsonl').stat().st_mode & 0o777 == 0o600


def test_actual_denial_worker_secret_staging_never_exports_credentials_or_raw_captures(
        diagnostic_guest, monkeypatch):
    """Actual reproduce_denial -> run_distribution -> SecretVariables.stage."""
    import e2e_worker
    import fixture_credentials
    import observation_transport
    import vm_config
    guest = diagnostic_guest
    env, lease = guest.env, guest.lease
    canary = 'private-transport-secret-canary-427!'
    lease.state.update(phase='running', domain_id=1)
    lease.fd = 17
    monkeypatch.setattr(fixture_credentials, 'read_password', lambda: canary)
    def provision(credentials, selected, transport):
        credentials._lease, credentials._ready, credentials._online = selected, True, True
    monkeypatch.setattr(fixture_credentials.FixtureCredentials, 'provision_online', provision)
    monkeypatch.setattr(observation_transport, 'ReadOnlyObservations', lambda transport: None)
    monkeypatch.setattr(vm_config, 'selected', lambda: SimpleNamespace(name='target-a'))
    monkeypatch.setattr(e2e_worker, 'ROOT', env.root)
    monkeypatch.setattr(e2e_worker, 'DISTRIBUTION', env.root / 'tests/integration/graphical_smoke')
    monkeypatch.setattr(e2e_worker, 'stage_distribution', lambda *args: 'e' * 64)
    monkeypatch.setattr(e2e_worker, 'variables', lambda *args, **kwargs: {'BACKEND': 'generalhw'})
    monkeypatch.setattr(e2e_worker, 'Adapter', lambda *args, **kwargs:
                        SimpleNamespace(events=[], revalidate=lambda: None))
    monkeypatch.setattr(e2e_worker, 'CallbackServer', lambda adapter, directory:
        SimpleNamespace(path=directory / 'callback.sock', serve_once=lambda: None, close=lambda: None))
    staged = []
    def worker(directory, *args):
        # This reads the real exclusive SecretVariables.stage output. Raw
        # backend artifacts deliberately contain the same sentinel.
        assert json.loads((directory / 'vars.json').read_bytes())['_SECRET_ONPC_PARENT_PASSWORD'] == canary
        for name in ('parent.password', 'autoinst-log.txt', 'command-0001.txt', 'raw.png'):
            (directory / name).write_text(canary)
        (directory / 'testresults').mkdir(mode=0o700)
        (directory / 'testresults/result-smoke.json').write_text(json.dumps({'raw': canary}))
        (directory / 'boundary.request.json').write_text(json.dumps({'stage': 'boundary', 'screenshot': None}))
        staged.append(directory)
        return SimpleNamespace(poll=lambda: None, ready=True, result=None, close=lambda: None)
    monkeypatch.setattr(e2e_worker, 'Worker', worker)
    class Journey:
        def __init__(self, context, progress):
            self.steps, self.failed = [], False
            self.plan = SimpleNamespace(stages=('boundary',))
    guest.probe.reproduce_denial(lease, Journey, None, 'boundary', 'secret-fixture')
    assert len(staged) == 1
    store = retention.Store(env.state / 'recovery-diagnostics-1000-target-a')
    state = json.loads((store.path / 'current.json').read_bytes())
    assert not state.get('captures')
    forbidden = {'vars.json', 'parent.password', 'autoinst-log.txt',
                 'command-0001.txt', 'raw.png', 'result-smoke.json'}
    reports = [Path(item['path']) for item in state['paths'] if item['path'] != str(staged[0])]
    assert reports
    for directory in reports:
        for path in directory.iterdir():
            assert path.name not in forbidden
            assert canary.encode() not in path.read_bytes()
    for index in range(4):
        with storage.recovery_session(check='later-secret-diagnostic'):
            directory = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-later-secret-'))
            (directory / 'result.json').write_text('{"purpose":"diagnostic-only"}')
    assert not staged[0].exists()


def test_actual_baseline_failure_keeps_bounded_tail_then_rotates_normally(
        qualification_environment):
    import baseline_guest
    log = b'old excluded prefix\n' + b'x' * 16384
    guest = SimpleNamespace(exists=lambda path: True, is_symlink=lambda path: False,
        realpath=lambda path: path,
        lstatns=lambda path: dict(st_mode=0o100600, st_uid=0, st_nlink=1),
        filesize=lambda path: len(log), pread=lambda path, count, offset: log[offset:offset + count])
    message = baseline_guest.preparation_failure(guest, attempt='c' * 32)
    assert message.startswith('no-stage; artifact:')
    original = Path(message.split('; artifact:', 1)[1])
    assert original.read_bytes() == log[-16384:]
    availability = original.parent / 'native-log-result.json'
    expected = availability.read_bytes()
    for index in range(4):
        with storage.recovery_session(check='later-baseline-diagnostic'):
            path = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-baseline-fixture-'))
            (path / 'result.json').write_bytes(b'{"purpose":"diagnostic-only"}\n')
    assert not original.exists()
    assert json.loads(expected)['may_be_truncated'] is True


def test_later_recovery_reports_its_attempt_without_changing_original_observation(
        diagnostic_guest, monkeypatch):
    import check_graphical_recovery as recovery
    guest = diagnostic_guest
    guest.probe.probe_lock_curtain(guest.lease)
    original_observation = guest.lease.commands.directory.parent / 'observed.json'
    before = original_observation.read_bytes()
    original_attempt = guest.lease.state['run']
    source = SimpleNamespace(close=lambda: None)
    state = dict(run=original_attempt, phase='started')
    def clean():
        state['phase'] = 'restored'
    lease = SimpleNamespace(state=state, recover_graphical_cleanup=clean)
    api = SimpleNamespace(virEventRegisterDefaultImpl=lambda: None)
    monkeypatch.setattr(recovery, 'importlib', SimpleNamespace(import_module=lambda name:
        api if name == 'libvirt' else SimpleNamespace()))
    monkeypatch.setattr(recovery, 'threading', SimpleNamespace(Thread=lambda **kwargs:
        SimpleNamespace(start=lambda: None)))
    monkeypatch.setattr(recovery.runner.baseline, 'LibvirtSource', lambda api: source)
    monkeypatch.setattr(recovery.runner, 'Lease', lambda *args, **kwargs: lease)
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(umask=lambda _: None))
    assert recovery.recover('vnc') == 0
    state = json.loads((guest.env.state / 'recovery-diagnostics-1000-target-a/current.json').read_bytes())
    assert not state.get('captures')
    directory = Path(state['paths'][0]['path'])
    result = json.loads((directory / 'result.json').read_bytes())
    assert result['outcome'] == 'passed'
    assert result['recovered_attempt'] == original_attempt
    assert result['original_attempt_outcome'] == 'unchanged'
    assert original_observation.read_bytes() == before


@pytest.mark.parametrize('fault', ['path', 'identity', 'duplicate', 'mode', 'active', 'mount'])
def test_legacy_cleanup_audits_everything_before_removing(tmp_path, monkeypatch, fault):
    record = dict(path='/tmp/onpc-graphical-smoke-abcdefgh', device=1, inode=2, mode=0o700)
    records = [record, dict(record, path='/tmp/onpc-e2e-evidence-abcdefgh')]
    calls = []
    def remove(value, *, validate_only=False):
        calls.append(validate_only)
        if validate_only and value is records[-1] and fault in ('identity', 'mount'):
            raise ValueError(fault)
    monkeypatch.setattr(legacy.retention, 'remove', remove)
    if fault == 'path':
        records[-1]['path'] = '/tmp/unrelated'
    if fault == 'duplicate':
        records[-1] = record
    if fault == 'mode':
        records[-1]['mode'] = 0o755
    def guard(paths):
        if fault == 'active':
            raise ValueError('active')
    with pytest.raises(ValueError):
        legacy.cleanup(records, guard)
    assert not any(value is False for value in calls)


def test_legacy_cleanup_removes_only_explicit_identity_records(monkeypatch):
    records = [dict(path='/tmp/onpc-graphical-smoke-abcdefgh', device=1, inode=2, mode=0o700)]
    calls = []
    monkeypatch.setattr(legacy.retention, 'remove', lambda record, **kw: calls.append((record, kw)))
    legacy.cleanup(records, lambda paths: None)
    assert calls == [(records[0], {'validate_only': True}), (records[0], {})]
