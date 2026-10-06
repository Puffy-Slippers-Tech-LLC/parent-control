"""Real detach, cancellation and restart paths using private process doubles."""
from tests.support.vm_registry import vm_name

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
from rich.text import Text

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
        if '--worker' in args[0]:
            spawned.append(child)
        return child

    monkeypatch.setattr(fix_tests.subprocess, 'Popen', record)
    yield tmp_path, spawned
    from test_storage import directory
    for path in (tmp_path / 'artifacts/fix-tests', directory('fix-tests', root=tmp_path),
                 directory('fix-tests-host', root=tmp_path)):
        run = fix_tests.current_run(path)
        if run is not None:
            (run / 'cancel').touch()
    (tmp_path / 'release').touch()
    for child in spawned:
        child.wait(timeout=20)


@pytest.mark.parametrize('rounds', [1, 2, 3])
def test_worker_round_count_and_top_frame(checkout, rounds):
    root, _ = checkout
    (root / 'mode').write_text('pass')
    run, _ = fix_tests.select(root, categories=('unit',), rounds=rounds)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit'] * rounds
    progress = json.loads((run / 'controller.json').read_text())
    assert [step['lines'][0] for step in progress] == [
        f'Round {number}: Category: unit (1/1)' for number in range(max(1, rounds - 1), rounds + 1)]
    rendered = Text.from_ansi(output.getvalue()).plain
    assert all(f'Round {number}: Category: unit' in rendered
               for number in range(1, rounds + 1))


