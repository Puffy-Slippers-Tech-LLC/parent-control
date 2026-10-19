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


class SessionResultRejected(ValueError):
    """A successful agent turn needs correction before the workflow can advance."""

    def __init__(self, message, result=None):
        super().__init__(message)
        self.result = result


def read_session_result(run):
    try:
        return json.loads((run / 'agent-result.json').read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError) as error:
        raise SessionResultRejected('agent response is missing or invalid JSON: ' + str(error)) from error


def validate_session_result(result, validate):
    """Only response validation is recoverable; transport/ownership failures escape."""
    try:
        return validate(result)
    except ValueError as error:
        raise SessionResultRejected(str(error), result) from error


def result_rejection(error, response):
    result = error.result if isinstance(error.result, dict) else {}
    return dict(reason=str(error), response=str(response),
                **{key: result[key][:16000] for key in ('summary', 'handoff')
                   if isinstance(result.get(key), str)})


def retain_result_rejection(run, error, *, label, checkpoint=None):
    """Keep the latest rejected response in the existing bounded run allocation.

    Callers finish owned cleanup before invoking this, keep their original task
    and acceptance baseline, and spend their normal session budget on correction.
    Never call this for provider refusals, execution failures or Git close-out.
    A checkpointed workflow records recovery before retaining its source response;
    interruption during retention can still use that exact source in the old run.
    """
    response = run / 'agent-result.json'
    rejected = run / 'rejected-agent-result.json'
    record = result_rejection(error, response if checkpoint is not None else rejected)
    if checkpoint is not None:
        checkpoint['result_recovery'] = record
        launcher.atomic(run / 'checkpoint.json', checkpoint)
    if response.exists():
        temporary = rejected.with_suffix('.tmp')
        temporary.write_bytes(response.read_bytes())
        temporary.replace(rejected)
    elif error.result is not None:
        launcher.atomic(rejected, error.result)
    else:
        rejected.write_text('', encoding='utf-8')  # Missing output must not reuse an older response.
    record['response'] = str(rejected)
    launcher.atomic(run / 'result-rejection.json', record)
    if checkpoint is not None:
        launcher.atomic(run / 'checkpoint.json', checkpoint)
    print(f'{label}: response rejected: {error}. Returning to the coordinator within '
          'the existing session limit; no task accepted.', flush=True)
    return record


def result_recovery_instructions(recovery):
    if not recovery:
        return ''
    return ('\nThe controller rejected the preceding response. Correct this handoff before '
            'advancing; this session consumes the existing task/case session allowance.\n'
            + json.dumps(recovery, ensure_ascii=False) + '\n'
            'Inspect the retained response and current files. Preserve the original task, '
            'queue baseline, acceptance targets, unrelated work and valid evidence. '
            'Repair the response or authorized partial edits to satisfy the reported guard; '
            'do not weaken acceptance, skip obligations, change permissions or claim completion '
            'without evidence. Reconcile owned cleanup before new work. Return a corrected '
            'structured result, or a concrete developer blocker when a decision is required.\n')


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

    def initialize(self, tasks, *, remaining=None):
        value = dict(tasks=task_limit(tasks), started=0, completed=0)
        if remaining is not None:
            value['remaining'] = remaining
        launcher.atomic(self.run / 'limits.json', value)

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


def task_progress(run, steps, *, remaining=None):
    path = run / 'limits.json'
    if not path.exists():
        return steps
    value = TaskBudget(run).read()
    limit = value['tasks']
    completed = value.get('completed', 0)
    if limit is None:
        limit = value.get('remaining', '—')
        if remaining is not None:
            try:
                limit = completed + remaining()
            except (OSError, ValueError):
                pass  # Editable plan metadata must never prevent attachment.
    return [{'key': 'runtime-tasks', 'pinned': True,
             'lines': [f'Tasks: {completed}/{limit}']}, *steps]
