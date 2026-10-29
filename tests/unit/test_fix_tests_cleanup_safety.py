"""Real detach, cancellation and restart paths using private process doubles."""
from tests.support.vm_registry import vm_name

from concurrent.futures import ThreadPoolExecutor
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import shutil
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
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, capture_output=True,
                              text=True, check=True, timeout=10)
    git('init', '-q')
    git('config', 'user.name', 'Repair launcher test')
    git('config', 'user.email', 'repair@example.invalid')
    (tmp_path / '.gitignore').write_text('*\n!.gitignore\n!owned.py\n!repair-*.py\n')
    (tmp_path / 'owned.py').write_text('original\n')
    git('add', '--', '.gitignore', 'owned.py')
    git('commit', '-qm', 'Initial fixture')
    remote = tmp_path / 'remote.git'
    git('init', '--bare', '-q', str(remote))
    git('remote', 'add', 'origin', str(remote))
    git('push', '-qu', 'origin', 'HEAD')
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
        if '--worker' in args[0]:
            # Keep real launcher ownership, but route VM reservations through
            # the harmless child double rather than the installed host helper.
            command = list(args[0])
            command[2] = str(ROOT / 'tests/support/fix_tests_child.py')
            args = (command, *args[1:])
            kwargs['env'] = dict(kwargs.get('env', os.environ),
                                 ONPC_FIXTURE_RUN=command[command.index('--worker') + 2])
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


@pytest.fixture
def controller_checkout(checkout):
    import repair_evidence
    root, _ = checkout
    source_root = root / 'controller'
    (source_root / 'tools').mkdir(parents=True)
    for name in repair_evidence.controller_sources():
        destination = source_root / 'tools' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'tools' / name, destination)
    (root / 'controller-root').write_text(str(source_root))
    (root / 'tests/unit').mkdir(parents=True)
    return checkout


@pytest.mark.parametrize('result', ['test_fixed', 'invalid-status', 'malformed', 'blocked'])
def test_changed_dependency_bytes_reload_before_validation_retry_or_answer_continuation(controller_checkout, result):
    from launcher_question import submit

    root, _ = controller_checkout
    source_root = Path((root / 'controller-root').read_text())
    script = dict(agents=['invalid-status' if result == 'malformed' else result], tests=['A', None])
    if result != 'test_fixed':
        script['agents'].append('test_fixed')
    if result == 'malformed':
        script['raw_response'] = '{not valid JSON'
    if result != 'blocked':
        script['change_source'] = 'repair_evidence.py'
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(script))
    run, _ = fix_tests.select(root, categories=('unit',))
    if result == 'blocked':
        wait_for(run / 'question.json')
        source = source_root / 'tools/repair_evidence.py'
        source.write_bytes(source.read_bytes() + b'\n# changed after blocker\n')
        from launcher_reload import request
        request(run)
        question = json.loads((run / 'question.json').read_text())
        assert submit(run, question['id'], 0)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    assert 'manual reload requested' in output.getvalue()
    assert 'Reloading controller in the same run' in output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == (
        ['test', 'agent', 'test', 'test'] if result == 'test_fixed' else ['test', 'agent', 'agent', 'test', 'test'])
    state = json.loads((run / 'checkpoint.json').read_text())
    assert list(state['session_counts'].values()) == [1 if result == 'test_fixed' else 2]
    assert 'controller_restart' in state
    assert not state.get('turns')
    assert not list(run.glob('specialized-turn-*.json'))
    if result == 'malformed':
        assert (run / 'rejected-agent-result.json').read_text() == '{not valid JSON'
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert [row['repair_session'] for row in usage if row['event'] == 'turn'] == (
        [1] if result == 'test_fixed' else [1, 2])
    if result in ('invalid-status', 'malformed'):
        assert 'controller rejected' in calls[2]['prompt']
        assert 'model_reasoning_effort="low"' in calls[2]['args']
    reloads = [json.loads(line) for line in (root / 'reloads').read_text().splitlines()]
    assert len({item['pid'] for item in reloads}) == 1
    assert all(item['inherited'] for item in reloads)
    assert subprocess.run(['git', 'log', '-1', '--format=%s', '@{upstream}'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout.strip() == 'TA: Fixed unit A'
    assert state['repairs'] == {}
    limits = json.loads((run / 'limits.json').read_text())
    assert limits['started'] == limits['completed'] == 1
    if result == 'blocked':
        continuation = state['controller_restart']['continuation']
        assert continuation['result']['status'] == 'blocked'
        assert continuation['failure'] == dict(category='unit', case='A', vm='')
        assert json.loads((run / 'developer-answers.json').read_text()) == continuation['answers']
        assert 'Restore the specified behavior.' in calls[2]['prompt']
        assert 'Previous attempt paused with this handoff:\nfixture result 1' in calls[2]['prompt']


def test_reload_preserves_diagnostic_execution_and_interpretation(controller_checkout):
    root, _ = controller_checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['diagnostic_ready', 'test_fixed'], tests=['A', None, None],
        change_source='repair_evidence.py', change_test_source=[1])))
    run, _ = fix_tests.select(root, categories=('unit', '-k', 'selected'), tasks=1)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent', 'test', 'agent', 'test', 'test']
    assert 'Interpret these observations' in calls[3]['prompt']
    assert all('-k' in call['args'] and 'selected' in call['args'] for call in calls if call['kind'] == 'test')
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert len([row for row in usage if row['event'] == 'diagnostic_execution']) == 1
    assert [row['repair_session'] for row in usage if row['event'] == 'turn'] == [1, 2]
    limits = json.loads((run / 'limits.json').read_text())
    assert limits['started'] == limits['completed'] == 1


@pytest.mark.parametrize('rounds,tests', [(1, ['A', None]), (2, [None, None])])
def test_reload_retains_completed_runner_output_and_rounds(controller_checkout, rounds, tests):
    root, _ = controller_checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=tests, change_test_source=list(range(len(tests))))))
    run, _ = fix_tests.select(root, categories=('unit', '-k', 'selected'), rounds=rounds)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert len([call for call in calls if call['kind'] == 'test']) == (3 if rounds == 1 else 2)
    assert all('selected' in call['args'] for call in calls if call['kind'] == 'test')
    limits = json.loads((run / 'limits.json').read_text())
    assert limits['started'] == limits['completed'] == rounds


def test_repeated_reload_cannot_renew_case_budget(controller_checkout):
    root, _ = controller_checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['invalid-status'] * 6, tests=['A'], change_source='repair_evidence.py')))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1, output.getvalue()
    assert 'session allowance exhausted (5/5)' in output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert len([call for call in calls if call['kind'] == 'agent']) == 5
    assert json.loads((run / 'repair-stop.json').read_text())['sessions'] == 5


def test_reload_after_owned_recovery_continues_original_category(controller_checkout):
    root, _ = controller_checkout
    (root / 'mode').write_text('retention-once')
    (root / 'change-recovery-source').touch()
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'recovery', 'test']