def test_resume_after_cancellation_keeps_passed_category_and_fresh_run_resets(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=[], tests=[None, None], wait_test=1)))
    run, _ = fix_tests.select(root, categories=('unit', 'ui'))
    wait_for(root / 'test-ready')
    assert fix_tests.select(root, categories=('unit', 'ui'), stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    (root / 'mode').write_text('pass')
    resumed, started = fix_tests.select(root, categories=('unit', 'ui'), resume=True)
    assert started and resumed != run
    assert fix_tests.follow(resumed, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit', 'ui', 'ui']
    assert '--resume' in calls[-1]['args']
    fresh, started = fix_tests.select(root, categories=('unit', 'ui'))
    assert started and fix_tests.follow(fresh, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit', 'ui', 'ui', 'unit', 'ui']
    assert all('--resume' not in call['args'] for call in calls[-2:])


def test_resume_interrupted_clean_verification_repeats_the_whole_pass(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=[None, None, None, 'ui-case', None, None], wait_test=5)))
    run, _ = fix_tests.select(root, categories=('unit', 'ui'), rounds=2)
    wait_for(root / 'test-ready')
    assert fix_tests.select(root, categories=('unit', 'ui'), stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    from test_checkpoint import Checkpoint
    checkpoint = Checkpoint(root, [('unit', []), ('ui', [])],
                            namespace='fix-tests', resume=True)
    assert not checkpoint.complete('unit') and not checkpoint.complete('ui')
    assert checkpoint.state['round'] == 2 and checkpoint.state['pending'] == 'unit'
    (root / 'mode').write_text('pass')
    resumed, started = fix_tests.select(root, categories=('unit', 'ui'), rounds=2, resume=True)
    assert started and fix_tests.follow(resumed, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    tests = [call for call in calls if call['kind'] == 'test']
    assert [call['category'] for call in tests] == ['unit', 'ui', 'unit', 'ui', 'ui', 'unit', 'unit', 'ui']
    assert '--resume' in tests[-2]['args'] and '--resume' not in tests[-1]['args']


def test_host_and_vm_repair_runs_have_independent_owners_and_cancellation(checkout):
    root, spawned = checkout
    host, host_started = fix_tests.select(root, categories=('host',))
    vm, vm_started = fix_tests.select(root, categories=('vm',))
    assert host_started and vm_started and host != vm
    deadline = time.monotonic() + 12
    while not (host / 'last-test.log').exists() or not (vm / 'last-test.log').exists():
        assert time.monotonic() < deadline
        time.sleep(.02)
    assert fix_tests.select(root, categories=('host',)) == (host, False)
    assert fix_tests.select(root, categories=('vm',)) == (vm, False)
    assert fix_tests.select(root, categories=('host',), stop=True) == (host, False)
    assert fix_tests.follow(host, io.StringIO()) == 130
    assert not (vm / 'cancel').exists()
    assert all(child.poll() is None for child in spawned if str(vm) in child.args)
    (root / 'release').touch()
    assert fix_tests.follow(vm, io.StringIO()) == 0


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
    assert fix_tests.select(root, rounds=2) == (run, False)
    assert spawned[0].poll() is None
    assert fix_tests.select(root, stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    assert (root / 'test-interrupted').exists() and (root / 'test-cleaned').exists()


@pytest.mark.parametrize('action', ['stop', 'ctrl-c', 'kill-owner'])
def test_cancellation_waits_for_runner_cleanup_then_fresh_start(checkout, monkeypatch, action):
    root, spawned = checkout
    run, _ = fix_tests.select(root, rounds=2)
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
        assert fix_tests.main(['--vm', vm_name(), *(['--stop'] if action == 'stop' else [])]) == 130
    assert (root / 'test-cleaned').exists()
    (root / 'mode').write_text('pass')
    # Remove the main-only hook; this is a new caller after ownership is idle.
    if action != 'kill-owner':
        monkeypatch.setattr(fix_tests, 'select', select)
    next_run, started = fix_tests.select(root, rounds=2)
    assert started and next_run != run
    # Use the implementation, not the Ctrl+C hook, for the new observer.
    if action == 'ctrl-c':
        monkeypatch.setattr(fix_tests, 'follow', follow)
    assert fix_tests.follow(next_run, io.StringIO()) == 0
    assert (run / 'output').exists()


@pytest.mark.parametrize('mode,expected', [('agent-pass', 0), ('agent-invalid', 1)])
def test_real_script_uses_fresh_agent_prompt_and_granular_rounds(checkout, mode, expected):
    root, _ = checkout
    (root / 'mode').write_text(mode)
    run, _ = fix_tests.select(root, rounds=2)
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
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    if mode == 'agent-invalid':
        assert usage[0]['event'] == 'missing_usage' and usage[0]['usage'] is None
        assert not any(row['event'] == 'verification' for row in usage)
    executed = [call['category'] for call in calls if call['kind'] == 'test']
    assert executed == (['unit', 'unit', 'ui', 'system', 'e2e', 'all'] if expected == 0 else ['unit'])
    assert 'Traceback' not in output.getvalue()
    assert 'PRIVATE REASONING FIXTURE' not in output.getvalue()
    rendered = Text.from_ansi(output.getvalue()).plain
    assert 'Explored' in rendered
    assert 'Read example.py' in rendered
    assert 'Result · source' not in rendered
    assert 'Exit 0' not in rendered
    assert 'display lines omitted' not in rendered
    assert '+24 lines' not in rendered
    source = '\n'.join(f'if value == {number}: return True' for number in range(30))
    assert all(line not in rendered for line in source.splitlines())
    assert (run / 'agent-commands.log').read_text() == (
        f'\nCommand source: cat example.py\n{source}\nExit: 0\n')


@pytest.mark.parametrize('mode', ['agent-blocked', 'agent-app-blocked', 'agent-blocked-twice'])
@pytest.mark.parametrize('custom', [False, True])
def test_blocker_waits_for_reattached_menu_answer_before_repair_or_tests(checkout, monkeypatch,
                                                                     mode, custom):
    from launcher_render import LauncherDisplay
    root, spawned = checkout
    (root / 'mode').write_text(mode)
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',))
    wait_for(run / 'question.json')
    before = (root / 'calls').read_text()
    # No terminal, timeout or preselected recommendation may authorize work.
    time.sleep(.2)
    assert (root / 'calls').read_text() == before
    assert spawned[0].poll() is None
    assert not (run / 'result.json').exists()
    assert json.loads((run / 'question.json').read_text())['answer'] is None
    assert fix_tests.select(root, categories=('host',)) == (run, False)
    answered = []

    def type_answer(display):
        if display.question is not None and not display.question.sent:
            answered.append(display.question.question['id'])
            assert display.question.selected == 0
            display.question.feed(b'3Preserve the requirement; repair the product.\r'
                                  if custom else b'\r')

    monkeypatch.setattr(LauncherDisplay, 'poll_input', type_answer)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    assert len(set(answered)) == (2 if mode == 'agent-blocked-twice' else 1)
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert [call['kind'] for call in calls] == ['test'] + ['agent'] * len(agents) + ['test', 'test']
    assert len(agents) == (2 if mode == 'agent-blocked' else 3)
    assert len({agent['pid'] for agent in agents}) == len(agents)
    answer = 'Preserve the requirement; repair the product.' if custom else 'Restore the specified behavior.'
    assert answer in agents[-1]['prompt']
    assert 'fixture result' in agents[-1]['prompt']
    assert all(agent['prompt'].startswith('LATEST FAILURE ONLY\n') for agent in agents)
    assert all(agent['args'][agent['args'].index('--model') + 1] == 'gpt-6.1-sol'
               for agent in agents)
    efforts = (['medium', 'high', 'high'] if mode == 'agent-app-blocked'
               else ['medium'] * len(agents))
    for agent, effort in zip(agents, efforts):
        assert f'model_reasoning_effort="{effort}"' in agent['args']
    assert len(json.loads((run / 'developer-answers.json').read_text())) == len(answered)
    rendered = Text.from_ansi(output.getvalue()).plain
    assert 'No timeout. Reattach with tools/fix-tests host' in rendered
    assert 'Answer received. Continuing this repair.' in rendered


def test_stop_while_awaiting_developer_never_runs_repair_or_tests(checkout):
    root, spawned = checkout
    (root / 'mode').write_text('agent-blocked')
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',))
    wait_for(run / 'question.json')
    before = (root / 'calls').read_text()
    assert fix_tests.select(root, categories=('host',), stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    spawned[0].wait(timeout=5)
    assert (root / 'calls').read_text() == before
    assert json.loads((run / 'question.json').read_text())['answer'] is None


@pytest.mark.parametrize('kill_owner', [False, True])
def test_agent_stop_terminates_its_group_and_preserves_unrelated_sentinel(checkout, kill_owner):
    root, spawned = checkout
    (root / 'mode').write_text('agent-wait')
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
    sentinel_fd = os.pidfd_open(sentinel.pid)
    try:
        run, _ = fix_tests.select(root, rounds=2)
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
    run, started = fix_tests.select(root, rounds=2)
    assert started and fix_tests.follow(run, io.StringIO()) == 0
    assert fix_tests.select(root, stop=True) == (None, False)


def test_unread_predecessor_result_does_not_count_as_the_requested_category(checkout):
    root, _ = checkout
    (root / 'mode').write_text('attach-once')
    run, _ = fix_tests.select(root, rounds=2)
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit', 'unit', 'ui', 'system', 'e2e', 'all']
    assert all(call['kind'] == 'test' for call in calls)


@pytest.mark.parametrize('scope', ['host', 'vm', 'batch'])
def test_stale_runner_uses_existing_recovery_route_then_retries_category(checkout, monkeypatch, scope):
    from vm_selection import VARIABLE, execution_selection
    vm_args = []
    if scope == 'host':
        monkeypatch.delenv(VARIABLE, raising=False)
    elif scope == 'batch':
        _, vms = execution_selection()
        vm_args = ['--vm', ','.join(vm.name for vm in vms)]
    else:
        vm_args = ['--vm', vm_name()]
    root, _ = checkout
    (root / 'mode').write_text('retention-once')
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    recovery_args = ['--host-only'] if scope == 'host' else vm_args
    assert [call['args'] for call in calls] == [
        ['--stop-on-error', 'unit', *vm_args], recovery_args,
        ['--stop-on-error', 'unit', *vm_args], ['--stop-on-error', 'unit', *vm_args]]
    assert calls[1]['kind'] == 'recovery'
    assert ('recovering host retention' if scope == 'host' else
            'recovering both retention scopes') in output.getvalue()
    assert 'Traceback' not in output.getvalue()
    assert not [call for call in calls if call['kind'] == 'agent']


def test_recovery_failure_handoff_is_repaired_then_recovery_and_category_retry(checkout):
    root, _ = checkout
    (root / 'mode').write_text('retention-repair')
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',))
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
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',))
    wait_for(root / 'test-ready')
    assert fix_tests.select(root, categories=('host',), stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130
    assert (root / 'test-interrupted').exists()
    assert (root / 'test-cleaned').exists()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'recovery']


@pytest.mark.parametrize('categories', [('host',), ('unit', 'ui'), ('unit ui',)])
def test_selected_categories_stay_scoped_through_worker_and_repair(checkout, categories):
    root, _ = checkout
    (root / 'mode').write_text('agent-repeat')
    run, _ = fix_tests.select(root, rounds=2, categories=categories)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls if call['kind'] == 'test'] == [
        'unit', 'unit', 'unit', 'ui', 'unit', 'ui']
    assert len([call for call in calls if call['kind'] == 'agent']) == 2
    assert 'all selected categories passed' in output.getvalue()


@pytest.mark.parametrize('options', [
    ['-k', 'unit or component', '-q', '--tb=short'],
    ['tests/unit/test_selected.py::test_case[has spaces]', '--durations', '2'],
])
def test_category_arguments_survive_worker_repairs_and_verification(checkout, options):
    root, _ = checkout
    tests = root / 'tests/unit'
    tests.mkdir(parents=True)
    (tests / 'test_selected.py').write_text('def test_case(): pass\n')
    (root / 'mode').write_text('agent-repeat')
    run, _ = fix_tests.select(root, rounds=3, categories=['unit', *options])
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    tests = [call for call in calls if call['kind'] == 'test']
    assert len(tests) == 5  # Initial attempt, two repair retries, two verification rounds.
    assert [call['args'] for call in tests] == [
        [*(['--resume'] if index in (1, 2) else []), '--stop-on-error', 'unit',
         *options, '--vm', vm_name()] for index in range(5)]
    assert len([call for call in calls if call['kind'] == 'agent']) == 2


def test_repeated_repairs_are_distinct_processes_with_no_accumulated_prompt(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-repeat')
    run, _ = fix_tests.select(root, rounds=2)
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == 2 and agents[0]['pid'] != agents[1]['pid']
    assert [agent['args'][agent['args'].index('--model') + 1] for agent in agents] == [
        'gpt-6.1-sol', 'gpt-6.1-sol']
    assert 'model_reasoning_effort="medium"' in agents[0]['args']
    assert 'model_reasoning_effort="high"' in agents[1]['args']
    assert 'verification_failed: fixture result' in agents[1]['prompt']
    records = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turns = [row for row in records if row['event'] == 'turn']
    assert len(turns) == 2
    assert turns[0]['repair_id'] == turns[1]['repair_id']
    assert turns[0]['session_id'] != turns[1]['session_id']
    assert [row['attempt'] for row in turns] == [1, 2]
    assert all(row['usage'] == {'input_tokens': 100, 'cached_input_tokens': 40,
                                'output_tokens': 20} for row in turns)
    assert [row['passed'] for row in records if row['event'] == 'verification'] == [False, True]
    assert [row['result'] for row in records if row['event'] == 'result'] == ['test_fixed', 'fixed']
    for index, agent in enumerate(agents, 1):
        assert agent['prompt'].startswith(f'LATEST FAILURE ONLY {index}\n')
        assert agent['prompt'].count('LATEST FAILURE ONLY') == 1
        assert 'PREVIOUS AGENT TRANSCRIPT' not in agent['prompt']
        assert agent['thread'] is None
        assert '--ephemeral' in agent['args']
        assert not {'resume', 'fork', '--last'} & set(agent['args'])


@pytest.mark.parametrize('options', [{'effort': 'high'}, {'model': 'gpt-6.1-sol', 'effort': 'xhigh'},
                                    {'model': 'gpt-6-astra', 'effort': 'low'}])
def test_initial_override_preserves_requested_model_and_effort_standard(checkout, options):
    root, _ = checkout
    (root / 'mode').write_text('agent-pass')
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',), **options)
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agent, = [call for call in calls if call['kind'] == 'agent']
    assert agent['args'][agent['args'].index('--model') + 1] == options.get('model', 'gpt-6.1-sol')
    assert f'model_reasoning_effort="{options["effort"]}"' in agent['args']
    assert 'service_tier="default"' in agent['args'] and 'features.fast_mode=false' in agent['args']


@pytest.mark.parametrize('statuses,tests,expected', [
    (['test_fixed'] + ['fixed'] * 4, ['case-A'] * 6, 1),
    (['uncertain'] + ['fixed'] * 4, ['case-A'] * 5, 1),
    (['test_fixed'] + ['fixed'] * 4, ['case-A'] * 5 + [None], 0),
    (['test_fixed', 'fixed'] * 6,
     [f'case-{index // 2}' for index in range(12)] + [None], 0),
    (['test_fixed', 'fixed'] * 3,
     [dict(category='e2e', case='case-A', vm=f'guest-{index // 2}')
      for index in range(6)] + [None], 0),
    (['test_fixed'] * 2 + ['fixed'] * 8,
     [f'case-{index % 2}' for index in range(11)], 1),
    (['uncertain', 'stalled', 'stalled', 'stalled'], ['case-A'], 1),
])
def test_repair_budget_is_per_case_and_stalled_diagnosis_stops_early(checkout, statuses, tests, expected):
    root, spawned = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({'agents': statuses, 'tests': tests}))
    category = tests[0]['category'] if isinstance(tests[0], dict) else 'unit'
    run, _ = fix_tests.select(root, categories=(category,))
    spawned[-1].wait(timeout=20)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == expected
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == len(statuses)
    assert len(calls) == len(statuses) + len(tests)
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turns = [row for row in usage if row['event'] == 'turn']
    assert all(row['repair_session'] <= 5 for row in turns)
    for row, agent in zip(turns, agents):
        effort = ('medium', 'high', 'high', 'xhigh', 'xhigh')[row['repair_session'] - 1]
        assert f'model_reasoning_effort="{effort}"' in agent['args']
    if expected and statuses[-1] != 'stalled':
        assert 'repair session limit reached (5/5)' in output.getvalue()
        assert usage[-1]['event'] == 'session_limit'
        assert (run / 'last-test.log').exists() and (run / 'agent-result.json').exists()
        stopped = json.loads((run / 'repair-stop.json').read_text())
        assert stopped['reason'] == 'session_limit' and stopped['sessions'] == 5
        assert stopped['failure'] == usage[-1]['failure']
        last_case_session = max(index for index, row in enumerate(turns, 1)
                                if row['failure'] == stopped['failure'])
        assert stopped['result']['summary'] == f'fixture result {last_case_session}'
    if statuses[-1] == 'stalled':
        assert 'repair stalled' in output.getvalue()
        assert json.loads((run / 'repair-stop.json').read_text())['reason'] == 'stalled'


def test_answered_blockers_use_case_budget_and_do_not_ask_after_limit(checkout, monkeypatch):
    from launcher_render import LauncherDisplay
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({'agents': ['blocked'] * 5, 'tests': ['case-A']}))
    run, _ = fix_tests.select(root, categories=('unit',))
    answers = []
    def answer(display):
        if display.question is not None and not display.question.sent:
            answers.append(display.question.question['id'])
            display.question.feed(b'\r')
    monkeypatch.setattr(LauncherDisplay, 'poll_input', answer)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1
    assert len(set(answers)) == 4
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test'] + ['agent'] * 5
    assert 'repair session limit reached (5/5)' in output.getvalue()


def test_later_verification_round_does_not_reset_case_budget(checkout):
    root, spawned = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({'agents': ['test_fixed'] + ['fixed'] * 4,
        'tests': ['case-A'] * 5 + [None, 'case-A']}))
    run, _ = fix_tests.select(root, categories=('unit',), rounds=2)
    spawned[-1].wait(timeout=20)
    assert fix_tests.follow(run, io.StringIO()) == 1
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert len([call for call in calls if call['kind'] == 'agent']) == 5
    assert len([call for call in calls if call['kind'] == 'test']) == 7


@pytest.mark.parametrize('statuses, tests, options, tiers', [
    (['uncertain', 'stalled', 'fixed'], ['A', None], {},
     [('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'high'), ('gpt-6-astra', 'high')]),
    (['uncertain', 'fixed', 'fixed', 'fixed'], ['A', 'A', 'A', None], {},
     [('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'high'),
      ('gpt-6-astra', 'high'), ('gpt-6-astra', 'xhigh')]),
    (['uncertain', 'fixed'], ['A', None], {'model': 'gpt-6-astra', 'effort': 'high'},
     [('gpt-6-astra', 'high'), ('gpt-6-astra', 'high')]),
    (['stalled'], ['A'], {'model': 'gpt-6-astra', 'effort': 'xhigh'},
     [('gpt-6-astra', 'xhigh')]),
    (['uncertain', 'stalled', 'fixed'], ['A', None], {'effort': 'xhigh'},
     [('gpt-6.1-sol', 'xhigh'), ('gpt-6.1-sol', 'xhigh'), ('gpt-6-astra', 'xhigh')]),
])
def test_escalation_uses_stronger_serial_sessions_and_preserves_overrides(
        checkout, statuses, tests, options, tiers):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({'agents': statuses, 'tests': tests}))
    run, _ = fix_tests.select(root, categories=('unit',), **options)
    assert fix_tests.follow(run, io.StringIO()) == (1 if statuses[-1] == 'stalled' else 0)
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == len(tiers)
    assert len({call['pid'] for call in agents}) == len(agents)
    for agent, (model, effort) in zip(agents, tiers):
        assert agent['args'][agent['args'].index('--model') + 1] == model
        assert f'model_reasoning_effort="{effort}"' in agent['args']
        assert 'service_tier="default"' in agent['args']
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    transitions = [row for row in rows if row['event'] == 'tier_transition']
    assert [(row['model'], row['effort']) for row in transitions] == [
        tier for previous, tier in zip(tiers, tiers[1:]) if tier != previous]
    assert all(row['reason'] in ('uncertain', 'stalled', 'same_case_verification_failed')
               for row in transitions)


@pytest.mark.parametrize('interruption', ['B', ''])
def test_other_case_or_preparation_failure_keeps_repair_unknown(checkout, interruption):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['uncertain', 'fixed', 'test_fixed', 'fixed'],
        'tests': ['A', interruption, 'A', None]}))
    run, _ = fix_tests.select(root, categories=('unit',))
    assert fix_tests.follow(run, io.StringIO()) == 0
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    verification = [row for row in rows if row['event'] == 'verification']
    assert verification[0]['failure']['case'] == 'A'
    assert verification[0]['passed'] is None
    assert verification[0]['outcome'] == 'unknown_or_not_executed'
    turns = [row for row in rows if row['event'] == 'turn']
    assert [(row['failure']['case'], row['model'], row['effort']) for row in turns] == [
        ('A', 'gpt-6.1-sol', 'medium'), ('A', 'gpt-6.1-sol', 'high'),
        (interruption, 'gpt-6.1-sol', 'medium'), ('A', 'gpt-6-astra', 'high')]


@pytest.mark.parametrize('observations', [['A', 'A', None], ['A', None, None],
                                        ['A', '', 'A', None]])
def test_diagnostic_experiment_retains_evidence_and_selectors_without_repair_claim(checkout, observations):
    root, _ = checkout
    (root / 'tests/unit').mkdir(parents=True)
    (root / 'tests/unit/test_selected.py').write_text('def test_selected(): pass\n')
    (root / 'mode').write_text('agent-script')
    statuses = ['diagnostic_ready', 'fixed'] if len(observations) == 3 else [
        'diagnostic_ready', 'test_fixed', 'fixed']
    (root / 'script.json').write_text(json.dumps({'agents': statuses, 'tests': observations}))
    run, _ = fix_tests.select(root, categories=('unit', '-k', 'selected', '-q'))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert 'diagnostic evidence: fixture result 1' in agents[-1]['prompt']
    assert 'Launcher-owned diagnostic execution outcome:' in agents[-1]['prompt']
    assert 'verification_failed:' not in agents[-1]['prompt']
    assert all('model_reasoning_effort="medium"' in call['args'] for call in agents)
    tests = [call for call in calls if call['kind'] == 'test']
    retries = ['A', '', 'A'] if len(observations) == 4 else ['A', 'A']
    assert [call['args'] for call in tests] == [
        ['--stop-on-error', 'unit', '-k', 'selected', '-q', '--vm', vm_name()],
        *[['--resume', '--stop-on-error', 'unit', '-k', 'selected', '-q',
           *(['--resume-case=' + case] if case else []), '--vm', vm_name()]
          for case in retries]]
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    diagnostics = [row for row in rows if row['event'] == 'diagnostic_execution']
    assert diagnostics and all(row['failure']['case'] == 'A' for row in diagnostics)
    assert diagnostics[0]['passed'] == (False if observations[1] == 'A' else
                                        True if observations[1] is None else None)
    for row in diagnostics:
        evidence = Path(row['evidence_path'])
        assert evidence.parent == run
        assert json.loads(evidence.read_text())['output_tail']
    assert diagnostics[-1]['evidence_path'] in agents[-1]['prompt']


def test_astra_blocker_continuation_keeps_tier_and_counts_diagnostic_session(checkout, monkeypatch):
    from launcher_render import LauncherDisplay
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['uncertain', 'stalled', 'blocked', 'diagnostic_ready', 'fixed'],
        'tests': ['A', 'A', None]}))
    def answer(display):
        if display.question is not None and not display.question.sent:
            display.question.feed(b'\r')
    monkeypatch.setattr(LauncherDisplay, 'poll_input', answer)
    run, _ = fix_tests.select(root, categories=('unit',))
    assert fix_tests.follow(run, io.StringIO()) == 0
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turns = [row for row in rows if row['event'] == 'turn']
    assert [row['repair_session'] for row in turns] == [1, 2, 3, 4, 5]
    assert [(row['model'], row['effort']) for row in turns[2:]] == [('gpt-6-astra', 'high')] * 3
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert 'Restore the specified behavior.' in agents[3]['prompt']
    assert 'case session 5/5; 0 further agent sessions remain' in agents[4]['prompt']


