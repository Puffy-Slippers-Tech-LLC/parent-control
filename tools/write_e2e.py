"""Implement one queued task at a time, handing off after a failed live VM test."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detached_launcher as launcher


PLAN = 'docs/TestAutomation/E2E-Execution-Plan.md'
QUEUE = 'docs/TestAutomation/E2E-Task-Queue.md'
MODEL = 'gpt-6-astra'
MAX_TASK_SESSIONS = 5
INITIAL_PROMPT = """Implement the next task in docs/TestAutomation/E2E-Execution-Plan.md
through host validation and the first live VM test. Close the task if it passes;
if it fails, hand off the failure to the next session.
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
            'task_sessions': 0,
            'summary': 'Implementation, host validation and the first live VM test remain.',
            'handoff': INITIAL_PROMPT, 'in_flight': False, 'stage_candidates': []}


def session_progress(root, state, count):
    task = state['task_id']
    queue = (root / QUEUE).read_text().split('## Deferred future work', 1)[0]
    row = re.search(r'^\| \[[ x]\] \| ' + re.escape(task) + r' \| ([^|]+) \|', queue, re.MULTILINE)
    title = row[1].strip() if row else task
    brief = re.search(r'\[[^\]]+\]\(([^)]+)\)', title)
    target = (root / QUEUE).parent / brief[1] if brief else root / QUEUE
    # OSC 8 file links let the hosting editor handle navigation and its preview
    # preference. Keep the link and bold style confined to the task label.
    link = target.resolve().as_uri()
    task_label = f'\033]8;;{link}\033\\\033[1mTask {task}\033[22m\033]8;;\033\\'
    title = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', title).replace('`', '').replace('**', '')
    summary = {'implement': 'Writing task code + host validation + first live VM test; close on success, hand off on failure',
               'recover': 'Recovering interrupted work + host validation'}.get(
                   state['phase'], f"Live VM test {state['live_attempts'] + 1}, fix errors if any + host validation")
    return [f'{task_label}: {title}',
            f"\033[1mSession [{state['task_sessions']}/{count}]\033[22m: {summary}"]


def session_prompt(state):
    task = state['task_id']
    common = f"""
Task {task}: follow AGENTS.md and {PLAN}, using its scoped reading routes.
This tools/write-e2e session stops at the phase boundary below.

Treat staged code as the baseline. Do not analyze staged diffs or compare it to
HEAD; read current source as needed. The launcher owns staging. Do not commit,
push, publish, start other agents, invoke write-e2e/fix-tests, or access prior
Codex sessions, memories or transcripts.
Run tests through tools/run-tests for owned cancellation; preserve
ONPC_WORKFLOW_DIRECTORY. Use maintained launchers/viewers for background work
and wait for tests and owned cleanup before returning.

Return the required structured result; unresolved blockers return blocked and
stop the loop. Keep summary under 600 characters and handoff under 16000.
The handoff is a standalone prompt with only remaining work, task ID, exact next
commands/selectors, evidence paths, blockers and recommended model/effort.
Format summary and handoff as Markdown: backticks for inline paths, selectors
and identifiers; fenced bash blocks for commands; Markdown links for references.
For task_complete, list every task-related code, test and close-out file in
stage_paths, including deletions, plan and queue. Use explicit checkout-relative
files, excluding unrelated work. Otherwise return stage_paths empty.
"""
    if state['phase'] == 'implement':
        return INITIAL_PROMPT + common + """
After host checks pass, run this task's first live VM acceptance, including
required regressions, under the plan. If it fails, preserve failure evidence,
wait for owned cleanup and return ready_for_vm with live_result failed and a
handoff for GPT-6-Astra High. Leave failure review and repairs to the next
session; do not retry live acceptance or advance the pointer in this session.
After all acceptance and cleanup pass, complete the plan's close-out and return
task_complete with live_result passed and the next-task handoff. Leave the next
task's implementation to a fresh session. Task 192 may instead return
task_complete with live_result not_run after its host-only acceptance and close-out.
"""
    if state['phase'] == 'recover':
        return common + f"""
Recover this task with GPT-6-Astra High from the handoff and current source/evidence.
Recheck the blocker or interrupted operation and test cleanup. If the interrupted
first live attempt failed, review unstaged code (including new files) before
repairing it. Finish remaining implementation and host validation, then return
ready_for_vm with live_result not_run. Do not run live VM tests or close the
task/advance the pointer in this recovery session.

Recovery handoff:
Last operation evidence: {state.get('recovery_run', 'see handoff')}/output and prompt.txt.
{state['handoff']}
"""
    review = (
        'This is the first live VM attempt for this task. If it fails, review the '
        'unstaged code (including new files) before fixing it.'
        if state['live_attempts'] == 0 else
        'The first live attempt failed. Before another live attempt, review the '
        'unstaged code (including new files) and failure evidence, apply the '
        'repository failure contract, repair authorized defects and host-validate.'
        if state['live_attempts'] == 1 else
        'The first live attempt has already happened; use its failure evidence and current source.'
    )
    return common + f"""
Continue the handoff with GPT-6-Astra High. Run this task's live acceptance,
including required regressions, under the plan. {review}
On failure, apply the repository failure contract, repair authorized defects
and host-validate, then return ready_for_vm with live_result failed and a fresh
handoff. Do not rerun live acceptance after a repair in this session.
After all acceptance and cleanup pass, complete the plan's close-out and return
task_complete with live_result passed and the next-task handoff. Leave the next
task's implementation to a fresh session.

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
                or (task != '192' and (state['phase'] not in ('implement', 'live')
                                      or result['live_result'] != 'passed'))):
            raise ValueError('task completion lacks acceptance or queue close-out')
    elif current != task or after.get(task):
        raise ValueError('incomplete task advanced the queue pointer')
    if status == 'ready_for_vm':
        expected_live = 'not_run' if state['phase'] == 'recover' else 'failed'
        if not result['host_validated'] or result['live_result'] != expected_live:
            raise ValueError('VM handoff lacks host validation or a matching live outcome')
    updated = dict(state, summary=result['summary'], handoff=result['handoff'], in_flight=False)
    if state['phase'] in ('implement', 'live') and result['live_result'] != 'not_run':
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


def worktree_snapshot(root):
    """Fingerprint unstaged and untracked files without including existing index work."""
    result = subprocess.run(
        ['git', 'ls-files', '--modified', '--deleted', '--others',
         '--exclude-standard', '-z'], cwd=root, env=launcher.environment(),
        capture_output=True, check=True)
    snapshot = {}
    for raw in result.stdout.split(b'\0'):
        if not raw:
            continue
        name = os.fsdecode(raw)
        if name.startswith('output/'):
            continue
        path = root / name
        if path.is_symlink():
            fingerprint = 'link:' + os.readlink(path)
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
            fingerprint = 'file:' + digest.hexdigest()
        else:
            fingerprint = 'deleted'
        snapshot[name] = fingerprint
    return snapshot


def session_changes(root, before):
    after = worktree_snapshot(root)
    return [name for name, fingerprint in after.items()
            if before.get(name) != fingerprint]


def save_handoff(run, state, reason, *, display=True):
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
    if display:
        from launcher_render import AgentRenderer
        AgentRenderer(sys.stdout).message(text)
        sys.stdout.flush()


def format_duration(seconds):
    minutes = max(0, int(seconds / 60 + 0.5))
    if seconds < 3600:
        return f'{minutes} {"minute" if minutes == 1 else "minutes"}'
    hours, minutes = divmod(minutes, 60)
    return (f'{hours} {"hour" if hours == 1 else "hours"} '
            f'{minutes} {"minute" if minutes == 1 else "minutes"}')


def show_completion(task, task_sessions, launcher_sessions, duration):
    from launcher_render import AgentRenderer
    from rich.text import Text
    console = AgentRenderer(sys.stdout).console
    console.rule(style='dim')
    console.print(Text(f'Task {task} complete.', style='bold green'))
    print(f'- Took {task_sessions} sessions.\n'
          f'- Total launcher sessions: {launcher_sessions}\n'
          f'- Duration: {format_duration(duration)}', flush=True)
    sys.stdout.flush()


def task_session_limit_reached(state):
    return (state['phase'] != 'complete'
            and state.get('task_sessions', 0) >= MAX_TASK_SESSIONS)


def show_session_limit(state):
    from launcher_render import AgentRenderer
    from rich.text import Text
    message = (f"Task {state['task_id']} is not complete in {state['task_sessions']} sessions. "
               'Launcher exited early.')
    AgentRenderer(sys.stdout).console.print(Text(message, style='bold red'), soft_wrap=True)
    sys.stdout.flush()


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
    from launcher_progress import publish_progress, read_progress
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def cancel(*_):
        (run / 'cancel').touch(mode=0o600)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)
    state = json.loads(state_json)
    count, completed, status, reason = 0, 0, 0, 'session limit reached'
    try:
        while True:
            with launcher.lock(run / 'limits-gate') as gate:
                fcntl.flock(gate, fcntl.LOCK_EX)
                limits = json.loads((run / 'limits.json').read_text())
                sessions, tasks = limits['sessions'], limits['tasks']
                if task_session_limit_reached(state):
                    status, reason = 1, 'task session limit reached'
                    launcher.atomic(run / 'limits.json', dict(limits, closed=True))
                    break
                if completed >= tasks or (sessions is not None and count >= sessions):
                    reason = 'task limit reached' if completed >= tasks else 'session limit reached'
                    launcher.atomic(run / 'limits.json', dict(limits, closed=True))
                    break
                launcher.atomic(run / 'limits.json', dict(limits, started=count + 1))
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
            state.setdefault('started_at', time.time())
            state['task_sessions'] = state.get('task_sessions', 0) + 1
            effort = 'low' if state['phase'] == 'implement' else 'high'
            prompt = session_prompt(state)
            (run / 'prompt.txt').write_text(prompt, encoding='utf-8')
            state.setdefault('stage_baseline', worktree_snapshot(root))
            state['worktree_before'] = worktree_snapshot(root)
            state['in_flight'] = True
            launcher.atomic(run / 'checkpoint.json', state)
            launcher.atomic(run / 'progress.json', {'session': count, 'limit': sessions,
                                                   'task_id': task, 'phase': state['phase']})
            publish_progress(run, str(count), session_progress(root, state, count))
            print(f"\nwrite-e2e: session {count}{'/' + str(sessions) if sessions else ''}; "
                  f"task {task}; {MODEL} {effort}", flush=True)
            try:
                result = execute(root, run, owner, effort)
            finally:
                candidates = set(state['stage_candidates'])
                candidates.update(session_changes(root, state['worktree_before']))
                state['stage_candidates'] = sorted(candidates)
                launcher.atomic(run / 'checkpoint.json', state)
            updated = accept_result(root, state, result, before)
            if updated['phase'] == 'complete':
                current = worktree_snapshot(root)
                changed = [path for path in state['stage_candidates']
                           if path in current
                           and current[path] != state['stage_baseline'].get(path)]
                stage_task(root, [*result['stage_paths'], *changed])
                completed += 1
            state = updated
            state.pop('worktree_before', None)
            launcher.atomic(run / 'checkpoint.json', state)
            if state['phase'] == 'complete':
                show_completion(task, state['task_sessions'], count,
                                time.time() - state['started_at'])
            if state['phase'] == 'blocked':
                status, reason = 1, 'blocked'
                break
        if (run / 'stop').exists():
            reason = 'stopped at a session boundary'
    except launcher.Stopped:
        status, reason = 130, 'cancelled after owned cleanup'
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        status, reason = 1, str(error)
    finally:
        previous = read_progress(run)
        if previous:
            lines = previous[-1]['lines']
            outcome = ('Stopped' if status == 130 else 'Blocked' if status else
                       'Complete' if state['phase'] == 'complete' else reason)
            lines[-1] += ' — ' + outcome
            publish_progress(run, previous[-1]['key'], lines)
        save_handoff(run, state, reason,
                     display=not (status == 0 and completed and state['phase'] == 'complete'))
        if task_session_limit_reached(state):
            show_session_limit(state)
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
                if state.get('worktree_before') is not None:
                    candidates = set(state.get('stage_candidates', []))
                    candidates.update(session_changes(root, state['worktree_before']))
                    state['stage_candidates'] = sorted(candidates)
                state = dict(state, phase='recover', in_flight=False,
                             recovery_run=str(previous))
            return state
        if state.get('in_flight'):
            raise ValueError(f'interrupted task changed the queue; inspect the handoff in {previous}')
    return fresh_state(task)


def select(root, argv):
    initial_limits = {}

    def parse(attaching=False):
        parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
        kind = int if attaching else positive
        parser.add_argument('--sessions', type=kind,
                            help='new run: maximum sessions (plain invocation defaults to 5); active run: signed adjustment')
        parser.add_argument('--tasks', type=kind,
                            help='new run: maximum completed tasks (default 1); active run: signed adjustment')
        parser.add_argument('--stop', action='store_true', help='finish the current session and stop before the next')
        return parser.parse_args(argv)

    def attach(run):
        args = parse(attaching=True)
        if args.sessions is None and args.tasks is None:
            return
        with launcher.lock(run / 'limits-gate') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            path = run / 'limits.json'
            if not path.exists():
                raise ValueError('active launcher predates adjustable limits; attach without parameters or restart after it stops')
            limits = json.loads(path.read_text())
            if limits.get('closed') or (run / 'result.json').exists():
                raise ValueError('active launcher is finishing; limits can no longer be adjusted')
            for key in ('tasks', 'sessions'):
                delta = getattr(args, key)
                if delta is not None:
                    base = limits[key] if limits[key] is not None else limits['started']
                    limits[key] = max(0, base + delta)
            launcher.atomic(path, limits)
            print(f"write-e2e: limits now tasks={limits['tasks']}, "
                  f"sessions={limits['sessions'] if limits['sessions'] is not None else 'unlimited'}", flush=True)

    def command(run, owner):
        args = parse()
        if not argv:
            args.sessions = 5
        if args.tasks is None:
            args.tasks = 1
        initial_limits.update(sessions=args.sessions, tasks=args.tasks, started=0)
        state = initial_state(root, run.parent)
        # Preflight transport/rendering only; do not spend a model session here.
        from launcher_render import AgentRenderer
        launcher.agent_command(root, MODEL, 'low')
        return ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), '--worker',
                str(root), str(run), str(owner), json.dumps(args.sessions),
                json.dumps(args.tasks), json.dumps(state)]
    return launcher.select(root, 'write-e2e', command, stop='--stop' in argv, stop_marker='stop',
                           on_attach=attach,
                           on_start=lambda run: launcher.atomic(run / 'limits.json', initial_limits))


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
        sys.exit(launcher.supervise(root, run, int(owner), 'agent', command, nested=True,
                                    hide_task_completion=True))
    raise SystemExit('private write-e2e worker entry point')