def test_reload_keeps_classification_and_failed_verification_tiers(controller_checkout):
    root, _ = controller_checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['app_issue', 'test_fixed', 'test_fixed'], tests=['A', 'A', None],
        change_source='repair_evidence.py')))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert [row['effort'] for row in usage if row['event'] == 'turn'] == ['low', 'medium', 'high']
    assert [row['repair_session'] for row in usage if row['event'] == 'turn'] == [1, 2, 3]


def test_reload_keeps_owner_and_honors_cancellation_before_more_work(controller_checkout):
    root, _ = controller_checkout
    (root / 'mode').write_text('agent-script')
    (root / 'pause-reload').touch()
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['A'], change_source='repair_evidence.py')))
    run, _ = fix_tests.select(root, categories=('unit',))
    wait_for(root / 'reloads')
    attached, started = fix_tests.select(root, categories=('unit',))
    assert attached == run and not started
    assert not (run / 'result.json').exists()
    (run / 'cancel').touch()
    (root / 'release').touch()
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 130, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent']


def test_failed_agent_stops_once_and_explicit_fresh_run_can_retry(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    script = dict(agents=['test_fixed', 'test_fixed'], tests=['A', None], agent_exit=7)
    (root / 'script.json').write_text(json.dumps(script))
    first, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(first, output) == 1
    assert 'repair agent exited with status 7' in output.getvalue()
    original = json.loads((first / 'checkpoint.json').read_text())
    assert all('pending_response' not in entry for entry in original['repairs'].values())
    assert not original.get('turns')
    assert not list(first.glob('specialized-turn-*.json'))
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent']
    script.pop('agent_exit')
    (root / 'script.json').write_text(json.dumps(script))
    resumed, _ = fix_tests.select(root, categories=('unit',), resume=True)
    output = io.StringIO()
    assert fix_tests.follow(resumed, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent', 'agent', 'test', 'test']
    usage = [json.loads(line) for line in (resumed / 'agent-usage.jsonl').read_text().splitlines()]
    assert [row['repair_session'] for row in usage if row['event'] == 'turn'] == [1]
    assert json.loads((resumed / 'checkpoint.json').read_text())['repairs'] == {}


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
    assert [Text.from_ansi(step['lines'][0]).plain for step in progress] == [
        f'Round {number}: Category: unit (1/1)' for number in range(max(1, rounds - 1), rounds + 1)]
    rendered = Text.from_ansi(output.getvalue()).plain
    assert all(f'Round {number}: Category: unit' in rendered
               for number in range(1, rounds + 1))


def test_verified_case_is_pushed_before_repairing_the_next_failure(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed', 'test_fixed'], tests=['A', 'B', 'B', None],
        passed={'1': ['A']}, record_git=True)))
    # Unrelated staged work must survive both commits.
    (root / 'owned.py').write_text('unrelated staged work\n')
    subprocess.run(['git', 'add', '--', 'owned.py'], cwd=root, check=True, timeout=10)
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert [call['pushed_subject'] for call in agents] == ['Initial fixture', 'TA: Fixed unit A']
    log = subprocess.run(['git', 'log', '-2', '--format=%s', '@{upstream}'], cwd=root,
                         capture_output=True, text=True, check=True, timeout=10).stdout.splitlines()
    assert log == ['TA: Fixed unit B', 'TA: Fixed unit A']
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=root,
                            capture_output=True, text=True, check=True, timeout=10).stdout
    assert staged == 'owned.py\n'
    assert (root / 'owned.py').read_text() == 'unrelated staged work\n'


def test_case_closeout_finishes_before_remaining_tests_start(checkout, monkeypatch):
    from vm_selection import BATCH, execution_selection
    root, _ = checkout
    _, vms = execution_selection()
    assert len(vms) == 2
    # Both harmless pipeline doubles must fail before the shared repair starts;
    # the development host's real VM concurrency may intentionally be only one.
    monkeypatch.setenv(BATCH, json.dumps({'concurrency': 2, 'vms': [vm.name for vm in vms]}))
    (root / 'mode').write_text('vm-pipeline')
    # The synthetic runner's cases need the same identity lookup input as a
    # real checkout now that per-case progress resolves public case metadata.
    identities = root / 'tests/integration/system_case_ids.py'
    identities.parent.mkdir(parents=True)
    identities.write_text(
        'from types import SimpleNamespace\n'
        'CASES = {name: SimpleNamespace(numeric_id=index, title=name)\n'
        '         for index, name in enumerate(("installed::case-a", "installed::case-b"), 1)}\n'
        'def identity_for_event(nodeid):\n'
        '    return CASES.get(nodeid)\n')
    (root / 'inventory.json').write_text(json.dumps({'system': {'scope': 'vm', 'args': []}}))
    run, _ = fix_tests.select(root, categories=('system',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == 1  # Both failed cases use the first verified shared fix.
    tests = [call for call in calls if call['kind'] == 'test']
    for vm in vms:
        selected = [call for call in tests if call['vm'] == vm.name]
        assert len(selected) == 3
        assert all('--resume-case-only' in call['args'] for call in selected)
        assert '--resume-case=installed::case-b' in selected[-1]['args']
    states = json.loads((run / 'pipelines.json').read_text())
    assert all(state['status'] == 'complete' for state in states.values())
    assert json.loads((run / 'repair-queue.json').read_text()) == []
    assert not (run / 'repair-pending.json').exists()


def test_failed_push_resumes_before_remaining_tests_without_duplicate_commit(checkout):
    root, _ = checkout
    hook = root / 'remote.git/hooks/pre-receive'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o700)
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(agents=['test_fixed'], tests=['A', None])))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1
    assert 'completion push failed' in output.getvalue()
    accepted = json.loads((run / 'checkpoint.json').read_text())
    assert accepted['pending'] and accepted['commit_intent']
    from fix_tests_queue import resumed_source_owner, source_directory
    fence = source_directory(root) / 'repair-source-pending.json'
    original_owner = {'run': str(run)}
    assert json.loads(fence.read_text()) == original_owner
    # A legacy interrupted resume copied ownership without transferring its
    # source fence. Recover only identical repairs with the original identity.
    stranded = fix_tests.private_directory(run.parent / 'stranded')
    fix_tests.atomic(stranded / 'repair-pending.json', {'run': '.'})
    copied = dict(accepted, controller_restart={'run': str(run)})
    assert resumed_source_owner(root, stranded, '.', copied) == original_owner
    assert resumed_source_owner(root, stranded, '.', dict(copied, repairs={})) is None
    # A second interruption must carry the handoff without needing old reports.
    fix_tests.atomic(stranded / 'repair-source-resume.json', original_owner)
    assert resumed_source_owner(root, stranded, '.', {}) == original_owner
    before = (root / 'calls').read_text()
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout
    hook.unlink()
    resumed, started = fix_tests.select(root, categories=('unit',), resume=True)
    output = io.StringIO()
    assert started and fix_tests.follow(resumed, output) == 0, output.getvalue()
    assert json.loads((resumed / 'repair-source-resume.json').read_text()) == original_owner
    assert not fence.exists()
    after = (root / 'calls').read_text()
    assert after.startswith(before)
    remaining, = [json.loads(line) for line in after[len(before):].splitlines()]
    assert remaining['kind'] == 'test' and '--resume' in remaining['args']
    assert not any(arg.startswith('--resume-case=') for arg in remaining['args'])
    assert subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout == head
    assert subprocess.run(['git', 'rev-parse', '@{upstream}'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout == head
    assert json.loads((resumed / 'checkpoint.json').read_text())['repairs'] == {}


def test_verified_push_retry_ignores_expired_proof_before_remaining_tests(checkout):
    root, _ = checkout
    hook = root / 'remote.git/hooks/pre-receive'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o700)
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['A', None])))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1, output.getvalue()
    assert 'completion push failed' in output.getvalue()
    state = json.loads((run / 'checkpoint.json').read_text())
    entry = state['repairs'][state['pending']]
    entry['failure_attempts'] = [dict(handoffs=[dict(path='/expired/report.json')])]
    entry['verification_attempt']['handoffs'] = [dict(path='/expired/pass.json')]
    state['turns'] = [dict(path='/expired/turn.json', sha256='old')]
    fix_tests.atomic(run / 'checkpoint.json', state)
    before = (root / 'calls').read_bytes()
    hook.unlink()
    resumed, _ = fix_tests.select(root, categories=('unit',), resume=True)
    output = io.StringIO()
    assert fix_tests.follow(resumed, output) == 0, output.getvalue()
    after = (root / 'calls').read_bytes()
    assert after.startswith(before)
    remaining, = [json.loads(line) for line in after[len(before):].splitlines()]
    assert remaining['kind'] == 'test' and '--resume' in remaining['args']
    assert not any(arg.startswith('--resume-case=') for arg in remaining['args'])
    carried = json.loads((resumed / 'checkpoint.json').read_text())
    assert carried['repairs'] == {} and carried['runner_attempt']['status'] == 0
    assert not carried.get('turns')
    assert not list(resumed.glob('runner-evidence-*.json'))
    (root / 'mode').write_text('pass')
    fresh, _ = fix_tests.select(root, categories=('unit',))
    assert fix_tests.follow(fresh, io.StringIO()) == 0
    unrelated = json.loads((fresh / 'checkpoint.json').read_text())
    assert unrelated['runner_attempt']['status'] == 0
    assert not unrelated.get('turns') and 'session_counts' not in unrelated
    assert 'controller_restart' not in unrelated
    assert json.loads((resumed / 'checkpoint.json').read_text()) == carried


