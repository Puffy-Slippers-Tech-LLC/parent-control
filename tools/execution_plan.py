"""Ordered Markdown plans, independent of task execution and acceptance policy."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


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


def closeout_structure(rows, selected):
    """Normalize selected-row bookkeeping, including pre-normalization checkpoints."""
    normalized = []
    for original in rows:
        row = original.copy()
        if row[2] == selected:
            row[3] = '<selected task link>'
            if len(row) > 7:  # Optional Estimate column, before the trailing delimiter.
                row[6] = '<selected task estimate>'
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
        current, states = queue_state(self.root, self.path, self.queue)
        if [task.id for task in tasks] != list(states):
            raise ValueError('queue rows need Done, ID, Task, Requires and Scope columns')
        earlier = {}
        for task in tasks:
            if any(dependency not in earlier for dependency in task.requires):
                raise ValueError(f'task {task.id} requires an unknown or later task')
            if task.id == current and any(not earlier[dependency] for dependency in task.requires):
                raise ValueError(f'task {task.id} has unfinished prerequisites')
            earlier[task.id] = task.complete
        if current is None and not re.search(r'^Next task: none\.?$', (self.root / self.path).read_text(), re.M):
            raise ValueError('a finished plan must declare Next task: none.')
        return tasks

    def state(self):
        return {task.id: task.complete for task in self.tasks()}

    def structure(self, *, selected=None):
        text = (self.root / self.queue).read_text().split('## Deferred future work', 1)[0]
        rows = []
        for line in text.splitlines():
            if re.match(r'^\| \[[ x]\] \|', line):
                fields = [field.strip() for field in line.split('|')]
                fields[1] = '[ ]'
                rows.append(fields)
        return closeout_structure(rows, selected)

    def validate_recovery(self, state):
        """Only an interrupted selected row may have partially closed out."""
        _, after = queue_state(self.root, self.path, self.queue, validate_pointer=False)
        before = state['queue_before']
        if (list(after) != list(before)
                or any(after[key] != done for key, done in before.items() if key != state['task_id'])
                or (state.get('queue_structure') is not None and
                    self.structure(selected=state['task_id']) !=
                    closeout_structure(state['queue_structure'], state['task_id']))):
            raise ValueError('interrupted plan changed outside its selected task; inspect retained handoff')
        return after

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
        saved = closeout_structure(saved, consumer)
        # Existing rows retain every field; only the consumer's Requires field
        # may change. Its link is already masked in the saved structure.
        current = {row[2]: row for row in self.structure(selected=consumer)}
        for original in saved:
            row = current[original[2]].copy()
            if original[2] == consumer:
                dependencies = (tuple(item.strip() for item in original[4].split(','))
                                if original[4] not in ('', '—', '-', 'Baseline') else ())
                if not set(dependencies).issubset(by_id[consumer].requires):
                    return None
                row[4] = original[4]
            if row != original:
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
        if list(after) != list(expected) or after != expected:
            raise ValueError('only the selected task may change completion; preserve task order and scope')
        if (structure is not None and self.structure(selected=task_id) !=
                closeout_structure(structure, task_id)):
            raise ValueError('task scope or prerequisites changed; retain the queue for review')
