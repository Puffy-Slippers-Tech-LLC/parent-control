"""Terminal loss must not restart an aggregate or lose its final status."""
from tests.support.vm_registry import vm_name

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
import test_storage


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


def test_identical_session_frames_do_not_replace_the_file(tmp_path):
    output = session.SessionOutput(tmp_path, io.StringIO())
    lines = ['Waiting for I/O pressure to recover']
    output.frame(lines)
    frame = tmp_path / 'frame.json'
    first = frame.stat()
    for _ in range(20):
        output.frame(list(lines))
    assert frame.stat() == first
    lines[0] = 'Running tests'
    output.frame(lines)
    assert json.loads(frame.read_text()) == lines
    output.frame([])
    assert json.loads(frame.read_text()) == []


@pytest.mark.parametrize('metadata,supervised', [
    ('frame.json', False), ('frame.json', True),
    ('controller.json', False), ('controller.json', True),
    ('test-controller.json', False)])
@pytest.mark.parametrize('fault', ['oversized', 'invalid', 'hardlink'])
def test_rejected_metadata_does_not_block_log_replay(tmp_path, metadata, fault, supervised):
    import detached_launcher
    from launcher_render import LauncherDisplay
    run = tmp_path / 'runner'
    run.mkdir()
    transcript = 'first log line\n' + 'x' * 70000 + '\nlast log line\n'
    (run / 'output').write_text(transcript)
    (run / 'result').write_text('0')
    (run / 'controller.json').write_text(json.dumps([
        dict(key='unit', lines=['Category: unit', 'Status: Running tests'])]))
    path = run / metadata
    path.write_text(' ' * 65537 if fault == 'oversized' else '{' if fault == 'invalid' else '[]')
    if fault == 'hardlink':
        os.link(path, run / 'alias')
    destination = tmp_path / 'supervisor' if supervised else None
    if destination is not None:
        destination.mkdir()
    output = io.StringIO()
    with LauncherDisplay(output) as display:
        assert detached_launcher.follow_output(
            run, output, display, label='fix-tests', test_session=True,
            destination=destination, owner_busy=lambda _: False) == 0
    assert transcript in output.getvalue()
    assert (run / 'delivered').exists()
    if destination is not None:
        assert not list(destination.iterdir())


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
    current = json.loads((tmp_path / 'output/test-runs/host/sessions/current.json').read_text())
    assert current['argv'] == ['all']
    wait_for(tmp_path / 'arguments')
    assert (tmp_path / 'arguments').read_text() == 'all'
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


def test_active_vm_session_refuses_missing_or_other_vm_before_cancellation(tmp_path, workers):
    vm_args = ['--vm', vm_name(1)]
    run, started = session.select(tmp_path, ['e2e', *vm_args])
    assert started
    for argv in (['--stop'], ['--stop', '--vm', vm_name()]):
        with pytest.raises(ValueError, match='original --vm NAME'):
            session.select(tmp_path, argv)
        assert not (run / 'cancel').exists()
    assert session.select(tmp_path, ['e2e', *vm_args]) == (run, False)
    assert len(workers) == 1
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


def test_active_vm_session_keeps_its_guest_when_configured_ids_swap(tmp_path, workers, monkeypatch):
    import vm_config
    config = tmp_path / 'test-vm.json'
    entries = [
        {'id': '17', 'name': 'first-guest', 'disk_anchor': '/first', 'enabled': 'true'},
        {'id': '83', 'name': 'second-guest', 'disk_anchor': '/second', 'enabled': 'true'}]
    config.write_text(json.dumps({'vms': entries}))
    monkeypatch.setattr(vm_config, 'CONFIG', config)
    run, started = session.select(tmp_path, ['e2e', '--vm', '17'])
    assert started
    current = json.loads((run.parent / 'current.json').read_text())
    assert current['argv'] == ['e2e', '--vm', 'first-guest']
    entries[0]['id'], entries[1]['id'] = entries[1]['id'], entries[0]['id']
    config.write_text(json.dumps({'vms': entries}))
    with pytest.raises(ValueError, match='original --vm NAME'):
        session.select(tmp_path, ['--stop', '--vm', '17'])
    assert not (run / 'cancel').exists()
    for selector in ('83', 'first-guest'):
        assert session.select(tmp_path, ['e2e', '--vm', selector]) == (run, False)
    assert len(workers) == 1


