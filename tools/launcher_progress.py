"""Durable controller steps, separate from frequently changing child output."""

import hashlib
import json
import re
import sys
import time


ANSI = re.compile(r'\x1b\[[?0-9;]*[A-Za-z]')


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
    return [heading, f'\033[1mSession [{session}]\033[22m: {detail}']


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
    color = '\033[38;2;0;102;255m' if state['phase'] != 'complete' else ''
    reset = '\033[39m' if color else ''
    return [dict(step, lines=[color + line + reset
                             for line in [step['lines'][0] + summary, *step['lines'][1:]]])
            if not step.get('replaces') and step['key'] in keys
            else step for step in steps]


def plan_status(run, steps, *, reader, active):
    """Shared editor projection for every execution-plan launcher."""
    from launcher_render import clean
    from launcher_session import clock_duration
    # Retain compact completions and only the latest session for each task.
    latest = {step['lines'][0]: step for step in steps
              if not step.get('pinned') and not step.get('replaces')}
    steps = [step for step in steps if step.get('pinned') or step.get('replaces')
             or latest[step['lines'][0]] is step]
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


def completed_text(text):
    """Render completed progress consistently in controller and dashboard rows."""
    return re.sub(r'(?<=\()\d+(?=/)',
                  lambda match: '\033[32m' + match[0] + '\033[0m', ANSI.sub('', text))


def case_counts(completed, failed, total, error_log):
    from pathlib import Path
    count = f'\033[31;4m{failed}\033[0m'
    if error_log:
        count = f'\033]8;;{Path(error_log).as_uri()}\033\\{count}\033]8;;\033\\'
    return f'\033[32m{completed}\033[0m/{count}/{total}'


def category_cases(current):
    name = 'E2E' if current['category'] == 'e2e' else current['category'].capitalize()
    return f'{name} Cases: (' + case_counts(current['completed'], current.get('failed', 0),
        current['total'], current.get('error_log')) + ')'


def case_progress(run, *, reader=None):
    """Read spectator counts only; checkpoints remain the execution authority."""
    from watch_output import read_json
    value = (reader.read(run / 'case-progress.json', 8192) if reader is not None else
             read_json(run / 'case-progress.json', 8192))
    if (not isinstance(value, dict) or value.get('category') not in ('system', 'integration', 'e2e')
            or type(value.get('area', False)) is not bool
            or any(type(value.get(key)) is not int for key in
                   ('completed', 'total', 'index', 'round', 'vm_started_ns', 'started_ns', 'case_started_ns'))
            or not 0 <= value['completed'] <= value['total'] <= 100000
            or not 1 <= value['index'] <= value['total']
            or value['round'] < 1
            or not 0 <= value['vm_started_ns'] <= value['started_ns'] <= value['case_started_ns'] <= time.monotonic_ns()
            or not isinstance(value.get('case_id'), str)
            or not re.fullmatch(r'check_[a-z][a-z0-9_]*' if value['category'] == 'integration'
                                else r'[1-9][0-9]{0,9}', value['case_id'])
            or not isinstance(value.get('title'), str) or len(value['title']) > 384
            or not value['title'].isprintable()):
        raise ValueError('invalid category display progress')
    counts = value.get('categories')
    if (not isinstance(counts, dict) or not counts or set(counts) - {'system', 'integration', 'e2e'}
            or any(not isinstance(item, dict) or not {'completed', 'total'} <= set(item)
                   or type(item['completed']) is not int or type(item['total']) is not int
                   or not 0 <= item['completed'] <= item['total'] <= 100000
                   for item in counts.values())
            or any(type(item.get('failed', 0)) is not int or not 0 <= item.get('failed', 0) <= item['total']
                   for item in counts.values())
            or any(counts.get(value['category'], {}).get(key) != value[key] for key in ('completed', 'total'))):
        raise ValueError('invalid overall display progress')
    return value


