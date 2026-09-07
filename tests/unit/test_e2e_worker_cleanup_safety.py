"""Host-only worker ownership, interruption and failure-retention regressions."""

import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
import e2e_worker as runtime
sys.path.pop(0)
sys.path.insert(0, str(ROOT / 'tests/integration'))
import system_runner
sys.path.pop(0)


@pytest.fixture
def attempt(tmp_path, monkeypatch):
    directory = tmp_path / 'work'
    directory.mkdir(mode=0o700)
    reports = tmp_path / 'reports'
    reports.mkdir(mode=0o700)
    real_collector = runtime.PrivateCollector
    collector = real_collector(run_id='worker-' + 'a' * 32, secrets=[], parent=reports)
    monkeypatch.setattr(runtime, 'PrivateCollector', lambda **kwargs: collector)
    events = []
    adapter = Mock()
    worker = Mock()
    worker.poll.return_value = 0
    worker.close.side_effect = lambda: events.append('worker-close')
    server = Mock(path=directory / 'callback.sock')
    server.close.side_effect = lambda: events.append('server-close')
    monkeypatch.setattr(runtime, 'Adapter', Mock(return_value=adapter))
    monkeypatch.setattr(runtime, 'CallbackServer', Mock(return_value=server))
    monkeypatch.setattr(runtime, 'Worker', Mock(return_value=worker))
    original_save = collector.save_report
    def save(name, data):
        events.append(name)
        return original_save(name, data)
    monkeypatch.setattr(collector, 'save_report', save)
    prefix = runtime.DISTRIBUTION.relative_to(ROOT).as_posix() + '/'
    inputs = {prefix + name: hashlib.sha256(data).hexdigest()
              for name, data in runtime.distribution_inputs().items()}
    ledger = system_runner.RunLedger()
    options = dict(expected_inputs=inputs, observe=Mock(), validate=Mock())
    lease = Mock(state={'run': 'a' * 32})
    def run(**changes):
        return runtime.run_distribution(directory, lease, ledger, **{**options, **changes})
    yield Mock(run=run, directory=directory, collector=collector, events=events,
               adapter=adapter, worker=worker, server=server, options=options,
               ledger=ledger, lease=lease)
    collector.close()


def report(attempt, name='worker-result'):
    return json.loads((attempt.collector.path / (name + '.json')).read_text())


def test_completed_worker_requires_controller_validation_and_owned_cleanup(attempt):
    result = attempt.run()
    attempt.options['validate'].assert_called_once_with()
    attempt.adapter.revalidate.assert_called_once_with()
    assert attempt.events == ['worker-before-cleanup', 'worker-close', 'server-close', 'worker-result']
    assert result['outcome'] == 'passed'
    assert result['worker_stopped'] and result['callback_closed']
    assert report(attempt, 'worker-before-cleanup')['worker_stopped'] is False
    assert report(attempt)['scope'] == 'credential-free-worker'
    assert runtime.Worker.call_args.args[-1] == list(runtime.COMMAND)


@pytest.mark.parametrize('hook_fails', [False, True])
def test_scenario_failure_hook_precedes_worker_cleanup_and_cannot_prevent_it(attempt, hook_fails):
    original = KeyboardInterrupt('private-canary')
    attempt.worker.poll.side_effect = original
    seen = []
    def checkpoint(category, code):
        seen.append((category, code))
        attempt.events.append('scenario-failure')
        if hook_fails:
            raise OSError('private-canary-report')
    with pytest.raises(KeyboardInterrupt) as caught:
        attempt.run(on_failure=checkpoint)
    assert caught.value is original
    assert seen == [('infrastructure', 'worker-interrupted')]
    assert attempt.events.index('scenario-failure') < attempt.events.index('worker-close')
    attempt.worker.close.assert_called_once()
    attempt.server.close.assert_called_once()
    final = report(attempt)
    assert final['first_failure']['code'] == 'worker-interrupted'
    assert ('scenario-checkpoint-failed' in [f['code'] for f in final['failures']]) == hook_fails


@pytest.mark.parametrize('boundary', ['spawn', 'poll', 'callback', 'observe', 'validate', 'guard'])
@pytest.mark.parametrize('interrupt', [False, True])
def test_failure_is_persisted_before_cleanup_without_raw_exception(attempt, boundary, interrupt):
    error = KeyboardInterrupt('private-canary') if interrupt else RuntimeError('private-canary')
    if boundary == 'spawn':
        runtime.Worker.side_effect = error
    elif boundary == 'guard':
        attempt.adapter.revalidate.side_effect = error
    elif boundary == 'poll':
        attempt.worker.poll.side_effect = error
    elif boundary == 'validate':
        attempt.options['validate'].side_effect = error
    else:
        attempt.worker.poll.return_value = None
        (attempt.server.serve_once if boundary == 'callback'
         else attempt.options['observe']).side_effect = error
    with pytest.raises(type(error)) as caught:
        attempt.run()
    assert caught.value is error
    original = report(attempt, 'worker-before-cleanup')
    final = report(attempt)
    assert original['first_failure'] == final['first_failure']
    assert original['first_failure']['category'] == 'infrastructure'
    assert original['first_failure']['code'] == ('worker-interrupted' if interrupt else 'worker-execution-failed')
    assert attempt.events[0] == 'worker-before-cleanup'
    assert attempt.events[-2:] == ['server-close', 'worker-result']
    assert 'private-canary' not in json.dumps(final)
    assert final['outcome'] == 'failed'
    if boundary == 'spawn':
        attempt.worker.close.assert_not_called()
    else:
        attempt.worker.close.assert_called_once()


