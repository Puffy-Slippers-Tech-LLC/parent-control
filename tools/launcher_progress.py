"""Durable controller steps, separate from frequently changing child output."""

import json


def read_progress(run):
    try:
        return json.loads((run / 'controller.json').read_text())
    except FileNotFoundError:
        return []


def publish_progress(run, key, lines):
    steps = read_progress(run)
    step = {'key': key, 'lines': lines}
    if steps and steps[-1] == step:
        return
    if steps and steps[-1]['key'] == key:
        steps[-1] = step
    else:
        steps.append(step)
    # Reconnecting observers start with the latest two major steps. Attached
    # observers retain their own controller scrollback.
    temporary = run / 'controller.tmp'
    temporary.write_text(json.dumps(steps[-2:]))
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
