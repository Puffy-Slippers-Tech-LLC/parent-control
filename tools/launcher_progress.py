"""Durable controller steps, separate from frequently changing child output."""

import hashlib
import json
import re
import time


ANSI = re.compile(r'\x1b\[[?0-9;]*[A-Za-z]')


def completed_text(text):
    """Render completed progress consistently in controller and dashboard rows."""
    return re.sub(r'(?<=\()\d+(?=/\d+\))',
                  lambda match: '\033[32m' + match[0] + '\033[0m', ANSI.sub('', text))


def category_cases(current):
    name = 'E2E' if current['category'] == 'e2e' else current['category'].capitalize()
    return completed_text(f'{name} Cases: ({current["completed"]}/{current["total"]})')


def case_progress(run, *, reader=None):
    """Read spectator counts only; checkpoints remain the execution authority."""
    from watch_output import read_json
    value = (reader.read(run / 'case-progress.json', 8192) if reader is not None else
             read_json(run / 'case-progress.json', 8192))
    if (not isinstance(value, dict) or value.get('category') not in ('system', 'e2e')
            or type(value.get('area', False)) is not bool
            or any(type(value.get(key)) is not int for key in
                   ('completed', 'total', 'index', 'round', 'vm_started_ns', 'started_ns', 'case_started_ns'))
            or not 0 <= value['completed'] <= value['total'] <= 100000
            or not 1 <= value['index'] <= value['total']
            or value['round'] < 1
            or not 0 <= value['vm_started_ns'] <= value['started_ns'] <= value['case_started_ns'] <= time.monotonic_ns()
            or not isinstance(value.get('case_id'), str)
            or not re.fullmatch(r'[1-9][0-9]{0,9}', value['case_id'])
            or not isinstance(value.get('title'), str) or len(value['title']) > 384
            or not value['title'].isprintable()):
        raise ValueError('invalid category display progress')
    counts = value.get('categories')
    if (not isinstance(counts, dict) or not counts or set(counts) - {'system', 'e2e'}
            or any(not isinstance(item, dict) or set(item) != {'completed', 'total'}
                   or type(item['completed']) is not int or type(item['total']) is not int
                   or not 0 <= item['completed'] <= item['total'] <= 100000
                   for item in counts.values())
            or counts.get(value['category']) != dict(completed=value['completed'], total=value['total'])):
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
    elapsed = (now - current['vm_started_ns'] / 1e9) / 60
    overall = (f'Overall - {int(100 * overall_done / max(overall_total, 1))}% '
               f'({overall_done}/{overall_total}) - {elapsed:.1f}m')
    summary = Dashboard.ANSI.sub('', steps[-1]['lines'][0])
    steps[-1]['lines'][0] = completed_text(
        re.sub(r'Overall - [^|]+', overall + ' ', summary).rstrip()
        if ' | Overall - ' in summary else summary + ' | ' + overall)
    result = []
    for line in lines:
        plain = Dashboard.ANSI.sub('', line)
        if plain.startswith('Overall - '):
            line = completed_text(overall)
        else:
            prefix, marker, row = plain.partition('[')
            label, separator, tail = row.partition('] ')
            if marker and separator and tail.startswith(item.name):
                item.state = ('Failed' if label == '✗' else 'Passed' if done == total else
                              'Pending' if label in ('Pending', 'Waiting') else 'Running')
                item.wait_reason = ''
                if label == 'Waiting':
                    item.wait_reason = tail[len(item.name):].removeprefix(': ').rsplit(' (', 1)[0]
                elif reason := re.search(r'\) - [0-9.]+[sm] \((.*)\)$', tail):
                    item.wait_reason = reason[1]
                line = prefix + Dashboard([]).category(item, now)
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
    if status == 'fixing errors' and previous:
        key = previous[-1]['key']
        summary = previous[-1]['lines'][0]
    if status == 'fixing errors' and model:
        status += f' ({model}' + (f' {effort}' if effort else '') + ')'
    publish_progress(run, key, [completed_text(summary), 'Status: ' + status])


def repair_progress(run, steps, *, child_steps=None):
    """Overlay a child's test summary without changing the repair controller."""
    if not steps or steps[-1]['lines'][-1] not in ('Status: Running tests', 'Status: Verifying'):
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
