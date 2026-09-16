"""Terminal loss must not restart an aggregate or lose its final status."""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import pytest

import regression_session as session
import test_activity
import test_retention
import regression
import test_commands


@pytest.fixture
def workers(tmp_path, monkeypatch):
    children = []
    spawn = subprocess.Popen
    checkout = Path(__file__).resolve().parents[2]

    def launch(command, **kwargs):
        command[3] = str(checkout / 'tests/support/regression_session_worker.py')
        kwargs['env']['PYTHONPATH'] = str(checkout / 'tools')
        child = spawn(command, **kwargs)
        children.append(child)
        return child

    # Isolate from the unit launcher's inherited checkout activity identity.
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    monkeypatch.setattr(test_activity, '_descriptor', None)
    monkeypatch.setattr(session.subprocess, 'Popen', launch)
    monkeypatch.setattr(test_commands, 'validate', lambda root, argv: None)
    yield children
    (tmp_path / 'release').touch()
    for child in children:
        child.wait(timeout=20)


def test_continue_on_errors_survives_detach_and_ignores_new_arguments(tmp_path, workers):
    run, started = session.select(tmp_path, ['all', '--continue-on-errors'])
    assert started
    wait_for(tmp_path / 'arguments')
    assert (tmp_path / 'arguments').read_text() == 'all --continue-on-errors'
    assert session.select(tmp_path, ['all', '--continue-on-errors']) == (run, False)
    assert session.select(tmp_path, ['all']) == (run, False)
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


def wait_for(path):
    deadline = time.monotonic() + 10
    while not path.exists():
        assert time.monotonic() < deadline, f'timed out waiting for {path.name}'
        time.sleep(0.02)


def test_lost_terminal_reconnects_and_preserves_summary_status(tmp_path, workers):
    run, started = session.select(tmp_path, ['all-verify'])
    assert started
    wait_for(tmp_path / 'started')
    assert os.getsid(workers[0].pid) == workers[0].pid

    class ClosedTerminal(io.StringIO):
        def write(self, value):
            raise BrokenPipeError('terminal closed')

    with pytest.raises(BrokenPipeError):
        session.follow(run, ClosedTerminal())
    assert workers[0].poll() is None
    assert session.select(tmp_path, ['all-verify']) == (run, False)
    assert session.select(tmp_path, ['all']) == (run, False)
    with pytest.raises(ValueError, match='another test launcher'):
        with test_activity.activity(tmp_path):
            pass
    (tmp_path / 'release').touch()
    assert workers[0].wait(timeout=10) == 7
    # Completion while detached must still replay, rather than start over.
    assert session.select(tmp_path, ['all-verify']) == (run, False)
    output = io.StringIO()
    assert session.follow(run, output) == 7
    assert 'usual final summary' in output.getvalue()
    assert len(workers) == 1
    next_run, started = session.select(tmp_path, ['all'])
    assert started and next_run != run


def test_concurrent_reconnections_share_one_worker(tmp_path, workers):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: session.select(tmp_path, ['all']), range(2)))
    assert results[0][0] == results[1][0]
    assert sorted(result[1] for result in results) == [False, True]
    assert len(workers) == 1


@pytest.mark.parametrize('argv', [[category, '--test-option'] for category in test_commands.CATEGORIES])
def test_every_category_preserves_arguments_and_reconnects_before_validation(
        tmp_path, workers, monkeypatch, argv):
    run, started = session.select(tmp_path, argv)
    assert started
    wait_for(tmp_path / 'arguments')
    assert (tmp_path / 'arguments').read_text() == ' '.join(argv)
    def refuse(*_):
        pytest.fail('new arguments must not be validated during attachment')
    monkeypatch.setattr(test_commands, 'validate', refuse)
    for replacement in ([], ['--help'], ['--list'], ['unknown', '--invalid'], ['e2e', '--list']):
        assert session.select(tmp_path, replacement) == (run, False)
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7
    assert len(workers) == 1


def test_attach_warns_and_ctrl_c_cancels_real_nonaggregate_child(tmp_path, workers, monkeypatch, capsys):
    run, _ = session.select(tmp_path, ['traceability', 'stage'])
    wait_for(tmp_path / 'child-ready')
    follow = session.follow
    def interrupt(run):
        signal.raise_signal(signal.SIGINT)
        return follow(run)
    monkeypatch.setattr(session, 'follow', interrupt)
    assert session.main(tmp_path, ['unknown', '--invalid']) == 130
    output = capsys.readouterr()
    assert 'WARNING: A previous run is in the background' in output.err
    assert 'ignoring all new arguments and attaching to it' in output.err
    assert 'owned cleanup finished' in output.out
    assert workers[0].wait(timeout=10) == 130