def test_noncase_repair_commits_after_its_bounded_case_pass_without_archives(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['', None], verification_case=None)))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    state = json.loads((run / 'checkpoint.json').read_text())
    assert state['repairs'] == {} and state['runner_attempt']['status'] == 0
    assert 'pending' not in state
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent', 'test', 'test']
    assert '--resume-case=verification::case' in calls[2]['args']
    assert '--resume-case-only' in calls[2]['args']
    assert '--resume' in calls[3]['args']
    assert '--resume-case-only' not in calls[3]['args']
    assert subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout.strip() == 'TA: Fixed unit infrastructure'


@pytest.mark.parametrize('staged', [False, True])
def test_repair_closeout_refuses_preexisting_owned_work(checkout, staged):
    root, _ = checkout
    (root / 'owned.py').write_text('preexisting work\n')
    if staged:
        subprocess.run(['git', 'add', '--', 'owned.py'], cwd=root, check=True, timeout=10)
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['A', None], repair_path='owned.py')))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1
    assert 'close-out overlaps pre-existing work: owned.py' in output.getvalue()
    assert subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout.strip() == 'Initial fixture'


@pytest.mark.parametrize('baseline', ['clean', 'dirty', 'staged', 'intervening'])
def test_pending_repair_recovers_only_proven_launcher_owned_baselines(checkout, baseline):
    from fix_tests_git import RepairCommits
    from launcher_git import worktree_snapshot

    root, _ = checkout
    run = root / 'closeout'
    run.mkdir()
    if baseline in ('dirty', 'staged'):
        (root / 'owned.py').write_text('preexisting work\n')
    if baseline == 'staged':
        subprocess.run(['git', 'add', '--', 'owned.py'], cwd=root, check=True, timeout=10)
    commits = RepairCommits(root, run)
    for number, case in enumerate(('A', 'B', 'C')):
        if baseline == 'intervening' and number == 1:
            (root / 'owned.py').write_text('unrelated edit between sessions\n')
        target = ('unit', case, '')
        commits.begin(target)
        before = worktree_snapshot(root)
        (root / 'owned.py').write_text(f'launcher edit {number}\n')
        commits.capture_session(target, before)
        commits.record(target, dict(status='test_fixed' if case == 'C' else 'diagnostic_ready',
                                    stage_paths=['owned.py']))
    # The old controller stopped here after verification. Reuse its checkpoint
    # unchanged, including the original diagnostic fingerprints and baselines.
    commits.state['pending'] = commits.key(target)
    commits.save()
    retained = json.loads((run / 'checkpoint.json').read_text())
    if baseline == 'clean':
        RepairCommits(root, run).finish_pending()
        state = json.loads((run / 'checkpoint.json').read_text())
        assert 'pending' not in state
        for key, entry in state['repairs'].items():
            assert entry == retained['repairs'][key]
        assert subprocess.run(['git', 'show', '@{upstream}:owned.py'], cwd=root,
                              capture_output=True, text=True, check=True, timeout=10).stdout == 'launcher edit 2\n'
    else:
        with pytest.raises(ValueError, match='close-out overlaps pre-existing work: owned.py'):
            RepairCommits(root, run).finish_pending()
        state = json.loads((run / 'checkpoint.json').read_text())
        assert state['repairs'] == retained['repairs'] and state['pending'] == retained['pending']
        assert 'commit_intent' not in state
        assert subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=root, capture_output=True,
                              text=True, check=True, timeout=10).stdout.strip() == 'Initial fixture'


