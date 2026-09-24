"""Implement one queued task at a time, handing off before each live VM attempt."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detached_launcher as launcher


PLAN = 'docs/TestAutomation/E2E-Execution-Plan.md'
QUEUE = 'docs/TestAutomation/E2E-Task-Queue.md'
MODEL = 'gpt-6-astra'
INITIAL_PROMPT = """Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md. Write the code, do host validation.
Do handoff before live VM test.
Treat staged code as latest code, do not analyze the diff
"""


def queue_state(root):
    text = (root / QUEUE).read_text().split('## Deferred future work', 1)[0]
    rows = re.findall(r'^\| \[([ x])\] \| ([^|]+) \|', text, re.MULTILINE)
    if not rows:
        raise ValueError('no active task table found in the canonical queue')
    tasks = {task.strip(): mark == 'x' for mark, task in rows}
    if len(tasks) != len(rows):
        raise ValueError('duplicate task IDs in the canonical queue')
    current = next((task for task, complete in tasks.items() if not complete), None)
    pointer = re.search(r'^Next task: \*\*([^ ]+) —', (root / PLAN).read_text(), re.MULTILINE)
    if current is not None and (pointer is None or pointer[1] != current):
        raise ValueError(f'plan pointer must name first unchecked task {current}')
    return current, tasks


def fresh_state(task):
    return {'task_id': task, 'phase': 'implement', 'live_attempts': 0,
            'summary': 'Implementation and host validation remain.',
            'handoff': INITIAL_PROMPT, 'in_flight': False}


def session_prompt(state):
    task = state['task_id']
    common = f"""
This is one independent unattended session in tools/write-e2e, for task {task}.
Follow AGENTS.md and the execution plan's scoped reading routes. Work on exactly
the first unchecked active queue row; do not implement a later task. Preserve
unrelated edits. Treat staged code as the latest baseline. Do not analyze staged
diffs or compare staged code to HEAD. Read current source as needed.
Use existing grants, sandbox and maintained test launchers. Do not install the
product on the development host. Missing authority, prerequisites or unresolved
expected-versus-actual behavior decisions are blockers: preserve the evidence
and return blocked. Never weaken tests or accept a changed expectation to pass.
Do not stage files yourself. Do not commit, push, publish, start other agents,
invoke write-e2e/fix-tests, or
read/resume/fork prior Codex sessions, memories or transcripts. Do not start
untracked background jobs; use maintained launchers and viewers. Wait for each
test and its owned cleanup before returning.
Run tests through tools/run-tests so this launcher can own their cancellation;
do not clear or override ONPC_WORKFLOW_DIRECTORY.
Return the required structured result. Keep summary under 600 characters and
handoff under 16000 characters. The handoff must be a concise standalone
prompt containing only remaining work, task ID, exact next commands/selectors,
relevant artifact/evidence paths, blockers and recommended model/effort. Never
paste previous conversations. ready_for_vm requires successful host validation
and a handoff BEFORE the next live VM attempt. blocked stops the launcher.
Only task 192 has the plan's host-only acceptance exception.
The launcher owns staging after successful acceptance and close-out. For
task_complete, return stage_paths listing every task-related code, test and
close-out file (including deleted files), relative to the checkout; include the
plan and queue. Use explicit files, never directories, wildcards or unrelated
work. For other statuses return stage_paths empty.
"""
    if state['phase'] == 'implement':
        return INITIAL_PROMPT + common + """
Implement and host-validate this task. Do not run live VM tests, stage changes,
mark the task complete or advance the pointer in this session (except task 192
after its complete host-only acceptance). Return ready_for_vm, with live_result
not_run and a handoff recommending GPT-6-Astra High for the live session.
"""
    if state['phase'] == 'recover':
        return common + f"""
