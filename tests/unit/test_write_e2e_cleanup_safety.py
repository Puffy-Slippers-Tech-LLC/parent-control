"""Real owner lifetimes with isolated agent and test doubles, never a live VM."""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import re

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


def finish_answered_run(run, spawned, output=None):
    # A broken resume must fail this regression instead of hanging the suite.
    spawned[-1].wait(timeout=20)
    return launcher.follow(run, output or io.StringIO())


def test_first_session_success_closes_and_stages_without_another_session(checkout):
    root, _ = checkout
    script(root, {'result': reply('task_complete', 'passed'), 'close': True})
    run, _ = workflow.select(root, [])
    output = io.StringIO()
    assert launcher.follow(run, output) == 0
    from rich.text import Text
    assert ('Task 001 complete.\n- Took 1 sessions.\n'
            '- Total launcher sessions: 1\n') in Text.from_ansi(output.getvalue()).plain
    assert len(calls(root)) == 1
    assert workflow.queue_state(root)[0] == '002'
    state = json.loads((run / 'checkpoint.json').read_text())
    assert state['phase'] == 'complete' and state['live_attempts'] == 1
    staged = subprocess.run(['git', 'ls-files'], cwd=root, capture_output=True, text=True, check=True)
    assert workflow.PLAN in staged.stdout and workflow.QUEUE in staged.stdout


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
    assert re.search(
        r'Task 001 complete\.\n- Took 2 sessions\.\n'
        r'- Total launcher sessions: 2\n- Duration: \d+ minutes$',
        rendered.plain.rstrip())
    assert rendered.plain.count('Task 001 complete.') == 1
    assert re.search(r'─+\nTask 001 complete\.', rendered.plain)
    assert 'Next session prompt:' not in rendered.plain
    assert 'Task complete' not in rendered.plain
    assert 'Turn complete' not in rendered.plain
    offset = rendered.plain.index('Task 001 complete')
    style = rendered.get_style_at_offset(Console(), offset)
    assert style.bold and style.color.get_truecolor().hex == '#008000'
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
    from launcher_progress import read_progress
    assert 'Session [2/2]' in Text.from_ansi(read_progress(second)[-1]['lines'][-1]).plain
    assert json.loads((second / 'result.json').read_text())['sessions'] == 1


def test_cumulative_sessions_restart_only_for_a_new_task(checkout):
    from launcher_progress import read_progress
    from rich.text import Text
    root, _ = checkout
    script(root, {'result': reply()},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002')},
           {'result': reply('task_complete', 'passed', task_id='002'), 'close': True})
    for sessions, expected in [('2', '2/2'), ('1', '1/1'), ('1', '2/2')]:
        run, started = workflow.select(root, ['--sessions', sessions])
        assert started
        assert launcher.follow(run, io.StringIO()) == 0
        line = Text.from_ansi(read_progress(run)[-1]['lines'][-1]).plain
        assert f'Session [{expected}]' in line


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
    assert 'first live attempt failed' in invocations[1]['prompt']
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
    run, _ = workflow.select(root, ['--sessions', '9', '--tasks', '2'])
    output = io.StringIO()
    assert launcher.follow(run, output) == 0
    from rich.text import Text
    rendered = Text.from_ansi(output.getvalue()).plain
    assert 'Task 001 complete.\n- Took 2 sessions.\n- Total launcher sessions: 2' in rendered
    assert 'Task 002 complete.\n- Took 3 sessions.\n- Total launcher sessions: 5' in rendered
    assert rendered.count('- Duration: ') == 2
    assert len(re.findall(r'─+\nTask \d+ complete\.', rendered)) == 2
    recap = rendered[rendered.index('Task 001 complete.'):]
    assert 'write-e2e: session' not in recap
    assert 'Working' not in recap
    from launcher_progress import read_progress
    steps = read_progress(run)
    assert len(steps) == 2
    for step, task, title, sessions in zip(steps, ['001', '002'], ['First', 'Second'], [2, 3]):
        assert re.fullmatch(
            rf'Task {task}: {title} \(sessions={sessions}, duration=\d+m\)',
            Text.from_ansi(step['lines'][0]).plain)


