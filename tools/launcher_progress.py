"""Durable controller steps, separate from frequently changing child output."""

import json


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


def repair_progress(run, steps):
    """Overlay a child's test summary without changing the repair controller."""
    if not steps or steps[-1]['lines'][-1] != 'Status: Running tests':
        return steps
    child = run / 'test-controller.json'
    child_steps = json.loads(child.read_text()) if child.exists() else []
    if child_steps:
        prefix, _, summary = steps[-1]['lines'][0].partition(': ')
        nested = child_steps[-1]['lines'][0]
        if 'Category: all ' in summary:
            summary = nested
        else:
            summary = summary.partition(' | ')[0] + ' | ' + nested.partition(' | ')[2]
        steps[-1]['lines'][0] = prefix + ': ' + summary
    return steps
