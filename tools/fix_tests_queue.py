"""Independent VM execution with one launcher-wide case repair transaction."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from contextlib import contextmanager

import detached_launcher as launcher
from launcher_runtime import TaskBudget


_repair_descriptors = set()
_source_descriptors = set()
_workflow_descriptors = set()
WORKER = Path(__file__).with_name('fix_tests.py')
STARTUP_SOURCE = 'ONPC_REPAIR_STARTUP_FD'
STARTUP_REPAIR = 'ONPC_REPAIR_WRITER_FD'
RECOVERY_ONLY = 'ONPC_REPAIR_RECOVERY_ONLY'


def repair_descriptors():
    return tuple(_repair_descriptors | _source_descriptors | _workflow_descriptors)


def retain_owner(owner):
    _workflow_descriptors.add(owner)


def parent_run(run):
    path = run / 'pipeline.json'
    return Path(json.loads(path.read_text())['parent']) if path.exists() else None


def finish_startup(run):
    """The spawning reader protects imports until the worker can enter the gate."""
    inherited = os.environ.pop(STARTUP_SOURCE, None)
    if inherited is not None:
        fd = int(inherited)
        actual, expected = os.fstat(fd), (parent_run(run) / 'repair-owner').stat()
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise ValueError('inherited source lease identity changed')
        os.close(fd)


class RepairGate:
    """Parallel case readers, FIFO exclusive repairs, no unverified handoff."""
    def __init__(self, run, *, stopped=lambda: False):
        self.run = run
        self.parent = parent_run(run)
        self.fd = None
        self.stopped = stopped
        self.last_generation = None
        inherited = os.environ.pop(STARTUP_REPAIR, None)
        lease = run / 'repair-lease.json'
        if self.parent is not None and (inherited is not None or lease.exists()):
            saved = (dict(pid=os.getpid(), fds=[int(inherited)]) if inherited is not None else
                     json.loads(lease.read_text()))
            if saved['pid'] == os.getpid():
                self.fd, = saved['fds']
                actual, expected = os.fstat(self.fd), (self.parent / 'repair-owner').stat()
                if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                    raise ValueError('inherited repair lease identity changed')
                os.set_inheritable(self.fd, False)
                _repair_descriptors.add(self.fd)

    def detach(self):
        """Close the spawning parent's copy; the child now owns this lease."""
        if self.fd is not None:
            _repair_descriptors.discard(self.fd)
            os.close(self.fd)
            self.fd = None

    def generation(self):
        path = (self.parent or self.run) / 'repair-generation.json'
        return json.loads(path.read_text()) if path.exists() else 0

    def acquire(self):
        if self.parent is None or self.fd is not None:
            return False
        self.enqueue()
        fd = os.open(self.parent / 'repair-owner', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            while True:
                with self.queue() as waiting:
                    self._check_pending()
                    first = bool(waiting) and waiting[0] == self.run.name
                if first:
                    break
                self._check_stop()
                time.sleep(.1)
            self._wait(fd, fcntl.LOCK_EX)
            self._check_pending(claiming=True)
            launcher.atomic(self.parent / 'repair-pending.json', {'run': self.run.name})
            self.fd = fd
            _repair_descriptors.add(fd)
            return True
        except BaseException:
            os.close(fd)
            # A stopped waiter still owns its FIFO ticket for the next run.
            raise

    def enqueue(self):
        with self.queue() as waiting:
            if self.run.name not in waiting:
                waiting.append(self.run.name)

    @contextmanager
    def queue(self):
        with launcher.lock(self.parent / 'repair-queue-gate') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            path = self.parent / 'repair-queue.json'
            waiting = json.loads(path.read_text()) if path.exists() else []
            before = list(waiting)
            yield waiting
            if waiting != before:
                launcher.atomic(path, waiting)

    def dequeue(self):
        with self.queue() as waiting:
            if self.run.name in waiting:
                waiting.remove(self.run.name)

    def _check_stop(self):
        if self.stopped() or (self.run / 'cancel').exists() or (self.parent / 'cancel').exists():
            raise launcher.Stopped()

    def _wait(self, fd, mode):
        while True:
            self._check_stop()
            try:
                fcntl.flock(fd, mode | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                time.sleep(.1)

    def _check_pending(self, *, reading=False, claiming=False):
        path = self.parent / 'repair-pending.json'
        if path.exists():
            previous = json.loads(path.read_text())['run']
            result = self.parent / previous / 'result.json'
            # A live writer is ordinary queued work. A stopped writer's edits
            # remain fenced until that exact retained repair resumes.
            if previous != self.run.name and (claiming or result.exists()):
                raise ValueError('an unfinished case repair retains unverified edits; resume that repair first')
        if reading and path.exists():
            raise ValueError('an unfinished case repair retains unverified edits; resume that repair first')

    @contextmanager
    def source(self):
        """A waiting writer stops new cases; active readers finish normally."""
        if self.parent is None or self.fd is not None:
            yield None
            return
        with launcher.lock(self.parent / 'repair-owner') as source:
            while True:
                self._check_stop()
                with self.queue() as waiting:
                    if not waiting:
                        self._check_pending(reading=True)
                        # Admission and the read lease are atomic with respect
                        # to registration of every queued repair, not just its head.
                        try:
                            fcntl.flock(source, fcntl.LOCK_SH | fcntl.LOCK_NB)
                        except BlockingIOError:
                            pass  # A supervisor may still be finishing owned cleanup.
                        else:
                            break
                    self._check_pending()
                time.sleep(.1)
            _source_descriptors.add(source)
            try:
                yield source
            finally:
                _source_descriptors.discard(source)

    def release(self, *, changed=False, unfinished=False):
        if self.fd is not None:
            if changed:
                launcher.atomic(self.parent / 'repair-generation.json', self.generation() + 1)
            if not unfinished:
                (self.parent / 'repair-pending.json').unlink(missing_ok=True)
            _repair_descriptors.discard(self.fd)
            (self.run / 'repair-lease.json').unlink(missing_ok=True)
            os.close(self.fd)
            self.fd = None
            if not unfinished:
                self.dequeue()


def case_inventory(root, category, options):
    """Use the runner's original order and selectors, including lifecycle phases."""
    if category == 'system':
        from vm_selection import selected
        command = [str(root / 'tools/run-tests'), 'system', *options, '--vm', selected().name, '--list']
        result = subprocess.run(command, cwd=root, env=launcher.environment(),
                                capture_output=True, text=True, check=True,
                                pass_fds=(*launcher.scratch_descriptors(), *repair_descriptors()))
        import re
        cases = [match[1] for line in result.stdout.splitlines()
                 if (match := re.fullmatch(r'    (\S+::\S+) \[selected\](?: \[system-\d+\])?', line))]
    else:
        import runpy
        runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
        plan = runner['preflight'](list(options), root=root, allow_missing_artifacts=True)
        if 'cases' not in plan:
            return None  # Qualification selectors remain one non-case operation.
        cases = [case['case_id'] for case in plan['cases']]
    if not cases or len(cases) != len(set(cases)):
        raise ValueError('VM case inventory is empty or contains duplicate identities')
    return cases


def run_cases(root, category, options, execute, gate):
    """Start a fresh maintained runner for every case, never a frozen whole batch.

    The case-only runner retains the original checkpoint selectors and reconstructs
    required lifecycle prerequisites. Its teardown-complete checkpoint owns credit.
    """
    from test_checkpoint import Checkpoint
    from vm_selection import selected
    original = [arg for arg in options if arg != '--resume']
    checkpoint = Checkpoint(root, [(category, original)], resume='--resume' in options,
                            binding=selected().name)
    inventory_generation = None
    while True:
        with gate.source():
            generation = gate.generation()
            if inventory_generation != generation:
                cases = case_inventory(root, category, original)
                inventory_generation = generation
            if cases is None:
                gate.last_generation = generation
                status = execute(original)
                if status:
                    gate.enqueue()
                return status
            passed = checkpoint.passed(category)
            case = next((case for case in cases if case not in passed), None)
            if case is None:
                break
            print(f'fix-tests: executing case {case}', flush=True)
            launcher.atomic(gate.run / 'case-progress.json', dict(category=category, case=case,
                completed=len(set(cases) & passed), total=len(cases)))
            gate.last_generation = generation
            status = execute([*original, '--resume', '--resume-case=' + case, '--resume-case-only'])
            if status:
                gate.enqueue()  # Close admission before releasing this case's read lease.
        checkpoint = Checkpoint(root, [(category, original)], resume=True, binding=selected().name)
        if status:
            return status
        if case not in checkpoint.passed(category):
            raise ValueError('case runner returned success without teardown-complete case evidence')
    if not set(cases) <= checkpoint.passed(category):
        raise ValueError('VM selection is incomplete after case execution')
    checkpoint.entry(category)['complete'] = True
    checkpoint.save()
    launcher.atomic(gate.run / 'case-progress.json', dict(category=category, case=None,
        completed=len(cases), total=len(cases)))
    return 0


def run(root, run, owner, model, effort, app_model, requested, rounds, resume):
    """Run host work once, then refill VM slots after complete per-VM pipelines."""
    from fix_tests import category_inventory, requested_inventory
    from regression_process import Control
    from vm_queue import dispatch
    from vm_selection import BATCH, VARIABLE, vm_config
    snapshot = json.loads(os.environ[BATCH])
    listing = subprocess.run([str(root / 'tools/run-tests'), '--list'], cwd=root,
                             env=launcher.environment(), capture_output=True, text=True, check=True)
    inventory = requested_inventory(root, json.loads(requested), inventory=category_inventory(listing.stdout))
    from test_commands import inventory_scope
    host = {kind: spec for kind, spec in inventory.items() if inventory_scope(kind, spec) == 'host'}
    guests = {kind: spec for kind, spec in inventory.items() if inventory_scope(kind, spec) == 'vm'}
    configured = vm_config.registry()
    vms = tuple(configured[name] for name in snapshot['vms'])
    output_lock = threading.Lock()
    parent_budget = TaskBudget(run)
    state_path = run / 'pipelines.json'
    states = json.loads(state_path.read_text()) if state_path.exists() else {}
    states = {name: states.get(name, dict(status='queued'))
              for name in (*(['host'] if host else []), *snapshot['vms'])}
    launcher.atomic(run / 'controller.json', [dict(key='pipelines',
        lines=['VM test pipelines', 'Status: Running cases'])])

    def child_run(name):
        return launcher.private_directory(run / ('pipeline-' + hashlib.sha256(name.encode()).hexdigest()[:24]))

    # Upgrade the old batch-wide repair checkpoint without losing edit ownership
    # or a push already awaiting recovery. Keep its original record as provenance.
    legacy_path = run / 'checkpoint.json'
    legacy = json.loads(legacy_path.read_text()) if legacy_path.exists() else {}
    for entry in legacy.get('repairs', {}).values():
        name = entry['failure'][2] or 'host'
        if name not in states and not (child_run(name) / 'checkpoint.json').exists():
            raise ValueError('resume the original selection to finish its retained legacy repair')
    for name in states:
        child = child_run(name)
        if (child / 'checkpoint.json').exists():
            continue
        repairs = {key: value for key, value in legacy.get('repairs', {}).items()
                   if value['failure'][2] == ('' if name == 'host' else name)}
        if repairs:
            state = dict(repairs=repairs)
            if legacy.get('pending') in repairs:
                state.update({key: value for key, value in legacy.items()
                              if key in ('pending', 'commit_intent', 'pull_intent', 'worktree_propagation')})
            launcher.atomic(child / 'checkpoint.json', state)
            if not (run / 'repair-pending.json').exists():
                launcher.atomic(run / 'repair-pending.json', {'run': child.name})
    pending_path = run / 'repair-pending.json'
    queue_path = run / 'repair-queue.json'
    waiting = json.loads(queue_path.read_text()) if queue_path.exists() else []
    accepted = []
    for name in states:
        child = child_run(name)
        path = child / 'checkpoint.json'
        saved = json.loads(path.read_text()) if path.exists() else {}
        selection = host if name == 'host' else guests
        for entry in saved.get('repairs', {}).values():
            category = entry['failure'][0]
            if category not in selection or entry['args'] != selection[category]['args']:
                raise ValueError('pending repair selectors changed; resume the original selection')
        queued = saved.get('queued_failure')
        if queued is not None and queued['category'] not in selection:
            raise ValueError('queued failure category removed; resume the original selection')
        if saved.get('pending') is not None:
            accepted.append(child.name)
        if (saved.get('repairs') or saved.get('queued_failure')) and child.name not in waiting:
            waiting.append(child.name)
    children = {child_run(name).name for name in states}
    if set(waiting) - children:
        raise ValueError('resume the original VM selection to finish its queued failures')
    if pending_path.exists():
        pending_owner = json.loads(pending_path.read_text())['run']
        if pending_owner not in children:
            raise ValueError('resume the original VM selection to finish its retained case repair')
        waiting = [pending_owner, *[name for name in waiting if name != pending_owner]]
    if accepted:
        if len(accepted) != 1:
            raise ValueError('multiple retained Git transactions need their original owner')
        # Legacy migration may split diagnostics before its accepted close-out.
        # Finish that immutable Git transaction before any repair verification.
        pending_owner, = accepted
        launcher.atomic(pending_path, {'run': pending_owner})
        waiting = [pending_owner, *[name for name in waiting if name != pending_owner]]
    launcher.atomic(queue_path, waiting)

    def publish():
        from launcher_progress import read_progress, repair_progress
        from launcher_question import pending
        lines = [f'VM pipelines | concurrency {snapshot["concurrency"]}']
        queue_path = run / 'repair-queue.json'
        waiting = json.loads(queue_path.read_text()) if queue_path.exists() else []
        if waiting:
            lines.append(f'Repair queue: {len(waiting)} | new cases waiting')
        for name in states:
            child = child_run(name)
            steps = repair_progress(child, read_progress(child))
            lines.extend([f'VM: {name}', *[line for step in steps[-1:] for line in step['lines']]])
            progress = child / 'case-progress.json'
            if progress.exists():
                current = json.loads(progress.read_text())
                lines.append(f'Cases: {current["completed"]}/{current["total"]}')
            frame = child / 'frame.json'
            if frame.exists():
                lines.extend(json.loads(frame.read_text()))
            question = pending(child)
            parent_question = run / 'question.json'
            displayed = json.loads(parent_question.read_text()) if parent_question.exists() else None
            if question and (displayed is None or displayed.get('id') == question['id']
                             or displayed.get('answer') is not None):
                if displayed and displayed['id'] == question['id'] and displayed.get('answer') is not None:
                    launcher.atomic(child / 'question.json', displayed)
                elif displayed is None or displayed['id'] != question['id']:
                    launcher.atomic(parent_question, dict(question, explanation=name + ': ' + question['explanation']))
        launcher.atomic(run / 'frame.json', lines)
        launcher.atomic(state_path, states)

    with Control().installed() as control:
        failed = threading.Event()
        def execute_owned(name, selection, *, recovery=False):
            if control.stopped.is_set() or (run / 'cancel').exists():
                return 130
            child = child_run(name)
            (child / 'result.json').unlink(missing_ok=True)
            launcher.atomic(child / 'pipeline.json', dict(parent=str(run)))
            launcher.atomic(child / 'vm.json', {'vm': None if name == 'host' else name})
            if not (child / 'limits.json').exists():
                TaskBudget(child).initialize(None)
            # The runner checkpoint validates selectors and rounds even for a
            # completed pipeline. Presentation state cannot grant a pass.
            states[name]['status'] = 'running'
            args = [value for kind, spec in selection.items() for value in (kind, *spec['args'])]
            environment = launcher.environment()
            environment.pop(BATCH, None)
            if recovery:
                environment[RECOVERY_ONLY] = '1'
            if name == 'host':
                environment.pop(VARIABLE, None)
            else:
                environment[VARIABLE] = name
            command = ['/usr/bin/python3', '-IBu', str(WORKER),
                       '--worker', str(root), str(child), str(owner), model, effort, app_model,
                       json.dumps(args), rounds, 'true' if recovery else resume]
            pending = b''
            with (child / 'output').open('ab') as log:
                def output(data):
                    nonlocal pending
                    log.write(data)
                    log.flush()
                    pending += data
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        with output_lock:
                            print(f'[{name}] ' + line.decode('utf-8', errors='replace'), flush=True)
                def tick():
                    with output_lock:
                        if (run / 'cancel').exists():
                            control.stop()
                        publish()
                from contextlib import ExitStack
                with ExitStack() as startup:
                    gate = RepairGate(child, stopped=control.stopped.is_set)
                    # A retained writer enters its exclusive gate in the worker.
                    # Everyone else inherits a reader across initial imports.
                    if not recovery:
                        source = startup.enter_context(gate.source())
                        environment[STARTUP_SOURCE] = str(source)
                    else:
                        gate.acquire()
                        source = gate.fd
                        environment[STARTUP_REPAIR] = str(source)
                        startup.callback(gate.detach)
                    status = control.run(command, cwd=root, env=environment, output=output, tick=tick,
                        cooperative=True, started=startup.close,
                        pass_fds=(owner, *launcher.scratch_descriptors(),
                                  *((source,) if source is not None else ())))
                if pending:
                    output(b'\n')
            with output_lock:
                # Failed/cancelled tickets stay in FIFO order for recovery.
                path = child / 'checkpoint.json'
                saved = json.loads(path.read_text()) if path.exists() else {}
                unfinished = bool(saved.get('repairs') or saved.get('queued_failure'))
                if status == 0 and unfinished and not recovery:
                    raise ValueError('pipeline finished with unresolved retained repairs')
                if status == 0 and not unfinished:
                    RepairGate(child).dequeue()
                states[name]['status'] = ('limited' if (child / 'limited').exists() else
                    'queued' if status == 0 and recovery else
                    'complete' if status == 0 else 'stopped' if status == 130 else 'blocked')
                publish()
            return status

        def execute(name, selection, *, recovery=False):
            try:
                status = execute_owned(name, selection, recovery=recovery)
            except launcher.Stopped:
                status = 130
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                with output_lock:
                    print(f'[{name}] pipeline infrastructure failed: {error}', flush=True)
                    states[name]['status'] = 'blocked'
                status = 2
            if status:
                if status != 130:
                    failed.set()
                control.stop()  # No worker can wait behind a dead queue owner.
            return status

        # Drain retained VM recovery before starting any host category. Keep
        # FIFO order when a prior host failure is itself among those tickets.
        for ticket in waiting:
            name = next(name for name in states if child_run(name).name == ticket)
            path = child_run(name) / 'checkpoint.json'
            saved = json.loads(path.read_text()) if path.exists() else {}
            while True:
                previous = saved.get('last_commit')
                status = execute(name, host if name == 'host' else guests, recovery=True)
                if status:
                    return status
                saved = json.loads(path.read_text()) if path.exists() else {}
                if not (saved.get('repairs') or saved.get('queued_failure')):
                    break
                if saved.get('last_commit') == previous:
                    raise ValueError('retained repair recovery made no accepted progress')
        # Reset/validate the whole selection before admitting normal work. A VM
        # left queued by a limit or cancellation must not inherit an older run's
        # category passes on the next --resume.
        from test_checkpoint import Checkpoint
        from launcher_runtime import warn_remaining
        remaining = 0
        for name in states:
            selection = host if name == 'host' else guests
            saved = Checkpoint(root, [(kind, spec['args']) for kind, spec in selection.items()],
                resume=resume == 'true', namespace='fix-tests', binding='' if name == 'host' else name)
            number = saved.state.get('round', 1)
            if number > int(rounds):
                raise ValueError('resume round exceeds --rounds; retain the original round count')
            remaining += sum(not saved.complete(kind) for kind in selection)
            remaining += (int(rounds) - number) * len(selection)
        parent_budget.update(lambda value: value.update(remaining=remaining))
        warn_remaining(parent_budget.read()['tasks'], remaining, label='fix-tests')
        if host:
            status = execute('host', host)
            if status:
                return status
        results = dispatch(vms, snapshot['concurrency'], lambda vm: execute(vm.name, guests), control.stopped)
        statuses = {name: value['status'] if isinstance(value, dict) else value for name, value in results.items()}
        launcher.atomic(run / 'vm-results.json', results)
        if any(value['status'] == 'limited' for value in states.values()):
            (run / 'limited').touch(mode=0o600)
        return 1 if failed.is_set() else 130 if control.stopped.is_set() else 1 if any(statuses.values()) else 0
