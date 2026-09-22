"""Terminal loss must not restart an aggregate or lose its final status."""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

import regression_session as session
import test_activity
import test_retention
import regression
import regression_process
import test_commands


def test_supervised_progress_is_forwarded_without_log_frames(tmp_path, monkeypatch):
    run = tmp_path / 'runner'
    destination = tmp_path / 'supervisor'
    run.mkdir()
    destination.mkdir()
    (run / 'output').write_text('runner log\n')
    (run / 'frame.json').write_text(json.dumps(['Overall - 0%']))
    (run / 'result').write_text('0')
    monkeypatch.setenv(session.FRAME_DIRECTORY, str(destination))
    monkeypatch.setattr(session, 'busy', lambda _: True)

    def advance(_):
        assert json.loads((destination / 'frame.json').read_text()) == ['Overall - 0%']
        monkeypatch.setattr(session, 'busy', lambda _: False)

    monkeypatch.setattr(session.time, 'sleep', advance)
    output = io.StringIO()
    assert session.follow(run, output) == 0
    assert output.getvalue() == 'runner log\n'
    assert json.loads((destination / 'frame.json').read_text()) == []


@pytest.mark.parametrize('chunk_size', [1, 7, 65536])
def test_cleanup_frames_survive_pipes_without_scrollback(tmp_path, chunk_size):
    wire = io.StringIO()
    sender = regression_process.PipeFrameOutput(wire)
    frames = [
        ['Cleanup safety prerequisites — collecting', 'Overall - ?% (0/?)'],
        ['Cleanup — café [Running] (18/1503)', 'Overall - 1% (18/1503)'],
    ]
    for frame in frames:
        sender.frame(frame)
    sender.write('final cleanup summary\n')
    sender.write('diagnostic without newline')
    output = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
    stream = session.SessionOutput(tmp_path, output)
    observed = []
    publish = stream.frame

    def record(lines):
        publish(lines)
        observed.append(json.loads((tmp_path / 'frame.json').read_text()))

    stream.frame = record
    reader = regression_process.PipeFrameReader(stream)
    payload = wire.getvalue().encode()
    for offset in range(0, len(payload), chunk_size):
        reader(payload[offset:offset + chunk_size])
    reader.finish()
    assert observed == [*frames, []]
    assert output.buffer.getvalue() == b'final cleanup summary\ndiagnostic without newline'


@pytest.mark.parametrize('detached', [False, True])
@pytest.mark.parametrize('relay', [False, True])
def test_cleanup_child_publishes_session_frame_and_keeps_final_output(
        tmp_path, monkeypatch, detached, relay):
    output = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
    monkeypatch.setattr(sys, 'stdout', session.SessionOutput(tmp_path, output) if detached else output)
    script = (
        'import sys; from regression_process import PipeFrameOutput; '
        'out = PipeFrameOutput(sys.stdout); '
        'out.frame(["Cleanup safety prerequisites", "Overall - 1% (18/1503)"]); '
        'out.write("final cleanup summary\\n"); out.flush()'
    )
    if relay:
        script = (
            'import os, sys; from regression_process import Control; '
            'control = Control(); control.pipe = True; '
            f'sys.exit(control.run([sys.executable, "-B", "-c", {script!r}], '
            'cwd=os.getcwd(), env=os.environ))'
        )
    status = regression_process.Control().run(
        [sys.executable, '-B', '-c', script], cwd=tmp_path,
        env=os.environ | {'PYTHONPATH': str(Path(regression_process.__file__).parent)})
    assert status == 0
    if detached:
        assert json.loads((tmp_path / 'frame.json').read_text()) == []
    else:
        assert not (tmp_path / 'frame.json').exists()
    assert output.buffer.getvalue() == b'final cleanup summary\n'


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


def test_idle_empty_argv_starts_all_aggregate(tmp_path, workers):
    run, started = session.select(tmp_path, [])
    assert started
    current = json.loads((tmp_path / 'artifacts/test-sessions/current.json').read_text())
    assert current['argv'] == ['all']
    wait_for(tmp_path / 'arguments')
    assert (tmp_path / 'arguments').read_text() == 'all'
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


def test_host_and_vm_sessions_start_and_reconnect_independently(tmp_path, workers, monkeypatch):
    monkeypatch.setattr(test_commands, 'validate',
                        lambda root, argv: [(argv[0], argv[1:])])

    host_run, host_started = session.select(tmp_path, ['ui'])
    vm_run, vm_started = session.select(tmp_path, ['e2e'])

    assert host_started and vm_started
    assert host_run.parent == tmp_path / 'artifacts/test-sessions-host'
    assert vm_run.parent == tmp_path / 'artifacts/test-sessions'
    assert session.select(tmp_path, ['ui']) == (host_run, False)
    assert session.select(tmp_path, ['e2e']) == (vm_run, False)
    assert len(workers) == 2
    (tmp_path / 'release').touch()
    assert session.follow(host_run, io.StringIO()) == 7
    assert session.follow(vm_run, io.StringIO()) == 7