def test_diagnostic_budget_exhaustion_runs_last_experiment_but_no_sixth_agent(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['diagnostic_ready'] * 5, 'tests': ['A'] * 6}))
    run, _ = fix_tests.select(root, categories=('unit',))
    assert fix_tests.follow(run, io.StringIO()) == 1
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert len([row for row in rows if row['event'] == 'diagnostic_execution']) == 5
    assert rows[-1]['event'] == 'session_limit'
    assert not any(row['event'] == 'verification' for row in rows)


def test_diagnostic_execution_cancellation_finishes_owned_cleanup(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['diagnostic_ready'], 'tests': ['A', 'A'], 'wait_test': 1}))
    run, _ = fix_tests.select(root, categories=('unit',))
    wait_for(root / 'test-ready')
    fix_tests.select(root, categories=('host',), stop=True)
    assert fix_tests.follow(run, io.StringIO()) == 130
    assert (root / 'test-interrupted').exists() and (root / 'test-cleaned').exists()
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert not any(row['event'] in ('verification', 'diagnostic_execution') for row in rows)


def test_missing_required_model_refuses_before_any_test_or_agent(checkout, monkeypatch):
    root, spawned = checkout
    monkeypatch.chdir(root)
    (root / 'catalog.json').write_text(json.dumps({'models': [{
        'slug': 'gpt-6.1-sol', 'visibility': 'list',
        'supported_reasoning_levels': [{'effort': 'medium'}, {'effort': 'high'}]}]}))
    with pytest.raises(ValueError, match='gpt-6-astra with high reasoning'):
        fix_tests.select(root, categories=('unit',))
    assert not spawned and not (root / 'calls').exists()


