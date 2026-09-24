"""Real owner lifetimes with isolated agent and test doubles, never a live VM."""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import pytest

import detached_launcher as launcher
import write_e2e as workflow
from tests.support.paths import ROOT
from tests.support.write_e2e_fixtures import prepare, reply


def wait_for(path):
    deadline = time.monotonic() + 15
    while not path.exists():
        assert time.monotonic() < deadline, f'timed out waiting for {path}'
        time.sleep(.02)


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    prepare(tmp_path)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / '.git/info/exclude').write_text(
        'bin/\nscript.json\ncalls.jsonl\nagent-ready-*\nrelease*\n'
        'nested-ready\ncleanup-started\nnested-cleaned\n')
    (tmp_path / 'bin').mkdir()
    codex = tmp_path / 'bin/codex'
    codex.write_text('#!/usr/bin/python3\nimport runpy\n'
                     f'runpy.run_path({str(ROOT / "tests/support/write_e2e_child.py")!r}, run_name="__main__")\n')
    codex.chmod(0o700)
    monkeypatch.setenv('PATH', str(tmp_path / 'bin') + ':/usr/bin:/bin')
    monkeypatch.setenv('CODEX_THREAD_ID', 'parent-thread-must-not-leak')
    spawned = []
    popen = subprocess.Popen

    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        if '--worker' in args[0]:
            spawned.append(child)
        return child

    monkeypatch.setattr(subprocess, 'Popen', record)
    yield tmp_path, spawned
    directory = launcher.current_run(
        __import__('test_storage').directory('write-e2e', root=tmp_path))
    if directory is not None:
        (directory / 'cancel').touch()
    (tmp_path / 'release').touch()
    (tmp_path / 'release-nested').touch()
    for child in spawned:
        child.wait(timeout=20)


def script(root, *steps):
    (root / 'script.json').write_text(json.dumps(steps))


def calls(root):
    return [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]


def test_limit_and_restart_pass_only_last_handoff_in_fresh_process(checkout):
    root, _ = checkout
    script(root, {'result': reply(handoff='LATEST LIVE HANDOFF')},
           {'result': reply('task_complete', 'passed'), 'close': True})
    first, _ = workflow.select(root, ['--sessions', '1'])
    assert launcher.follow(first, io.StringIO()) == 0
    assert len(calls(root)) == 1
    assert 'LATEST LIVE HANDOFF' in (first / 'handoff.txt').read_text()
    second, started = workflow.select(root, ['--sessions', '1'])
    assert started and second != first
    output = io.StringIO()
    assert launcher.follow(second, output) == 0
    from rich.console import Console
    from rich.text import Text
    rendered = Text.from_ansi(output.getvalue())
    assert rendered.plain.rstrip().endswith(
        'Task 001 complete.\n- Took 2 sessions.\n- Total launcher sessions: 1')
    assert rendered.plain.count('Task 001 complete.') == 1
    assert 'Next session prompt:' not in rendered.plain
    assert 'Task complete' not in rendered.plain
    assert 'Turn complete' not in rendered.plain
    offset = rendered.plain.index('Task 001 complete')
    assert rendered.get_style_at_offset(Console(), offset).color.get_truecolor().hex == '#008000'
    assert 'Next session prompt:' in (second / 'handoff.txt').read_text()
    invocations = calls(root)
    assert len({call['pid'] for call in invocations}) == 2
    for call, effort in zip(invocations, ['low', 'high']):
        assert call['thread'] is None
        assert '--ephemeral' in call['args']
        assert not {'resume', 'fork', '--last'} & set(call['args'])
        assert call['args'][call['args'].index('--model') + 1] == 'gpt-6-astra'
        assert f'model_reasoning_effort="{effort}"' in call['args']
        assert '--output-schema' in call['args']
    assert 'LATEST LIVE HANDOFF' in invocations[1]['prompt']
    assert workflow.queue_state(root)[0] == '002'
    staged = subprocess.run(['git', 'ls-files'], cwd=root, capture_output=True, text=True, check=True)
    assert workflow.PLAN in staged.stdout and workflow.QUEUE in staged.stdout