def test_diagnostic_overlap_verifies_once_and_resumes_failed_push(checkout):
    root, _ = checkout
    hook = root / 'remote.git/hooks/pre-receive'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o700)
    (root / 'repair-unrelated.py').write_text('unrelated staged work\n')
    subprocess.run(['git', 'add', '--', 'repair-unrelated.py'], cwd=root, check=True, timeout=10)
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['diagnostic_ready', 'diagnostic_ready', 'test_fixed'], tests=['A', 'B', 'C', None],
        repair_path='owned.py', record_git=True)))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1, output.getvalue()
    assert 'recovered launcher-owned overlap: owned.py' in output.getvalue()
    assert 'completion push failed' in output.getvalue()
    calls = (root / 'calls').read_bytes()
    agents = [json.loads(line) for line in calls.splitlines() if json.loads(line)['kind'] == 'agent']
    assert [call['pushed_subject'] for call in agents] == ['Initial fixture'] * 3

    def recovery_details(path):
        state = json.loads((path / 'checkpoint.json').read_text())
        loop = state.get('controller_restart', {}).get('runtime', {}).get('loop', {})
        return dict(
            pending=state.get('pending'),
            queued_failures=state.get('queued_failure', {}).get('failure', {}).get('failures', []),
            repairs=[dict(failure=entry['failure'], status=entry.get('status'),
                          pending_response=entry.get('pending_response') is not None)
                     for entry in state['repairs'].values()],
            loop_phase=loop.get('phase'),
            handoffs=[dict(failure=key, status=value.get('status'),
                           verification=value.get('verification'),
                           has_evidence_path=bool(value.get('evidence_path')))
                      for key, value in loop.get('handoffs', [])])

    # Expose only this fixture's control metadata on failure, so a restart's
    # selected repair can be compared with the pending push and diagnostic loop.
    before_resume = recovery_details(run)
    hook.unlink()
    resumed, _ = fix_tests.select(root, categories=('unit',), resume=True)
    output = io.StringIO()
    status = fix_tests.follow(resumed, output)
    assert status == 0, output.getvalue() + '\nRecovery diagnostics: ' + json.dumps(dict(
        before_resume=before_resume, after_resume=recovery_details(resumed)), sort_keys=True)
    after = (root / 'calls').read_bytes()
    assert after.startswith(calls)
    remaining, = [json.loads(line) for line in after[len(calls):].splitlines()]
    assert remaining['kind'] == 'test' and remaining['pushed_subject'] == 'TA: Fixed unit C'
    assert subprocess.run(['git', 'show', '@{upstream}:owned.py'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout == 'fixture repair 3\n'
    assert subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout == 'repair-unrelated.py\n'
    assert (root / 'repair-unrelated.py').read_text() == 'unrelated staged work\n'


def test_diagnostics_and_failed_verification_are_never_committed(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['diagnostic_ready', 'fixed', 'fixed'], tests=['A', None, 'A', None], record_git=True)))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    agents = [json.loads(line) for line in (root / 'calls').read_text().splitlines()
              if json.loads(line)['kind'] == 'agent']
    assert [call['pushed_subject'] for call in agents] == ['Initial fixture'] * 3
    assert subprocess.run(['git', 'rev-list', '--count', 'HEAD'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout.strip() == '2'


@pytest.mark.parametrize('failure', ['stage', 'commit', 'push', 'after_commit', 'propagate'])
def test_repair_git_recovers_each_interrupted_closeout_step(checkout, monkeypatch, failure):
    import fix_tests_git
    import launcher_git
    root, _ = checkout
    run = root / 'closeout'
    run.mkdir()
    commits = fix_tests_git.RepairCommits(root, run)
    target = ('unit', 'A', '')
    commits.begin(target)
    (root / 'owned.py').write_text('validated fix\n')
    commits.record(target, dict(status='test_fixed', stage_paths=['owned.py']))
    original_git = fix_tests_git.git_output
    def reject(*args, **kwargs):
        raise ValueError('injected Git interruption')
    def interrupted_git(root, *args, **kwargs):
        if failure == 'commit' and 'commit' in args:
            return subprocess.CompletedProcess(args, 1, '', 'injected Git interruption')
        if failure == 'push' and args == ('push',):
            return subprocess.CompletedProcess(args, 1, '', 'injected Git interruption')
        result = original_git(root, *args, **kwargs)
        if failure == 'after_commit' and 'commit' in args:
            raise OSError('injected Git interruption')
        return result
    with monkeypatch.context() as patch:
        if failure == 'stage':
            patch.setattr(fix_tests_git, 'stage_task', reject)
        elif failure == 'propagate':
            patch.setattr(launcher_git, '_propagate_worktrees', reject)
        else:
            patch.setattr(fix_tests_git, 'git_output', interrupted_git)
        with pytest.raises((OSError, ValueError), match='injected Git interruption'):
            commits.verified(target)
    fix_tests_git.RepairCommits(root, run).finish_pending()
    assert subprocess.run(['git', 'rev-list', '--count', '@{upstream}'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout.strip() == '2'
    assert json.loads((run / 'checkpoint.json').read_text())['repairs'] == {}


@pytest.mark.parametrize('change', ['content', 'mode'])
def test_repair_git_accepts_changed_validated_files(checkout, change):
    from fix_tests_git import RepairCommits
    root, _ = checkout
    run = root / 'closeout'
    run.mkdir()
    commits = RepairCommits(root, run)
    target = ('unit', 'A', '')
    commits.begin(target)
    (root / 'owned.py').write_text('validated fix\n')
    commits.record(target, dict(status='fixed', stage_paths=['owned.py']))
    if change == 'content':
        (root / 'owned.py').write_text('untested change\n')
    else:
        (root / 'owned.py').chmod(0o700)
    commits.verified(target)
    assert subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout.strip() == 'TA: Fixed unit A'


def test_category_success_without_the_repaired_case_pass_cannot_commit(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['A', None], unexecuted=['A'])))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1
    assert 'repair case has no confirmed pass' in output.getvalue()
    assert subprocess.run(['git', 'log', '-1', '--format=%s'], cwd=root, capture_output=True,
                          text=True, check=True, timeout=10).stdout.strip() == 'Initial fixture'
    script = json.loads((root / 'script.json').read_text())
    script.pop('unexecuted')
    script['tests'].append(None)
    (root / 'script.json').write_text(json.dumps(script))
    resumed, _ = fix_tests.select(root, categories=('unit',), resume=True)
    output = io.StringIO()
    assert fix_tests.follow(resumed, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    # The refused verification and its resumed retry both stop at A. Only
    # after A earns a pass may the launcher resume the remaining category.
    assert [call['kind'] for call in calls] == ['test', 'agent', 'test', 'test', 'test']
    for call in calls[2:4]:
        assert '--resume-case=A' in call['args']
        assert '--resume-case-only' in call['args']
    assert '--resume' in calls[4]['args']
    assert '--resume-case-only' not in calls[4]['args']
    assert subprocess.run(['git', 'log', '-1', '--format=%s', '@{upstream}'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout.strip() == 'TA: Fixed unit A'


def test_unreported_repair_edits_include_all_changes_and_accept_external_commit(checkout):
    from fix_tests_git import RepairCommits
    from launcher_git import worktree_snapshot

    root, _ = checkout
    (root / 'owned.py').write_text('preexisting unstaged work\n')
    (root / 'repair-unrelated.py').write_text('preexisting staged work\n')
    subprocess.run(['git', 'add', '--', 'repair-unrelated.py'], cwd=root, check=True, timeout=10)
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['A', None], omit_paths_once=True)))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent', 'test', 'test']
    assert 'including all checkout changes after case verification' in output.getvalue()
    for path, content in (('owned.py', 'preexisting unstaged work\n'),
                          ('repair-unrelated.py', 'preexisting staged work\n')):
        assert subprocess.run(['git', 'show', '@{upstream}:' + path], cwd=root,
                              capture_output=True, text=True, check=True, timeout=10).stdout == content
    assert worktree_snapshot(root) == {}

    # Another owner can commit the captured changes before verified close-out.
    commits = RepairCommits(root, run)
    target = ('unit', 'B', '')
    commits.begin(target)
    before = worktree_snapshot(root)
    (root / 'owned.py').write_text('externally committed repair\n')
    commits.capture_session(target, before)
    result = dict(status='test_fixed', stage_paths=[])
    commits.validate_paths(target, result)
    commits.record(target, result)
    subprocess.run(['git', 'add', '--', 'owned.py'], cwd=root, check=True, timeout=10)
    subprocess.run(['git', 'commit', '-qm', 'External repair'], cwd=root, check=True, timeout=10)
    head = subprocess.run(['git', 'rev-parse', 'HEAD', '@{upstream}'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout
    RepairCommits(root, run).verified(target)
    assert subprocess.run(['git', 'rev-parse', 'HEAD', '@{upstream}'], cwd=root,
                          capture_output=True, text=True, check=True, timeout=10).stdout == head
    state = json.loads((run / 'checkpoint.json').read_text())
    assert state['repairs'] == {} and 'pending' not in state and 'commit_intent' not in state


@pytest.mark.parametrize('next_category', [False, True])
def test_repair_panel_uses_shared_metadata_clocks_and_resets_for_next_category(
        checkout, monkeypatch, next_category):
    from launcher_chat import read_state, task_info
    from launcher_display import TaskDisplay
    from launcher_progress import read_progress
    from tests.support.terminal_screen import Terminal

    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['failed-case', None, None], wait_test=1,
        panel_updates=[{'explanation': 'Checks that repairs preserve the expected results.',
                        'status': 'Root cause identified, fixing'}])))
    run, _ = fix_tests.select(root, categories=('unit', 'ui') if next_category else ('unit',))
    wait_for(root / 'test-ready')
    before = task_info(run, '1:unit')
    assert before['last_error'] == 'The unit checks did not pass.'
    assert before['status'] == 'Testing fix, previous error point not reached yet'
    assert 'LAUNCHER_STATUS' not in (run / 'output').read_text()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert 'LAUNCHER_STATUS' in next(call['prompt'] for call in calls if call['kind'] == 'agent')

    # Both clocks refresh without output and reconnect from owner metadata.
    now = max(before['last_error_at'], before['status_at']) + 72 * 60
    monkeypatch.setattr('launcher_display.time.time', lambda: now)
    for minute in range(2):
        terminal = Terminal(400, 55)
        display = TaskDisplay(terminal, run=run, input_mode='question',
                              terminal_size=lambda: terminal.size)
        display.refresh_chat()
        display.update(read_progress(run), [])
        text = terminal.visible()
        assert f'Last Error: The unit checks did not pass. (1h {12 + minute}m ago)' in text
        assert f'Status: Testing fix, previous error point not reached yet (1h {12 + minute}m ago)' in text
        now += 60

    (root / 'release').touch()
    assert fix_tests.follow(run, io.StringIO()) == 0
    after = task_info(run, '1:unit')
    assert after['last_error_at'] == before['last_error_at']
    assert after['status'] == 'Testing fix, previous error point passed'
    assert after['status_at'] >= before['status_at']
    if next_category:
        assert read_state(run)['task_id'] == '1:ui'
        assert task_info(run, '1:ui')['status'] == 'Running'
        assert 'last_error' not in task_info(run, '1:ui')


def test_diagnostic_execution_does_not_claim_a_verified_fix(checkout):
    from launcher_chat import task_info
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['diagnostic_ready', 'test_fixed'],
        tests=['failed-case', None, None], wait_test=1)))
    run, _ = fix_tests.select(root, categories=('unit',))
    wait_for(root / 'test-ready')
    assert task_info(run, '1:unit')['status'] == 'Investigating'
    (root / 'release').touch()
    assert fix_tests.follow(run, io.StringIO()) == 0
    assert task_info(run, '1:unit')['status'] == 'Testing fix, previous error point passed'


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


