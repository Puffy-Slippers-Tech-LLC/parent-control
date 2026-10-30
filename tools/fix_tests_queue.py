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
from contextlib import contextmanager, ExitStack

import detached_launcher as launcher
import launcher_reload
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


def source_directory(root):
    from test_storage import directory
    return launcher.private_directory(directory('state', root=root) / 'fix-tests-source')


def resumed_source_owner(root, previous, ticket, saved):
    """Bind an explicit resume to its retained writer before retention rotates.

    This records permission to transfer, not a transfer itself. Admission still
    needs the FIFO ticket and the exclusive kernel source lease.
    """
    child = previous / ticket
    coordinator = RepairCoordinator(previous, source=source_directory(root))
    with coordinator.state() as (_, owner):
        pending = coordinator.source / 'repair-source-pending.json'
        if owner != ticket or not pending.exists():
            return None
        source_owner = json.loads(pending.read_text())['run']
        candidates = [str(child.resolve())]
        inherited = child / 'repair-source-resume.json'
        if inherited.exists():
            candidates.append(json.loads(inherited.read_text())['run'])
        if source_owner in candidates:
            return {'run': source_owner}
        # Older launchers copied checkpoints without carrying the source fence.
        # Recover only the exact retained repair named by their restart record;
        # a matching filename or dirty checkout alone supplies no ownership.
        origin = saved.get('controller_restart', {}).get('run')
        if origin == source_owner:
            original = Path(origin)
            workflow = original.parent if ticket == '.' else original.parent.parent
            if workflow == previous.parent and (ticket == '.' or original.name == ticket):
                state = json.loads((original / 'checkpoint.json').read_text())
                original_run = original if ticket == '.' else original.parent
                original_pending = json.loads((original_run / 'repair-pending.json').read_text())
                if (saved.get('repairs') and saved['repairs'] == state.get('repairs')
                        and original_pending['run'] == ticket):
                    return {'run': source_owner}
        return None


def finish_startup(run, *, root=None):
    """The spawning reader protects imports until the worker can enter the gate."""
    inherited = os.environ.pop(STARTUP_SOURCE, None)
    if inherited is not None:
        fd = int(inherited)
        actual = os.fstat(fd)
        paths = [(parent_run(run) or run) / 'repair-owner']
        if root is not None:
            paths.insert(0, source_directory(root) / 'repair-owner')
        if not any(path.exists() and (actual.st_dev, actual.st_ino) ==
                   (path.stat().st_dev, path.stat().st_ino) for path in paths):
            raise ValueError('inherited source lease identity changed')
        os.close(fd)