def test_completion_stages_changes_from_every_session_despite_omitted_stage_paths(checkout):
    root, _ = checkout
    unrelated = root / 'unrelated.txt'
    unrelated.write_text('pre-existing work')
    script(root, {'result': reply(), 'writes': {'implementation.py': 'first session\n'}},
           {'result': reply('task_complete', 'passed'), 'close': True,
            'writes': {'final-note.md': 'last session\n'}})
    first, _ = workflow.select(root, ['--sessions', '1'])
    assert launcher.follow(first, io.StringIO()) == 0
    second, _ = workflow.select(root, ['--sessions', '1'])
    assert launcher.follow(second, io.StringIO()) == 0
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=root,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    assert set(staged) == {workflow.PLAN, workflow.QUEUE,
                           'implementation.py', 'final-note.md'}
    assert unrelated.read_text() == 'pre-existing work'


def test_failure_repair_returns_before_retry_and_counts_every_session(checkout):
    root, _ = checkout
    script(root, {'result': reply(handoff='FIRST')},
           {'result': reply(live='failed', handoff='REPAIRED')},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002', handoff='NEXT TASK LIVE')})
    run, _ = workflow.select(root, ['--sessions', '4', '--tasks', '2'])
    assert launcher.follow(run, io.StringIO()) == 0
    invocations = calls(root)
    assert len(invocations) == 4
    assert 'first live VM attempt' in invocations[1]['prompt']
    assert 'REPAIRED' in invocations[2]['prompt'] and 'FIRST' not in invocations[2]['prompt']
    assert 'first live attempt has already happened' in invocations[2]['prompt']
    assert invocations[3]['prompt'].startswith(workflow.INITIAL_PROMPT)
    assert 'REPAIRED' not in invocations[3]['prompt']
    assert 'Task 002' in (run / 'handoff.txt').read_text()


def test_completion_reports_each_task_sessions_and_cumulative_launcher_sessions(checkout):
    root, _ = checkout
    script(root, {'result': reply()},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002')},
           {'result': reply(task_id='002', live='failed')},
           {'result': reply('task_complete', 'passed', task_id='002'), 'close': True})
    run, _ = workflow.select(root, ['--sessions', '5', '--tasks', '2'])
    output = io.StringIO()
    assert launcher.follow(run, output) == 0
    from rich.text import Text
    rendered = Text.from_ansi(output.getvalue()).plain
    assert 'Task 001 complete.\n- Took 2 sessions.\n- Total launcher sessions: 2' in rendered
    assert 'Task 002 complete.\n- Took 3 sessions.\n- Total launcher sessions: 5' in rendered


@pytest.mark.parametrize('args, sessions, completed, reason', [
    ([], 2, 1, 'task limit reached'),
    (['--sessions', '3', '--tasks', '1'], 2, 1, 'task limit reached'),
    (['--sessions', '1', '--tasks', '2'], 1, 0, 'session limit reached'),
    (['--sessions', '3', '--tasks', '2'], 3, 1, 'session limit reached'),
    (['--tasks', '2'], 4, 2, 'task limit reached'),
    (['--sessions', '2', '--tasks', '1'], 2, 1, 'task limit reached'),
])
def test_first_limit_stops_after_accepted_completion(checkout, args, sessions, completed, reason):
    root, _ = checkout
    script(root, {'result': reply()},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002')},
           {'result': reply('task_complete', 'passed', task_id='002'), 'close': True})
    run, _ = workflow.select(root, args)
    assert launcher.follow(run, io.StringIO()) == 0
    assert len(calls(root)) == sessions
    assert json.loads((run / 'result.json').read_text()) == {
        'status': 0, 'sessions': sessions, 'tasks': completed}
    assert reason in (run / 'handoff.txt').read_text()
    _, queue = workflow.queue_state(root)
    assert sum(queue.values()) == completed
    if completed:
        staged = subprocess.run(['git', 'show', ':' + workflow.QUEUE], cwd=root,
                                capture_output=True, text=True, check=True)
        assert staged.stdout.count('| [x] |') == completed


@pytest.mark.parametrize('args', [[], ['--tasks', '2'], ['--sessions', '20', '--tasks', '2']])
def test_task_cap_stops_entire_launcher_with_final_red_warning(checkout, args):
    root, _ = checkout
    script(root, {'result': reply()},
           *({'result': reply(live='failed')} for _ in range(4)))
    run, started = workflow.select(root, args)
    assert started
    output = io.StringIO()
    assert launcher.follow(run, output) == 1
    assert len(calls(root)) == 5
    assert json.loads((run / 'result.json').read_text()) == {
        'status': 1, 'sessions': 5, 'tasks': 0}
    assert 'task session limit reached' in (run / 'handoff.txt').read_text()
    from rich.console import Console
    from rich.text import Text
    rendered = Text.from_ansi(output.getvalue())
    warning = 'Task 001 is not complete in 5 sessions. Launcher exited early.'
    assert rendered.plain.rstrip().splitlines()[-1] == warning
    assert rendered.plain.index('Next session prompt:') < rendered.plain.index(warning)
    style = rendered.get_style_at_offset(Console(), rendered.plain.index(warning))
    assert style.bold and style.color.get_truecolor().hex == '#800000'
    assert workflow.queue_state(root)[0] == '001'
    restarted, started = workflow.select(root, ['--tasks', '2'])
    assert started
    assert launcher.follow(restarted, io.StringIO()) == 1
    assert len(calls(root)) == 5


def test_task_cap_counts_sessions_before_restart(checkout):
    root, _ = checkout
    script(root, {'result': reply()},
           *({'result': reply(live='failed')} for _ in range(4)))
    first, _ = workflow.select(root, ['--sessions', '3'])
    assert launcher.follow(first, io.StringIO()) == 0
    second, _ = workflow.select(root, ['--tasks', '2'])
    assert launcher.follow(second, io.StringIO()) == 1
    assert len(calls(root)) == 5
    assert json.loads((second / 'result.json').read_text()) == {
        'status': 1, 'sessions': 2, 'tasks': 0}


def test_completion_on_fifth_session_resets_cap_for_next_task(checkout):
    root, _ = checkout
    script(root, {'result': reply()},
           *({'result': reply(live='failed')} for _ in range(3)),
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002')},
           {'result': reply('task_complete', 'passed', task_id='002'), 'close': True})
    run, _ = workflow.select(root, ['--tasks', '2'])
    output = io.StringIO()
    assert launcher.follow(run, output) == 0
    assert len(calls(root)) == 7
    assert 'Launcher exited early.' not in output.getvalue()
    assert json.loads((run / 'result.json').read_text()) == {
        'status': 0, 'sessions': 7, 'tasks': 2}


def test_concurrent_plain_attach_preserves_limits_and_terminal_loss(checkout):
    root, spawned = checkout
    script(root, {'result': reply(), 'wait': True})
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _: workflow.select(root, []), range(2)))
    run = values[0][0]
    assert values[1][0] == run and sorted(item[1] for item in values) == [False, True]
    wait_for(root / 'agent-ready-1')
    assert len(spawned) == 1 and os.getsid(spawned[0].pid) == spawned[0].pid
    limits = (run / 'limits.json').read_text()
    assert json.loads(limits)['sessions'] == 5
    assert json.loads(limits)['tasks'] == 1
    assert workflow.select(root, []) == (run, False)
    assert (run / 'limits.json').read_text() == limits
    with pytest.raises(SystemExit):
        workflow.select(root, ['--sessions', 'invalid', '--tasks', 'invalid', '--unknown'])
    assert (run / 'limits.json').read_text() == limits

    class Closed(io.StringIO):
        def write(self, value):
            raise BrokenPipeError()

    with pytest.raises(BrokenPipeError):
        launcher.follow(run, Closed())
    assert spawned[0].poll() is None
    workflow.select(root, ['--stop'])
    (root / 'release').touch()
    assert launcher.follow(run, io.StringIO()) == 0


