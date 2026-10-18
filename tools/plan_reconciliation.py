"""Explicit task consolidation, verified against a committed retained queue.

Only administrative reconciliation calls this module. Ordinary restart and
acceptance guards never infer or adopt a merge.
"""

import re

from execution_plan import acceptance_metadata, local_path


def consolidation(root, plan, state, declarations, base, *, git):
    merges = {}
    for declaration in declarations:
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)=([A-Za-z0-9][A-Za-z0-9._-]*)', declaration)
        if match is None or match[1] in merges or match[1] == match[2]:
            raise ValueError('task merges need distinct OLD=KEEP declarations')
        merges[match[1]] = match[2]
    if not merges or not isinstance(base, str) or not re.fullmatch(r'[0-9a-f]{40,64}', base):
        raise ValueError('task consolidation needs explicit merges and a full committed base ID')
    if set(merges) & set(merges.values()):
        raise ValueError('task consolidation cannot chain merges')
    if git(root, 'merge-base', '--is-ancestor', base, 'HEAD', check=False).returncode:
        raise ValueError('consolidation base must be an ancestor of HEAD')

    before, after = state['queue_before'], plan.state()
    if (set(before) - set(after) != set(merges) or set(after) - set(before)
            or [key for key in before if key not in merges] != list(after)):
        raise ValueError('consolidation must remove exactly its declared sources without reordering tasks')
    if state.get('pending_completion') is not None or any(
            before[key] or target not in after or before[target] or after[target]
            or list(before).index(target) >= list(before).index(key)
            for key, target in merges.items()):
        raise ValueError('consolidation requires unchecked sources and earlier unchecked destinations')
    if any(before[key] != after[key] for key in after):
        raise ValueError('consolidation cannot change task completion')

    master = git(root, 'show', f'{base}:{plan.path}').stdout
    links = re.findall(r'^Task queue: \[[^\]]+\]\(([^)]+)\)\.?$', master, re.M)
    if (len(links) != 1 or local_path(root, links[0], base=(root / plan.path).parent)
            != root / plan.queue):
        raise ValueError('consolidation base must use the retained master and queue')
    text = git(root, 'show', f'{base}:{plan.queue}').stdout.split('## Deferred future work', 1)[0]
    original = [[field.strip() for field in line.split('|')]
                for line in text.splitlines() if re.match(r'^\| \[[ x]\] \|', line)]
    if ([row[2] for row in original] != list(before)
            or any(len(row) < 6 or (row[1] == '[x]') != before[row[2]] for row in original)):
        raise ValueError('consolidation base does not match retained task identities and completion')
    saved = {row[2]: row for row in state['queue_structure']}
    if any(row[4:6] != saved[row[2]][4:6] for row in original):
        raise ValueError('consolidation base does not match retained scopes and dependencies')
    originals = {row[2]: row for row in original}
    tasks = {task.id: task for task in plan.tasks()}
    rows = {row[2]: row for row in plan.structure()}

    def dependencies(row):
        return {value.strip() for value in row[4].split(',')} - {'', '—', '-', 'Baseline'}

    records, obligations = {}, {}
    inherited = state.get('consolidation_obligations', {})
    if type(inherited) is not dict or any(type(items) is not list for items in inherited.values()):
        raise ValueError('retained consolidation obligations are malformed')
    for identity, items in inherited.items():
        obligations.setdefault(merges.get(identity, identity), []).extend(items)

    def metadata(identity):
        match = re.fullmatch(r'\[[^\]]+\]\(([^)]+)\)', originals[identity][3])
        if match is None:
            raise ValueError('consolidation base needs an original unfinished brief')
        brief = local_path(root, match[1], base=(root / plan.queue).parent)
        text = git(root, 'show', f'{base}:{brief.relative_to(root)}').stdout
        record = acceptance_metadata(text, identity)
        records[identity] = dict(record, brief=str(brief))
        if identity in merges or identity in merges.values():
            obligations.setdefault(merges.get(identity, identity), []).append(
                dict(task_id=identity, scope=originals[identity][5], brief=text, **record))
        return record

    for identity, task in tasks.items():
        group = [identity, *(key for key, target in merges.items() if target == identity)]
        expected = {merges.get(key, key) for member in group
                    for key in dependencies(originals[member])} - {identity}
        if dependencies(rows[identity]) != expected:
            raise ValueError('consolidation must preserve dependencies through the declared mapping')
        if len(group) == 1 and rows[identity][5] != originals[identity][5]:
            raise ValueError('consolidation cannot change an unrelated task scope')
        if not task.complete:
            prior = [metadata(member) for member in group]
            current = task.acceptance_metadata()
            if (any(item['acceptance'] != current['acceptance'] for item in prior)
                    or set(current['targets']) != {target for item in prior for target in item['targets']}):
                raise ValueError('consolidation must preserve acceptance kind and the union of targets')
            if len(group) > 1 and any(originals[member][5] not in task.brief.read_text() for member in group):
                raise ValueError('combined brief must retain every original task scope verbatim')
    pending = state.get('suspended_tasks', {})
    if type(pending) is not dict or set(pending) & set(merges) or state.get('task_id') in merges:
        raise ValueError('consolidation cannot discard a source task with a retained handoff')
    for retained in (state, *pending.values()):
        if type(retained) is not dict:
            raise ValueError('retained task is malformed')
        if retained.get('task') and not before.get(retained.get('task_id'), False):
            record = records.get(retained.get('task_id'))
            if (type(retained['task']) is not dict or record is None
                    or any(retained['task'].get(key) != value for key, value in record.items())):
                raise ValueError('retained task metadata does not match the consolidation base')
    return merges, obligations