@pytest.mark.parametrize('failed_resource', ['worker', 'server', 'both'])
@pytest.mark.parametrize('original_failure', [False, True])
def test_cleanup_failure_never_skips_other_owner_or_overwrites_original(attempt, failed_resource, original_failure):
    initial = ValueError('original private-canary')
    if original_failure:
        attempt.worker.poll.side_effect = initial
    if failed_resource in ('worker', 'both'):
        attempt.worker.close.side_effect = RuntimeError('private worker error')
    if failed_resource in ('server', 'both'):
        attempt.server.close.side_effect = RuntimeError('private callback error')
    with pytest.raises(ValueError if original_failure else RuntimeError) as caught:
        attempt.run()
    if original_failure:
        assert caught.value is initial
    attempt.worker.close.assert_called_once()
    attempt.server.close.assert_called_once()
    result = report(attempt)
    assert result['first_failure']['category'] == ('infrastructure' if original_failure else 'cleanup')
    assert result['outcome'] == 'failed'
    assert attempt.ledger.outcomes['cleanup']['outcome'] == 'failed'
    assert result['worker_stopped'] is (failed_resource == 'server')
    assert result['callback_closed'] is (failed_resource == 'worker')


@pytest.mark.parametrize('which', ['worker-before-cleanup', 'worker-result', 'both'])
def test_report_write_failure_cannot_prevent_cleanup_or_return_success(attempt, monkeypatch, which):
    original_save = attempt.collector.save_report
    def save(name, data):
        if name == which or which == 'both':
            raise OSError('private disk error')
        return original_save(name, data)
    monkeypatch.setattr(attempt.collector, 'save_report', save)
    with pytest.raises(OSError):
        attempt.run()
    attempt.worker.close.assert_called_once()
    attempt.server.close.assert_called_once()
    assert attempt.ledger.outcomes['collection']['outcome'] == 'failed'
    if which == 'worker-before-cleanup':
        assert report(attempt)['first_failure']['category'] == 'collection'


def test_identity_replacement_refuses_more_input_but_closes_recorded_worker(attempt):
    attempt.worker.poll.return_value = None
    attempt.adapter.revalidate.side_effect = [None, RuntimeError('replacement')]
    with pytest.raises(RuntimeError, match='replacement'):
        attempt.run()
    attempt.server.serve_once.assert_called_once()
    attempt.options['observe'].assert_called_once()
    attempt.worker.close.assert_called_once()
    attempt.lease.stop.assert_not_called()  # outer lease remains sole VM owner


def test_timeout_refuses_and_cleans_up(attempt, monkeypatch):
    ticks = iter(range(100))
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: next(ticks))
    attempt.worker.poll.return_value = None
    with pytest.raises(RuntimeError, match='deadline'):
        attempt.run(timeout=1)
    attempt.worker.close.assert_called_once()
    attempt.server.close.assert_called_once()
    attempt.options['validate'].assert_not_called()


@pytest.mark.parametrize('status', [1, -1, 124])
def test_nonzero_worker_status_never_reaches_validation(attempt, status):
    attempt.worker.poll.return_value = status
    with pytest.raises(RuntimeError, match='backend-failed'):
        attempt.run()
    attempt.options['validate'].assert_not_called()


def test_refused_lease_never_creates_callback_or_worker(attempt):
    runtime.Adapter.side_effect = RuntimeError('unprepared-lease')
    with pytest.raises(RuntimeError, match='unprepared-lease'):
        attempt.run()
    runtime.CallbackServer.assert_not_called()
    runtime.Worker.assert_not_called()
    assert not list(attempt.directory.iterdir())


@pytest.mark.parametrize('change', ['digest', 'missing', 'additional'])
def test_changed_distribution_refused_before_worker_or_callback(attempt, change):
    inputs = dict(attempt.options['expected_inputs'])
    key = next(iter(inputs))
    if change == 'digest':
        inputs[key] = '0' * 64
    elif change == 'missing':
        del inputs[key]
    else:
        inputs[key + '.pm'] = '0' * 64
    with pytest.raises(RuntimeError, match='distribution-inputs-changed'):
        attempt.run(expected_inputs=inputs)
    runtime.CallbackServer.assert_not_called()
    runtime.Worker.assert_not_called()
    assert not (attempt.directory / 'distribution').exists()


def test_unsafe_worker_directory_refuses_before_lease_or_spawn(attempt):
    attempt.directory.chmod(0o755)
    with pytest.raises(RuntimeError, match='private-directory'):
        attempt.run()
    runtime.Adapter.assert_not_called()
    runtime.Worker.assert_not_called()


def test_vars_cannot_be_overwritten_or_exported_as_reviewed_evidence(attempt):
    path = attempt.directory / 'vars.json'
    path.write_text('private-canary')
    with pytest.raises(FileExistsError):
        attempt.run()
    runtime.Worker.assert_not_called()
    assert path.read_text() == 'private-canary'
    assert all(p.suffix == '.json' for p in attempt.collector.path.iterdir())
    assert 'private-canary' not in json.dumps(report(attempt))
