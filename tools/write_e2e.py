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
import uuid

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
    summary = ('Writing task code + host validation + first live VM test; close on success, hand off on failure'
               if state['phase'] == 'implement' else
               f"Investigate/fix previous failure + host validation + live VM test {state['live_attempts'] + 1}; close on success, hand off on failure")
    return [f'{task_label}: {title}',
            f"\033[1mSession [{state['task_sessions']}]\033[22m: {summary}"]


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

Return the required structured result; unresolved blockers return blocked so the
launcher pauses for the user's answer. Keep summary under 600 characters and
handoff under 16000.
For blocked, supply blocker with explanation, question and options. Write the
explanation in concise, user-friendly, scenario-oriented language (at most 200
words and 2000 characters): what is finished, what the user/test tries to do,
what actually prevents progress and the practical steps to unblock. Distinguish
test/tooling failures from established product defects. Keep technical evidence,
long commands and continuation prompts in handoff only; do not repeat them in
the explanation or commentary. Ask one concrete question (under 240 characters)
that resolves the blocker. Provide 2 or 3 specific, distinct suggestions (under
300 characters each), with the recommended action first. The launcher adds the
recommended label and an editable Other option; do not include those yourself.
Never propose bypassing a denied grant or weakening acceptance to make it pass.
For other statuses set blocker to null. Do not print a separate final summary;
the launcher displays the explanation once and waits without a timeout.
The handoff is a standalone prompt with only remaining work, task ID, exact next
commands/selectors, evidence paths, blockers and recommended model/effort.
Carry forward user decisions that still apply to that remaining work.
Format summary and handoff as Markdown: backticks for inline paths, selectors
and identifiers; fenced bash blocks for commands; Markdown links for references.
For task_complete, list every task-related code, test and close-out file in
stage_paths, including deletions, plan and queue. Use explicit checkout-relative
files, excluding unrelated work. Otherwise return stage_paths empty.
"""
    if state.get('user_answer'):
        common += ('\nThe user answered the blocker question below. Apply these instructions '
                   'to the current task while preserving its baseline and unrelated work. '
                   'Recheck the prerequisite before continuing; an answer alone is not '
                   'evidence that it passed.\n' + json.dumps(state['user_answer'], ensure_ascii=False) + '\n')
    if state['phase'] == 'implement':
        preparation = INITIAL_PROMPT + common + "\nImplement this task and complete host validation.\n"
    else:
        preparation = common + """
Continue this task with GPT-6-Astra High from the handoff and current source/evidence.
Start by investigating the previous VM validation error, when present. Review
unstaged code (including new files) and retained failure evidence, apply the
repository failure contract and repair authorized defects. For interrupted or
blocked work, recheck the operation or prerequisite and owned test cleanup first.
Finish remaining implementation or repairs and complete host validation before
starting live acceptance in this same session.
"""
        if state['phase'] == 'recover':
            preparation += f"\nLast operation evidence: {state.get('recovery_run', 'see handoff')}/output and prompt.txt.\n"
        preparation += f"\nPrevious session's handoff:\n{state['handoff']}\n"
    return preparation + """
Use this same validation and handoff boundary in every session, including recovery.
After host checks pass, run this task's live VM acceptance, including required
regressions, under the plan. Wait for validation and owned cleanup to finish.
If live acceptance fails, preserve failure evidence and return ready_for_vm with
host_validated true, live_result failed and a fresh handoff for GPT-6-Astra High.
Leave investigation and repairs of this new failure to the next session; do not
repair it, retry live acceptance or advance the pointer in this session.
Do not end a normal session with only host validation: finish live VM validation
with a passed or failed result. If a prerequisite or unresolved blocker prevents
validation, return blocked with the actual live_result; do not claim a VM attempt.
After all acceptance and cleanup pass, complete the plan's close-out and return
task_complete with live_result passed and the next-task handoff. Leave the next
task's implementation to a fresh session. Task 192 may instead return
task_complete with live_result not_run after its host-only acceptance and close-out.
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
    blocker = result.get('blocker')
    if result['status'] == 'blocked':
        validate_blocker(blocker)
    elif blocker is not None:
        raise ValueError('only a blocked result may ask a question')
    current, after = queue_state(root)
    task = state['task_id']
    if any(after.get(key) != complete for key, complete in before.items() if key != task):
        raise ValueError('agent changed another task status; inspect the queue')
    status = result['status']
    if status != 'task_complete' and result['stage_paths']:
        raise ValueError('incomplete task requested staging')
    if status == 'task_complete':
        if (not after.get(task) or current == task or not result['host_validated']
                or (task != '192' and (state['phase'] not in ('implement', 'live', 'recover')
                                      or result['live_result'] != 'passed'))):
            raise ValueError('task completion lacks acceptance or queue close-out')
    elif current != task or after.get(task):
        raise ValueError('incomplete task advanced the queue pointer')
    if status == 'ready_for_vm':
        if not result['host_validated'] or result['live_result'] != 'failed':
            raise ValueError('VM handoff lacks host validation or a matching live outcome')
    updated = dict(state, summary=result['summary'], handoff=result['handoff'], in_flight=False)
    updated.pop('blocker_id', None)
    updated['blocker'] = blocker
    if state['phase'] in ('implement', 'live', 'recover') and result['live_result'] != 'not_run':
        updated['live_attempts'] += 1
    updated['phase'] = 'complete' if status == 'task_complete' else 'live' if status == 'ready_for_vm' else 'blocked'
    return updated