def test_explicit_vm_queue_reattaches_by_canonical_names_and_rejects_other_selection(
        tmp_path, workers, monkeypatch):
    import vm_config
    import vm_selection
    config = tmp_path / 'test-vm.json'
    entries = [dict(id=str(index + 1), name=f'guest-{index}', disk_anchor=f'/disk-{index}',
                    enabled='true' if index == 0 else 'false') for index in range(3)]
    config.write_text(json.dumps({'concurrency': 2, 'vms': entries}))
    monkeypatch.setattr(vm_config, 'CONFIG', config)
    vm_selection.execution_selection('2,1')
    run, started = session.select(tmp_path, ['e2e', '--vm', '2,1'])
    assert started
    current = json.loads((run.parent / 'current.json').read_text())
    assert current['argv'] == ['e2e', '--vm', 'guest-1,guest-0']
    assert current['vm_batch'] == {'concurrency': 2, 'vms': ['guest-1', 'guest-0']}
    for selector in ('2,1', 'guest-1,guest-0'):
        assert session.select(tmp_path, ['e2e', '--vm', selector]) == (run, False)
    for options in ([], ['--vm', '1'], ['--vm', 'all']):
        with pytest.raises(ValueError, match='original'):
            session.select(tmp_path, ['--stop', *options])
        assert not (run / 'cancel').exists()
    assert len(workers) == 1


@pytest.mark.parametrize('category', ['ui', 'e2e'])
def test_active_session_wins_within_its_scope_before_validation(tmp_path, workers, monkeypatch, category):
    monkeypatch.setattr(test_commands, 'validate',
                        lambda root, argv: [(argv[0], argv[1:])])
    run, started = session.select(tmp_path, [category])
    assert started
    def refuse(*_):
        pytest.fail('attachment must not validate or start another operation')
    monkeypatch.setattr(test_commands, 'validate', refuse)
    monkeypatch.setattr(test_activity, 'activity', refuse)
    requests = ([['ui'], ['--stop-on-error', 'unit']] if category == 'ui' else
                [[], ['e2e'], ['invalid']])
    for argv in requests:
        assert session.select(tmp_path, argv) == (run, False)
    assert len(workers) == 1
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


def test_host_run_does_not_consume_unread_vm_result(tmp_path, workers):
    vm_run, _ = session.select(tmp_path, ['e2e'])
    (tmp_path / 'release').touch()
    assert workers[0].wait(timeout=10) == 7
    (vm_run / 'result').write_text('0')
    (tmp_path / 'release').unlink()
    host_run, started = session.select(tmp_path, ['ui'])
    assert started
    assert session.select(tmp_path, ['ui']) == (host_run, False)
    assert session.select(tmp_path, []) == (vm_run, False)
    assert not (vm_run / 'delivered').exists()


@pytest.mark.parametrize(('argv', 'expected'), [
    ([], False),
    (['ui'], True),
    (['ui', '-m', 'e2e'], True),
    (['unit', '-q'], True),
    (['host'], True),
    (['vm'], False),
    (['host', 'vm'], False),
    (['vm', 'host'], False),
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
    assert prepare_appsnapshot.main(['--overwrite', 'false', '--vm', vm_name(), '--y']) == expected
    cleanup.assert_not_called()
    assert control.run.call_count == int(expected == 0)
    assert check.call_count == int(expected == 0)
    (tmp_path / 'release').touch()
    assert session.follow(run, io.StringIO()) == 7


@pytest.mark.parametrize('argv', [['--help'], ['-h'], ['--list']])
def test_inspection_prints_without_starting_a_session(tmp_path, workers, capsys, argv):
    assert session.select(tmp_path, argv) == (None, False)
    assert workers == []
    assert not (tmp_path / 'output/test-runs/host/sessions/current.json').exists()
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
@pytest.mark.parametrize('category', ['all', 'ui'])
def test_inspection_preserves_existing_session(
        tmp_path, workers, monkeypatch, capsys, argv, state, category):
    run, _ = session.select(tmp_path, [category])
    wait_for(tmp_path / 'started')
    if state == 'unread':
        (tmp_path / 'release').touch()
        assert workers[0].wait(timeout=10) == 7
        (run / 'result').write_text('0')
    current = run.parent / 'current.json'
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


def test_concurrent_host_and_vm_requests_start_independent_workers(tmp_path, workers):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda category: session.select(tmp_path, [category]), ['host', 'vm']))
    host_run, vm_run = (result[0] for result in results)
    assert host_run != vm_run
    assert all(started for _, started in results)
    assert len(workers) == 2
    assert session.select(tmp_path, ['host']) == (host_run, False)
    assert session.select(tmp_path, ['vm']) == (vm_run, False)
    assert session.select(tmp_path, ['host', '--stop']) == (host_run, False)
    assert session.follow(host_run, io.StringIO()) == 130
    assert not (vm_run / 'cancel').exists()
    assert session.current_session(vm_run.parent) == (vm_run, True)
    (tmp_path / 'release').touch()
    assert session.follow(vm_run, io.StringIO()) == 7


@pytest.mark.parametrize('category', ['all', 'all-verify'])
def test_complete_run_reserves_both_host_and_vm_scopes(tmp_path, workers, category):
    run, started = session.select(tmp_path, [category])
    assert started
    with pytest.raises(ValueError, match='another test launcher'):
        with test_activity.activity(tmp_path, host_only=True):
            pass
    with pytest.raises(ValueError, match='another test launcher'):
        with test_activity.activity(tmp_path, host_only=False):
            pass
    assert session.select(tmp_path, [category]) == (run, False)