def test_resume_after_session_limit_retains_completed_diagnostic_categories(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['uncertain', 'diagnostic_ready', 'diagnostic_ready', 'diagnostic_ready', 'stalled'],
        tests=[None, 'reminder-case', None, None, None])))
    categories = ('unit', 'ui', 'system')
    run, _ = fix_tests.select(root, categories=categories)
    assert fix_tests.follow(run, io.StringIO()) == 1
    stopped = json.loads((run / 'repair-stop.json').read_text())
    assert stopped['reason'] == 'session_limit' and stopped['sessions'] == 5
    from test_checkpoint import Checkpoint
    checkpoint = Checkpoint(root, [(kind, []) for kind in categories],
                            namespace='fix-tests', resume=True)
    assert checkpoint.complete('unit') and checkpoint.complete('ui')
    # Exhausting diagnostic interpretation fails the case, but later categories
    # still run and completed diagnostic categories retain their runner passes.
    assert checkpoint.complete('system')
    failed = json.loads((run / 'checkpoint.json').read_text())['failed_cases']
    assert len(failed) == 1
    assert failed[0]['failure'] == ['ui', 'reminder-case', '']
    assert failed[0]['reason'] == 'session allowance exhausted (5/5)'
    evidence_marker = 'Retained private failure context (bounded log tails): '
    evidence_path = Path(failed[0]['prompt'].split(evidence_marker, 1)[1].splitlines()[0])
    evidence = json.loads(evidence_path.read_text())
    from fix_tests_queue import error_log
    errors = error_log(run).read_text()
    assert 'reminder-case' in errors and 'session allowance exhausted (5/5)' in errors
    before_resume = (root / 'calls').read_text()
    (root / 'mode').write_text('pass')
    resumed, started = fix_tests.select(root, categories=categories, resume=True)
    output = io.StringIO()
    assert started and fix_tests.follow(resumed, output) == 1
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    tests = [call['category'] for call in calls if call['kind'] == 'test']
    # Initial UI failure, three diagnostic runs, then continuation of the
    # remaining UI selection after the case exhausts its allowance.
    assert tests == ['unit', 'ui', 'ui', 'ui', 'ui', 'ui', 'system']
    assert (root / 'calls').read_text() == before_resume
    assert len([call for call in calls if call['kind'] == 'agent']) == 5
    assert 'retaining passed categories: unit, ui, system.' in output.getvalue()
    # Resume copies retained evidence into its new run and updates that reference;
    # the full failure record and evidence contents must otherwise stay intact.
    resumed_evidence = resumed / evidence_path.relative_to(run)
    expected_failed = [dict(failed[0], prompt=failed[0]['prompt'].replace(
        evidence_marker + str(evidence_path), evidence_marker + str(resumed_evidence), 1))]
    assert json.loads((resumed / 'checkpoint.json').read_text())['failed_cases'] == expected_failed
    assert json.loads(resumed_evidence.read_text()) == evidence
    assert error_log(resumed).read_text() == errors
    assert json.loads((run / 'repair-stop.json').read_text()) == stopped


def test_resume_interrupted_clean_verification_repeats_the_whole_pass(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=[None, None, None, 'ui-case', None, None, None], wait_test=6)))
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
    assert [call['category'] for call in tests] == ['unit', 'ui', 'unit', 'ui', 'ui', 'ui', 'unit', 'unit', 'ui']
    assert '--resume' in tests[-2]['args'] and '--resume' not in tests[-1]['args']


