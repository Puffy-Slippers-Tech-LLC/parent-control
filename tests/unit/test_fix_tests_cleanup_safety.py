"""Real detach, cancellation and restart paths using private process doubles."""

from concurrent.futures import ThreadPoolExecutor
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

import fix_tests
from regression_session import busy, lock
from tests.support.paths import ROOT


def wait_for(path):
    deadline = time.monotonic() + 12
    while not path.exists():
        assert time.monotonic() < deadline, f'timed out waiting for {path}'
        time.sleep(.02)


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'bin').mkdir()
    for target, kind in ((tmp_path / 'tools/run-tests', 'test'),
                         (tmp_path / 'tools/cleanup-e2e', 'recovery'),
                         (tmp_path / 'bin/codex', 'agent')):
        target.write_text('#!/usr/bin/python3\nimport runpy,sys\n'
                          f'sys.argv.insert(1, {kind!r})\n'
                          f'runpy.run_path({str(ROOT / "tests/support/fix_tests_child.py")!r}, run_name="__main__")\n')
        target.chmod(0o700)
    (tmp_path / 'mode').write_text('test-wait')
    monkeypatch.setenv('PATH', str(tmp_path / 'bin') + ':/usr/bin:/bin')
    monkeypatch.setenv('CODEX_THREAD_ID', 'do-not-inherit-this-thread')
    # Record every directly spawned owner for bounded teardown, never scan PIDs.
    spawned = []
    popen = subprocess.Popen

    def record(*args, **kwargs):
        child = popen(*args, **kwargs)
        spawned.append(child)
        return child

    monkeypatch.setattr(fix_tests.subprocess, 'Popen', record)
    yield tmp_path, spawned
    run = fix_tests.current_run(tmp_path / 'artifacts/fix-tests')
    if run is not None:
        (run / 'cancel').touch()
    (tmp_path / 'release').touch()
    for child in spawned:
        child.wait(timeout=20)