def test_completed_task_is_compacted_while_next_task_keeps_live_updates(checkout):
    from launcher_progress import read_progress
    from rich.console import Console
    from rich.text import Text
    root, _ = checkout
    queue = root / workflow.QUEUE
    queue.write_text(queue.read_text().replace('| First |', '| [First](first.md) |'))
    script(root, {'result': reply()},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002')},
           {'result': reply('task_complete', 'passed', task_id='002'),
            'close': True, 'wait': True})
    run, _ = workflow.select(root, ['--tasks', '2'])
    wait_for(root / 'agent-ready-4')
    steps = read_progress(run)
    assert [step['key'] for step in steps] == ['complete-001', '3', '4']
    summary = Text.from_ansi(steps[0]['lines'][0])
    assert re.fullmatch(r'Task 001: First \(sessions=2, duration=\d+m\)', summary.plain)
    label_style = summary.get_style_at_offset(Console(), 0)
    assert label_style.bold
    assert label_style.link == (queue.parent / 'first.md').as_uri()
    title_style = summary.get_style_at_offset(Console(), len('Task 001: '))
    assert not title_style.bold and not title_style.link
    lines = [Text.from_ansi(line).plain for step in steps[1:] for line in step['lines']]
    assert 'Session [1/3]: Writing task code + host validation + first live VM test; close on success, hand off on failure' in lines
    assert 'Session [2/4]: Live VM test 2, fix errors if any + host validation' in lines
    (root / 'release').touch()
    assert launcher.follow(run, io.StringIO()) == 0


def test_completion_excludes_sessions_from_previous_completed_launcher(checkout):
    from rich.text import Text
    root, _ = checkout
    script(root, {'result': reply()},
           {'result': reply(live='failed')},
           {'result': reply(live='failed')},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply('task_complete', 'passed', task_id='002'), 'close': True})
    first, _ = workflow.select(root, [])
    assert launcher.follow(first, io.StringIO()) == 0
    second, started = workflow.select(root, [])
    assert started and second != first
    output = io.StringIO()
    assert launcher.follow(second, output) == 0
    assert len(calls(root)) == 5
    assert ('Task 002 complete.\n- Took 1 sessions.\n'
            '- Total launcher sessions: 1\n') in Text.from_ansi(output.getvalue()).plain


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
           *({'result': reply(live='failed')} for _ in range(9)))
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
    assert len(calls(root)) == 10
    assert json.loads((restarted / 'result.json').read_text()) == {
        'status': 1, 'sessions': 5, 'tasks': 0}
    assert json.loads((restarted / 'checkpoint.json').read_text())['task_session_limit'] == 10


def test_task_cap_renews_without_resetting_task_sessions(checkout):
    root, _ = checkout
    script(root, {'result': reply()},
           *({'result': reply(live='failed')} for _ in range(7)))
    first, _ = workflow.select(root, ['--sessions', '3'])
    assert launcher.follow(first, io.StringIO()) == 0
    second, _ = workflow.select(root, ['--tasks', '2'])
    assert launcher.follow(second, io.StringIO()) == 1
    assert len(calls(root)) == 8
    assert json.loads((second / 'result.json').read_text()) == {
        'status': 1, 'sessions': 5, 'tasks': 0}
    assert json.loads((second / 'checkpoint.json').read_text())['task_sessions'] == 8


def test_six_prior_sessions_get_five_more_in_plain_new_launcher(checkout):
    from rich.text import Text
    root, _ = checkout
    script(root, {'result': reply()},
           *({'result': reply(live='failed')} for _ in range(10)))
    first, _ = workflow.select(root, [])
    assert launcher.follow(first, io.StringIO()) == 1
    second, _ = workflow.select(root, ['--sessions', '1'])
    assert launcher.follow(second, io.StringIO()) == 0
    assert json.loads((second / 'checkpoint.json').read_text())['task_sessions'] == 6
    third, started = workflow.select(root, [])
    assert started
    output = io.StringIO()
    assert launcher.follow(third, output) == 1
    assert len(calls(root)) == 11
    assert json.loads((third / 'result.json').read_text()) == {
        'status': 1, 'sessions': 5, 'tasks': 0}
    assert json.loads((third / 'checkpoint.json').read_text())['task_session_limit'] == 11
    assert 'Task 001' in calls(root)[6]['prompt']
    assert 'Task 001 is not complete in 11 sessions. Launcher exited early.' in Text.from_ansi(output.getvalue()).plain


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