@pytest.mark.parametrize('replacement', [[('ui', [])], [('unit', ['-k', 'unrelated'])]])
def test_repair_replays_original_selection_after_another_run_replaces_checkpoint(checkout, replacement):
    root, _ = checkout
    (root / 'tests/unit').mkdir(parents=True)
    (root / 'tests/unit/test_selected.py').write_text('def test_selected(): pass\n')
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['failed-case', None],
        checkpoint=[('unit', ['-k', 'selected', '-q'])], replace_checkpoint=replacement)))
    run, _ = fix_tests.select(root, categories=('unit', '-k', 'selected', '-q'))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    tests = [call for call in calls if call['kind'] == 'test']
    original = ['--stop-on-error', 'unit', '-k', 'selected', '-q', '--vm', vm_name()]
    changed_selectors = replacement[0][0] == 'unit'
    assert [call['args'] for call in tests] == [
        original, ['--resume', *original[:-2], '--resume-case=failed-case', '--resume-case-only', *original[-2:]],
        original if changed_selectors else ['--resume', *original]]
    assert len([call for call in calls if call['kind'] == 'agent']) == 1
    assert ('replaying the requested category from the start with its original selectors'
            in output.getvalue()) == changed_selectors
    from test_checkpoint import Checkpoint
    checkpoint = Checkpoint(root, [('unit', ['-k', 'selected', '-q'])], resume=True)
    assert checkpoint.passed('unit') == {'earlier-pass', 'failed-case'}


def test_repair_does_not_reset_an_invalid_checkpoint(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['failed-case'], checkpoint=[('unit', [])],
        replace_checkpoint=[('unit', [])], invalid_checkpoint=True)))
    run, _ = fix_tests.select(root, categories=('unit',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent', 'test']
    assert 'invalid resume checkpoint' in output.getvalue()
    assert 'replaying the requested category' not in output.getvalue()


def test_vm_repair_does_not_reset_checkpoints_after_selection_mismatch(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['test_fixed'], tests=['failed-case'], checkpoint=[('system', [])],
        replace_checkpoint=[('system', ['--area', 'other'])])))
    run, _ = fix_tests.select(root, categories=('system',))
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 1
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in calls] == ['test', 'agent', 'test']
    assert 'resume selection differs from checkpoint' in output.getvalue()
    assert 'replaying the requested category' not in output.getvalue()


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


def test_reserved_driver_cannot_join_a_repair_waiting_for_its_checkout(checkout, monkeypatch):
    import vm_pool
    root, spawned = checkout
    run, started = fix_tests.select(root)
    assert started
    monkeypatch.setenv(vm_pool.VARIABLE,
                       'f95890e1-88e7-4779-8ae3-53fdcc34330a:' + 'a' * 32)
    with pytest.raises(ValueError, match='another reservation'):
        fix_tests.select(root)
    assert len(spawned) == 1
    assert fix_tests.select(root, stop=True) == (run, False)
    assert fix_tests.follow(run, io.StringIO()) == 130


@pytest.mark.parametrize('action', ['stop', 'ctrl-c', 'kill-owner'])
def test_cancellation_waits_for_runner_cleanup_then_fresh_start(checkout, monkeypatch, action):
    from vm_selection import WORKER

    # This fixture starts a single worker directly, rather than a public VM
    # queue. Keep the CLI observer in that same scope when it attaches.
    monkeypatch.setenv(WORKER, '1')
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
    assert len(agents) == (5 if mode == 'agent-invalid' else 1)
    assert agents[0]['thread'] is None
    assert agents[0]['frame_directory'] is None
    assert all(call['frame_directory'] == str(run) for call in calls if call['kind'] == 'test')
    assert json.loads((run / 'frame.json').read_text()) == []
    assert agents[0]['prompt'].startswith('LATEST FAILURE ONLY\n')
    assert 'PREVIOUS AGENT TRANSCRIPT' not in agents[0]['prompt']
    assert '--ephemeral' not in agents[0]['args']
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    if mode == 'agent-invalid':
        assert usage[0]['event'] == 'missing_usage' and usage[0]['usage'] is None
        assert not any(row['event'] == 'verification' for row in usage)
        assert all('controller rejected' in agent['prompt'] for agent in agents[1:])
        assert all('model_reasoning_effort="low"' in agent['args'] for agent in agents)
        assert (run / 'rejected-agent-result.json').read_text() == '[]'
        assert json.loads((run / 'repair-stop.json').read_text())['sessions'] == 5
    executed = [call['category'] for call in calls if call['kind'] == 'test']
    # Exhausting one failure's allowance still drains independent categories
    # in both rounds, without retrying or accepting the exhausted failure.
    assert executed == (['unit', 'unit', 'unit', 'ui', 'system', 'e2e', 'all'] if expected == 0
                        else ['unit', 'ui', 'system', 'e2e', 'ui', 'system', 'e2e'])
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
        f'\nCommand source: cat example.py\n{source}\nExit: 0\n') * len(agents)


def test_rejected_handoff_is_corrected_before_verification_without_promotion(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(
        agents=['invalid-status', 'test_fixed'], tests=['one-case', None])))
    run, _ = fix_tests.select(root, categories=('unit',))
    assert fix_tests.follow(run, io.StringIO()) == 0
    invocations = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['kind'] for call in invocations] == ['test', 'agent', 'agent', 'test', 'test']
    agents = [call for call in invocations if call['kind'] == 'agent']
    assert 'controller rejected' in agents[1]['prompt']
    assert 'fixture result 1' in agents[1]['prompt']
    assert all('model_reasoning_effort="low"' in call['args'] for call in agents)
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert len([row for row in usage if row['event'] == 'verification']) == 1
    assert not any(row['event'] == 'tier_transition' for row in usage)


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
    if mode == 'agent-blocked' and custom:
        # Reuse this process boundary case to expire the real persisted prompt.
        from detached_launcher import atomic
        question = json.loads((run / 'question.json').read_text())
        assert 0 < question['deadline'] - time.time() <= 30 * 60
        atomic(run / 'question.json', dict(question, deadline=time.time() - 1))
        output = io.StringIO()
        assert fix_tests.follow(run, output) == 1
        calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
        assert [call['kind'] for call in calls] == ['test', 'agent']
        from fix_tests_queue import error_log
        errors = error_log(run).read_text()
        assert 'waiting for input: developer prompt timed out' in errors
        assert question['question'] in errors
        assert json.loads((run / 'question.json').read_text())['expired']
        assert json.loads((run / 'checkpoint.json').read_text())['repairs'] == {}
        return
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
    assert [call['kind'] for call in calls] == ['test'] + ['agent'] * len(agents) + ['test', 'test', 'test']
    assert len(agents) == (2 if mode == 'agent-blocked' else 3)
    assert len({agent['pid'] for agent in agents}) == len(agents)
    answer = 'Preserve the requirement; repair the product.' if custom else 'Restore the specified behavior.'
    assert answer in agents[-1]['prompt']
    assert 'fixture result' in agents[-1]['prompt']
    assert all(agent['prompt'].startswith('LATEST FAILURE ONLY\n') for agent in agents)
    assert all(agent['args'][agent['args'].index('--model') + 1] == 'gpt-6.1-sol'
               for agent in agents)
    efforts = (['low', 'medium', 'medium'] if mode == 'agent-app-blocked'
               else ['low'] * len(agents))
    for agent, effort in zip(agents, efforts):
        assert f'model_reasoning_effort="{effort}"' in agent['args']
    assert len(json.loads((run / 'developer-answers.json').read_text())) == len(answered)
    rendered = Text.from_ansi(output.getvalue()).plain
    assert 'Waiting up to ' in rendered
    assert 'Reattach with tools/fix-tests host' in rendered
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
    assert 'app-server' in agent['args']


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
        'unit', 'unit', 'unit', 'unit', 'ui', 'unit', 'ui']
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
    assert len(tests) == 6  # Initial, two bounded retries, remaining work, two rounds.
    assert [call['args'] for call in tests] == [
        [*(['--resume'] if index in (1, 2, 3) else []), '--stop-on-error', 'unit',
         *options, *(['--resume-case=verification::case', '--resume-case-only']
                    if index in (1, 2) else []), '--vm', vm_name()] for index in range(6)]
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
    assert 'model_reasoning_effort="low"' in agents[0]['args']
    assert 'model_reasoning_effort="medium"' in agents[1]['args']
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
        assert '--ephemeral' not in agent['args']
        assert not {'resume', 'fork', '--last'} & set(agent['args'])


