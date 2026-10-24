"""Independent VM execution with one launcher-wide case repair transaction."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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


class RepairCoordinator:
    """The shared gate serializes every admission and repair-state transition.

    Processes may call this coordinator independently; none keeps a private
    scheduling decision. Kernel source leases still outlive their controllers.
    The existing files remain the restart journal, with no additional protocol.
    """
    def __init__(self, run):
        self.run = run

    @staticmethod
    def recovery_state(saved):
        if saved.get('pending') is not None:
            return 'closeout'
        if saved.get('repairs') or saved.get('queued_failure'):
            return 'repair'
        return 'complete'

    @contextmanager
    def state(self):
        with launcher.lock(self.run / 'repair-queue-gate') as gate:
            fcntl.flock(gate, fcntl.LOCK_EX)
            path = self.run / 'repair-queue.json'
            waiting = json.loads(path.read_text()) if path.exists() else []
            pending = self.run / 'repair-pending.json'
            owner = json.loads(pending.read_text())['run'] if pending.exists() else None
            yield waiting, owner

    def generation(self):
        path = self.run / 'repair-generation.json'
        return json.loads(path.read_text()) if path.exists() else 0

    def enqueue(self, ticket):
        with self.state() as (waiting, _):
            if ticket not in waiting:
                launcher.atomic(self.run / 'repair-queue.json', [*waiting, ticket])

    def admit(self, ticket, descriptor, *, writer):
        """Check FIFO, source fencing and the kernel lease in one transition."""
        with self.state() as (waiting, owner):
            eligible = waiting[:1] == [ticket] if writer else not waiting
            if owner is not None and owner != ticket:
                if (self.run / owner / 'result.json').exists() or writer and eligible:
                    raise ValueError('an unfinished case repair retains unverified edits; resume that repair first')
            if not eligible:
                return False
            if owner is not None and not writer:
                raise ValueError('an unfinished case repair retains unverified edits; resume that repair first')
            try:
                fcntl.flock(descriptor, (fcntl.LOCK_EX if writer else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError:
                return False  # Active cases or their supervisors still own cleanup.
            if writer:
                launcher.atomic(self.run / 'repair-pending.json', {'run': ticket})
            return True

    def finish(self, ticket, *, changed=False, unfinished=False):
        with self.state() as (waiting, owner):
            if owner is not None and owner != ticket:
                raise ValueError('case repair ownership changed before release')
            if changed:
                launcher.atomic(self.run / 'repair-generation.json', self.generation() + 1)
            if not unfinished:
                # Clear the fence before removing its ticket. An interruption
                # between writes still blocks admission until restart drains it.
                (self.run / 'repair-pending.json').unlink(missing_ok=True)
                if ticket in waiting:
                    launcher.atomic(self.run / 'repair-queue.json', [name for name in waiting if name != ticket])

    def discard(self, ticket):
        with self.state() as (waiting, owner):
            if owner == ticket:
                raise ValueError('a retained repair must release its source fence before completion')
            if ticket in waiting:
                launcher.atomic(self.run / 'repair-queue.json', [name for name in waiting if name != ticket])

    def recover(self, pipelines, execute):
        """Restore journal -> drain FIFO transactions -> admit normal work.

        A recovery worker drains its entire ticket with one session budget.
        The coordinator never respawns it to retry an incomplete transaction.
        """
        def saved(child):
            path = child / 'checkpoint.json'
            return json.loads(path.read_text()) if path.exists() else {}

        # Retain legacy ownership records as provenance while splitting them
        # into the selected pipelines. An accepted Git close-out comes first.
        legacy = saved(self.run)
        by_ticket = {child.name: name for name, (child, _) in pipelines.items()}
        for entry in legacy.get('repairs', {}).values():
            name = entry['failure'][2] or 'host'
            child = self.run / ('pipeline-' + hashlib.sha256(name.encode()).hexdigest()[:24])
            if name not in pipelines and not (child / 'checkpoint.json').exists():
                raise ValueError('resume the original selection to finish its retained legacy repair')
        with self.state() as (waiting, owner):
            accepted = []
            for name, (child, selection) in pipelines.items():
                if not (child / 'checkpoint.json').exists():
                    repairs = {key: value for key, value in legacy.get('repairs', {}).items()
                               if value['failure'][2] == ('' if name == 'host' else name)}
                    if repairs:
                        state = dict(repairs=repairs)
                        if legacy.get('pending') in repairs:
                            state.update({key: value for key, value in legacy.items()
                                if key in ('pending', 'commit_intent', 'pull_intent', 'worktree_propagation')})
                        launcher.atomic(child / 'checkpoint.json', state)
                        owner = owner or child.name
                state = saved(child)
                for entry in state.get('repairs', {}).values():
                    category = entry['failure'][0]
                    if category not in selection or entry['args'] != selection[category]['args']:
                        raise ValueError('pending repair selectors changed; resume the original selection')
                queued = state.get('queued_failure')
                if queued is not None and queued['category'] not in selection:
                    raise ValueError('queued failure category removed; resume the original selection')
                phase = self.recovery_state(state)
                if phase == 'closeout':
                    accepted.append(child.name)
                if phase != 'complete' and child.name not in waiting:
                    waiting.append(child.name)
            if set(waiting) - by_ticket.keys():
                raise ValueError('resume the original VM selection to finish its queued failures')
            if owner is not None and owner not in by_ticket:
                raise ValueError('resume the original VM selection to finish its retained case repair')
            if accepted:
                if len(accepted) != 1:
                    raise ValueError('multiple retained Git transactions need their original owner')
                owner, = accepted
            if owner is not None:
                waiting = [owner, *[ticket for ticket in waiting if ticket != owner]]
                launcher.atomic(self.run / 'repair-pending.json', {'run': owner})
            launcher.atomic(self.run / 'repair-queue.json', waiting)

        for ticket in waiting:
            name = by_ticket[ticket]
            status = execute(name)
            if status:
                return status
            child, _ = pipelines[name]
            if self.recovery_state(saved(child)) != 'complete':
                raise ValueError('retained repair recovery did not finish its FIFO transaction')
        with self.state() as (waiting, owner):
            if waiting or owner is not None:
                raise ValueError('retained repair recovery left the source fenced')
        return 0


class RepairGate:
    """Worker-owned descriptors; scheduling belongs to RepairCoordinator."""
    def __init__(self, run, *, stopped=lambda: False):
        self.run = run
        self.parent = parent_run(run)
        self.coordinator = RepairCoordinator(self.parent) if self.parent is not None else None
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
        return self.coordinator.generation() if self.coordinator is not None else 0

    def acquire(self):
        if self.parent is None or self.fd is not None:
            return False
        self.enqueue()
        fd = os.open(self.parent / 'repair-owner', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            self._admit(fd, writer=True)
            self.fd = fd
            _repair_descriptors.add(fd)
            return True
        except BaseException:
            os.close(fd)
            # A stopped waiter still owns its FIFO ticket for the next run.
            raise

    def enqueue(self):
        self.coordinator.enqueue(self.run.name)

    def case_result(self, status):
        """Report failure before giving up this case's source lease."""
        if status and self.coordinator is not None:
            self.coordinator.enqueue(self.run.name)

    def _check_stop(self):
        if self.stopped() or (self.run / 'cancel').exists() or (self.parent / 'cancel').exists():
            raise launcher.Stopped()

    def _admit(self, fd, *, writer):
        from launcher_progress import read_progress, publish_progress
        previous = None
        try:
            while True:
                self._check_stop()
                if self.coordinator.admit(self.run.name, fd, writer=writer):
                    return
                if previous is None:
                    previous = read_progress(self.run)
                    step = previous[-1] if previous else dict(key='admission', lines=['Waiting for repair'])
                    publish_progress(self.run, step['key'],
                                     [step['lines'][0], 'Status: Queued on repair'])
                time.sleep(.1)
        finally:
            if previous is not None:
                launcher.atomic(self.run / 'controller.json', previous)

    @contextmanager
    def source(self):
        """A waiting writer stops new cases; active readers finish normally."""
        if self.parent is None or self.fd is not None:
            yield None
            return
        with launcher.lock(self.parent / 'repair-owner') as source:
            self._admit(source, writer=False)
            _source_descriptors.add(source)
            try:
                yield source
            finally:
                _source_descriptors.discard(source)

    def release(self, *, changed=False, unfinished=False):
        if self.fd is not None:
            self.coordinator.finish(self.run.name, changed=changed, unfinished=unfinished)
            _repair_descriptors.discard(self.fd)
            (self.run / 'repair-lease.json').unlink(missing_ok=True)
            os.close(self.fd)
            self.fd = None


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
    elif category == 'e2e':
        import runpy
        runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
        plan = runner['preflight'](list(options), root=root, allow_missing_artifacts=True)
        if 'cases' not in plan:
            return None  # Qualification selectors remain one non-case operation.
        cases = [case['case_id'] for case in plan['cases']]
    else:
        from regression_events import PREFIX
        command = [str(root / 'tools/run-tests'), category, *options, '--collect-only', '-q']
        environment = launcher.environment()
        environment['ONPC_REGRESSION_EVENTS'] = '1'
        result = subprocess.run(command, cwd=root, env=environment,
                                capture_output=True, text=True, check=True, timeout=120,
                                pass_fds=(*launcher.scratch_descriptors(), *repair_descriptors()))
        cases = [case for line in result.stdout.splitlines() if line.startswith(PREFIX)
                 for event in [json.loads(line[len(PREFIX):])]
                 if event.get('kind') == 'collection' for case in event['nodeids']]
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
                gate.case_result(status)
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
            gate.case_result(status)
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