def case_frame(steps, lines, current):
    """Show VM-wide overall progress and category-specific selected-case counters."""
    from regression import Category, Dashboard, CATEGORY_NAMES
    if not steps or f'Category: {current["category"]} (' not in steps[-1]['lines'][0]:
        return lines
    done, total = current['completed'], current['total']
    now = time.monotonic()
    item = Category(CATEGORY_NAMES[current['category']], total, done=done,
                    started=current['started_ns'] / 1e9)
    overall_done = sum(count['completed'] for count in current['categories'].values())
    overall_total = sum(count['total'] for count in current['categories'].values())
    overall_failed = sum(count.get('failed', 0) for count in current['categories'].values())
    elapsed = (now - current['vm_started_ns'] / 1e9) / 60
    overall = (f'Overall - {int(100 * overall_done / max(overall_total, 1))}% '
               f'({case_counts(overall_done, overall_failed, overall_total, current.get("error_log"))}) - {elapsed:.1f}m')
    summary = Dashboard.ANSI.sub('', steps[-1]['lines'][0])
    steps[-1]['lines'][0] = (
        re.sub(r'Overall - [^|]+', overall + ' ', summary).rstrip()
        if ' | Overall - ' in summary else summary + ' | ' + overall)
    # The main suite and separate upgrade attempts share a category name.
    # Their selected-case counts belong to one summary, not to each attempt.
    pattern = re.compile(r'^(.*?)\[([^]]+)\] (' + re.escape(item.name) + r'(?=[: ]).*)$')
    rows = {index: match for index, line in enumerate(lines)
            if (match := pattern.match(Dashboard.ANSI.sub('', line)))}
    priority = ('✗', 'Running', 'Waiting', 'Pending', '✓')
    representative = min(rows.values(), key=lambda match:
                         priority.index(match[2]) if match[2] in priority else len(priority),
                         default=None)
    result = []
    for index, line in enumerate(lines):
        plain = Dashboard.ANSI.sub('', line)
        if plain.startswith('Overall - '):
            line = overall
        else:
            if index in rows:
                if index != next(iter(rows)):
                    continue
                prefix = rows[index][1]
                label, tail = representative[2], representative[3]
                item.state = ('Failed' if label == '✗' else 'Passed' if done == total else
                              'Pending' if label in ('Pending', 'Waiting') else 'Running')
                item.wait_reason = ''
                if label == 'Waiting':
                    item.wait_reason = tail[len(item.name):].removeprefix(': ').rsplit(' (', 1)[0]
                elif reason := re.search(r'\) - [0-9.]+[sm] \((.*)\)$', tail):
                    item.wait_reason = reason[1]
                line = prefix + Dashboard([]).category(item, now)
                line = re.sub(r'\(\d+/\d+\)', lambda _: '(' + case_counts(done,
                    current.get('failed', 0), total, current.get('error_log')) + ')',
                    Dashboard.ANSI.sub('', line))
        result.append(line)
    return result


def watch_case_progress(root, vm, progress, *, reader):
    """Overlay the active repair queue on both manual and recorded VM tiles."""
    from test_storage import directory
    from watch_output import active_run, snapshot
    try:
        run = active_run(directory('fix-tests', root=root, create=False), workflow=True, reader=reader)
        if run is None or reader.read(run / 'pipelines.json').get(vm, {}).get('status') != 'running':
            return progress
        child = run / ('pipeline-' + hashlib.sha256(vm.encode()).hexdigest()[:24])
        if (reader.read(child / 'vm.json') != {'vm': vm}
                or reader.read(child / 'pipeline.json') != {'parent': str(run)}):
            return progress
        current = case_progress(child, reader=reader)
        steps = snapshot(child / 'controller.json', steps=True, reader=reader)
        if not steps or f'Category: {current["category"]} (' not in steps[-1]['lines'][0]:
            return progress
        # A previous invocation's heartbeat can remain fresh during startup.
        if not progress or progress.get('started_ns', 0) < current['case_started_ns']:
            progress = dict(step='', operation='Preparing VM: Waiting for test runner')
        else:
            progress = dict(progress)
        # An area invocation runs multiple selected checks. Its fresh shared
        # heartbeat owns their live IDs/timers; the launcher still owns totals.
        active = ({key: progress[key] for key in ('case_id', 'title', 'case_started_ns')}
                  if current.get('area') and 'case_id' in progress else {})
        progress.update(current=current['completed'], total=current['total'],
                        case_id=current['case_id'], title=current['title'],
                        started_ns=current['started_ns'], case_started_ns=current['case_started_ns'])
        progress.update(active)
        return progress
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return progress