Recover the same unfinished task with GPT-6-Astra High using only the handoff
below and current source/evidence. Recheck the recorded blocker or interrupted
operation and test cleanup. If the interrupted first live attempt failed, review
unstaged code before repairing it. Do the remaining implementation and host
validation. Do not start live VM tests, stage code, close the task or advance
the pointer in this recovery session. Return ready_for_vm with live_result
not_run only after host checks pass, otherwise blocked with the exact remaining
requirement. Hand off before the next live attempt.

Recovery handoff:
Last operation evidence: {state.get('recovery_run', 'see handoff')}/output and prompt.txt.
{state['handoff']}
"""
    review = (
        'This is the first live VM attempt for this task. If it fails, review the '
        'unstaged code (including new files) before fixing it; do not review the staged diff.'
        if state['live_attempts'] == 0 else
        'The first live attempt has already happened; use its failure evidence and current source.'
    )
    return common + f"""
Continue the handoff below with GPT-6-Astra High. This exec transport cannot
switch models in-session, so the requested Astra High fallback is already active.
Run the task's required live VM acceptance and wait for completion, evidence
collection, owned cleanup and baseline restoration. {review}
If live acceptance fails, preserve expected versus actual and its evidence,
fix authorized root causes, run the affected host validation, then return
ready_for_vm with live_result failed and a new handoff BEFORE another live VM
attempt. Do not rerun live acceptance in this session after a repair.
If it passes, prepare only this task's code and supporting tests for staging.
Complete the original plan's
acceptance and close-out, refresh required coverage, check this row and advance
the sole Next task pointer. Include this task's close-out files in stage_paths. Do not
implement the following task. Return task_complete only after all of that,
with live_result passed and the next-task handoff. If additional required live
regressions fail, this is a failure, not task_complete.

