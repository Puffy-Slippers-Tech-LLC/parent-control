"""Qualification rotation and explicit legacy cleanup fail closed."""

import json
import os
from contextlib import contextmanager, nullcontext
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
            (path / 'evidence').write_text('diagnostics')
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
    monkeypatch.setattr(storage, 'os', SimpleNamespace(geteuid=lambda: 0, environ=os.environ))
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(umask=lambda _: None))
    # This legacy rotation check owns only storage. Actual finalized producer
    # and publication chains are exercised below with a shared private checkout.
    monkeypatch.setattr(storage, '_capture', lambda *args, **kwargs: nullcontext())
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
def captured_qualification(tmp_path, monkeypatch):
    """Real capture/publication owners; no VM, process, display or service."""
    from tools import evidence_capture, runner_evidence, test_storage
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
    monkeypatch.setattr(storage, '_target', lambda: os.environ.get('ONPC_TEST_VM', ''))
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid:
        test_storage.directory('state') / ('retention-1000' +
            ('-' + os.environ['ONPC_TEST_VM'] if 'ONPC_TEST_VM' in os.environ else '')))
    monkeypatch.setattr(evidence_capture, '_authenticated_caller',
                        lambda: dict(uid=os.geteuid(), gid=os.getegid()))
    monkeypatch.setattr(evidence_capture, 'validate_targets', lambda checkout, targets: None)
    monkeypatch.setattr(runner_evidence.regression_inputs, 'identity', lambda root: 'f' * 64)
    monkeypatch.setattr(storage.runpy, 'run_path', lambda path: {'retention_guard': lambda root: None})
    captures = []
    finish = storage._Producer.finish
    def record(producer, error):
        finish(producer, error)
        if producer.evidence is not None:
            captures.append(producer.evidence._result)
    monkeypatch.setattr(storage._Producer, 'finish', record)
    return SimpleNamespace(root=root, captures=captures, runner=runner_evidence,
                           state=test_storage.directory('state'))


def _originals(capture):
    return {member['original_path']: member for member in capture['records'][-1]['members']}


def _archived(environment, capture, path):
    member = _originals(capture)[str(path)]
    reference = next(item for item in capture['references'] if item['member_id'] == member['member_id'])
    return environment.runner.resolve_reference(environment.root, reference)


def test_named_standalone_and_reused_qualification_preserve_original_verdict_and_collector(
        captured_qualification, monkeypatch):
    env = captured_qualification
    from private_artifacts import PrivateCollector
    for target in ('target-a', 'target-b'):
        monkeypatch.setenv('ONPC_TEST_VM', target)
        outer = retention.Store(env.state / ('outer-' + target))
        with outer.session():
            token = retention.token()
            with storage.session(check='standalone-fixture', inputs={'selector': target}):
                work = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-qualification-fixture-'))
                (work / 'result.json').write_bytes(b'{"outcome":"failed"}\n')
                (work / 'results.tap').write_bytes(b'TAP version 13\n1..1\nnot ok 1 - original\n')
                (work / 'results.xml').write_bytes(b'<testsuite failures="1"/>\n')
                (work / 'ssh-key').write_bytes(b'transport credential excluded')
                with PrivateCollector(run_id='qualification-fixture', secrets=[]) as collector:
                    storage.start_collector(collector)
                    proof = collector.save_report('original', {'outcome': 'failed'})
                storage.finish_collector(collector, {'outcome': 'failed'}, cleanup='complete')
                assert retention.token() == token
            saved = env.captures[-1]
            terminal = saved['records'][-1]
            assert terminal['context']['target'] == target
            assert terminal['context']['check'] == 'standalone-fixture'
            assert terminal['status'] == 'failed'
            assert terminal['cleanup']['state'] == 'complete'
            assert str(work / 'ssh-key') not in _originals(saved)
            assert _archived(env, saved, work / 'result.json') == b'{"outcome":"failed"}\n'
            assert _archived(env, saved, proof) == Path(proof).read_bytes()
            assert {'junit', 'tap', 'input', 'command', 'cleanup'} <= {
                member['role'] for member in terminal['members']}