def pipeline_heading(name, state, steps, question, saved, *, blocker=None, stopping=False):
    """Summarize scheduling and repair phases without granting execution credit."""
    terminal = {'complete': 'Complete', 'limited': 'Task limit reached',
                'stopped': 'Stopped', 'blocked': 'Blocked'}
    phase = steps[-1]['lines'][-1] if steps else ''
    status = terminal.get(state)
    if status is None:
        if stopping:
            status = 'Stopping' if state == 'running' else 'Stopped'
        elif state == 'queued' or phase == 'Status: Queued on repair':
            status = (f'Queued on {blocker} repair' if blocker and blocker != name else
                      'Repairing' if blocker == name and state == 'running' else 'Queued on VM slot')
        elif question:
            status = 'Waiting for input'
        elif saved.get('pending') is not None:
            status = 'Save fix'
        elif phase == 'Status: Verifying':
            status = 'Verifying'
        elif phase.startswith(('Status: fixing errors', 'Status: validating retained response')):
            status = 'Repairing'
        elif blocker == name or saved.get('repairs') or saved.get('queued_failure'):
            status = 'Verifying'
        else:
            status = 'Running'
    color = ('90' if status.startswith('Queued on ') else
             '38;2;0;152;255' if status == 'Running' else
             '38;2;255;165;0' if status in ('Repairing', 'Verifying', 'Save fix') else
             '32' if status == 'Complete' else '31')
    return f'VM: {name} (\033[1;{color}m{status}\033[0m)'


