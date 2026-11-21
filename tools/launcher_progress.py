"""Durable controller steps, separate from frequently changing child output."""

import json
import re
import sys
import time


def task_heading(task, title, brief=None):
    """Use the same linked, bold task label in every execution-plan pane."""
    label = f'\033[1mTask {task}\033[22m'
    if brief is not None:
        label = f'\033]8;;{brief.resolve().as_uri()}\033\\{label}\033]8;;\033\\'
    title = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', title).replace('`', '').replace('**', '')
    return f'{label}: {title}'


def plan_task_heading(root, queue, task):
    text = (root / queue).read_text().split('## Deferred future work', 1)[0]
    row = re.search(r'^\| \[[ x]\] \| ' + re.escape(task) + r' \| ([^|]+) \|', text, re.MULTILINE)
    title = row[1].strip() if row else task
    brief = re.search(r'\[[^\]]+\]\(([^)]+)\)', title)
    target = (root / queue).parent / brief[1] if brief else root / queue
    return task_heading(task, title, target)


def session_lines(heading, session, model, effort, *, summary=None):
    detail = f'{summary} ({model} {effort})' if summary else f'{model} {effort}'
    return [heading, f'\033[1mSession {session}\033[22m: {detail}']


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


def progress_keys(state):
    """Specialized engines may use session keys; ordinary plans use task IDs."""
    return state.get('progress_keys', [state.get('task_id')])


def task_recap(run, steps, *, reader=None, now=None):
    """Project plan task timing and suspension without changing durable rows."""
    from rich.color import Color
    from launcher_render import BLUE
    checkpoint = run / 'checkpoint.json'
    if not steps:
        return steps
    try:
        state = reader.read(checkpoint) if reader is not None else json.loads(checkpoint.read_text())
    except FileNotFoundError:
        return steps
    for suspended in state.get('suspended_tasks', {}).values():
        keys = progress_keys(suspended)
        previous = [step for step in steps if not step.get('replaces') and step['key'] in keys]
        if previous:
            latest = previous[-1]
            steps = [dict(step, lines=[f"\033[38;2;128;128;128m{step['lines'][0]} — Suspended for prerequisite\033[39m"])
                     if step is latest else step for step in steps
                     if step not in previous or step is latest]
    keys = progress_keys(state)
    if (steps[-1].get('replaces') or 'started_at' not in state
            or steps[-1]['key'] not in keys):
        return steps
    from launcher_session import clock_duration
    duration = state.get('completed_at', time.time() if now is None else now) - state['started_at']
    summary = ' | ' + clock_duration(duration)
    color = '\033[' + ';'.join(Color.parse(BLUE).get_ansi_codes()) + 'm' if state['phase'] != 'complete' else ''
    reset = '\033[39m' if color else ''
    return [dict(step, lines=[color + line + reset
                             for line in [step['lines'][0] + summary, *step['lines'][1:]]])
            if not step.get('replaces') and step['key'] in keys
            else step for step in steps]


def plan_status(run, steps, *, reader, active):
    """Shared editor projection for every execution-plan launcher."""
    from launcher_render import clean
    from launcher_session import clock_duration
    steps = [dict(step, lines=[re.sub(r'Session \[(\d+)\]', r'Session \1', line)
                               for line in step['lines']]) for step in steps]
    # Retain compact completions and only the latest session for each task.
    def task_key(step):
        heading = clean(step['lines'][0])
        # A blocker reached before the first session has only a task ID.
        # Group it with the later titled session instead of retaining a stale pause.
        task = re.match(r'^Task ([\w.-]+)(?=:|$)', heading)
        return ('task', task[1]) if task else ('heading', heading)

    latest = {task_key(step): step for step in steps
              if not step.get('pinned') and not step.get('replaces')}
    steps = [step for step in steps if step.get('pinned') or step.get('replaces')
             or latest[task_key(step)] is step]
    steps = [dict(step, lines=[completion_line(step['lines'][0])])
             if step.get('replaces') else step for step in steps]
    try:
        state = reader.read(run / 'chat-state.json')
    except FileNotFoundError:
        state = {}
    steps = task_recap(run, steps, reader=reader,
                      now=state.get('finished_at') if not active else None)
    current = next((step for step in reversed(steps)
                    if not step.get('pinned') and not step.get('replaces')), None)
    session = state.get('task_session', state.get('session'))
    started = state.get('started_at')
    if (current and current['key'] == state.get('progress_key')
            and started is not None and len(current['lines']) > 1
            and clean(current['lines'][-1]).startswith(
                (f'Session [{session}]:', f'Session {session}:'))):
        elapsed = clock_duration(state.get('finished_at', time.time()) - started)
        current['lines'][-1] += ' | ' + elapsed
    return steps


def completion_line(line):
    """Normalize old and current plan recaps without rewriting publications."""
    from rich.text import Text
    from launcher_render import AgentRenderer
    text = Text.from_ansi(line)
    if not re.match(r'^(?:✓ )?Task [\w.-]+:', text.plain):
        return line
    suffix = re.search(r'\s+[—–-]\s+complete\.?$', text.plain, re.IGNORECASE)
    if suffix:
        text = text[:suffix.start()]
    duration = re.search(r'\s+(?:\((?:sessions=\d+,\s*duration=)?(\d+(?:h \d+m|m)|duration unavailable)\)|\| (\d+(?:h \d+m|m)|duration unavailable))$', text.plain)
    elapsed = (duration[1] or duration[2]) if duration else 'duration unavailable'
    if duration:
        text = text[:duration.start()]
    if not text.plain.startswith('✓ '):
        text = Text('✓ ') + text
    text.append(' | ' + elapsed)
    text.stylize('green')
    console = AgentRenderer(sys.stdout).console
    with console.capture() as capture:
        console.print(text, end='', soft_wrap=True)
    return capture.get()


def plan_progress(run, steps, child_steps=None, *, remaining=None):
    from launcher_runtime import task_progress
    return task_progress(run, task_recap(run, steps), remaining=remaining)


def publish_completion(run, key, heading, duration, keys):
    """Compact accepted plan sessions into one durable green overview entry."""
    from launcher_session import clock_duration
    from launcher_render import AgentRenderer
    from rich.text import Text
    recap = Text('✓ ') + Text.from_ansi(heading)
    elapsed = clock_duration(duration) if duration is not None else 'duration unavailable'
    recap.append(f' ({elapsed})')
    recap.stylize('green')
    console = AgentRenderer(sys.stdout).console
    with console.capture() as capture:
        console.print(recap, end='', soft_wrap=True)
    publish_progress(run, 'complete-' + key, [capture.get()], replaces=keys)


def read_progress(run):
    try:
        return json.loads((run / 'controller.json').read_text())
    except FileNotFoundError:
        return []


def publish_progress(run, key, lines, *, replaces=()):
    steps = read_progress(run)
    step = {'key': key, 'lines': lines}
    if replaces:
        step['replaces'] = list(replaces)
        steps = [previous for previous in steps if previous['key'] not in replaces]
    if (steps and steps[-1] == step) or (replaces and step in steps):
        return
    existing = (next((index for index, previous in enumerate(steps)
                      if previous['key'] == key), None) if replaces else
                len(steps) - 1 if steps and steps[-1]['key'] == key else None)
    if existing is not None:
        steps[existing] = step
    else:
        steps.append(step)
    # Keep compact completions alongside the latest two active steps so a
    # reconnect can recover the same task recap as an attached observer.
    # Match entries by identity: an older step may have identical contents.
    active = [previous for previous in steps if not previous.get('replaces')][-2:]
    retained = [previous for previous in steps
                if previous.get('replaces') or any(previous is current for current in active)]
    temporary = run / 'controller.tmp'
    temporary.write_text(json.dumps(retained))
    temporary.replace(run / 'controller.json')