def test_actual_recovery_failure_records_survive_rotation_without_clearing_vm_obligation(
        captured_qualification, monkeypatch):
    import check_graphical_recovery as recovery
    env = captured_qualification
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(umask=lambda _: None))
    def missing_runtime(_):
        raise RuntimeError('private injected recovery failure')
    monkeypatch.setattr(recovery, 'importlib', SimpleNamespace(import_module=missing_runtime))
    vm_store = retention.Store(env.state / 'retention-1000')
    with vm_store.session():
        retention.preserve_for_recovery()
    before = (vm_store.path / 'current.json').read_bytes()
    paths = []
    for index in range(5):
        assert recovery.recover('vnc') == 1
        capture = env.captures[-1]
        record = capture['records'][-1]
        assert record['context']['target'] == ''
        assert record['context']['check'] == 'check_graphical_recovery'
        assert record['status'] == 'diagnostic' and record['completeness'] == 'partial'
        path = next(Path(member['original_path']) for member in record['members']
                    if Path(member['original_path']).name == 'result.json')
        paths.append(path)
        if index == 0:
            first = capture
            original = path.read_bytes()
    assert not paths[0].exists() and paths[-1].is_file()
    assert _archived(env, first, paths[0]) == original
    assert json.loads(original)['outcome'] == 'failed'
    assert (vm_store.path / 'current.json').read_bytes() == before
    assert (vm_store.path / 'recovery-required').is_file()


def test_public_recovery_preserves_pending_diagnostic_before_starting_next_run(
        captured_qualification, monkeypatch):
    import check_graphical_recovery as recovery
    env = captured_qualification
    monkeypatch.chdir(env.root)
    monkeypatch.setattr(recovery.sys, 'argv', ['check_graphical_recovery'])
    monkeypatch.setattr(recovery.runner, 'ROOT', env.root)
    monkeypatch.setattr(recovery.runner.baseline.guest_contract, 'CHECKOUT', env.root)
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(
        geteuid=lambda: 0, getegid=lambda: 0, umask=lambda _: None))
    def missing_runtime(_):
        raise RuntimeError('private injected recovery failure')
    monkeypatch.setattr(recovery, 'importlib', SimpleNamespace(import_module=missing_runtime))
    vm_store = retention.Store(env.state / 'retention-1000')
    with vm_store.session():
        retention.preserve_for_recovery()
    before = (vm_store.path / 'current.json').read_bytes()
    diagnostics = retention.Store(env.state / 'recovery-diagnostics-1000')
    with diagnostics.session():
        producer = storage._Producer(diagnostics, 'check_graphical_recovery', '',
                                     {}, True, None, False)
        work = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-recovery-lost-'))
        producer.start(work)
        proof = work / 'result.json'
        original = b'{"outcome":"failed","category":"original-interruption"}\n'
        proof.write_bytes(original)
        # The real named producer writes under its restrictive scoped umask.
        proof.chmod(0o600)
        # Simulate process loss before the named wrapper can finalize its guard.
        del producer
    recovered = []
    recover_pending = storage.recover_pending
    def observe_pending(root, store):
        records = recover_pending(root, store)
        recovered.extend(records)
        return records
    monkeypatch.setattr(storage, 'recover_pending', observe_pending)
    for _ in range(4):
        assert recovery.main() == 1
    assert len(recovered) == 1
    record = recovered[0]['records'][-1]
    assert record['context']['check'] == 'check_graphical_recovery'
    assert record['context']['workflow'] == 'recovery-diagnostics'
    assert record['status'] == 'interrupted'
    assert record['completeness'] == 'partial'
    assert not proof.exists()
    assert _archived(env, recovered[0], proof) == original
    assert (vm_store.path / 'current.json').read_bytes() == before
    assert (vm_store.path / 'recovery-required').is_file()
    with diagnostics.opened() as fd, diagnostics.locked(fd, 'writer.lock', shared=True):
        state = diagnostics.read(fd)
        assert all(charge.get('acknowledgement') for entry in [state, *state['history']]
                   for charge in entry.get('captures', []))