@pytest.mark.parametrize('options', [{'effort': 'high'}, {'model': 'gpt-6.1-sol', 'effort': 'xhigh'},
                                    {'model': 'gpt-6.1-sol', 'effort': 'max'}])
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
    assert len(calls) == len(statuses) + len(tests) + 1
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turns = [row for row in usage if row['event'] == 'turn']
    assert all(row['repair_session'] <= 5 for row in turns)
    for row, agent in zip(turns, agents):
        ladder = (('low', 'medium', 'high', 'xhigh', 'xhigh') if category == 'unit'
                  else ('medium', 'high', 'xhigh', 'max', 'max'))
        effort = ladder[row['repair_session'] - 1]
        assert f'model_reasoning_effort="{effort}"' in agent['args']
    if expected and statuses[-1] != 'stalled':
        assert 'session allowance exhausted (5/5)' in output.getvalue()
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
    assert [call['kind'] for call in calls] == ['test'] + ['agent'] * 5 + ['test']
    assert 'session allowance exhausted (5/5)' in output.getvalue()


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
    assert len([call for call in calls if call['kind'] == 'test']) == 9


@pytest.mark.parametrize('category, statuses, tests, options, tiers', [
    ('ui', ['uncertain', 'stalled', 'fixed'], ['A', None], {},
     [('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'high'), ('gpt-6.1-sol', 'xhigh')]),
    ('ui', ['uncertain', 'fixed', 'fixed', 'fixed'], ['A', 'A', 'A', None], {},
     [('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'high'),
      ('gpt-6.1-sol', 'xhigh'), ('gpt-6.1-sol', 'max')]),
    ('unit', ['uncertain', 'stalled', 'fixed'], ['A', None], {},
     [('gpt-6.1-sol', 'low'), ('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'high')]),
    ('unit', ['uncertain', 'fixed', 'fixed', 'fixed'], ['A', 'A', 'A', None], {},
     [('gpt-6.1-sol', 'low'), ('gpt-6.1-sol', 'medium'),
      ('gpt-6.1-sol', 'high'), ('gpt-6.1-sol', 'xhigh')]),
    ('unit', ['uncertain', 'fixed'], ['A', None], {'effort': 'medium'},
     [('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'medium')]),
    ('unit', ['uncertain', 'fixed'], ['A', None], {'effort': 'high'},
     [('gpt-6.1-sol', 'high'), ('gpt-6.1-sol', 'high')]),
    ('unit', ['stalled'], ['A'], {'effort': 'max'},
     [('gpt-6.1-sol', 'max')]),
    ('unit', ['uncertain', 'fixed'], ['A', None], {'effort': 'max'},
     [('gpt-6.1-sol', 'max'), ('gpt-6.1-sol', 'max')]),
    ('unit', ['stalled'], ['A'], {'effort': 'xhigh'},
     [('gpt-6.1-sol', 'xhigh')]),
    ('ui', ['uncertain', 'stalled', 'fixed'], ['A', None], {'effort': 'xhigh'},
     [('gpt-6.1-sol', 'xhigh'), ('gpt-6.1-sol', 'xhigh'), ('gpt-6.1-sol', 'max')]),
])
def test_escalation_uses_stronger_serial_sessions_and_preserves_overrides(
        checkout, category, statuses, tests, options, tiers):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({'agents': statuses, 'tests': tests}))
    run, _ = fix_tests.select(root, categories=(category,), **options)
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
        ('A', 'gpt-6.1-sol', 'low'), ('A', 'gpt-6.1-sol', 'medium'),
        (interruption, 'gpt-6.1-sol', 'low'), ('A', 'gpt-6.1-sol', 'high')]


@pytest.mark.parametrize('categories', [('unit', 'ui'), ('host',), ('all',), ()])
def test_mixed_and_aggregate_runs_choose_ladder_per_failure_category(checkout, categories):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['uncertain', 'fixed', 'uncertain', 'fixed'],
        'tests': ['same-case', None, None, 'same-case', None, None, None, None]}))
    run, _ = fix_tests.select(root, categories=categories)
    assert fix_tests.follow(run, io.StringIO()) == 0
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turns = [row for row in rows if row['event'] == 'turn']
    assert [(row['failure']['category'], row['effort']) for row in turns] == [
        ('unit', 'low'), ('unit', 'medium'), ('ui', 'medium'), ('ui', 'high')]
    assert all(row['model'] == 'gpt-6.1-sol' for row in turns)


def test_aggregate_verification_unit_failure_uses_unit_ladder(checkout):
    root, _ = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['uncertain', 'fixed'],
        'tests': [None] * 4 + [dict(category='unit', case='A', vm=''), None, None]}))
    run, _ = fix_tests.select(root, rounds=2)
    assert fix_tests.follow(run, io.StringIO()) == 0
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turns = [row for row in rows if row['event'] == 'turn']
    assert [(row['failure']['category'], row['effort']) for row in turns] == [
        ('unit', 'low'), ('unit', 'medium')]


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
    assert all('model_reasoning_effort="low"' in call['args'] for call in agents)
    tests = [call for call in calls if call['kind'] == 'test']
    # An unidentified diagnostic failure retains the attempted case A. Its
    # bounded repair must use that case, ahead of the agent's fallback choice.
    retries = ['A', 'A', 'A'] if len(observations) == 4 else ['A', 'A']
    assert [call['args'] for call in tests] == [
        ['--stop-on-error', 'unit', '-k', 'selected', '-q', '--vm', vm_name()],
        *[[*(['--resume'] if case else []), '--stop-on-error', 'unit', '-k', 'selected', '-q',
           *(['--resume-case=' + case] if case else []),
           *(['--resume-case-only'] if index > 0 else []), '--vm', vm_name()]
          for index, case in enumerate(retries)],
        ['--resume', '--stop-on-error', 'unit', '-k', 'selected', '-q', '--vm', vm_name()]]
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


@pytest.mark.parametrize('resuming', [False, True])
def test_category_diagnostics_and_repairs_use_one_bounded_case(checkout, resuming):
    root, _ = checkout
    (root / 'tests/ui').mkdir(parents=True)
    (root / 'tests/ui/test_selected.py').write_text('def test_selected(): pass\n')
    (root / '.venv/onpc-ui-tests/bin').mkdir(parents=True)
    (root / '.venv/onpc-ui-tests/bin/python').symlink_to(sys.executable)
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps({
        'agents': ['diagnostic_ready', 'fixed'], 'tests': ['', None, None],
        # A removed preparation target must not pin selection or gain a verdict.
        'attempted_case': None if resuming else 'removed::case'}))
    if resuming:
        from test_checkpoint import Checkpoint
        # Startup can stop before the launcher records a pending category.
        Checkpoint(root, [('ui', ['--timeout', '1800s', '-m', 'not live_e2e'])],
                   namespace='fix-tests')
    run, _ = fix_tests.select(root, categories=('ui', '--timeout', '1800s', '-m', 'not live_e2e'),
                             resume=resuming)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0, output.getvalue()
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    tests = [call for call in calls if call['kind'] == 'test']
    original = ['--stop-on-error', 'ui', '--timeout', '1800s', '-m', 'not live_e2e',
                '--vm', vm_name()]
    assert [call['args'] for call in tests] == [
        [*(['--resume'] if resuming else []), *original],
        *[['--resume', *original[:-2], '--resume-case=verification::case',
           '--resume-case-only', *original[-2:]] for _ in range(2)],
        ['--resume', *original]]
    agents = [call for call in calls if call['kind'] == 'agent']
    assert len(agents) == 2
    assert 'Launcher-owned diagnostic execution outcome:' in agents[1]['prompt']
    usage = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    assert all(row.get('failure', {}).get('case') != 'removed::case' for row in usage)


def test_sol_high_blocker_continuation_keeps_tier_and_counts_diagnostic_session(checkout, monkeypatch):
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
    assert [(row['model'], row['effort']) for row in turns[2:]] == [('gpt-6.1-sol', 'high')] * 3
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
        'supported_reasoning_levels': [{'effort': 'low'}, {'effort': 'medium'}, {'effort': 'high'}]}]}))
    with pytest.raises(ValueError, match='gpt-6.1-sol with xhigh reasoning'):
        fix_tests.select(root, categories=('unit',))
    assert not spawned and not (root / 'calls').exists()