class RepairCoordinator:
    """The shared gate serializes every admission and repair-state transition.

    Processes may call this coordinator independently; none keeps a private
    scheduling decision. Kernel source leases still outlive their controllers.
    Per-run queues retain restart state; the checkout lease fences their shared
    source bytes, including edits retained by a stopped writer.
    """
    def __init__(self, run, *, source=None):
        self.run = run
        self.source = source if source is not None else run

    @staticmethod
    def recovery_state(saved):
        if saved.get('pending') is not None:
            return 'closeout'
        if saved.get('repairs') or saved.get('queued_failure'):
            return 'repair'
        return 'complete'

    @contextmanager
    def state(self):
        with ExitStack() as locks:
            gate = locks.enter_context(launcher.lock(self.run / 'repair-queue-gate'))
            fcntl.flock(gate, fcntl.LOCK_EX)
            if self.source != self.run:
                shared = locks.enter_context(launcher.lock(self.source / 'repair-queue-gate'))
                fcntl.flock(shared, fcntl.LOCK_EX)
            path = self.run / 'repair-queue.json'
            waiting = json.loads(path.read_text()) if path.exists() else []
            pending = self.run / 'repair-pending.json'
            owner = json.loads(pending.read_text())['run'] if pending.exists() else None
            yield waiting, owner

    def generation(self):
        path = self.source / 'repair-generation.json'
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
            # Independent host and VM queues still read and edit one checkout.
            # Retain the source fence even if its writer stopped before cleanup.
            pending = self.source / 'repair-source-pending.json'
            source_owner = json.loads(pending.read_text())['run'] if pending.exists() else None
            ticket_path = str((self.run / ticket).resolve())
            if source_owner is not None and (source_owner != ticket_path or not writer):
                inherited = self.run / ticket / 'repair-source-resume.json'
                try:
                    resumed = json.loads(inherited.read_text()) if writer and inherited.exists() else None
                    if resumed != {'run': source_owner}:
                        raise ValueError('another unfinished repair retains unverified checkout edits; resume that repair first')
                except BaseException:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                    raise
            if writer:
                # Publish local recovery ownership first: a crash must never
                # leave a shared fence with no retained ticket to resume.
                launcher.atomic(self.run / 'repair-pending.json', {'run': ticket})
                launcher.atomic(pending, {'run': ticket_path})
            return True

    def finish(self, ticket, *, changed=False, unfinished=False):
        with self.state() as (waiting, owner):
            if owner is not None and owner != ticket:
                raise ValueError('case repair ownership changed before release')
            pending = self.source / 'repair-source-pending.json'
            source_owner = json.loads(pending.read_text())['run'] if pending.exists() else None
            if source_owner is not None and source_owner != str((self.run / ticket).resolve()):
                raise ValueError('checkout repair ownership changed before release')
            if changed:
                launcher.atomic(self.source / 'repair-generation.json', self.generation() + 1)
            if not unfinished:
                # Clear the fence before removing its ticket. An interruption
                # between writes still blocks admission until restart drains it.
                pending.unlink(missing_ok=True)
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
    def __init__(self, run, *, root=None, stopped=lambda: False):
        self.run = run
        self.parent = parent_run(run)
        self.coordinator = RepairCoordinator(self.parent or run,
            source=source_directory(root) if root is not None else None)
        self.ticket = run.name if self.parent is not None else '.'
        self.fd = None
        self.stopped = stopped
        self.last_generation = None
        inherited = os.environ.pop(STARTUP_REPAIR, None)
        lease = run / 'repair-lease.json'
        if inherited is not None or lease.exists():
            saved = (dict(pid=os.getpid(), fds=[int(inherited)]) if inherited is not None else
                     json.loads(lease.read_text()))
            if saved['pid'] == os.getpid():
                self.fd, = saved['fds']
                actual = os.fstat(self.fd)
                path = self.coordinator.source / 'repair-owner'
                if not path.exists() or (actual.st_dev, actual.st_ino) != (path.stat().st_dev, path.stat().st_ino):
                    # Upgrade a live reload from the former per-run source lock.
                    legacy = (self.parent or run) / 'repair-owner'
                    if not legacy.exists() or (actual.st_dev, actual.st_ino) != (legacy.stat().st_dev, legacy.stat().st_ino):
                        raise ValueError('inherited repair lease identity changed')
                    with launcher.lock(path) as replacement:
                        self._admit(replacement, writer=True)
                        os.close(self.fd)
                        self.fd = os.dup(replacement)
                    launcher.atomic(lease, dict(pid=os.getpid(), fds=[self.fd]))
                os.set_inheritable(self.fd, False)
                _repair_descriptors.add(self.fd)

    def detach(self):
        """Close the spawning parent's copy; the child now owns this lease."""
        if self.fd is not None:
            _repair_descriptors.discard(self.fd)
            os.close(self.fd)
            self.fd = None

    def generation(self):
        return self.coordinator.generation()

    def acquire(self):
        if self.fd is not None:
            return False
        self.enqueue()
        with launcher.lock(self.coordinator.source / 'repair-owner') as opened:
            fd = os.dup(opened)
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
        self.coordinator.enqueue(self.ticket)

    def case_result(self, status):
        """Report failure before giving up this case's source lease."""
        if status:
            self.coordinator.enqueue(self.ticket)

    def _check_stop(self):
        if self.stopped() or (self.run / 'cancel').exists() or ((self.parent or self.run) / 'cancel').exists():
            raise launcher.Stopped()
        if launcher_reload.pending():
            getattr(self, 'on_reload', launcher_reload.check)()

    def _admit(self, fd, *, writer):
        from launcher_progress import read_progress, publish_progress
        previous = None
        try:
            while True:
                self._check_stop()
                if self.coordinator.admit(self.ticket, fd, writer=writer):
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
    def reload_source(self, *, root=None):
        """Protect coordinator imports under its retained pipeline's writer.

        Pipelines have drained before controller replacement. Normal reader
        admission must still refuse their unverified edits; only the recorded
        FIFO owner may carry those bytes through reload into recovery.
        """
        with self.coordinator.state() as (waiting, owner):
            ticket = owner or next(iter(waiting), None)
        if self.fd is None and self.parent is None and ticket not in (None, '.'):
            if not ticket.startswith('pipeline-') or Path(ticket).name != ticket:
                raise ValueError('invalid retained reload pipeline ticket')
            child = self.run / ticket
            if child.parent != self.run or parent_run(child) != self.run:
                raise ValueError('retained reload ticket is not a pipeline of this run')
            writer = RepairGate(child, root=root, stopped=self.stopped)
            try:
                writer.acquire()
                yield writer.fd
            finally:
                # Exec failure closes only our kernel lease, retaining the
                # journals and source fence for the same recovery transaction.
                writer.detach()
        else:
            with self.source() as source:
                yield source

    @contextmanager
    def source(self):
        """A waiting writer stops new cases; active readers finish normally."""
        if self.fd is not None:
            yield None
            return
        with launcher.lock(self.coordinator.source / 'repair-owner') as source:
            self._admit(source, writer=False)
            _source_descriptors.add(source)
            try:
                yield source
            finally:
                _source_descriptors.discard(source)

    def release(self, *, changed=False, unfinished=False):
        if self.fd is not None:
            self.coordinator.finish(self.ticket, changed=changed, unfinished=unfinished)
            _repair_descriptors.discard(self.fd)
            (self.run / 'repair-lease.json').unlink(missing_ok=True)
            os.close(self.fd)
            self.fd = None