def test_concurrent_starts_share_one_owner_and_terminal_loss_only_detaches(checkout):
    root, spawned = checkout
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: fix_tests.select(root), range(2)))
    run = results[0][0]
    assert results[1][0] == run
    assert sorted(result[1] for result in results) == [False, True]
    assert len(spawned) == 1
    wait_for(root / 'test-ready')
    assert os.getsid(spawned[0].pid) == spawned[0].pid

    class ClosedTerminal(io.StringIO):
        def write(self, value):
            raise BrokenPipeError('terminal closed')

    with pytest.raises(BrokenPipeError):
        fix_tests.follow(run, ClosedTerminal())
    assert fix_tests.select(root) == (run, False)
    assert spawned[0].poll() is None
    assert fix_tests.select(root, stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    assert (root / 'test-interrupted').exists() and (root / 'test-cleaned').exists()


@pytest.mark.parametrize('action', ['stop', 'ctrl-c', 'kill-owner'])
def test_cancellation_waits_for_runner_cleanup_then_fresh_start(checkout, monkeypatch, action):
    root, spawned = checkout
    run, _ = fix_tests.select(root)
    wait_for(root / 'test-ready')
    if action == 'kill-owner':
        with lock(run.parent / 'owner') as owner:
            assert busy(owner)
        descriptor = os.pidfd_open(spawned[0].pid)
        try:
            signal.pidfd_send_signal(descriptor, signal.SIGKILL)
        finally:
            os.close(descriptor)
        assert fix_tests.follow(run, io.StringIO()) == 1
    else:
        select = fix_tests.select
        monkeypatch.setattr(fix_tests, 'select', lambda _, **kwargs: select(root, **kwargs))
        if action == 'ctrl-c':
            follow = fix_tests.follow

            def interrupt(run):
                signal.raise_signal(signal.SIGINT)
                signal.raise_signal(signal.SIGINT)
                return follow(run, io.StringIO())

            monkeypatch.setattr(fix_tests, 'follow', interrupt)
        assert fix_tests.main(['--stop'] if action == 'stop' else []) == 130
    assert (root / 'test-cleaned').exists()
    (root / 'mode').write_text('pass')
    # Remove the main-only hook; this is a new caller after ownership is idle.
    if action != 'kill-owner':
        monkeypatch.setattr(fix_tests, 'select', select)
    next_run, started = fix_tests.select(root)
    assert started and next_run != run
    # Use the implementation, not the Ctrl+C hook, for the new observer.
    if action == 'ctrl-c':
        monkeypatch.setattr(fix_tests, 'follow', follow)
    assert fix_tests.follow(next_run, io.StringIO()) == 0
    assert (run / 'output').exists()


@pytest.mark.parametrize('mode,expected', [('agent-pass', 0), ('agent-blocked', 1), ('agent-invalid', 1)])
def test_real_script_uses_fresh_agent_prompt_and_granular_rounds(checkout, mode, expected):
    root, _ = checkout
    (root / 'mode').write_text(mode)
    run, _ = fix_tests.select(root)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == expected
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == 1
    assert agents[0]['thread'] is None
    assert agents[0]['frame_directory'] is None
    assert all(call['frame_directory'] == str(run) for call in calls if call['kind'] == 'test')
    assert json.loads((run / 'frame.json').read_text()) == []
    assert agents[0]['prompt'].startswith('LATEST FAILURE ONLY\n')
    assert 'PREVIOUS AGENT TRANSCRIPT' not in agents[0]['prompt']
    assert '--ephemeral' in agents[0]['args']
    executed = [call['category'] for call in calls if call['kind'] == 'test']
    assert executed == (['unit', 'unit', 'ui', 'system', 'e2e', 'all'] if expected == 0 else ['unit'])
    assert 'Traceback' not in output.getvalue()


@pytest.mark.parametrize('kill_owner', [False, True])
def test_agent_stop_terminates_its_group_and_preserves_unrelated_sentinel(checkout, kill_owner):
    root, spawned = checkout
    (root / 'mode').write_text('agent-wait')
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
    sentinel_fd = os.pidfd_open(sentinel.pid)
    try:
        run, _ = fix_tests.select(root)
        wait_for(root / 'agent-ready')
        if kill_owner:
            owner_fd = os.pidfd_open(spawned[-1].pid)
            try:
                signal.pidfd_send_signal(owner_fd, signal.SIGKILL)
            finally:
                os.close(owner_fd)
        else:
            fix_tests.select(root, stop=True)
        assert fix_tests.follow(run, io.StringIO()) == (1 if kill_owner else 130)
        assert sentinel.poll() is None
        descendant = Path('/proc') / (root / 'descendant').read_text() / 'stat'
        # A killed orphan can briefly remain a zombie until init reaps it.
        assert not descendant.exists() or descendant.read_text().split(') ')[1].startswith('Z ')
    finally:
        signal.pidfd_send_signal(sentinel_fd, signal.SIGTERM)
        sentinel.wait(timeout=5)
        os.close(sentinel_fd)


def test_stale_or_corrupt_metadata_cannot_block_a_fresh_owner(checkout):
    root, _ = checkout
    directory = fix_tests.private_directory(root / 'artifacts/fix-tests')
    (directory / 'current.json').write_text('interrupted metadata')
    (root / 'mode').write_text('pass')
    run, started = fix_tests.select(root)
    assert started and fix_tests.follow(run, io.StringIO()) == 0
    assert fix_tests.select(root, stop=True) == (None, False)


def test_unread_predecessor_result_does_not_count_as_the_requested_category(checkout):
    root, _ = checkout
    (root / 'mode').write_text('attach-once')
    run, _ = fix_tests.select(root)
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit', 'unit', 'ui', 'system', 'e2e', 'all']
    assert all(call['kind'] == 'test' for call in calls)


def test_stale_runner_uses_existing_recovery_route_then_retries_category(checkout):
    root, _ = checkout
    (root / 'mode').write_text('retention-once')
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['args'] for call in calls] == [
        ['--stop-on-error', 'unit'],
        [],
        ['--stop-on-error', 'unit'],
        ['--stop-on-error', 'unit'],
    ]
    assert calls[1]['kind'] == 'recovery'
    assert 'recovering both retention scopes' in output.getvalue()
    assert not [call for call in calls if call['kind'] == 'agent']