def validate_blocker(blocker):
    if (not isinstance(blocker, dict)
            or any(not isinstance(blocker.get(key), str) or not blocker[key].strip()
                   or len(blocker[key]) > limit
                   for key, limit in (('explanation', 2000), ('question', 240)))
            or not isinstance(blocker.get('options'), list)
            or not 2 <= len(blocker['options']) <= 3
            or any(not isinstance(option, str) or not option.strip() or len(option) > 300
                   for option in blocker['options'])
            or len(set(blocker['options'])) != len(blocker['options'])):
        raise ValueError('blocked result needs a concise explanation, question and 2–3 distinct suggestions')


def wait_for_answer(run, state, progress_key):
    """The detached owner waits; terminals may come and go without answering."""
    from launcher_progress import publish_progress, read_progress
    from launcher_question import QuestionInput
    from launcher_render import AgentRenderer
    blocker = state.get('blocker') or {
        'explanation': state['summary'],
        'question': 'How should we unblock this task?',
        'options': ['Recheck the blocker and resolve work already authorized.',
                    'Inspect the evidence and explain the decision needed before making changes.']}
    validate_blocker(blocker)
    state.setdefault('blocker_id', uuid.uuid4().hex)
    question = dict(blocker, id=state['blocker_id'], answer=None)
    with launcher.lock(run / 'question-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        path = run / 'question.json'
        previous = json.loads(path.read_text()) if path.exists() else None
        if previous is None or previous['id'] != question['id']:
            launcher.atomic(path, question)
    save_handoff(run, state, 'waiting for your answer', display=False)
    steps = read_progress(run)
    heading = steps[-1]['lines'][0] if steps else f"Task {state['task_id']}"
    publish_progress(run, progress_key, [heading, 'Paused — waiting for your answer'])
    renderer = AgentRenderer(sys.stdout)
    renderer.message(blocker['explanation'])
    # The observer owns the editable menu. Do not leave its initial selection
    # in the transcript, where it would reappear after submission.
    prompt = QuestionInput(question, None)
    prompt.selected = None
    renderer.console.print('\n'.join(prompt.lines()), markup=False)
    print('No timeout. Reattach with tools/write-e2e to answer after a disconnect.', flush=True)
    while True:
        if (run / 'cancel').exists():
            raise launcher.Stopped()
        if (run / 'stop').exists():
            return False
        question = json.loads(path.read_text())
        if question['answer'] is not None:
            renderer.console.print('\n'.join(QuestionInput(question, None).lines()), markup=False)
            state.update(phase='recover', recovery_run=str(run),
                         user_answer={'question': question['question'], 'answer': question['answer']})
            state.pop('blocker_id', None)
            state.pop('blocker', None)
            launcher.atomic(run / 'checkpoint.json', state)
            print('Answer received. Continuing this task.', flush=True)
            return True
        time.sleep(.1)


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
        if state['phase'] == 'blocked':
            # The decision was already shown when the workflow paused. Keep the
            # engineering continuation in the file, including on stop/cancel.
            text = f"Task {state['task_id']} is paused. Run tools/write-e2e to answer and continue."
        AgentRenderer(sys.stdout).message(text)
        sys.stdout.flush()


def format_duration(seconds, *, short=False):
    minutes = max(0, int(seconds / 60 + 0.5))
    if short:
        hours, remaining_minutes = divmod(minutes, 60)
        return f'{hours}h {remaining_minutes}m' if seconds >= 3600 else f'{minutes}m'
    if seconds < 3600:
        return f'{minutes} {"minute" if minutes == 1 else "minutes"}'
    hours, minutes = divmod(minutes, 60)
    return (f'{hours} {"hour" if hours == 1 else "hours"} '
            f'{minutes} {"minute" if minutes == 1 else "minutes"}')


def show_completion(task, task_sessions, duration):
    from launcher_render import AgentRenderer
    from rich.text import Text
    console = AgentRenderer(sys.stdout).console
    console.rule(style='dim')
    console.print(Text(f'Task {task} complete.', style='bold green'))
    print(f'- Took {task_sessions} sessions.\n'
          f'- Duration: {format_duration(duration)}', flush=True)
    sys.stdout.flush()


def task_session_limit_reached(state):
    return (state['phase'] != 'complete'
            and state.get('task_sessions', 0) >= state.get('task_session_limit', MAX_TASK_SESSIONS))


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
    total = state.get('total_sessions', state.get('task_sessions', 0))
    count, completed, status, reason = 0, 0, 0, 'session limit reached'
    completions = []

    def compact_completions():
        for task_id, task_sessions, duration, keys, heading in completions:
            publish_progress(run, 'complete-' + task_id,
                             [f'\033[32m{heading} '
                              f'(sessions={task_sessions}, duration={format_duration(duration, short=True)})\033[0m'],
                             replaces=keys)

    try:
        while True:
            if state['phase'] == 'blocked':
                if not wait_for_answer(run, state, str(count)):
                    reason = 'paused at your request'
                    break
                # An explicit answer authorizes a recovery session even when
                # the automatic-work budget ended at the blocker. Waiting itself
                # consumes no model session and never renews a budget.
                state['task_session_limit'] = max(state.get('task_session_limit', MAX_TASK_SESSIONS),
                                                  state['task_sessions'] + 1)
                with launcher.lock(run / 'limits-gate') as gate:
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    limits = json.loads((run / 'limits.json').read_text())
                    if limits['sessions'] is not None:
                        limits['sessions'] = max(limits['sessions'], count + 1)
                    launcher.atomic(run / 'limits.json', limits)
                launcher.atomic(run / 'checkpoint.json', state)
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
                compact_completions()
            if task != state['task_id']:
                raise ValueError('active task changed outside the workflow; inspect the checkpoint')
            count += 1
            total += 1
            state['total_sessions'] = total
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
            progress_lines = session_progress(root, state, total)
            publish_progress(run, str(count), progress_lines)
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
                keys = [str(index) for index in
                        range(max(1, count - state['task_sessions'] + 1), count + 1)]
                completions.append((task, state['task_sessions'],
                                    time.time() - state['started_at'], keys, progress_lines[0]))
                if tasks > 1 or completed > 1:
                    compact_completions()
        if (run / 'stop').exists():
            reason = 'stopped at a session boundary'
    except launcher.Stopped:
        status, reason = 130, 'cancelled after owned cleanup'
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        status, reason = 1, str(error)
    finally:
        previous = read_progress(run)
        if previous and not previous[-1].get('replaces'):
            lines = previous[-1]['lines']
            outcome = ('Stopped' if status == 130 else 'Blocked' if status else
                       'Complete' if state['phase'] == 'complete' else reason)
            lines[-1] += ' — ' + outcome
            publish_progress(run, previous[-1]['key'], lines)
        for task, task_sessions, duration, _, _ in completions:
            show_completion(task, task_sessions, duration)
        save_handoff(run, state, reason,
                     display=not (status == 0 and completed and state['phase'] == 'complete'))
        if task_session_limit_reached(state) and state['phase'] != 'blocked':
            show_session_limit(state)
        if completions:
            from launcher_render import AgentRenderer
            print(f'- Total launcher sessions: {total}', flush=True)
            AgentRenderer(sys.stdout).console.rule(style='dim')
            sys.stdout.flush()
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
            question_path = previous / 'question.json'
            if state.get('phase') == 'blocked' and question_path.exists():
                question = json.loads(question_path.read_text())
                if question['id'] == state.get('blocker_id') and question.get('answer') is not None:
                    # Preserve an answer submitted just before stop/worker death,
                    # even if the owner had not checkpointed its recovery yet.
                    state.update(phase='recover', recovery_run=str(previous),
                                 user_answer={'question': question['question'], 'answer': question['answer']},
                                 task_session_limit=max(state.get('task_session_limit', MAX_TASK_SESSIONS),
                                                        state.get('task_sessions', 0) + 1))
                    state.pop('blocker_id', None)
                    state.pop('blocker', None)
            if state.get('in_flight'):
                if state.get('worktree_before') is not None:
                    candidates = set(state.get('stage_candidates', []))
                    candidates.update(session_changes(root, state['worktree_before']))
                    state['stage_candidates'] = sorted(candidates)
                state = dict(state, phase='recover', in_flight=False,
                             recovery_run=str(previous))
            # Keep the task's cumulative numbering, but give this new owner
            # five sessions of its own before the per-task stop applies again.
            used = state.get('task_sessions', 0)
            return dict(state, total_sessions=used,
                        task_session_limit=used + MAX_TASK_SESSIONS)
        if state.get('in_flight'):
            raise ValueError(f'interrupted task changed the queue; inspect the handoff in {previous}')
        return fresh_state(task)
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