@pytest.fixture
def diagnostic_guest(captured_qualification, monkeypatch):
    import vm_probe
    import ui_observations
    import kiosk_entry
    lease = SimpleNamespace(state={'run': 'a' * 32, 'phase': 'started'},
                            commands=SimpleNamespace(directory=None, sequence=0),
                            guard=lambda **kwargs: None)
    observations = []
    class Observer:
        boot_proof = 'b' * 64
        boot_guard = ''
        def __init__(self, transport):
            pass
        def observe(self, name):
            observations.append(name)
            (lease.commands.directory / 'command-0001.txt').write_bytes(b'original command output\x00\n')
            return dict(fallback='guarded', operation=name, outcome='observed')
    def connect(selected):
        assert selected is lease
        (lease.commands.directory / 'ssh-key').write_bytes(b'excluded transport credential')
        return SimpleNamespace(reboot=lambda: None)
    monkeypatch.setattr(vm_probe, 'connect', connect)
    monkeypatch.setattr(vm_probe, 'operation', lambda *args: nullcontext())
    monkeypatch.setattr(ui_observations, 'UiObservations', Observer)
    monkeypatch.setattr(kiosk_entry, 'enter_station', lambda *args, **kwargs: (
        kwargs['on_input'](1, 2) if 'on_input' in kwargs else None) or 1)
    monkeypatch.setattr(vm_probe, 'clock_calibration', lambda *args: (1, 2))
    monkeypatch.setattr(vm_probe, 'startup_latency', lambda *args: {'witness': 'painted'})
    monkeypatch.setattr(vm_probe, 'logout_identity', lambda *args: {})
    monkeypatch.setattr(vm_probe, 'logout_latency', lambda *args: {})
    import time
    monkeypatch.setattr(time, 'sleep', lambda seconds: None)
    @contextmanager
    def native(*args):
        yield
        directory = args[-1]
        (directory / 'native-log-result.json').write_bytes(b'{"outcome":"captured","records":0}\n')
    monkeypatch.setattr(vm_probe, 'kiosk_native_evidence', native)
    monkeypatch.setenv('ONPC_TEST_VM', 'target-a')
    return SimpleNamespace(env=captured_qualification, probe=vm_probe, lease=lease,
                           observations=observations, observer=Observer)


@pytest.mark.parametrize('producer', [
    'reproduce_kiosk_refusal', 'probe_kiosk_latency', 'probe_kiosk_prompt_latency',
    'probe_kiosk_approval', 'probe_revoke_balances', 'probe_retained_app_launch',
    'probe_riley_native_grid', 'probe_remembered_return', 'probe_transfer_refusal',
    'probe_lock_curtain', 'reproduce_denial', 'prepare_maintenance_transport',
])
def test_actual_finite_vm_probe_producers_capture_original_records_with_live_cleanup_scope(
        diagnostic_guest, monkeypatch, producer):
    guest = diagnostic_guest
    probe, lease, env = guest.probe, guest.lease, guest.env
    options = {}
    args = [lease]
    if producer in ('probe_kiosk_latency', 'probe_kiosk_prompt_latency'):
        options['samples'] = 1
    if producer == 'probe_kiosk_prompt_latency':
        monkeypatch.setattr(probe, 'reproduce_denial', lambda *args: None)
    if producer == 'reproduce_denial':
        import fixture_credentials
        import observation_transport
        import e2e_worker
        class Credentials:
            def provision_online(self, *args):
                pass
        class Journey:
            def __init__(self, context, progress):
                self.steps, self.failed = [], False
                self.plan = SimpleNamespace(stages=('boundary',))
        monkeypatch.setattr(fixture_credentials, 'FixtureCredentials', Credentials)
        monkeypatch.setattr(observation_transport, 'ReadOnlyObservations', lambda transport: None)
        def worker(directory, selected, ledger, **kwargs):
            (directory / 'boundary.request.json').write_text(json.dumps({'stage': 'boundary', 'screenshot': None}))
            (directory / 'observations.jsonl').write_bytes(b'{"stage":"private-prefix","observed":{}}\n')
            assert kwargs['guarded_observe'](lambda: None) is True
            return dict(worker_stopped=True, callback_closed=True)
        monkeypatch.setattr(e2e_worker, 'run_distribution', worker)
        args += [Journey, None, 'boundary', 'private-fixture']
    elif producer == 'prepare_maintenance_transport':
        import online_snapshot
        monkeypatch.setitem(sys.modules, 'guestfs', SimpleNamespace())
        def bootstrap(commands, selected, directory, guestfs, **kwargs):
            (directory / 'command-0001.txt').write_bytes(b'bootstrap original\n')
            (directory / 'ssh-key').write_bytes(b'excluded transport credential')
            return 'public-host-key'
        monkeypatch.setattr(probe.system, 'bootstrap', bootstrap)
        monkeypatch.setattr(online_snapshot, 'publish_maintenance', lambda *args: None)
    getattr(probe, producer)(*args, **options)
    captured = env.captures[-1]
    record = captured['records'][-1]
    assert record['context']['check'] == producer
    assert record['context']['target'] == 'target-a'
    assert record['status'] == 'diagnostic' and record['completeness'] == 'partial'
    assert record['cleanup']['state'] == 'pending'
    assert record['cleanup']['scope']['resources'] == [
        dict(kind='maintenance-vm', id='a' * 32, disposition='preserved')]
    originals = _originals(captured)
    assert not any(Path(path).name in ('ssh-key', 'known-hosts') for path in originals)
    assert any(member['role'] in ('result', 'diagnostic') for member in record['members'])
    for path in originals:
        assert _archived(env, captured, path) == Path(path).read_bytes()


