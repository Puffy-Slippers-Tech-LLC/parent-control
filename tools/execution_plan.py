"""Ordered Markdown plans, independent of task execution and acceptance policy."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from document_checks import simple_inline_references


def queue_state(root, plan, queue, *, validate_pointer=True):
    text = (root / queue).read_text().split('## Deferred future work', 1)[0]
    rows = re.findall(r'^\| \[([ x])\] \| ([^|]+) \|', text, re.MULTILINE)
    if not rows:
        raise ValueError('no active task table found in the canonical queue')
    tasks = {task.strip(): mark == 'x' for mark, task in rows}
    if len(tasks) != len(rows):
        raise ValueError('duplicate task IDs in the canonical queue')
    current = next((task for task, complete in tasks.items() if not complete), None)
    pointer = re.search(r'^Next task: \*\*([^ ]+) —', (root / plan).read_text(), re.MULTILINE)
    if validate_pointer and current is not None and (pointer is None or pointer[1] != current):
        raise ValueError(f'plan pointer must name first unchecked task {current}')
    return current, tasks


def local_path(root, relative, *, base=None):
    """Validate a Markdown identity even while its file is being rewritten."""
    value = Path(relative)
    root = root.resolve()
    candidate = (base or root) / value
    if (value.is_absolute() or '..' in value.parts or value.suffix != '.md'
            or any(part.is_symlink() for part in (candidate, *candidate.parents))
            or not candidate.resolve().is_relative_to(root)):
        raise ValueError(f'plan path must name a regular checkout Markdown file: {relative}')
    return candidate


def local_file(root, relative, *, base=None):
    """Plan metadata can only name regular Markdown files within this checkout."""
    candidate = local_path(root, relative, base=base)
    if not candidate.is_file():
        raise ValueError(f'plan path must name a regular checkout Markdown file: {relative}')
    return candidate


def plan_namespace(path):
    return hashlib.sha256(path.encode()).hexdigest()


def evidence_references(text):
    """Compare simple inline references using their literal non-destination parts.

    Code spans, images and more complex Markdown remain literal: unsupported
    syntax must not turn an unrelated edit into an evidence-reference repair.
    """
    parts, position = [], 0
    for link in simple_inline_references(text):
        start, end = link.destination_start, link.destination_end
        parts.append(text[position:start])
        position = end
    # A tuple preserves link count and cannot collide with a literal placeholder
    # in unsupported Markdown. This comparison value never enters snapshots.
    return (*parts, text[position:])


def closeout_structure(rows, selected, *, completed=()):
    """Normalize bookkeeping using only completion captured before this task."""
    normalized = []
    for original in rows:
        row = original.copy()
        if row[2] == selected:
            row[3] = '<selected task link>'
            if len(row) > 7:  # Optional Estimate column, before the trailing delimiter.
                row[6] = '<selected task estimate>'
        elif row[2] in completed and len(row) > 7:
            row[6] = evidence_references(row[6])
        normalized.append(row)
    return normalized


def acceptance_metadata(text, identity):
    acceptance = re.findall(r'^Acceptance: (.*)$', text, re.M)
    if len(acceptance) != 1 or acceptance[0] not in ('installed', 'review', 'host', 'reconciliation'):
        raise ValueError(f'task {identity} needs one Acceptance declaration in its brief')
    targets = re.findall(r'^Targets: (.*)$', text, re.M)
    if len(targets) > 1:
        raise ValueError(f'task {identity} has duplicate Targets declarations')
    names = [name.strip() for name in targets[0].split(',')] if targets else []
    if (any(not name for name in names) or len(set(names)) != len(names)
            or acceptance[0] == 'installed' and not names):
        raise ValueError(f'task {identity} needs distinct explicit acceptance targets')
    return dict(acceptance=acceptance[0], targets=names)


@dataclass(frozen=True)
class Task:
    id: str
    complete: bool
    title: str
    brief: Path | None
    requires: tuple

    def acceptance_metadata(self):
        return acceptance_metadata(self.brief.read_text(), self.id)


@dataclass(frozen=True)
class Plan:
    root: Path
    path: str
    queue: str

    @classmethod
    def load(cls, root, path):
        master = local_file(root, path)
        links = re.findall(r'^Task queue: \[[^\]]+\]\(([^)]+)\)\.?$', master.read_text(), re.M)
        if len(links) != 1:
            raise ValueError('master plan needs one Task queue: [title](relative.md) declaration')
        queue = local_file(root, links[0], base=master.parent)
        return cls(root.resolve(), str(master.relative_to(root.resolve())),
                   str(queue.relative_to(root.resolve())))

    @property
    def namespace(self):
        return plan_namespace(self.path)

    def tasks(self):
        local_file(self.root, self.path)
        queue = local_file(self.root, self.queue)
        text = queue.read_text().split('## Deferred future work', 1)[0]
        tasks = []
        for line in text.splitlines():
            fields = [field.strip() for field in line.split('|')]
            if len(fields) < 6 or fields[1] not in ('[ ]', '[x]'):
                continue
            identity, title, dependencies = fields[2:5]
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', identity):
                raise ValueError('task IDs must be stable simple labels')
            complete = fields[1] == '[x]'
            link = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', title)
            if not complete and link is None:
                raise ValueError(f'unfinished task {identity} needs a brief link')
            brief = local_file(self.root, link[2], base=queue.parent) if link and not complete else None
            requires = tuple(item.strip() for item in dependencies.split(',')) if dependencies not in ('', '—', '-', 'Baseline') else ()
            tasks.append(Task(identity, complete, link[1] if link else title, brief, requires))
        # The queue is authoritative. A stale display pointer must not prevent
        # selection or recovery of its first unfinished task.
        current, states = queue_state(self.root, self.path, self.queue, validate_pointer=False)
        if [task.id for task in tasks] != list(states):
            raise ValueError('queue rows need Done, ID, Task, Requires and Scope columns')
        earlier = {}
        for task in tasks:
            if any(dependency not in earlier for dependency in task.requires):
                raise ValueError(f'task {task.id} requires an unknown or later task')
            if task.id == current and any(not earlier[dependency] for dependency in task.requires):
                raise ValueError(f'task {task.id} has unfinished prerequisites')
            earlier[task.id] = task.complete
        return tasks

    def state(self):
        return {task.id: task.complete for task in self.tasks()}

    def structure(self, *, selected=None, completed=()):
        text = (self.root / self.queue).read_text().split('## Deferred future work', 1)[0]
        rows = []
        for line in text.splitlines():
            if re.match(r'^\| \[[ x]\] \|', line):
                fields = [field.strip() for field in line.split('|')]
                fields[1] = '[ ]'
                rows.append(fields)
        return closeout_structure(rows, selected, completed=completed)

    def validate_recovery(self, state):
        """Protect sequential completion, not mutable queue descriptions."""
        _, after = queue_state(self.root, self.path, self.queue, validate_pointer=False)
        before = state['queue_before']
        if (list(after)[:len(before)] != list(before)
                or any(after[key] != done for key, done in before.items() if key != state['task_id'])
                or any(done for key, done in after.items() if key not in before)):
            raise ValueError('interrupted plan changed outside its selected task; inspect retained handoff')
        self.validate_scopes(state.get('queue_structure'), selected=state['task_id'],
                             completed={key for key, done in before.items() if done})
        return after

    def validate_scopes(self, before, *, selected=None, completed=()):
        """Presentation drift cannot silently replace retained task obligations."""
        if before is not None:
            current = {row[2]: row for row in self.structure()}
            if any(row[2] not in current or current[row[2]][5] != row[5] for row in before):
                raise ValueError('task scope changed; retain the queue for review')
            def dependencies(value):
                return {item.strip() for item in value.split(',')} - {'', '—', '-', 'Baseline'}
            earlier = set()
            for identity, row in current.items():
                if not dependencies(row[4]).issubset(earlier):
                    raise ValueError(f'task {identity} requires an unknown or later task')
                earlier.add(identity)
            for row in before:
                now = current[row[2]]
                if not dependencies(row[4]).issubset(dependencies(now[4])):
                    raise ValueError('task prerequisites changed; retain the queue for review')
                if row[2] not in completed and row[2] != selected:
                    old_link = re.fullmatch(r'\[[^\]]+\]\(([^)]+)\)', row[3])
                    new_link = re.fullmatch(r'\[[^\]]+\]\(([^)]+)\)', now[3])
                    if old_link is None or new_link is None or old_link[1] != new_link[1]:
                        raise ValueError('unfinished task brief changed; retain its acceptance obligations')
                if row[2] in completed and len(row) > 7:
                    if len(now) != len(row) or evidence_references(now[6]) != evidence_references(row[6]):
                        raise ValueError('completed task evidence claim changed; retain its accepted history')

    def prerequisite_repair(self, state):
        """Recognize only a new dependency block for the unfinished consumer.

        Recognition supplies the first prerequisite; it never changes a saved
        checkpoint or grants acceptance. Normal parsing retains pointer, path
        and backward-dependency guards before any structural repair is adopted.
        """
        if (state.get('pending_completion') is not None or state.get('commit_intent') is not None
                or state.get('phase') == 'complete' or state.get('status') == 'task_complete'):
            return None
        before = state.get('queue_before')
        saved = state.get('queue_structure')
        consumer = state.get('task_id')
        if (not isinstance(before, dict) or not isinstance(saved, list)
                or before.get(consumer) is not False
                or next((key for key, done in before.items() if not done), None) != consumer
                or any(not isinstance(row, list) or len(row) < 6 for row in saved)
                or [row[2] for row in saved] != list(before)):
            return None
        tasks = self.tasks()
        by_id = {task.id: task for task in tasks}
        ids = list(by_id)
        if ([identity for identity in ids if identity in before] != list(before)
                or any(identity not in by_id or by_id[identity].complete != done
                       for identity, done in before.items())):
            return None
        added = [identity for identity in ids if identity not in before]
        first = next((task for task in tasks if not task.complete), None)
        if not added or first is None or first.id != added[0] or any(by_id[key].complete for key in added):
            return None
        position = ids.index(consumer)
        if ids[max(0, position - len(added)):position] != added:
            return None
        try:
            self.validate_scopes(saved, selected=consumer,
                                 completed={key for key, done in before.items() if done})
        except ValueError:
            return None
        # Descriptions can evolve concurrently. Preserve the consumer's actual
        # dependency chain rather than requiring every table cell to match.
        original = next(row for row in saved if row[2] == consumer)
        dependencies = (tuple(item.strip() for item in original[4].split(','))
                        if original[4] not in ('', '—', '-', 'Baseline') else ())
        if not set(dependencies).issubset(by_id[consumer].requires):
            return None
        ancestry = set()
        pending = list(by_id[consumer].requires)
        while pending:
            identity = pending.pop()
            task = by_id[identity]  # tasks() already enforces backward known IDs.
            if task.complete or identity in ancestry:
                continue
            if identity not in added:
                return None
            ancestry.add(identity)
            pending.extend(task.requires)
        if ancestry != set(added):
            return None
        # New briefs must be executable plan tasks, not merely valid links.
        for identity in added:
            by_id[identity].acceptance_metadata()
        return first

    def next_task(self):
        return next((task for task in self.tasks() if not task.complete), None)

    def validate_transition(self, before, task_id, *, complete, structure=None):
        after = self.state()
        expected = dict(before)
        if complete:
            expected[task_id] = True
        if (list(after)[:len(expected)] != list(expected)
                or any(after[key] != done for key, done in expected.items())
                or any(done for key, done in after.items() if key not in expected)):
            raise ValueError('only the selected task may change completion; preserve task order and scope')
        self.validate_scopes(structure, selected=task_id,
                             completed={key for key, done in before.items() if done})