def test_reconnected_terminal_cancellation_reaches_owner(tmp_path, workers):
    run, _ = session.select(tmp_path, ['all'])
    wait_for(tmp_path / 'started')
    assert session.select(tmp_path, ['all']) == (run, False)
    (run / 'cancel').touch()
    output = io.StringIO()
    assert session.follow(run, output) == 130
    assert 'owned cleanup finished' in output.getvalue()
    assert workers[0].wait(timeout=10) == 130


@pytest.mark.parametrize('category', ['all-verify', 'traceability'])
def test_observer_hangup_leaves_reconnectable_worker(tmp_path, workers, category):
    observer = os.fork()
    if observer == 0:
        try:
            session.select(tmp_path, [category])
            signal.signal(signal.SIGHUP, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGHUP)
        finally:
            os._exit(2)
    _, status = os.waitpid(observer, 0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGHUP
    wait_for(tmp_path / 'started')
    run, started = session.select(tmp_path, ['ignored'])
    assert not started
    assert workers == []  # This observer never launched a replacement worker.
    (tmp_path / 'release').touch()
    output = io.StringIO()
    assert session.follow(run, output) == 7
    assert 'usual final summary' in output.getvalue()


def test_dead_owner_is_incomplete_not_a_fabricated_pass(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('partial progress\n')
    output = io.StringIO()
    assert session.follow(run, output) == 1
    assert 'incomplete' in output.getvalue()


def test_legacy_activity_refuses_duplicate_without_starting_worker(tmp_path, workers):
    # Hold an independent file description, as an older running launcher does.
    with test_activity.activity(tmp_path):
        descriptor = test_activity._descriptor
        test_activity._descriptor = None
        try:
            with pytest.raises(ValueError, match='another test launcher'):
                session.select(tmp_path, ['all'])
        finally:
            test_activity._descriptor = descriptor
    assert workers == []


@pytest.mark.parametrize('change', ['none', 'passed-gate', 'started-suite', 'missing-progress',
                                  'extra-allocation', 'schedule', 'no-activity', 'parallel-cleanup'])
def test_initial_check_recovery_requires_proven_pre_suite_stop(tmp_path, monkeypatch, change):
    monkeypatch.delenv(test_activity.VARIABLE, raising=False)
    monkeypatch.setattr(test_activity, '_descriptor', None)
    report = tmp_path / 'docs/TestAutomation/Evidence/test-all-runs/old'
    report.mkdir(parents=True, mode=0o700)
    progress = [dict(name=name, state=state, done=0, failures=0, started=None)
                for name, state in [('Discovery and prerequisites', 'Passed'),
                                    ('Cleanup safety prerequisites', 'Running'),
                                    ('Unit and contracts', 'Pending')]]
    if change == 'passed-gate':
        progress[1]['state'] = 'Passed'
    if change == 'started-suite':
        progress[2]['state'] = 'Running'
    if change == 'parallel-cleanup':
        progress[1].update(name='Cleanup — fixture_cleanup_safety', phase='cleanup')
    if change != 'missing-progress':
        (report / 'progress.json').write_text(json.dumps(progress))
    if change == 'schedule':
        (report / 'schedule.jsonl').touch()
    store = test_retention.Store(tmp_path / 'state')
    with store.session():
        test_retention.retain(report)
        if change == 'extra-allocation':
            extra = tmp_path / 'extra'
            extra.mkdir(mode=0o700)
            test_retention.retain(extra)
    state = json.loads((store.path / 'current.json').read_text())
    state['finished'] = False
    (store.path / 'current.json').write_text(json.dumps(state))
    with test_activity.activity(tmp_path):
        if change == 'no-activity':
            monkeypatch.setattr(test_activity, 'descriptors', lambda: ())
        def start():
            with store.session(recover=lambda old: regression.recover_initial_checks(tmp_path, old)):
                pass
        if change == 'none':
            start()
            assert (store.path / f'interrupted-{state["run"]}.json').exists()
        else:
            with pytest.raises(ValueError, match='previous owner did not finish'):
                start()
        assert report.exists()