@pytest.mark.parametrize('failure', [RuntimeError, KeyboardInterrupt])
def test_partial_vm_probe_failure_excludes_raw_command_and_preserves_nonpassing_status(
        diagnostic_guest, monkeypatch, failure):
    guest = diagnostic_guest
    def observe(observer, name):
        (guest.lease.commands.directory / 'command-0001.txt').write_bytes(b'partial original\n')
        raise failure('original observer failure')
    monkeypatch.setattr(guest.observer, 'observe', observe)
    with pytest.raises(failure, match='original observer failure'):
        guest.probe.probe_revoke_balances(guest.lease)
    saved = guest.env.captures[-1]
    record = saved['records'][-1]
    assert record['status'] == 'diagnostic' and record['cleanup']['state'] == 'pending'
    assert not any(Path(path).name == 'command-0001.txt' for path in _originals(saved))
    assert (guest.lease.commands.directory / 'command-0001.txt').read_bytes() == b'partial original\n'


def test_qualification_command_ledger_keeps_invocations_without_input_or_output(
        captured_qualification):
    from owned_commands import Commands
    env = captured_qualification
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
    capture = env.captures[-1]
    original = _archived(env, capture, work / 'producer-commands.jsonl')
    records = [json.loads(line) for line in original.splitlines()]
    assert [item['phase'] for item in records] == ['start', 'end', 'start', 'end']
    assert [item['sequence'] for item in records] == [1, 2, 3, 4]
    assert [item['exit_status'] for item in records] == [None, 0, None, 7]
    assert all(item['timeout'] == 30 for item in records)
    assert records[-1]['check'] is False
    assert records[1]['argv'][0] == sys.executable
    assert len(capture['records']) == 2  # Startup plus one aggregate, not per command.
    for path in _originals(capture):
        assert secret not in _archived(env, capture, path)
    command = next(member for member in capture['records'][-1]['members']
                   if member['role'] == 'command' and member['original_path'] != str(work / 'producer-commands.jsonl'))
    payload = json.loads(_archived(env, capture, command['original_path']))
    assert [item['exit_status'] for item in payload['commands']] == [0, 7]


def test_smoke_collector_lost_objects_recover_exact_proof_then_survive_rotation(
        captured_qualification):
    import check_graphical_smoke as smoke
    from private_artifacts import PrivateCollector
    env = captured_qualification
    store = retention.Store(env.state / 'retention-host')
    with store.session():
        # A hard stop skips the qualification wrapper's finish entirely. Only
        # its already persisted lifecycle/checkpoints may recover the originals.
        producer = storage._Producer(store, 'check_graphical_smoke', '', {}, False, None, False)
        token = storage._producer.set(producer)
        try:
            work = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-smoke-lost-'))
            with PrivateCollector(run_id='smoke-lost-owner', secrets=[]) as collector:
                storage.start_collector(collector)
                media = collector.add('approved-screen', 'screen', b'original approved pixels', reviewed=True)
                result = dict(outcome='failed', scope='private-smoke-fixture')
                controller = smoke.Qualification(work, None, smoke.runner.RunLedger(),
                    collector, result, None)
                controller.checkpoint('before-hard-stop')
                paths = {collector.path / media['path']: b'original approved pixels'}
                paths.update({collector.path / name: (collector.path / name).read_bytes()
                              for name in collector._reports})
        finally:
            storage._producer.reset(token)
        del producer, collector, controller
    recovered = env.runner.recover_pending(env.root, store)
    assert recovered
    # The collector's recovered record has a truthful interruption/partial
    # status and the original bytes, independently of a terminal wrapper.
    terminal = next(item for item in recovered
                    if item['records'][-1]['context']['workflow'] == 'e2e')
    record = terminal['records'][-1]
    assert record['status'] == 'interrupted' and record['cleanup']['state'] == 'pending'
    references = {member['original_path']: next(reference for reference in terminal['references']
                  if reference['member_id'] == member['member_id']) for member in record['members']}
    for index in range(4):
        with store.session():
            pass
    for path, data in paths.items():
        assert not path.exists()
        assert env.runner.resolve_reference(env.root, references[str(path)]) == data