def watch_integration_progress(root, vm, progress, *, reader):
    """Resolve focused integration runs, which have no system/E2E heartbeat."""
    import ast
    from test_storage import directory
    from watch_output import active_run
    try:
        base = directory('sessions', root=root, create=False) / ('vm-' + vm)
        run = active_run(base, reader=reader)
        if run is None:
            return progress
        current = reader.read(base / 'current.json', 4096)
        if current['run'] != run.name:
            return progress
        args = current['argv']
        if 'integration' not in args:
            return progress
        case = next((arg.partition('=')[2] for arg in args
                     if arg.startswith('--resume-case=')), None)
        if case is None:
            index = args.index('integration') + 1
            case = args[index] if index < len(args) else ''
        case = case.removesuffix('.py')
        if not re.fullmatch(r'check_[a-z][a-z0-9_]*', case):
            return progress
        source = root / 'tests/integration' / (case + '.py')
        if source.is_symlink():
            return progress
        description = ast.get_docstring(ast.parse(source.read_text())) or ''
        title = case.removeprefix('check_').replace('_', ' ').capitalize()
        counts = ({key: progress[key] for key in ('current', 'total')}
                  if progress and progress.get('case_id') == case else dict(current=1, total=1))
        return dict(**counts, case_id=case, title=title,
                    step=' '.join(description.split()), operation='')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, SyntaxError):
        return progress


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
    active = [previous for previous in steps if not previous.get('replaces')][-2:]
    retained = [previous for previous in steps if previous.get('replaces') or previous in active]
    temporary = run / 'controller.tmp'
    temporary.write_text(json.dumps(retained))
    temporary.replace(run / 'controller.json')


def publish_repair_status(run, round_number, category, categories, status, *, model=None, effort=None,
                          completed=0):
    """Update one category entry through testing, repair and retries."""
    previous = repair_progress(run, read_progress(run))
    key = f'{round_number}:{category}'
    summary = f'Round {round_number}: Category: {category} ({completed}/{len(categories)})'
    if previous and previous[-1]['key'] == key:
        # A phase change is not a new case selection. Keep the last normal
        # runner's counts while repairing, verifying or waiting to resume.
        _, separator, detail = previous[-1]['lines'][0].partition(' | ')
        if separator:
            summary += separator + detail
    if status == 'fixing errors' and previous:
        key = previous[-1]['key']
        summary = previous[-1]['lines'][0]
    if status == 'fixing errors' and model:
        status += f' ({model}' + (f' {effort}' if effort else '') + ')'
    publish_progress(run, key, [completed_text(summary), 'Status: ' + status])


def repair_progress(run, steps, *, child_steps=None):
    """Overlay a child's test summary without changing the repair controller."""
    # A focused verification describes only its retry, not the category's
    # accumulated passes. Retain the normal-run summary until work resumes.
    if not steps or steps[-1]['lines'][-1] != 'Status: Running tests':
        return steps
    if child_steps is None:
        child = run / 'test-controller.json'
        child_steps = json.loads(child.read_text()) if child.exists() else []
    if child_steps:
        prefix, _, summary = ANSI.sub('', steps[-1]['lines'][0]).partition(': ')
        nested = ANSI.sub('', child_steps[-1]['lines'][0])
        if 'Category: all ' in summary and (category := re.search(r'Category: (\S+) ', nested)):
            summary = summary.replace('Category: all ', f'Category: {category[1]} ', 1)
        summary = summary.partition(' | ')[0] + ' | ' + nested.partition(' | ')[2]
        steps[-1]['lines'][0] = completed_text(prefix + ': ' + summary)
    return steps