@pytest.mark.parametrize(('argv', 'expected'), [
    ([], False),
    (['ui'], True),
    (['ui', '-m', 'e2e'], True),
    (['unit', '-q'], True),
    (['host'], True),
    (['host', 'system'], False),
    (['system', 'host'], False),
    (['e2e'], False),
    (['integration', 'check_future'], False),
    (['--stop-on-error'], False),
    (['--stop-on-error', 'host'], True),
    (['--stop-on-error', 'host', 'e2e'], False),
])
def test_request_scope_is_known_before_session_attachment(argv, expected):
    assert test_commands.host_only_request(argv) is expected


@pytest.mark.parametrize('category, expected', [('ui', 0), ('unit', 0), ('host', 0),
                                              ('system', 2), ('e2e', 2), ('all', 2)])
def test_snapshot_probe_can_overlap_only_host_session(tmp_path, workers, monkeypatch,
                                                      category, expected):
    from contextlib import nullcontext
    from unittest.mock import Mock
    import prepare_appsnapshot

    monkeypatch.setattr(test_commands, 'validate', lambda root, argv: [(argv[0], [])])
    run, started = session.select(tmp_path, [category])
    assert started
    wait_for(tmp_path / 'child-ready')
    monkeypatch.setattr(prepare_appsnapshot, '__file__',
                        str(tmp_path / 'tools/prepare_appsnapshot.py'))
    check = Mock()
    monkeypatch.setattr(prepare_appsnapshot, 'check', check)
    cleanup = Mock(return_value=0)
    monkeypatch.setattr(prepare_appsnapshot, 'cleanup', cleanup)
    control = Mock()
    control.installed.return_value = nullcontext(control)
    control.stopped.is_set.return_value = False
    control.run.return_value = 0
    monkeypatch.setattr(prepare_appsnapshot, 'Control', lambda: control)
    assert prepare_appsnapshot.main(['--overwrite', 'false']) == expected
    assert cleanup.call_count == int(expected == 0)
    assert control.run.call_count == 2 * int(expected == 0)
    assert check.call_count == int(expected == 0)
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


@pytest.mark.parametrize('argv', [['--help'], ['-h'], ['--list']])
def test_inspection_prints_without_starting_a_session(tmp_path, workers, capsys, argv):
    assert session.select(tmp_path, argv) == (None, False)
    assert workers == []
    assert not (tmp_path / 'artifacts/test-sessions/current.json').exists()
    assert session.main(tmp_path, argv) == 0
    output = capsys.readouterr().out
    if argv == ['--list']:
        assert json.loads(output) == test_commands.suite_inventory()
    else:
        assert output == test_commands.usage() + '\n'
        assert 'host and e2e' in output
    assert workers == []


@pytest.mark.parametrize('argv', [['--help'], ['-h'], ['--list'],
                                  ['unit', '--collect-only'], ['e2e', '--list']])
@pytest.mark.parametrize('state', ['active', 'unread'])
def test_inspection_preserves_existing_session(
        tmp_path, workers, monkeypatch, capsys, argv, state):
    run, _ = session.select(tmp_path, ['all'])
    wait_for(tmp_path / 'started')
    if state == 'unread':
        (tmp_path / 'release').touch()
        assert workers[0].wait(timeout=10) == 7
        (run / 'result').write_text('0')
    current = tmp_path / 'artifacts/test-sessions/current.json'
    before = current.read_bytes()

    def refuse(*args, **kwargs):
        pytest.fail('help must not acquire session locks or follow a run')

    monkeypatch.setattr(session, 'lock', refuse)
    monkeypatch.setattr(session, 'follow', refuse)
    execute = Mock(return_value=0)
    monkeypatch.setattr(test_commands, '_main', execute)
    assert session.main(tmp_path, argv) == 0
    execute.assert_called_once_with(argv)
    assert current.read_bytes() == before
    assert not (run / 'delivered').exists()
    assert not (run / 'cancel').exists()
    assert len(workers) == 1
    if state == 'active':
        assert workers[0].poll() is None


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
    # No new selection still replays a completed detached run. An explicit
    # selection may replace an idle failed owner without an extra attach step.
    assert session.select(tmp_path, []) == (run, False)
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
    replacement = ['unit', '--invalid'] if test_commands.host_only_request(argv) else [
        'e2e', '--invalid']
    for replacement in ([replacement] if test_commands.host_only_request(argv)
                        else [replacement, []]):
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
    assert session.main(tmp_path, ['unit', '--invalid']) == 130
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
    replacement = ['unit', '--invalid'] if test_commands.host_only_request([category]) else [
        'e2e', '--invalid']
    run, started = session.select(tmp_path, replacement)
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


@pytest.mark.parametrize('result', [None, '1', '130'])
def test_explicit_selection_replaces_idle_failed_owner_without_erasing_output(tmp_path, workers, result):
    directory = session.prepare(tmp_path, host_only=True)
    old = directory / ('a' * 32)
    old.mkdir(mode=0o700)
    (old / 'output').write_text('failed evidence')
    if result is not None:
        (old / 'result').write_text(result)
    (directory / 'current.json').write_text(json.dumps({'run': old.name, 'argv': ['all']}))
    run, started = session.select(tmp_path, ['unit'])
    assert started and run != old
    assert (old / 'output').read_text() == 'failed evidence'
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


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