def test_unit_only_run_accepts_catalog_without_max(checkout, monkeypatch):
    root, _ = checkout
    monkeypatch.chdir(root)
    (root / 'mode').write_text('agent-pass')
    (root / 'catalog.json').write_text(json.dumps({'models': [{
        'slug': 'gpt-6.1-sol', 'visibility': 'list',
        'supported_reasoning_levels': [{'effort': effort} for effort in ('low', 'medium', 'high', 'xhigh')]}]}))
    run, _ = fix_tests.select(root, categories=('unit',))
    assert fix_tests.follow(run, io.StringIO()) == 0
    rows = [json.loads(line) for line in (run / 'agent-usage.jsonl').read_text().splitlines()]
    turn, = [row for row in rows if row['event'] == 'turn']
    assert turn['model'] == 'gpt-6.1-sol' and turn['effort'] == 'low'


@pytest.mark.parametrize('mode, classification', [
    ('agent-app', 'app_issue'), ('agent-uncertain', 'uncertain')])
def test_unit_app_or_uncertain_classification_starts_fresh_sol_medium_agent(checkout, mode,
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
    assert 'model_reasoning_effort="low"' in agents[0]['args']
    assert 'model_reasoning_effort="medium"' in agents[1]['args']
    assert all('service_tier="default"' in agent['args'] and 'features.fast_mode=false' in agent['args']
               for agent in agents)
    assert agents[1]['prompt'].startswith('LATEST FAILURE ONLY\n')
    assert f'{classification}: fixture result' in agents[1]['prompt']
    assert 'PREVIOUS AGENT TRANSCRIPT' not in agents[1]['prompt']
    assert '--ephemeral' not in agents[1]['args']
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


def test_task_limit_stops_after_first_category_and_preserves_resume_checkpoint(checkout):
    root, spawned = checkout
    (root / 'mode').write_text('pass')
    run, started = fix_tests.select(root, categories=('unit', 'ui'), tasks=1)
    assert started
    spawned[-1].wait(timeout=20)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit']
    assert json.loads((run / 'result.json').read_text()) == dict(status=0, tasks=1)
    assert 'task limit reached' in output.getvalue()
    progress = json.loads((run / 'controller.json').read_text())
    assert progress[-1]['lines'][-1] == 'Status: Task limit reached'
    from test_checkpoint import Checkpoint
    checkpoint = Checkpoint(root, [('unit', []), ('ui', [])], namespace='fix-tests', resume=True)
    assert checkpoint.complete('unit') and not checkpoint.complete('ui')
    with lock(run.parent / 'owner') as owner:
        assert not busy(owner)


@pytest.mark.parametrize('limit', [0, -4, 10])
def test_nonpositive_and_oversized_task_limits_exhaust_selected_categories(checkout, limit):
    root, spawned = checkout
    (root / 'mode').write_text('pass')
    run, started = fix_tests.select(root, categories=('unit', 'ui'), tasks=limit)
    assert started
    spawned[-1].wait(timeout=20)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit', 'ui']
    assert json.loads((run / 'result.json').read_text()) == dict(status=0, tasks=2)
    limits = json.loads((run / 'limits.json').read_text())
    assert limits['tasks'] == (None if limit <= 0 else limit)
    assert 'all selected categories passed' in output.getvalue()
    assert 'task limit reached' not in output.getvalue()
    if limit > 2:
        assert 'requested 10 tasks, but only 2 remain' in output.getvalue()
    with lock(run.parent / 'owner') as owner:
        assert not busy(owner)


def test_live_task_limit_replacement_allows_second_selected_category(checkout):
    root, spawned = checkout
    (root / 'mode').write_text('agent-script')
    (root / 'script.json').write_text(json.dumps(dict(agents=[], tests=[None, None], wait_test=0)))
    run, started = fix_tests.select(root, categories=('unit', 'ui'), tasks=1)
    assert started
    wait_for(root / 'test-ready')
    assert fix_tests.select(root, categories=('unit', 'ui'), tasks=2) == (run, False)
    limits = json.loads((run / 'limits.json').read_text())
    assert limits['tasks'] == 2 and limits['completed'] == 0
    (root / 'release').touch()
    spawned[-1].wait(timeout=20)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['unit', 'ui']
    assert json.loads((run / 'result.json').read_text()) == dict(status=0, tasks=2)
    assert len(spawned) == 1


def test_resumed_composite_verification_warns_with_actual_remaining_task_count(checkout):
    root, spawned = checkout
    (root / 'mode').write_text('pass')
    from test_checkpoint import Checkpoint
    checkpoint = Checkpoint(root, [(kind, []) for kind in ('unit', 'ui', 'system', 'e2e')],
                            namespace='fix-tests')
    checkpoint.state.update(round=2, pending='all')
    checkpoint.save()
    run, _ = fix_tests.select(root, rounds=3, resume=True, tasks=3)
    spawned[-1].wait(timeout=20)
    output = io.StringIO()
    assert fix_tests.follow(run, output) == 0
    calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
    assert [call['category'] for call in calls] == ['all', 'all']
    assert json.loads((run / 'result.json').read_text()) == dict(status=0, tasks=2)
    assert 'requested 3 tasks, but only 2 remain' in output.getvalue()