def test_recovery_failure_handoff_is_repaired_then_recovery_and_category_retry(checkout):
    root, _ = checkout
    (root / 'mode').write_text('retention-repair')
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [(call['kind'], call['category']) for call in calls] == [
        ('test', 'unit'),
        ('recovery', 'recovery'),
        ('agent', 'agent'),
        ('test', 'unit'),
        ('recovery', 'recovery'),
        ('test', 'unit'),
        ('test', 'unit'),
    ]
    agent = next(call for call in calls if call['kind'] == 'agent')
    assert agent['prompt'].startswith('LATEST RECOVERY FAILURE ONLY\n')
    assert output.getvalue().count('recovering both retention scopes') == 2
    from rich.text import Text
    transcript = Text.from_ansi(output.getvalue()).plain
    assert 'Formatted repair' in transcript and '**Formatted repair**' not in transcript
    assert 'def repaired():' in transcript and '```' not in transcript
    assert 'agent stderr diagnostic' in transcript
    assert '\033[' in (run / 'output').read_text()
    assert '--json' in agent['args']


def test_cancellation_during_recovery_waits_for_cleanup(checkout):
    root, _ = checkout
    (root / 'mode').write_text('recovery-wait')
    run, _ = fix_tests.select(root, categories=('unit',))
    wait_for(root / 'test-ready')
    assert fix_tests.select(root, stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    assert (root / 'test-interrupted').exists()
    assert (root / 'test-cleaned').exists()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'recovery']


@pytest.mark.parametrize('categories', [('host',), ('unit', 'ui'), ('unit ui',)])
def test_selected_categories_stay_scoped_through_worker_and_repair(checkout, categories):
    root, _ = checkout
    (root / 'mode').write_text('agent-repeat')
    run, _ = fix_tests.select(root, categories=categories)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls if call['kind'] == 'test'] == [
        'unit', 'unit', 'unit', 'ui', 'unit', 'ui']
    assert len([call for call in calls if call['kind'] == 'agent']) == 2
    assert 'all selected categories passed' in output.getvalue()


def test_repeated_repairs_are_distinct_processes_with_no_accumulated_prompt(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-repeat')
    run, _ = fix_tests.select(root)
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == 2 and agents[0]['pid'] != agents[1]['pid']
    for index, agent in enumerate(agents, 1):
        assert agent['prompt'].startswith(f'LATEST FAILURE ONLY {index}\n')
        assert agent['prompt'].count('LATEST FAILURE ONLY') == 1
        assert 'PREVIOUS AGENT TRANSCRIPT' not in agent['prompt']
        assert agent['thread'] is None
        assert '--ephemeral' in agent['args']
        assert not {'resume', 'fork', '--last'} & set(agent['args'])


def test_discovered_arguments_reach_each_test_without_reconstruction(checkout):
    root, _ = checkout
    (root / 'mode').write_text('pass')
    (root / 'inventory.json').write_text(json.dumps({
        'e2e': {'args': []}, 'future-suite': {'args': ['--case', 'two words']},
        'unit': {'args': ['--future-option']}}))
    run, _ = fix_tests.select(root)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['args'] for call in calls] == [
        ['--stop-on-error', 'unit', '--future-option'],
        ['--stop-on-error', 'future-suite', '--case', 'two words'],
        ['--stop-on-error', 'e2e'], ['--stop-on-error', 'all']]
    marker = '\033[1;36mRunning category [future-suite] (2/3)\033[0m'
    text = output.getvalue()
    assert marker in text
    assert text.rfind('Overall - ', 0, text.index(marker)) >= 0


@pytest.mark.parametrize('reason', ['cancel-marker', 'parent-death'])
def test_supervisor_does_not_spawn_work_after_startup_cancellation(checkout, reason):
    root, _ = checkout
    run = fix_tests.private_directory(root / 'cancelled-run')
    if reason == 'cancel-marker':
        (run / 'cancel').touch()
    read_fd, write_fd = os.pipe()
    if reason == 'parent-death':
        os.close(write_fd)
    try:
        with lock(run / 'owner') as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            child = subprocess.Popen(
                [sys.executable, '-IBu', str(ROOT / 'tools/fix_tests.py'), '--supervise',
                 str(root), str(run), str(owner), 'test', 'unit',
                 fix_tests.DEFAULT_MODEL, fix_tests.DEFAULT_EFFORT],
                stdin=read_fd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                pass_fds=(owner,), start_new_session=True)
            output, _ = child.communicate(timeout=10)
            assert child.returncode == 130, output.decode()
        assert not (root / 'calls').exists()
    finally:
        os.close(read_fd)
        if reason != 'parent-death':
            os.close(write_fd)