Previous session's handoff:
{state['handoff']}
"""


def accept_result(root, state, result, before):
    if (not isinstance(result, dict) or result.get('task_id') != state['task_id']
            or result.get('status') not in ('ready_for_vm', 'task_complete', 'blocked')
            or result.get('live_result') not in ('not_run', 'failed', 'passed')
            or type(result.get('host_validated')) is not bool
            or not isinstance(result.get('stage_paths'), list)
            or any(not isinstance(path, str) or not path for path in result['stage_paths'])
            or any(not isinstance(result.get(key), str) or not result[key].strip()
                   for key in ('summary', 'handoff'))
            or len(result['summary']) > 600 or len(result['handoff']) > 16000):
        raise ValueError('agent returned an invalid or wrong-task handoff')
    current, after = queue_state(root)
    task = state['task_id']
    if any(after.get(key) != complete for key, complete in before.items() if key != task):
        raise ValueError('agent changed another task status; inspect the queue')
    status = result['status']
    if status != 'task_complete' and result['stage_paths']:
        raise ValueError('incomplete task requested staging')
    if status == 'task_complete':
        if (not after.get(task) or current == task or not result['host_validated']
                or (task != '192' and (state['phase'] != 'live' or result['live_result'] != 'passed'))):
            raise ValueError('task completion lacks acceptance or queue close-out')
    elif current != task or after.get(task):
        raise ValueError('incomplete task advanced the queue pointer')
    if status == 'ready_for_vm':
        expected_live = 'not_run' if state['phase'] in ('implement', 'recover') else 'failed'
        if not result['host_validated'] or result['live_result'] != expected_live:
            raise ValueError('VM handoff lacks host validation or a matching live outcome')
    updated = dict(state, summary=result['summary'], handoff=result['handoff'], in_flight=False)
    if state['phase'] == 'live' and result['live_result'] != 'not_run':
        updated['live_attempts'] += 1
    updated['phase'] = 'complete' if status == 'task_complete' else 'live' if status == 'ready_for_vm' else 'blocked'
    return updated


def stage_task(root, paths):
    """Stage only explicit reported files; never interpret Git pathspec magic."""
    paths = list(dict.fromkeys(paths))
    if not {PLAN, QUEUE}.issubset(paths):
        raise ValueError('completed task must include plan and queue in stage_paths')
    for value in paths:
        path = Path(value)
        if (not value or '\x00' in value or path.is_absolute() or '..' in path.parts
                or '.git' in path.parts or value != path.as_posix() or path == Path('.')
                or (root / path).is_dir()
                or any(parent.is_symlink() for parent in (root / path).parents if parent != root)):
            raise ValueError('stage_paths must contain explicit checkout files')
    result = subprocess.run(['git', '--literal-pathspecs', 'add', '--', *paths], cwd=root,
                            env=launcher.environment(), capture_output=True, text=True)
    if result.returncode:
        raise ValueError('task staging failed: ' + result.stderr.strip())


def save_handoff(run, state, reason):
    prompt = state['handoff']
    if state['in_flight']:
        prompt = (
            f"Recover interrupted task {state['task_id']}. Inspect {run / 'output'} and "
            f"{run / 'prompt.txt'}; verify retained test results and owned cleanup "
            "before retrying. Do not assume live acceptance passed or advance the "
            "task. Continue with GPT-6-Astra High. Last safe handoff:\n" + prompt)
    text = f"Task {state['task_id'] or 'none'}: {reason}. {state['summary']}\n\nNext session prompt:\n{prompt}\n"
    (run / 'handoff.txt').write_text(text, encoding='utf-8')
    launcher.atomic(run / 'checkpoint.json', state)
    print('\n' + text, flush=True)


def execute(root, run, owner, effort):
    (run / 'agent-result.json').write_text('')
    with launcher.lock(run / 'nested-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        (run / 'nested-closed').unlink(missing_ok=True)
        launcher.atomic(run / 'nested.json', [])
    command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
               '--supervise', str(root), str(run), str(owner), effort]
    with subprocess.Popen(command, cwd=root, env=launcher.environment(),
                          stdin=subprocess.PIPE, start_new_session=True,
                          pass_fds=(owner, *launcher.scratch_descriptors())) as child:
        status = child.wait()
    sys.stdout.flush()
    launcher.compact_log(run / 'output', writer_fd=1)
    if (run / 'cancel').exists():
        raise launcher.Stopped()
    if status:
        raise ValueError(f'Codex session exited with status {status}; see retained output')
    return json.loads((run / 'agent-result.json').read_text())


def worker(root, run, owner, sessions, tasks, state_json):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)
    state = json.loads(state_json)
    count, completed, status, reason = 0, 0, 0, 'session limit reached'
    try:
        while sessions is None or count < sessions:
            if (run / 'cancel').exists():
                raise launcher.Stopped()
            if (run / 'stop').exists():
                reason = 'stopped at a session boundary'
                break
            task, before = queue_state(root)
            if task is None:
                state = dict(state, task_id=None, summary='All active queue tasks are complete.',
                             handoff='No active E2E task remains. Do not select deferred tasks.', phase='complete')
                reason = 'queue complete'
                break
            if state['phase'] == 'complete':
                state = fresh_state(task)
            if task != state['task_id']:
                raise ValueError('active task changed outside the workflow; inspect the checkpoint')
            count += 1
            effort = 'low' if state['phase'] == 'implement' else 'high'
            prompt = session_prompt(state)
            (run / 'prompt.txt').write_text(prompt, encoding='utf-8')
            state['in_flight'] = True
            launcher.atomic(run / 'checkpoint.json', state)
            launcher.atomic(run / 'progress.json', {'session': count, 'limit': sessions,
                                                   'task_id': task, 'phase': state['phase']})
            print(f"\nwrite-e2e: session {count}{'/' + str(sessions) if sessions else ''}; "
                  f"task {task}; {MODEL} {effort}", flush=True)
            result = execute(root, run, owner, effort)
            updated = accept_result(root, state, result, before)
            if updated['phase'] == 'complete':
                stage_task(root, result['stage_paths'])
                completed += 1
            state = updated
            launcher.atomic(run / 'checkpoint.json', state)
            if state['phase'] == 'blocked':
                status, reason = 1, 'blocked'
                break
            if completed >= tasks:
                reason = 'task limit reached'
                break
        if (run / 'stop').exists():
            reason = 'stopped at a session boundary'
    except launcher.Stopped:
        status, reason = 130, 'cancelled after owned cleanup'
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        status, reason = 1, str(error)
    finally:
        save_handoff(run, state, reason)
        launcher.atomic(run / 'result.json', {'status': status, 'sessions': count,
                                             'tasks': completed})
        os.close(owner)
    return status


def positive(value):
    if not value.isdecimal() or int(value) < 1:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return int(value)


def initial_state(root, directory):
    task, _ = queue_state(root)
    previous = launcher.current_run(directory)
    if previous and (previous / 'checkpoint.json').exists():
        state = json.loads((previous / 'checkpoint.json').read_text())
        if state.get('task_id') == task and state.get('phase') != 'complete':
            if state.get('in_flight') or state.get('phase') == 'blocked':
                state = dict(state, phase='recover', in_flight=False,
                             recovery_run=str(previous))
            return state
        if state.get('in_flight'):
            raise ValueError(f'interrupted task changed the queue; inspect the handoff in {previous}')
    return fresh_state(task)


def select(root, argv):
    def command(run, owner):
        parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
        parser.add_argument('--sessions', type=positive, help='maximum fresh sessions; omitted means unlimited')
        parser.add_argument('--tasks', type=positive, default=1,
                            help='maximum completed tasks; default: 1; stops when either limit is reached')
        parser.add_argument('--stop', action='store_true', help='finish the current session and stop before the next')
        args = parser.parse_args(argv)
        state = initial_state(root, run.parent)
        # Preflight transport/rendering only; do not spend a model session here.
        from launcher_render import AgentRenderer
        launcher.agent_command(root, MODEL, 'low')
        return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), '--worker',
                str(root), str(run), str(owner), json.dumps(args.sessions),
                json.dumps(args.tasks), json.dumps(state)]
    return launcher.select(root, 'write-e2e', command, stop='--stop' in argv, stop_marker='stop')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    run, interrupted = None, False

    def cancel(*_):
        nonlocal interrupted
        interrupted = True
        if run is not None:
            (run / 'cancel').touch(mode=0o600)

    previous = signal.signal(signal.SIGINT, cancel)
    try:
        run, started = select(root, argv)
        if run is None:
            print('write-e2e: no active launcher.')
            return 0
        if interrupted:
            cancel()
        print(f"write-e2e: {'started' if started else 'attached to'} {run.name}; log: {run / 'output'}",
              flush=True)
        print('Closing the terminal detaches. Ctrl+C cancels; --stop waits for a session boundary.',
              flush=True)
        return launcher.follow(run, label='write-e2e')
    except BrokenPipeError:
        return 0
    except (OSError, ValueError, ImportError) as error:
        print(f'write-e2e: {error}', file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGINT, previous)


if __name__ == '__main__':
    mode, root, run, owner, *options = sys.argv[1:]
    if mode == '--worker':
        sys.exit(worker(Path(root), Path(run), int(owner), json.loads(options[0]),
                        json.loads(options[1]), options[2]))
    if mode == '--supervise':
        root, run = Path(root), Path(run)
        command = launcher.agent_command(root, MODEL, options[0], run,
                                        schema=Path(__file__).with_name('write_e2e_response.schema.json'))
        command[-1:-1] = ['-c', 'shell_environment_policy.set.ONPC_WORKFLOW_DIRECTORY=' + json.dumps(str(run))]
        sys.exit(launcher.supervise(root, run, int(owner), 'agent', command, nested=True))
    raise SystemExit('private write-e2e worker entry point')