@pytest.mark.parametrize('mode, classification', [
    ('agent-app', 'app_issue'), ('agent-uncertain', 'uncertain')])
def test_app_or_uncertain_classification_starts_fresh_sol_high_agent(checkout, mode,
                                                                   classification):
    root, _ = checkout
    (root / 'mode').write_text(mode)
    run, _ = fix_tests.select(root, rounds=2, categories=('unit',))
    assert fix_tests.follow(run, io.StringIO()) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == 2 and agents[0]['pid'] != agents[1]['pid']
    assert [agent['args'][agent['args'].index('--model') + 1] for agent in agents] == [
        'gpt-6.1-sol', 'gpt-6.1-sol']
    assert 'model_reasoning_effort="medium"' in agents[0]['args']
    assert 'model_reasoning_effort="high"' in agents[1]['args']
    assert all('service_tier="default"' in agent['args'] and 'features.fast_mode=false' in agent['args']
               for agent in agents)
    assert agents[1]['prompt'].startswith('LATEST FAILURE ONLY\n')
    assert f'{classification}: fixture result' in agents[1]['prompt']
    assert 'PREVIOUS AGENT TRANSCRIPT' not in agents[1]['prompt']
    assert '--ephemeral' in agents[1]['args']
    assert not {'resume', 'fork', '--last'} & set(agents[1]['args'])


def test_discovered_arguments_reach_each_test_without_reconstruction(checkout):
    root, _ = checkout
    (root / 'mode').write_text('pass')
    (root / 'inventory.json').write_text(json.dumps({
        'e2e': {'args': []}, 'future-suite': {'args': ['--case', 'two words']},
        'unit': {'args': ['--future-option']}}))
    run, _ = fix_tests.select(root, rounds=2)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['args'] for call in calls] == [
        ['--stop-on-error', 'e2e', '--vm', vm_name()],
        ['--stop-on-error', 'future-suite', '--case', 'two words', '--vm', vm_name()],
        ['--stop-on-error', 'unit', '--future-option', '--vm', vm_name()],
        ['--stop-on-error', 'all', '--vm', vm_name()]]
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
                 'gpt-6-sol', fix_tests.DEFAULT_EFFORT],
                stdin=read_fd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                pass_fds=(owner,), start_new_session=True)
            output, _ = child.communicate(timeout=10)
            assert child.returncode == 130, output.decode()
        assert not (root / 'calls').exists()
    finally:
        os.close(read_fd)
        if reason != 'parent-death':
            os.close(write_fd)