@pytest.mark.parametrize('lost_wrapper', [False, True])
def test_actual_denial_worker_secret_staging_never_exports_credentials_or_raw_captures(
        diagnostic_guest, monkeypatch, lost_wrapper):
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
    original_finish = storage._Producer.finish
    if lost_wrapper:
        monkeypatch.setattr(storage._Producer, 'finish', lambda *args: None)
    guest.probe.reproduce_denial(lease, Journey, None, 'boundary', 'secret-fixture')
    assert len(staged) == 1
    store = retention.Store(env.state / 'recovery-diagnostics-1000-target-a')
    if lost_wrapper:
        monkeypatch.setattr(storage._Producer, 'finish', original_finish)
        captures = env.runner.recover_pending(env.root, store)
        assert captures and captures[-1]['records'][-1]['status'] == 'interrupted'
    else:
        captures = [env.captures[-1]]
    forbidden = {'vars.json', 'parent.password', 'autoinst-log.txt',
                 'command-0001.txt', 'raw.png', 'result-smoke.json'}
    for capture in captures:
        originals = _originals(capture)
        assert not any(Path(path).name in forbidden for path in originals)
        for path in originals:
            assert canary.encode() not in _archived(env, capture, path)
    for index in range(4):
        with storage.recovery_session(check='later-secret-diagnostic'):
            directory = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-later-secret-'))
            (directory / 'result.json').write_text('{"purpose":"diagnostic-only"}')
    assert not staged[0].exists()
    for capture in captures:
        for path in _originals(capture):
            assert canary.encode() not in _archived(env, capture, path)


def test_denied_diagnostic_publication_preserves_registered_source_and_never_retries(
        diagnostic_guest, monkeypatch):
    guest = diagnostic_guest
    from tools import evidence_bundle
    calls = []
    def denied(*args, **kwargs):
        calls.append(1)
        raise PermissionError('private helper denied')
    monkeypatch.setattr(evidence_bundle, 'export', denied)
    with pytest.raises(PermissionError, match='helper denied'):
        guest.probe.probe_lock_curtain(guest.lease)
    assert calls == [1]
    assert (guest.lease.commands.directory / 'command-0001.txt').is_file()
    state = json.loads((guest.env.state / 'recovery-diagnostics-1000-target-a/current.json').read_bytes())
    assert state['captures'] and all(not item.get('acknowledgement') for item in state['captures'])


def test_actual_baseline_failure_tail_and_availability_survive_later_diagnostic_rotation(
        captured_qualification):
    import baseline_guest
    env = captured_qualification
    log = b'old excluded prefix\n' + b'x' * 16384
    guest = SimpleNamespace(exists=lambda path: True, is_symlink=lambda path: False,
        realpath=lambda path: path,
        lstatns=lambda path: dict(st_mode=0o100600, st_uid=0, st_nlink=1),
        filesize=lambda path: len(log), pread=lambda path, count, offset: log[offset:offset + count])
    message = baseline_guest.preparation_failure(guest, attempt='c' * 32)
    assert message.startswith('no-stage; artifact:')
    original = Path(message.split('; artifact:', 1)[1])
    first = env.captures[-1]
    record = first['records'][-1]
    assert record['context']['check'] == 'baseline_guest.preparation_failure'
    assert record['status'] == 'diagnostic' and record['cleanup']['state'] == 'pending'
    assert record['cleanup']['scope']['resources'] == [
        dict(kind='baseline-preparation', id='c' * 32, disposition='preserved')]
    availability = original.parent / 'native-log-result.json'
    expected = availability.read_bytes()
    for index in range(4):
        with storage.recovery_session(check='later-baseline-diagnostic'):
            path = Path(storage.allocate(tempfile.mkdtemp, prefix='onpc-baseline-fixture-'))
            (path / 'result.json').write_bytes(b'{"purpose":"diagnostic-only"}\n')
    assert not original.exists()
    assert _archived(env, first, original) == log[-16384:]
    assert _archived(env, first, availability) == expected
    assert json.loads(expected)['may_be_truncated'] is True


def test_later_recovery_links_preserved_live_scene_without_promoting_diagnostic(
        diagnostic_guest, monkeypatch):
    import check_graphical_recovery as recovery
    guest = diagnostic_guest
    guest.probe.probe_lock_curtain(guest.lease)
    before = guest.env.captures[-1]
    saved = before['records'][-1]
    original_attempt = saved['cleanup']['scope']['resources'][0]['id']
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
    after = guest.env.captures[-1]
    record = after['records'][-1]
    assert record['record_id'] != saved['record_id']
    assert record['cleanup']['state'] == 'complete'
    assert record['cleanup']['scope']['resources'] == [
        dict(kind='maintenance-vm', id=original_attempt, disposition='cleaned')]
    assert record['status'] == saved['status'] == 'diagnostic'
    assert saved['cleanup']['state'] == 'pending'
    result = next(path for path in _originals(after) if Path(path).name == 'result.json')
    assert json.loads(_archived(guest.env, after, result))['recovered_attempt'] == original_attempt


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