@pytest.mark.parametrize('initial, adjustment, sessions, completed', [
    (['--tasks', '1'], ['--tasks', '2'], 4, 2),
    (['--tasks', '2'], ['--tasks', '-1'], 2, 1),
    (['--sessions', '1'], ['--sessions', '1'], 2, 1),
    (['--sessions', '2'], ['--sessions', '-1'], 1, 0),
    (['--tasks', '2', '--sessions', '4'], ['--tasks', '-1', '--sessions', '-3'], 1, 0),
    (['--tasks', '2'], ['--tasks', '-9'], 1, 0),
    ([], ['--sessions', '1'], 2, 1),
    ([], ['--sessions', '0'], 2, 1),
    ([], ['--sessions', '-5'], 1, 0),
])
def test_attached_adjustments_control_next_boundary(checkout, initial, adjustment, sessions, completed):
    root, spawned = checkout
    script(root, {'result': reply(), 'wait': True},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002')},
           {'result': reply('task_complete', 'passed', task_id='002'), 'close': True})
    run, _ = workflow.select(root, initial)
    wait_for(root / 'agent-ready-1')
    assert workflow.select(root, adjustment) == (run, False)
    assert len(spawned) == 1 and spawned[0].poll() is None
    (root / 'release').touch()
    assert launcher.follow(run, io.StringIO()) == 0
    assert json.loads((run / 'result.json').read_text()) == {
        'status': 0, 'sessions': sessions, 'tasks': completed}