def case_inventory(root, category, options):
    """Use the runner's original order and selectors, including lifecycle phases."""
    if category in ('system', 'integration', 'e2e'):
        from vm_case_queue import case_inventory as collect
        return collect(root, category, options,
                       pass_fds=(*launcher.scratch_descriptors(), *repair_descriptors()))
    else:
        from regression_process import Control
        from regression_events import PREFIX
        command = [str(root / 'tools/run-tests'), category, '--unattended',
                   *options, '--collect-only', '-q']
        output, errors = [], []
        # The unattended runner owns the event protocol and expects a live
        # cancellation pipe. Caller environment flags are deliberately stripped.
        with Control().installed() as control:
            status = control.run(command, cwd=root, env=launcher.environment(),
                                 output=output.append, stderr_output=errors.append,
                                 cooperative=True,
                                 pass_fds=(*launcher.scratch_descriptors(), *repair_descriptors()))
        stdout = b''.join(output).decode('utf-8', errors='replace')
        if status:
            raise subprocess.CalledProcessError(status, command, output=stdout,
                                               stderr=b''.join(errors).decode('utf-8', errors='replace'))
        cases = [case for line in stdout.splitlines() if line.startswith(PREFIX)
                 for event in [json.loads(line[len(PREFIX):])]
                 if event.get('kind') == 'collection' for case in event.get('nodeids', [])]
    # Repeated identities still name the same verification target. Keep the
    # runner's first-seen order without counting or scheduling them twice.
    cases = list(dict.fromkeys(cases))
    if not cases:
        raise ValueError(f'{category} collection returned no case identities for bounded verification')
    return cases


def case_totals(root, inventory, category, cases):
    """Discover every selected VM case category before showing the overall total."""
    totals = {category: len(cases)}
    for kind, spec in inventory.items():
        if kind in ('system', 'integration', 'e2e') and kind != category:
            selected = case_inventory(root, kind, spec['args'])
            if selected is not None:
                totals[kind] = len(selected)
    return totals


def run_cases(root, category, options, execute, gate, *, inventory, round_number, completed_categories=()):
    """Start fresh runners per system history/independent area or E2E case.

    Scoped runners retain the original checkpoint selectors and reconstruct
    required lifecycle prerequisites. Its teardown-complete checkpoint owns credit.
    """
    return run_family_cases(root, category, options, execute, gate,
                            inventory=inventory, round_number=round_number,
                            completed_categories=completed_categories)


