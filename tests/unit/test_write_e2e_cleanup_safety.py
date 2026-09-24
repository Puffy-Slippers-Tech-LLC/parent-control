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
from tests.unit.test_write_e2e import prepare, reply


def wait_for(path):
    deadline = time.monotonic() + 15
    while not path.exists():
        assert time.monotonic() < deadline, f'timed out waiting for {path}'
        time.sleep(.02)


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    prepare(tmp_path)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
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
    assert launcher.follow(second, io.StringIO()) == 0
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


def test_failure_repair_returns_before_retry_and_counts_every_session(checkout):
    root, _ = checkout
    script(root, {'result': reply(handoff='FIRST')},
           {'result': reply(live='failed', handoff='REPAIRED')},
           {'result': reply('task_complete', 'passed'), 'close': True},
           {'result': reply(task_id='002', handoff='NEXT TASK LIVE')})
    run, _ = workflow.select(root, ['--sessions', '4'])
    assert launcher.follow(run, io.StringIO()) == 0
    invocations = calls(root)
    assert len(invocations) == 4
    assert 'first live VM attempt' in invocations[1]['prompt']
    assert 'REPAIRED' in invocations[2]['prompt'] and 'FIRST' not in invocations[2]['prompt']
    assert 'first live attempt has already happened' in invocations[2]['prompt']
    assert invocations[3]['prompt'].startswith(workflow.INITIAL_PROMPT)
    assert 'REPAIRED' not in invocations[3]['prompt']
    assert 'Task 002' in (run / 'handoff.txt').read_text()


def test_concurrent_attach_ignores_all_new_parameters_and_terminal_loss(checkout):
    root, spawned = checkout
    script(root, {'result': reply(), 'wait': True})
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _: workflow.select(root, ['--sessions', '1']), range(2)))
    run = values[0][0]
    assert values[1][0] == run and sorted(item[1] for item in values) == [False, True]
    wait_for(root / 'agent-ready-1')
    assert len(spawned) == 1 and os.getsid(spawned[0].pid) == spawned[0].pid
    assert workflow.select(root, ['--sessions', 'invalid', '--unknown']) == (run, False)

    class Closed(io.StringIO):
        def write(self, value):
            raise BrokenPipeError()

    with pytest.raises(BrokenPipeError):
        launcher.follow(run, Closed())
    assert spawned[0].poll() is None
    (root / 'release').touch()
    assert launcher.follow(run, io.StringIO()) == 0


def test_unlimited_run_stops_at_handoff_without_interrupting_agent(checkout):
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
    invocation = calls(root)[1]
    assert 'model_reasoning_effort="high"' in invocation['args']
    assert 'Recover the same unfinished task' in invocation['prompt']
    assert 'RECOVERED HANDOFF' in (recovered / 'handoff.txt').read_text()