def test_concurrent_adjustments_accumulate_without_resetting_completed_work(checkout):
    root, _ = checkout
    script(root, {'result': reply()},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002'), 'wait': True})
    run, _ = workflow.select(root, ['--tasks', '2', '--sessions', '4'])
    wait_for(root / 'agent-ready-3')
    with ThreadPoolExecutor(max_workers=4) as pool:
        attached = list(pool.map(lambda _: workflow.select(root, ['--tasks', '1', '--sessions', '2']), range(4)))
    assert attached == [(run, False)] * 4
    assert json.loads((run / 'limits.json').read_text()) == {'tasks': 6, 'sessions': 12, 'started': 3}
    workflow.select(root, ['--tasks', '-6', '--sessions', '-12'])
    (root / 'release').touch()
    assert launcher.follow(run, io.StringIO()) == 0
    assert json.loads((run / 'result.json').read_text()) == {'status': 0, 'sessions': 3, 'tasks': 1}
    assert workflow.queue_state(root) == ('002', {'001': True, '002': False})


def test_plain_run_stops_at_handoff_without_interrupting_agent(checkout):
    root, spawned = checkout
    script(root, {'result': reply(), 'wait': True})
    run, _ = workflow.select(root, [])
    wait_for(root / 'agent-ready-1')
    assert workflow.select(root, ['--stop']) == (run, False)
    assert (run / 'stop').exists() and not (run / 'cancel').exists()
    assert spawned[0].poll() is None
    (root / 'release').touch()
    assert launcher.follow(run, io.StringIO()) == 0
    assert len(calls(root)) == 1
    assert 'stopped at a session boundary' in (run / 'handoff.txt').read_text()


@pytest.mark.parametrize('action', ['ctrl-c', 'kill-owner'])
def test_cancellation_awaits_only_registered_test_cleanup(checkout, monkeypatch, action):
    root, spawned = checkout
    script(root, {'result': reply(), 'nested': True, 'wait': True})
    run, _ = workflow.select(root, [])
    wait_for(root / 'agent-ready-1')
    unrelated = root / 'unrelated'
    unrelated.mkdir()
    with launcher.lock(unrelated / 'owner') as unrelated_owner:
        import fcntl
        fcntl.flock(unrelated_owner, fcntl.LOCK_EX)
        if action == 'kill-owner':
            descriptor = os.pidfd_open(spawned[0].pid)
            try:
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            finally:
                os.close(descriptor)
            assert launcher.follow(run, io.StringIO()) == 1
        else:
            select = workflow.select
            monkeypatch.setattr(workflow, 'select', lambda _, args: select(root, args))
            follow = launcher.follow

            def interrupt(run, **kwargs):
                signal.raise_signal(signal.SIGINT)
                return follow(run, io.StringIO())

            monkeypatch.setattr(launcher, 'follow', interrupt)
            assert workflow.main([]) == 130
        assert not (unrelated / 'cancel').exists()
    assert (root / 'nested-cleaned').exists()
    with launcher.lock(run.parent / 'owner') as owner:
        assert not launcher.busy(owner)


@pytest.mark.parametrize('kind', ['blocked', 'invalid', 'crash'])
def test_bad_agent_outcome_stops_without_advancing_or_reusing_a_reply(checkout, kind):
    root, _ = checkout
    step = {'result': reply('blocked') if kind == 'blocked' else reply()}
    if kind != 'blocked':
        step[kind] = True
    script(root, step)
    run, _ = workflow.select(root, [])
    output = io.StringIO()
    assert launcher.follow(run, output) == 1
    assert len(calls(root)) == 1
    assert workflow.queue_state(root)[0] == '001'
    assert 'Next session prompt:' in (run / 'handoff.txt').read_text()


def test_nested_registration_refuses_dead_parent_and_replaced_identity(tmp_path, monkeypatch):
    from test_storage import directory
    parent = directory('write-e2e', root=tmp_path) / ('a' * 32)
    parent.mkdir(mode=0o700)
    launcher.atomic(parent.parent / 'current.json', {'run': parent.name})
    child = directory('sessions', root=tmp_path) / ('b' * 32)
    child.mkdir(mode=0o700)
    monkeypatch.setenv(launcher.WORKFLOW_DIRECTORY, str(parent))
    with pytest.raises(ValueError, match='no longer accepting'):
        with launcher.nested_operation(tmp_path, child):
            pytest.fail('dead parent admitted a child')
    launcher.atomic(parent / 'nested.json', [{'path': str(child), 'device': 0, 'inode': 0}])
    with pytest.raises(ValueError, match='identity changed'):
        launcher.finish_nested(tmp_path, parent)
    assert not (child / 'cancel').exists()


def test_expired_completed_nested_run_does_not_block_the_next_session(tmp_path):
    from test_storage import directory
    parent = directory('write-e2e', root=tmp_path) / ('a' * 32)
    parent.mkdir(mode=0o700)
    expired = directory('sessions', root=tmp_path) / ('b' * 32)
    launcher.atomic(parent / 'nested.json', [{'path': str(expired), 'device': 0, 'inode': 0}])
    assert launcher.finish_nested(tmp_path, parent) is False


def test_cancelled_run_can_restart_through_fresh_recovery_session(checkout):
    root, _ = checkout
    script(root, {'result': reply(), 'wait': True},
           {'result': reply(handoff='RECOVERED HANDOFF')})
    run, _ = workflow.select(root, [])
    wait_for(root / 'agent-ready-1')
    (run / 'cancel').touch()
    assert launcher.follow(run, io.StringIO()) == 130
    recovered, started = workflow.select(root, ['--sessions', '1'])
    assert started and recovered != run
    assert launcher.follow(recovered, io.StringIO()) == 0
    invocations = calls(root)
    invocation = invocations[1]
    assert invocation['pid'] != invocations[0]['pid']
    assert 'model_reasoning_effort="high"' in invocation['args']
    progress = json.loads((recovered / 'progress.json').read_text())
    assert progress['task_id'] == '001' and progress['phase'] == 'recover'
    prompt = ' '.join(invocation['prompt'].split())
    assert 'Recover this task with GPT-6-Astra High' in prompt
    assert 'Do not run live VM tests or close the task/advance the pointer' in prompt
    assert str(run) in prompt
    assert workflow.queue_state(root) == ('001', {'001': False, '002': False})
    assert 'RECOVERED HANDOFF' in (recovered / 'handoff.txt').read_text()