class FamilyCases:
    """Small shared claim journal inside the existing repair-run allocation.

    The file lock covers selecting and recording a claim together. A failed or
    interrupted claim stays with its VM until that pipeline recovers it; another
    VM cannot adopt it just because the original process stopped.
    """
    def __init__(self, parent, family, category, options, round_number):
        self.family = family
        identity = json.dumps([family, category, options, round_number], sort_keys=True)
        self.path = launcher.private_directory(parent / 'family-cases') / (
            hashlib.sha256(identity.encode()).hexdigest() + '.json')

    @contextmanager
    def state(self, *, write=True):
        from test_retention import private
        lock = os.open(self.path.with_suffix('.lock'),
                       os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            private(os.fstat(lock), regular=True)
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = json.loads(self.path.read_text()) if self.path.exists() else dict(
                version=1, completed=[], claims={}, items={}, family=self.family)
            if hasattr(self, 'family'):
                state.setdefault('family', self.family)
            if (state.get('version') != 1 or not isinstance(state.get('completed'), list)
                    or not isinstance(state.get('claims'), dict)
                    or not isinstance(state.get('items'), dict)):
                raise ValueError('invalid family case queue')
            yield state
            if write:
                launcher.atomic(self.path, state)
        finally:
            os.close(lock)


def error_log(run):
    owner = parent_run(run) or run
    return owner.parent / 'errors.md'


def initialize_error_log(run, *, resume):
    from test_retention import private
    with launcher.lock(run.parent / 'errors-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        fd = os.open(error_log(run), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            private(os.fstat(stream.fileno()), regular=True)
            if not resume:
                stream.truncate(0)
                stream.write('# fix-tests errors\n')


def failed_case_selection(run, records):
    """Pass omitted identities to runners while preserving genuine case passes."""
    result = {}
    for record in records:
        category, case, _vm = record['failure']
        if case:
            result.setdefault(category, set()).add(case)
    owner = parent_run(run) or run
    from vm_selection import selected
    vm = selected(required=False)
    for path in (owner / 'family-cases').glob('*.json'):
        queue = FamilyCases.__new__(FamilyCases)
        queue.path = path
        with queue.state(write=False) as state:
            if vm is None or state.get('family') != vm.family:
                continue
            for key, cases in state.get('failed', {}).items():
                result.setdefault(state['items'][key]['category'], set()).update(cases)
    return {kind: sorted(cases) for kind, cases in result.items()}


def record_case_failure(run, record, *, root):
    """Append across resumes; the category owner resets the log on a new run."""
    owner = parent_run(run) or run
    with launcher.lock(owner.parent / 'errors-gate') as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        from test_retention import private
        fd = os.open(error_log(run), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a', encoding='utf-8') as stream:
            private(os.fstat(stream.fileno()), regular=True)
            stream.write('\n## ' + time.strftime('%Y-%m-%d %H:%M:%S %Z') + '\n\n')
            # Indented JSON is Markdown code, even when prompts contain fences.
            stream.write('\n'.join('    ' + line for line in
                json.dumps(record, ensure_ascii=False, indent=2).splitlines()) + '\n')
    category, case, vm_name = record['failure']
    if vm_name:
        from vm_selection import selected
        vm = selected()
        for path in (owner / 'family-cases').glob('*.json'):
            queue = FamilyCases.__new__(FamilyCases)
            queue.path = path
            with queue.state() as state:
                if state.get('family') != vm.family:
                    continue
                for key, claimant in list(state['claims'].items()):
                    item = state['items'][key]
                    if claimant == vm.name and item['category'] == category and (not case or case in item['cases']):
                        # A stateful history is indivisible; independent areas can
                        # continue with their remaining cases and original prerequisites.
                        from test_checkpoint import Checkpoint
                        passed = Checkpoint(root, [(category, item['options'])], resume=True,
                                            binding=vm.name).passed(category)
                        failed = ({case} if case and item['area'] else set(item['cases'])) - passed
                        state.setdefault('failed', {})[key] = list(set(
                            state.get('failed', {}).get(key, [])) | set(failed))
                        if not item['area'] or not case:
                            state['completed'] = sorted(set(state['completed']) | {key})
                            del state['claims'][key]
    current = run / 'case-progress.json'
    if current.exists():
        value = json.loads(current.read_text())
        counts = value['categories']
        if category in counts:
            failed = failed_case_selection(run, [record]).get(category, [])
            counts[category]['failed'] = len(failed)
            value['failed'] = counts[value['category']].get('failed', 0)
            value['error_log'] = str(error_log(run))
            launcher.atomic(current, value)


def run_family_cases(root, category, options, execute, gate, *, inventory,
                     round_number, completed_categories=()):
    from test_checkpoint import Checkpoint
    from vm_selection import selected
    from vm_case_queue import work_items, work_key, claim
    vm = selected()
    original = [arg for arg in options if arg != '--resume']
    queue = FamilyCases(parent_run(gate.run) or gate.run, vm.family, category, original, round_number)
    checkpoint = Checkpoint(root, [(category, original)], resume='--resume' in options,
                            binding=vm.name, recover_missing='--resume' in options)
    generation = None
    while True:
        with gate.source():
            current = gate.generation()
            if current != generation:
                cases = case_inventory(root, category, original)
                items = work_items(category, original, cases)
                totals = case_totals(root, inventory, category, cases) if cases is not None else None
                generation = current
            checkpoint = Checkpoint(root, [(category, original)], resume=True, binding=vm.name)
            saved_path = gate.run / 'checkpoint.json'
            records = json.loads(saved_path.read_text()).get('failed_cases', []) if saved_path.exists() else []
            omitted = set(failed_case_selection(gate.run, records).get(category, []))
            with queue.state() as state:
                state['items'].update({work_key(item): item for item in items})
                state['current'] = [work_key(item) for item in items]
                for item in items:
                    if unresolved := set(item['cases']) & omitted:
                        state.setdefault('failed', {})[work_key(item)] = sorted(unresolved)
                failed = {case for cases_failed in state.get('failed', {}).values() for case in cases_failed}
                accepted = {case for key in state['completed']
                            for case in state['items'][key]['cases']} - failed
                # Resume can retain runner passes from before this queue existed.
                # A live/interrupted claim still needs its runner to return after
                # finalization and cleanup, even if all case events were saved.
                claimed = {case for key in state['claims']
                           for case in state['items'][key]['cases']}
                accepted |= checkpoint.passed(category) - claimed - failed
                if cases is not None:
                    accepted.intersection_update(cases)
                state['completed'] = list(set(state['completed']) | {
                    work_key(item) for item in items if item['cases']
                    and set(item['cases']) <= accepted | failed})
                for key, owner in list(state['claims'].items()):
                    if owner == vm.name and key in state['completed']:
                        del state['claims'][key]
                pending = list({work_key(item): item for item in (
                    *(state['items'][key] for key in state['claims']), *items)}.values())
                owned = [item for item in pending if state['claims'].get(work_key(item)) == vm.name]
                item = owned[0] if owned else claim(pending, state['completed'], state['claims'], vm.name)
            passed = checkpoint.passed(category) | accepted
            if cases is not None:
                passed.intersection_update(cases)
            checkpoint.entry(category)['passed'] = sorted(passed)
            checkpoint.excluded[category] = passed | failed
            checkpoint.snapshot(category)
            checkpoint.save()
            if item is None:
                # Other workers may still own work. They must finish before the
                # parent accepts the family, but this idle VM need not occupy a
                # concurrency slot while a queued owner recovers its claim.
                checkpoint.entry(category)['complete'] = True
                checkpoint.save()
                if cases:
                    publish_case_progress(root, gate.run, category, cases, cases[-1], passed,
                        totals=totals, round_number=round_number,
                        completed_categories=completed_categories)
                return 0
            requested = set(item['cases'])
            target = item['case']
            # Original selectors stay in the VM checkpoint; the shared work
            # description controls only this bounded attempt's retry scope.
            if item['case'] is None:
                arguments = original
            else:
                target = (next((case for case in item['cases'] if case not in passed | failed), item['case'])
                          if item['area'] else item['case'])
                arguments = [*original, '--resume', '--resume-case=' + target,
                             '--resume-area-only' if item['area'] else '--resume-case-only']
            if cases:
                publish_case_progress(root, gate.run, category, cases, target,
                    checkpoint.passed(category), totals=totals, round_number=round_number,
                    completed_categories=completed_categories, area=item['area'])
            gate.last_generation = current
            status = execute(arguments)
            gate.case_result(status)
            if status:
                return status
            checkpoint = Checkpoint(root, [(category, original)], resume=True, binding=vm.name)
            if not requested <= checkpoint.passed(category) | failed:
                raise ValueError('case runner returned success without teardown-complete case evidence')
            with queue.state() as state:
                key = work_key(item)
                if state['claims'].get(key) != vm.name:
                    raise ValueError('family case claim ownership changed')
                state['completed'] = list(set(state['completed']) | {key} | {
                    work_key(candidate) for candidate in items
                    if set(candidate['cases']) & requested
                    and set(candidate['cases']) <= checkpoint.passed(category) | failed})
                del state['claims'][key]


def acknowledge_family_retry(root, gate, category, original, round_number, case):
    """A successful focused runner may finish its owner's retained claim.

    Saved case passes alone do not acknowledge report/recording finalization or
    cleanup. Call only after the current runner has returned success.
    """
    from test_checkpoint import Checkpoint
    from vm_selection import selected
    vm = selected()
    queue = FamilyCases(parent_run(gate.run), vm.family, category, original, round_number)
    if not queue.path.exists():
        return
    checkpoint = Checkpoint(root, [(category, original)], resume=True, binding=vm.name)
    with queue.state() as state:
        for key, owner in list(state['claims'].items()):
            item = state['items'][key]
            if (owner == vm.name and case in item['cases']
                    and set(item['cases']) <= checkpoint.passed(category)):
                state['completed'] = list(set(state['completed']) | {key})
                del state['claims'][key]


def publish_case_progress(root, run, category, cases, case, passed, *, totals, round_number,
                          completed_categories=(), area=False):
    """One selected-case count and clock for the dashboard and VM tile."""
    from launcher_progress import case_progress
    from vm_recording import case_identity
    nodeid = case or cases[-1]
    if category == 'integration':
        identifier = nodeid
        title = nodeid.removeprefix('check_').replace('_', ' ').capitalize()
    else:
        identifier, title = case_identity(root, category, dict(nodeid=nodeid))
    now = time.monotonic_ns()
    try:
        previous = case_progress(run)
    except (OSError, ValueError, KeyError, TypeError):
        previous = {}
    completed = len(set(cases) & passed)
    saved_path = run / 'checkpoint.json'
    records = json.loads(saved_path.read_text()).get('failed_cases', []) if saved_path.exists() else []
    omitted = failed_case_selection(run, records)
    same_round = previous.get('round') == round_number
    counts = {kind: dict(completed=total if kind in completed_categories else 0, failed=0, total=total)
              for kind, total in totals.items()}
    if same_round:
        for kind, value in previous['categories'].items():
            if kind in counts and value['total'] == counts[kind]['total']:
                counts[kind]['completed'] = max(counts[kind]['completed'], value['completed'])
                counts[kind]['failed'] = value.get('failed', 0)
                if counts[kind]['failed']:
                    counts[kind]['completed'] = value['completed']
    counts[category]['completed'] = completed
    counts[category]['failed'] = len(set(cases) & set(omitted.get(category, [])))
    same_category = (same_round and previous.get('category') == category
                     and previous.get('total') == len(cases)
                     and not (previous.get('completed') == len(cases) and not completed))
    launcher.atomic(run / 'case-progress.json', dict(category=category, case=case, area=area,
        completed=completed, failed=counts[category]['failed'], error_log=str(error_log(run)),
        total=len(cases), index=cases.index(nodeid) + 1,
        round=round_number, categories=counts,
        vm_started_ns=previous['vm_started_ns'] if same_round else now,
        case_id=str(identifier), title=title,
        started_ns=previous['started_ns'] if same_category else now,
        case_started_ns=(previous['case_started_ns'] if same_category
                         and previous.get('case') in (nodeid, None) else now)))


def pipeline_heading(name, state, steps, question, saved, *, blocker=None, stopping=False,
                     session=None):
    """Summarize scheduling and repair phases without granting execution credit."""
    terminal = {'complete': 'Complete', 'failed': 'Complete with failures', 'limited': 'Task limit reached',
                'stopped': 'Stopped', 'blocked': 'Blocked', 'reload': 'Waiting for controller reload'}
    phase = next((line for line in reversed(steps[-1]['lines'])
                  if line.startswith('Status: ')), '') if steps else ''
    agent_active = session is not None and session.get('status') == 'running'
    status = terminal.get(state)
    if status is None:
        if stopping:
            status = 'Stopping' if state == 'running' else 'Stopped'
        elif state == 'queued' or phase == 'Status: Queued on repair' and not agent_active:
            status = (f'Queued on {blocker} repair' if blocker and blocker != name else
                      'Repairing' if blocker == name and state == 'running' else 'Queued on VM slot')
        elif question:
            status = 'Waiting for input'
        elif saved.get('pending') is not None:
            status = 'Save fix'
        elif agent_active:
            status = 'Repairing'
        elif phase == 'Status: Verifying':
            status = 'Verifying'
        elif phase.startswith(('Status: fixing errors', 'Status: validating retained response')):
            status = 'Repairing'
        elif blocker == name or saved.get('repairs') or saved.get('queued_failure'):
            status = 'Verifying'
        else:
            status = 'Running'
    color = ('90' if status == 'Queued on VM slot' else
             '38;2;0;152;255' if status == 'Running' else
             '38;2;255;165;0' if status.startswith('Queued on ') or status in ('Repairing', 'Verifying', 'Save fix', 'Waiting for controller reload') else
             '32' if status == 'Complete' else '31')
    return f'VM: {name} (\033[1;{color}m{status}\033[0m)'


def run(root, run, owner, model, effort, app_model, requested, rounds, resume):
    """Own one recording controller across all VM pipelines and their cleanup."""
    from regression_process import Control
    from vm_recording import recording
    media = None
    status = 1
    try:
        with launcher_reload.watching(run), Control().installed() as control, recording(root, enabled=True) as media:
            status = _run_pipelines(root, run, owner, model, effort, app_model, requested, rounds, resume, control)
        if status == launcher_reload.STATUS:
            from fix_tests import ControllerReload
            raise ControllerReload()
        return status
    except KeyboardInterrupt:
        status = 130
        raise
    except launcher_reload.ReloadRequested:
        status = launcher_reload.STATUS
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
    from vm_selection import BATCH, VARIABLE, WORKER as VM_WORKER, vm_config
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
        from launcher_chat import read_state, send_input, take_input, task_info
        from launcher_progress import read_progress, repair_progress, case_progress, case_frame, category_cases
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
            for entry in take_input(run):
                state = read_state(child)
                if entry['kind'] == 'message' or entry['session'] in (None, state['session']):
                    send_input(child, entry['kind'], entry['text'])
        stopping = control.stopped.is_set() or (run / 'cancel').exists()
        if waiting:
            lines.append(f'Repair queue: {len(waiting)} | new cases waiting')
        sessions = []
        for name in states:
            child = child_run(name)
            steps = repair_progress(child, read_progress(child))
            question = pending(child)
            checkpoint_path = child / 'checkpoint.json'
            saved = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
            session_path = child / 'session-view.json'
            session = json.loads(session_path.read_text()) if session_path.exists() else None
            if session is not None:
                sessions.append((session['started_at'], child))
            lines.extend(['', pipeline_heading(name, states[name]['status'], steps, question, saved,
                                               blocker=blocker, stopping=stopping, session=session)])
            frame = child / 'frame.json'
            details = json.loads(frame.read_text()) if frame.exists() else []
            if not details:
                from watch_output import snapshot as read_frame
                details = read_frame(child / 'test-frame.json')
            try:
                current = case_progress(child)
            except (OSError, ValueError, KeyError, TypeError):
                current = None
            if current is not None:
                details = case_frame(steps, details, current)
            lines.extend(step['lines'][0] for step in steps[-1:] if step['key'] != 'admission')
            if current is not None and steps and f'Category: {current["category"]} (' in steps[-1]['lines'][0]:
                lines.append(category_cases(current))
            lines.extend(details)
            parent_question = run / 'question.json'
            displayed = json.loads(parent_question.read_text()) if parent_question.exists() else None
            if question and (displayed is None or displayed.get('id') == question['id']
                             or displayed.get('answer') is not None):
                if displayed and displayed['id'] == question['id'] and displayed.get('answer') is not None:
                    launcher.atomic(child / 'question.json', displayed)
                elif displayed is None or displayed['id'] != question['id']:
                    launcher.atomic(parent_question, dict(question, explanation=name + ': ' + question['explanation']))
            elif displayed and question is None and displayed.get('answer') is None:
                child_question = child / 'question.json'
                if child_question.exists():
                    expired = json.loads(child_question.read_text())
                    if expired.get('id') == displayed['id'] and expired.get('expired'):
                        launcher.atomic(parent_question, dict(displayed, expired=True))
        latest_session = max(sessions, key=lambda item: item[0])[1] if sessions else None
        panel_child = (next(child for child, _ in pipelines.values() if child.name == repair_owner)
                       if repair_owner is not None else latest_session)
        if panel_child is None:
            panel_child = next((child for name, (child, _) in pipelines.items()
                                if states[name]['status'] == 'running'), None)
        if panel_child is not None:
            state = read_state(panel_child)
            # The parent displays one aggregate controller row. Keep the
            # selected child's task identity and clocks aligned with that row.
            launcher.atomic(run / 'task-info.json', task_info(panel_child, state.get('task_id')))
            launcher.atomic(run / 'chat-state.json', dict(state, progress_key='pipelines'))
        if latest_session is not None:
            description = latest_session / 'descriptive-output.json'
            if description.exists():
                launcher.atomic(run / 'descriptive-output.json', json.loads(description.read_text()))
        launcher.atomic(run / 'frame.json', lines)
        launcher.atomic(state_path, states)

    failed = threading.Event()
    def execute_owned(name, selection, *, recovery=False, receipt=None):
        if control.stopped.is_set() or (run / 'cancel').exists():
            return 130
        if launcher_reload.pending():
            return launcher_reload.STATUS
        child = child_run(name)
        (child / 'result.json').unlink(missing_ok=True)
        # Older destination launchers authenticate these with the strict private
        # receipt reader too. Publish 0600 independently of the caller's umask.
        launcher._publish_start(child / 'pipeline.json', dict(parent=str(run)))
        launcher._publish_start(child / 'vm.json', {'vm': None if name == 'host' else name})
        if not (child / 'limits.json').exists():
            TaskBudget(child).initialize(None)
        # The runner checkpoint validates selectors and rounds even for a
        # completed pipeline. Presentation state cannot grant a pass.
        states[name]['status'] = 'running'
        args = [value for kind, spec in selection.items() for value in (kind, *spec['args'])]
        environment = launcher.environment()
        if launcher_reload.current is not None:
            launcher_reload.current.inherit(environment)
        environment.pop(BATCH, None)
        if receipt is not None:
            from vm_pool import VARIABLE as CHECKOUT
            environment[CHECKOUT] = receipt
        if recovery:
            environment[RECOVERY_ONLY] = '1'
        if name == 'host':
            environment.pop(VARIABLE, None)
            environment.pop(VM_WORKER, None)
        else:
            environment[VARIABLE] = name
            environment[VM_WORKER] = '1'
        command = ['/usr/bin/python3', '-IBu', str(WORKER),
                   '--reload-worker' if (child / 'reload-ready.json').exists() else '--worker',
                   str(root), str(child), str(owner), model, effort, app_model,
                   json.dumps(args), rounds,
                   'true' if recovery or (child / 'reload-ready.json').exists() else resume]
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
                gate = RepairGate(child, root=root, stopped=control.stopped.is_set)
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
            if status == launcher_reload.STATUS and not launcher_reload.pending():
                raise ValueError('pipeline exited with reload status without a reload request')
            from fix_tests import COMPLETED_WITH_FAILURES
            finished = status in (0, COMPLETED_WITH_FAILURES)
            if finished and unfinished and not recovery:
                raise ValueError('pipeline finished with unresolved retained repairs')
            if finished and not unfinished:
                coordinator.discard(child.name)
            states[name]['status'] = ('reload' if status == launcher_reload.STATUS else
                'limited' if (child / 'limited').exists() else
                'queued' if status == 0 and recovery else
                'failed' if status == COMPLETED_WITH_FAILURES else
                'complete' if status == 0 else 'stopped' if status == 130 else 'blocked')
            publish()
        return status

    slots = threading.Semaphore(snapshot['concurrency'])

    def needed(name, selection):
        """An unused busy VM must not delay a family whose queue has drained."""
        vm = configured[name]
        for category, spec in selection.items():
            for number in range(1, int(rounds) + 1):
                queue = FamilyCases(run, vm.family, category, spec['args'], number)
                if not queue.path.exists():
                    return True
                with queue.state(write=False) as saved:
                    if not saved['items']:
                        return True
                    if name in saved['claims'].values():
                        return True
                    if set(saved.get('current', saved['items'])) - set(saved['completed']) - set(saved['claims']):
                        return True
        return False

    def execute(name, selection, *, recovery=False):
        try:
            if name == 'host':
                status = execute_owned(name, selection, recovery=recovery)
            else:
                from vm_case_queue import available_worker
                with available_worker(configured[name], slots,
                        lambda: control.stopped.is_set() or (run / 'cancel').exists(),
                        needed=lambda: recovery or needed(name, selection)) as receipt:
                    if receipt is None:
                        with output_lock:
                            states[name]['status'] = 'complete'
                            publish()
                        return 0
                    status = execute_owned(name, selection, recovery=recovery, receipt=receipt)
        except launcher_reload.ReloadRequested:
            # A reload can arrive while the supervisor is waiting for a source
            # lease. No child was admitted; let the other pipelines drain.
            status = launcher_reload.STATUS
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
        from fix_tests import COMPLETED_WITH_FAILURES
        if status == COMPLETED_WITH_FAILURES:
            failed.set()
        elif status and status != launcher_reload.STATUS:
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
    parent_budget.update(lambda value: value.update(remaining=remaining + value['completed']))
    warn_remaining(parent_budget.read()['tasks'], remaining, label='fix-tests')
    with ThreadPoolExecutor(max_workers=1) as pool:
        host_task = pool.submit(execute, 'host', host) if host else None
        try:
            results = dispatch(vms, len(vms), lambda vm: execute(vm.name, guests), control.stopped)
            if host_task is not None:
                host_task.result()
        except BaseException:
            control.stop()
            raise
    statuses = {name: value['status'] if isinstance(value, dict) else value for name, value in results.items()}
    launcher.atomic(run / 'vm-results.json', results)
    if not failed.is_set() and not control.stopped.is_set() and not launcher_reload.pending():
        queues = run / 'family-cases'
        for path in queues.glob('*.json') if queues.exists() else ():
            saved = json.loads(path.read_text())
            if (not saved['items'] or saved['claims']
                    or not set(saved.get('current', saved['items'])) <= set(saved['completed'])):
                raise ValueError('family case queue is incomplete after workers finished')
    if any(value['status'] == 'limited' for value in states.values()):
        (run / 'limited').touch(mode=0o600)
    return (1 if failed.is_set() else 130 if control.stopped.is_set() else
            launcher_reload.STATUS if launcher_reload.pending() else 1 if any(statuses.values()) else 0)