def test_agent_owned_runs_register_before_spawn_and_clear_parent_from_tests(tmp_path, workers, monkeypatch):
    import fcntl
    import detached_launcher
    from test_storage import directory
    parent = directory('write-e2e', root=tmp_path) / ('a' * 32)
    parent.mkdir(mode=0o700)
    detached_launcher.atomic(parent.parent / 'current.json', {'run': parent.name})
    monkeypatch.setenv(detached_launcher.WORKFLOW_DIRECTORY, str(parent))
    spawn = session.subprocess.Popen

    def verify(command, **kwargs):
        entries = json.loads((parent / 'nested.json').read_text())
        assert entries[-1]['path'] == command[5]
        assert detached_launcher.WORKFLOW_DIRECTORY not in kwargs['env']
        return spawn(command, **kwargs)

    monkeypatch.setattr(session.subprocess, 'Popen', verify)
    with detached_launcher.lock(parent.parent / 'owner') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        run, started = session.select(tmp_path, ['unit'])
        assert started
        assert session.select(tmp_path, ['unit']) == (run, False)
        assert len(json.loads((parent / 'nested.json').read_text())) == 1
        (tmp_path / 'release').touch()
        assert session.follow(run, io.StringIO()) == 7


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


@pytest.mark.parametrize('category', ['ui', 'e2e'])
def test_stop_attaches_and_waits_for_owned_cleanup(tmp_path, workers, capsys, category):
    run, _ = session.select(tmp_path, [category])
    wait_for(tmp_path / 'child-ready')
    assert session.main(tmp_path, [category, '--stop']) == 130
    assert (run / 'cancel').exists()
    output = capsys.readouterr()
    assert 'owned cleanup finished' in output.out
    assert 'cancellation requested' in output.err
    assert len(workers) == 1
    assert workers[0].wait(timeout=10) == 130


@pytest.mark.parametrize('unread', [False, True])
def test_idle_stop_does_not_start_tests_or_consume_result(tmp_path, workers, capsys, unread):
    if unread:
        run, _ = session.select(tmp_path, ['ui'])
        (tmp_path / 'release').touch()
        assert workers[0].wait(timeout=10) == 7
    assert session.main(tmp_path, ['--stop']) == 0
    assert 'no active run to stop' in capsys.readouterr().err
    assert len(workers) == int(unread)
    if unread:
        assert not (run / 'delivered').exists()
        assert not (run / 'cancel').exists()


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


@pytest.mark.parametrize('batch', [False, True])
def test_host_restart_recovers_interrupted_session_and_test_retention(tmp_path, workers, batch):
    from vm_selection import execution_selection
    if batch:
        execution_selection()
    (tmp_path / 'recover-host').touch()
    directory = session.prepare(tmp_path, host_only=True)
    stores = [test_retention.Store(directory / 'retention'),
              test_retention.Store(test_storage.directory('state', root=tmp_path) / 'retention-host')]
    evidence = []
    receipts = []
    for index, store in enumerate(stores):
        with store.session() as token:
            path = tmp_path / f'evidence-{index}'
            path.mkdir(mode=0o700)
            test_retention.retain(path)
            (path / 'output').write_text('interrupted output')
            test_retention.preserve_for_recovery()
        evidence.append(path)
        receipts.append(store.path / f'recovered-{token}.json')
    run, started = session.select(tmp_path, ['unit'])
    assert started
    wait_for(tmp_path / 'started')
    (tmp_path / 'release').touch()
    output = io.StringIO()
    assert session.follow(run, output) == 7
    assert 'Traceback' not in output.getvalue()
    assert all(receipt.exists() for receipt in receipts)
    assert all((path / 'output').read_text() == 'interrupted output' for path in evidence)
    assert all(not (store.path / 'recovery-required').exists() for store in stores)


@pytest.mark.parametrize('fault', ['active', 'replaced'])
def test_session_recovery_refuses_unsafe_evidence_before_allocating_or_spawning(tmp_path, workers, fault):
    directory = session.prepare(tmp_path, host_only=True)
    store = test_retention.Store(directory / 'retention')
    with store.session():
        evidence = tmp_path / 'evidence'
        evidence.mkdir(mode=0o700)
        test_retention.retain(evidence)
        test_retention.preserve_for_recovery()
    original = (store.path / 'current.json').read_bytes()
    entries = set(directory.iterdir())
    if fault == 'active':
        with store.opened() as fd, store.locked(fd, 'owner.lock', blocking=False):
            with pytest.raises(ValueError, match='another owner'):
                session.select(tmp_path, ['unit'])
    else:
        evidence.rename(tmp_path / 'original')
        evidence.mkdir(mode=0o700)
        with pytest.raises(ValueError, match='replaced'):
            session.select(tmp_path, ['unit'])
    assert workers == []
    assert (store.path / 'current.json').read_bytes() == original
    assert (store.path / 'recovery-required').exists()
    assert set(directory.iterdir()) - entries == {directory / 'gate'}


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