@pytest.mark.parametrize('kind', ['invalid', 'crash'])
def test_bad_agent_outcome_stops_without_advancing_or_reusing_a_reply(checkout, kind):
    root, _ = checkout
    step = {'result': reply(), kind: True}
    script(root, step)
    run, _ = workflow.select(root, [])
    output = io.StringIO()
    assert launcher.follow(run, output) == 1
    assert len(calls(root)) == 1
    assert workflow.queue_state(root)[0] == '001'
    assert 'Next session prompt:' in (run / 'handoff.txt').read_text()


@pytest.mark.parametrize('custom', [False, True])
def test_blocker_pauses_across_detach_and_resumes_only_after_answer(checkout, custom):
    from launcher_question import submit
    from rich.text import Text
    root, spawned = checkout
    script(root, {'result': reply('blocked', handoff='ENGINEERING DETAILS ONLY IN SAVED HANDOFF')},
           {'result': reply(live='not_run'), 'wait': True},
           {'result': reply('task_complete', 'passed'), 'close': True})
    run, _ = workflow.select(root, [])
    wait_for(run / 'question.json')
    wait_for(run / 'handoff.txt')
    time.sleep(.3)
    assert len(calls(root)) == 1 and not (run / 'result.json').exists()
    assert json.loads((run / 'checkpoint.json').read_text())['phase'] == 'blocked'
    assert workflow.queue_state(root)[0] == '001'
    assert workflow.select(root, []) == (run, False)
    assert len(calls(root)) == 1
    question = json.loads((run / 'question.json').read_text())
    assert submit(run, question['id'], 3 if custom else 0, 'Keep 0m. Review only the two checks.')
    wait_for(root / 'agent-ready-2')
    prompt = calls(root)[1]['prompt']
    assert ('Keep 0m.' if custom else question['options'][0]) in prompt
    assert 'ENGINEERING DETAILS ONLY IN SAVED HANDOFF' in prompt
    assert 'Do not run live VM tests' in prompt
    (root / 'release').touch()
    output = io.StringIO()
    assert finish_answered_run(run, spawned, output) == 0
    rendered = Text.from_ansi(output.getvalue()).plain
    assert rendered.count(question['explanation']) == 1
    assert 'ENGINEERING DETAILS ONLY IN SAVED HANDOFF' not in rendered
    assert 'Turn complete' not in rendered.split('Answer received.')[0]
    assert 'recommended' in rendered and 'Other' in rendered
    selected = '› 4. Keep 0m. Review only the two checks.' if custom else f"› 1. {question['options'][0]}"
    assert selected in rendered
    if custom:
        assert f"› 1. {question['options'][0]}" not in rendered
    assert len(calls(root)) == 3
    assert workflow.queue_state(root)[0] == '002'


@pytest.mark.parametrize('action', ['stop', 'cancel'])
def test_waiting_can_stop_or_cancel_and_restart_still_requires_an_answer(checkout, action):
    from launcher_question import submit
    root, spawned = checkout
    script(root, {'result': reply('blocked')}, {'result': reply(live='not_run')})
    run, _ = workflow.select(root, [])
    wait_for(run / 'handoff.txt')
    (run / action).touch()
    output = io.StringIO()
    assert finish_answered_run(run, spawned, output) == (130 if action == 'cancel' else 0)
    assert 'Next session prompt:' not in output.getvalue()
    assert 'Next session prompt:' in (run / 'handoff.txt').read_text()
    resumed, started = workflow.select(root, ['--sessions', '1'])
    assert started and resumed != run
    wait_for(resumed / 'question.json')
    assert len(calls(root)) == 1
    question = json.loads((resumed / 'question.json').read_text())
    assert submit(resumed, question['id'], 0)
    assert finish_answered_run(resumed, spawned) == 0
    assert len(calls(root)) == 2


def test_answer_permits_recovery_when_blocker_used_the_last_session(checkout):
    from launcher_question import submit
    root, spawned = checkout
    script(root, *[{'result': reply()} for _ in range(4)],
           {'result': reply('blocked')}, {'result': reply(live='not_run')})
    run, _ = workflow.select(root, [])
    wait_for(run / 'question.json')
    assert len(calls(root)) == 5 and not (run / 'result.json').exists()
    question = json.loads((run / 'question.json').read_text())
    assert submit(run, question['id'], 0)
    assert finish_answered_run(run, spawned) == 1  # recovery used the explicitly extended task cap
    assert len(calls(root)) == 6
    assert json.loads((run / 'result.json').read_text())['sessions'] == 6


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
           {'result': reply(live='not_run', handoff='RECOVERED HANDOFF')})
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