def run(root, run, owner, model, effort, app_model, requested, rounds, resume):
    """Own one recording controller across all VM pipelines and their cleanup."""
    from regression_process import Control
    from vm_recording import recording
    media = None
    status = 1
    try:
        with Control().installed() as control, recording(root, enabled=True) as media:
            status = _run_pipelines(root, run, owner, model, effort, app_model, requested, rounds, resume, control)
        return status
    except KeyboardInterrupt:
        status = 130
        raise
    except Exception:
        status = 1
        raise
    finally:
        if media is not None:
            media.write_index(run, status)


def _run_pipelines(root, run, owner, model, effort, app_model, requested, rounds, resume, control):
    """Run host work once alongside the independently capped VM pipelines."""
    from fix_tests import category_inventory, requested_inventory
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

    coordinator = RepairCoordinator(run)
    pipelines = {name: (child_run(name), host if name == 'host' else guests) for name in states}

    def publish():
        from launcher_chat import read_state, send_input, take_input
        from launcher_progress import read_progress, repair_progress
        from launcher_question import pending
        lines = [f'VM pipelines | concurrency {snapshot["concurrency"]}']
        queue_path = run / 'repair-queue.json'
        waiting = json.loads(queue_path.read_text()) if queue_path.exists() else []
        pending_path = run / 'repair-pending.json'
        try:
            repair_owner = json.loads(pending_path.read_text())['run']
        except FileNotFoundError:
            repair_owner = None
        blocker = next((name for name, (child, _) in pipelines.items()
                        if child.name == (repair_owner or next(iter(waiting), None))), None)
        if repair_owner is not None:
            child = next(child for child, _ in pipelines.values() if child.name == repair_owner)
            launcher.atomic(run / 'chat-state.json', read_state(child))
            for entry in take_input(run):
                state = read_state(child)
                if entry['kind'] == 'message' or entry['session'] in (None, state['session']):
                    send_input(child, entry['kind'], entry['text'])
        stopping = control.stopped.is_set() or (run / 'cancel').exists()
        if waiting:
            lines.append(f'Repair queue: {len(waiting)} | new cases waiting')
        for name in states:
            child = child_run(name)
            steps = repair_progress(child, read_progress(child))
            question = pending(child)
            checkpoint_path = child / 'checkpoint.json'
            saved = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
            lines.extend(['', pipeline_heading(name, states[name]['status'], steps, question, saved,
                                               blocker=blocker, stopping=stopping)])
            lines.extend(step['lines'][0] for step in steps[-1:] if step['key'] != 'admission')
            progress = child / 'case-progress.json'
            if progress.exists():
                current = json.loads(progress.read_text())
                lines.append(f'Cases: {current["completed"]}/{current["total"]}')
            frame = child / 'frame.json'
            if frame.exists():
                lines.extend(json.loads(frame.read_text()))
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
            unfinished = coordinator.recovery_state(saved) != 'complete'
            if status == 0 and unfinished and not recovery:
                raise ValueError('pipeline finished with unresolved retained repairs')
            if status == 0 and not unfinished:
                coordinator.discard(child.name)
            states[name]['status'] = ('limited' if (child / 'limited').exists() else
                'queued' if status == 0 and recovery else
                'complete' if status == 0 else 'stopped' if status == 130 else 'blocked')
            publish()
        return status

    def execute(name, selection, *, recovery=False):
        try:
            status = execute_owned(name, selection, recovery=recovery)
        except launcher.Stopped:
            with output_lock:
                states[name]['status'] = 'stopped'
                publish()
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
            with output_lock:
                publish()
        return status

    status = coordinator.recover(pipelines, lambda name: execute(name, pipelines[name][1], recovery=True))
    if status:
        return status
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
    with ThreadPoolExecutor(max_workers=1) as pool:
        host_task = pool.submit(execute, 'host', host) if host else None
        try:
            results = dispatch(vms, snapshot['concurrency'], lambda vm: execute(vm.name, guests), control.stopped)
            if host_task is not None:
                host_task.result()
        except BaseException:
            control.stop()
            raise
    statuses = {name: value['status'] if isinstance(value, dict) else value for name, value in results.items()}
    launcher.atomic(run / 'vm-results.json', results)
    if any(value['status'] == 'limited' for value in states.values()):
        (run / 'limited').touch(mode=0o600)
    return 1 if failed.is_set() else 130 if control.stopped.is_set() else 1 if any(statuses.values()) else 0
