"""Workflow-neutral options and durable task budgets.

Workers own task boundaries; observers may replace the budget under the same
gate. A task means an accepted plan item, or a completed repair category pass.
Model sessions and test cases never consume this budget themselves.
"""

import fcntl
import json

import detached_launcher as launcher


class TaskLimitReached(Exception):
    """A bounded run finished its authorized work without a failure."""


def task_limit(value):
    return int(value) if value is not None and int(value) > 0 else None


def add_options(parser, *, stop_help='stop at the next safe task/session boundary'):
    parser.add_argument('--tasks', type=int,
                        help='maximum completed tasks; 0 or negative: all remaining; replaces an active limit')
    parser.add_argument('--stop', action='store_true', help=stop_help)


def warn_remaining(tasks, remaining, *, label):
    if tasks is not None and tasks > remaining:
        print(f'{label}: warning: requested {tasks} tasks, but only {remaining} remain; '
              'the launcher will finish when the queue is complete.', flush=True)


class TaskBudget:
    """One lock serializes admission, completion and live limit changes."""
    def __init__(self, run):
        self.run = run

    def initialize(self, tasks):
        launcher.atomic(self.run / 'limits.json', dict(tasks=task_limit(tasks), started=0, completed=0))

    def read(self):
        return json.loads((self.run / 'limits.json').read_text())

    def update(self, operation):
        with launcher.lock(self.run / 'limits-gate') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            value = self.read()
            result = operation(value)
            launcher.atomic(self.run / 'limits.json', value)
            return result

    def set_limit(self, tasks):
        def change(value):
            if value.get('closed') or (self.run / 'result.json').exists():
                raise ValueError('active launcher is finishing; limits can no longer be adjusted')
            value['tasks'] = task_limit(tasks)
            return value['tasks']
        if not (self.run / 'limits.json').exists():
            raise ValueError('active launcher predates adjustable limits; attach without --tasks')
        return self.update(change)

    def admit(self, *, exempt=False):
        def begin(value):
            if value.get('closed'):
                return False
            if not exempt and value['tasks'] is not None and value['completed'] >= value['tasks']:
                value['closed'] = True
                return False
            value['started'] += 1
            return True
        return self.update(begin)

    def complete(self):
        self.update(lambda value: value.update(completed=value['completed'] + 1))

    def close(self):
        self.update(lambda value: value.update(closed=True))


def task_progress(run, steps):
    path = run / 'limits.json'
    if not path.exists():
        return steps
    value = TaskBudget(run).read()
    limit = value['tasks']
    completed = value.get('completed', 0)
    position = completed + 1
    return [{'key': 'runtime-tasks', 'pinned': True,
             'lines': [f'Tasks: {position}/{limit if limit is not None else "all"}']}, *steps]
