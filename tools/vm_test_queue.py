"""Finite configured VM queue; workers use the maintained guarded controllers."""

import json
import os
from pathlib import Path
import sys
import tempfile
import threading

# Workers use isolated Python; restore only this checkout's sibling modules.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_source
if __name__ == '__main__':
    _source_imports = test_source.startup(Path(__file__).resolve().parents[1], sys.argv[1:])
    _source_imports.__enter__()

import test_activity
import test_launcher
import test_retention
from regression_process import Control, FRAME_PREFIX
from vm_selection import BATCH, VARIABLE, WORKER, vm_config
from vm_queue import Executor
from vm_pool import reservation
import launcher_reload
from vm_case_queue import case_inventory, work_items, arguments

if __name__ == '__main__':
    _source_imports.__exit__(None, None, None)

FAMILY_WORK = 'ONPC_TEST_FAMILY_WORK'
CHECKPOINT_READY = 'Family checkpoint ready: '


def queue_output_guard(root, store):
    """Recover queue output and completed host output from older mixed runs."""
    from test_storage import directory as storage_directory
    allocations = storage_directory('allocations', root=root)
    reports = storage_directory('reports', root=root)
    sbuild = storage_directory('sbuild', root=root)
    host_prefixes = ('onpc-test-publish-', 'onpc-ui-watch-', 'onpc-ui-preview-',
                     'onpc-ppa-check-', 'onpc-gjs-coverage-', 'onpc-coverage-')
    with store.opened() as fd:
        state = store.read(fd)
        entries = [*state['history'], state] if state else []
        for index, record in test_retention.latest_allocations(entries):
            path = Path(record['path'])
            if path.parent == allocations and path.name.startswith('onpc-vm-queue-'):
                continue
            completed = (index < len(entries) - 1 or
                         state['finished'] and 'recovery-required' not in os.listdir(fd))
            # The old host phase inherited the batch journal. Preserve those
            # records in normal retention, without accepting VM-bound inputs.
            # Store.reconcile/session still audit every recorded identity/tree.
            if completed and (path.parent == reports or
                    path.parent == allocations and path.name.startswith(host_prefixes) or
                    path.parent == sbuild and path.name.startswith('onpc-sbuild-scratch-')
                    and record.get('mode') == 0o711):
                continue
            try:
                path.lstat()
            except FileNotFoundError:
                continue
            raise ValueError('queue retention contains non-queue allocations; '
                             'recover them through their owning workflow before retrying')


def split(root, argv):
    from test_commands import execution_arguments, selections, AGGREGATES, PHASES
    args, stop = execution_arguments(argv or ['all'])
    selected = selections(root, args)
    if len(selected) == 1 and selected[0][0] in AGGREGATES:
        selected = [(kind, []) for kind in PHASES]
    host = [(kind, options) for kind, options in selected if kind not in ('system', 'e2e')]
    guests = [(kind, options) for kind, options in selected if kind in ('system', 'e2e')]
    def flatten(groups):
        result = [*(['--resume'] if '--resume' in argv else []),
                  *(['--resume-case-only'] if '--resume-case-only' in argv else []),
                  *(['--resume-area-only'] if '--resume-area-only' in argv else []),
                  *[arg for arg in argv if arg.startswith('--resume-case=')],
                  *(['--stop-on-error'] if stop else []),
                  *(value for kind, options in groups for value in (kind, *options))]
        if '--continue-on-errors' in args and all(kind in PHASES and not options
                                                for kind, options in groups):
            result.append('--continue-on-errors')
        return result
    return flatten(host) if host else [], flatten(guests)


@test_source.protected
def _plan(root, argv):
    """Load one coherent inventory before waiting for any VM reservation."""
    from test_commands import selections
    from test_checkpoint import guard_scheduling_checkpoints
    guard_scheduling_checkpoints(root)
    snapshot = json.loads(os.environ[BATCH])
    configured = vm_config.registry()
    vms = tuple(configured[name] for name in snapshot['vms'])
    host_args, guest_args = split(root, argv)
    guest_selection = selections(root, guest_args)
    families = {}
    original_vm = os.environ.get(VARIABLE)
    try:
        for vm in vms:
            if vm.family in families:
                continue
            vm_config.select(vm.name)
            items = [work for category, options in guest_selection
                     for work in work_items(category, options, case_inventory(
                         root, category, options, vm=vm.name,
                         pass_fds=test_source.descriptors()))]
            replay = [arg.partition('=')[2] for arg in guest_args if arg.startswith('--resume-case=')]
            if replay:
                if len(guest_selection) != 1 or not any(replay[0] in work['cases'] for work in items):
                    raise ValueError('case retry requires one category and a selected case')
            families[vm.family] = items
    finally:
        if original_vm is None:
            os.environ.pop(VARIABLE, None)
        else:
            vm_config.select(original_vm)
    return snapshot, vms, host_args, guest_args, guest_selection, families


class FamilyAdmission:
    """Balance ready workers, rotating ties without preempting active work."""

    def __init__(self, vms):
        self.families = {vm.name: vm.family for vm in vms}
        self.order = list(dict.fromkeys(self.families.values()))

    def choose(self, ready, active):
        counts = {family: sum(self.families[name] == family for name in active)
                  for family in self.order}
        candidates = {self.families[name] for name in ready}
        family = min((family for family in self.order if family in candidates),
                     key=lambda family: counts[family])
        self.order.remove(family)
        self.order.append(family)
        return next(name for name in ready if self.families[name] == family)


def source_identity(root):
    from regression_inputs import identity
    return dict(digest=identity(root), generation=test_source.SourceProtection(
        test_source.source_directory(root)).generation())


def execute_pass(root, plan, control, execute, *, host=None, actions=None,
                 pass_identity=None):
    """Own a finite pass; callbacks execute one assignment, never another queue.

    ``actions`` may hold admission and observe accepted/failing attempts. It
    supplies repair policy only; claims, acceptance and recovery stay here.
    A saved run/pass identity may be supplied by the composing repair workflow.
    """
    from test_checkpoint import PassCheckpoint
    snapshot, vms, host_args, guest_args, guest_selection, families = plan
    actions = actions or {}
    lock = threading.RLock()
    admission = FamilyAdmission(vms)
    accepted, failures = [], []
    repair_status = []
    suspended = False
    changed = False
    inflight = {}
    deferred = []
    focused = '--resume-case-only' in guest_args or '--resume-area-only' in guest_args
    replay = next((arg.partition('=')[2] for arg in guest_args if arg.startswith('--resume-case=')), None)
    focus_finished = set()
    if focused and replay is None:
        raise ValueError('focused retry requires a selected case')
    if '--resume-area-only' in guest_args:
        from test_checkpoint import INDEPENDENT_SYSTEM_AREAS
        if (len(guest_selection) != 1 or guest_selection[0][0] != 'system'
                or replay.partition('::')[0] not in INDEPENDENT_SYSTEM_AREAS):
            raise ValueError('area retry requires an independent system area')
    pool = {vm.name: vm.family for vm in vms}
    # Selection includes host and focused retry options; transport/control flags
    # do not change the original selected inventory on resume.
    def original(args):
        return [arg for arg in args if arg not in ('--resume', '--resume-case-only', '--resume-area-only')
                and not arg.startswith('--resume-case=')]
    selection = [['_host', original(host_args)], ['_guest', original(guest_args)]]
    with PassCheckpoint(root, selection, pool, families,
                        resume='--resume' in guest_args) as checkpoint:
        focus_owners = {claim['family']: claim['vm'] for claim in checkpoint.claims()
                        if focused and replay in claim['work']['cases']}
        if pass_identity is not None and pass_identity != {
                key: checkpoint.state[key] for key in ('run', 'pass')}:
            raise ValueError('saved pass identity differs from the selected run')
        if replay is not None:
            for family in families:
                checkpoint.retry(family, replay, area='--resume-area-only' in guest_args)

        def claims(family):
            return [claim for claim in checkpoint.claims(family)
                    if not focused or replay in claim['work']['cases']]

        def pending(family):
            return [work for work in checkpoint.pending(family)
                    if not focused or family not in focus_finished and replay in work['cases']]
        if host_args and not checkpoint.state['host_complete']:
            with test_source.reader(root, stopped=control.stopped.is_set):
                status = host() if host is not None else 2
                if not status:
                    checkpoint.state['host_complete'] = True
                    checkpoint.save()
            if status:
                return dict(status=status, results={}, accepted=[], failures=[dict(
                    vm='', status=status)], stopped=status == 130,
                    suspended=False, source_changed=False, repair_status=[])

        def admitted():
            nonlocal suspended
            if (control.stopped.is_set() or launcher_reload.pending() or changed or suspended
                    or 'admit' in actions and not actions['admit']()):
                suspended = not control.stopped.is_set()
                return False
            return True

        def needed(vm):
            with lock:
                unrelated = focused and any(claim['vm'] == vm.name and replay not in claim['work']['cases']
                                            for claim in checkpoint.claims(vm.family))
                return (not unrelated and (not focused or focus_owners.get(vm.family, vm.name) == vm.name)
                        and admitted() and (any(claim['vm'] == vm.name for claim in claims(vm.family))
                                            or bool(pending(vm.family))))

        def attempt(worker):
            vm = worker.vm
            with lock:
                # Uncertain claims are cleaned by their original worker before
                # returning to FIFO; its old checkpoint cannot award new credit.
                retained = next((claim for claim in claims(vm.family)
                                 if claim['vm'] == vm.name), None)
                recovering = retained is not None
                if recovering:
                    assignment = retained
                else:
                    available = pending(vm.family)
                    if not available or not admitted():
                        return dict(status=0, handoffs=[])
                    execution = None
                    if focused:
                        unit = available[0]
                        area = '--resume-area-only' in guest_args
                        execution = dict(unit, case=replay, area=area,
                                         cases=unit['cases'] if area else [replay])
                    assignment = checkpoint.claim(vm.family, vm.name, available[0], source_identity(root),
                                                  execution=execution)
                    if assignment is None:
                        return dict(status=0, handoffs=[])
                inherited = {kind: sorted(checkpoint.passed(vm.family, kind))
                             for kind, _ in guest_selection}
                inflight[vm.name] = assignment, recovering
            return execute(worker, assignment, inherited, recovering)

        def completed(vm, result):
            nonlocal changed, suspended
            with lock:
                current = inflight.pop(vm.name, None)
                if current is None:
                    if result['status']:
                        failures.append(dict(vm=vm.name, status=result['status']))
                    return result
                assignment, recovering = current
                evidence = result.get('evidence')
                if recovering:
                    if (not result['status'] and isinstance(evidence, dict)
                            and evidence.get('assignment') == assignment
                            and evidence.get('cleanup') is True):
                        checkpoint.recover(assignment, cleanup=True)
                    elif not result['status']:
                        result = dict(result, status=2, error='missing original-worker cleanup result')
                else:
                    changed |= isinstance(evidence, dict) and evidence.get('diagnostic') is True
                    complete = False
                    if result['status']:
                        # Failure notification can precede the retained worker's
                        # final check-in. Save partial credit only after join.
                        deferred.append((assignment, evidence, result['status']))
                    else:
                        try:
                            complete = checkpoint.accept(assignment, evidence, result['status'])
                        except ValueError as error:
                            result = dict(result, status=2, error=str(error))
                    if complete:
                        accepted.append(assignment)
                        if focused:
                            focus_finished.add(vm.family)
                    elif not result['status']:
                        result = dict(result, status=2,
                                      error='case runner returned success without qualified completion')
                if result['status']:
                    failures.append(dict(assignment=assignment, status=result['status']))
                if 'result' in actions:
                    outcome = actions['result'](assignment, result) or {}
                    changed |= bool(outcome.get('source_changed'))
                    suspended |= bool(outcome.get('suspended'))
                    if outcome.get('repair_status') is not None:
                        repair_status.append(outcome['repair_status'])
                if result['status'] not in (0, launcher_reload.STATUS) and '--stop-on-error' in guest_args:
                    control.stop()
            return result

        def choose(ready, active):
            with lock:
                eligible = [name for name in ready if sum(pool[other] == pool[name]
                    for other in active) < len(pending(pool[name]))
                    + len(claims(pool[name]))]
                return admission.choose(eligible, active) if eligible and admitted() else None

        with Executor(root, vms, snapshot['concurrency'], control.stopped) as executor:
            results = executor.run_ready(attempt, choose=choose, needed=needed, completed=completed)
        for assignment, evidence, status in deferred:
            try:
                checkpoint.accept(assignment, evidence, status)
            except ValueError:
                # Missing or unqualified failure evidence leaves its original
                # claim untouched; the terminal worker result already fails.
                pass
        unfinished = any((family not in focus_finished if focused else bool(checkpoint.pending(family)))
                         or claims(family) for family in families)
        statuses = [value['status'] for value in results.values()]
        stopped = control.stopped.is_set()
        status = (130 if stopped else launcher_reload.STATUS if launcher_reload.pending()
                  and all(value in (0, launcher_reload.STATUS) for value in statuses)
                  else 1 if any(statuses) or unfinished else 0)
        return dict(status=status, results=results, accepted=accepted, failures=failures,
                    stopped=stopped, suspended=suspended or unfinished and not any(statuses),
                    source_changed=changed, repair_status=repair_status,
                    run=checkpoint.state['run'], **{'pass': checkpoint.state['pass']})


def run(root, argv, *, reloading=False):
    plan = _plan(root, argv)
    snapshot, vms, host_args, guest_args, guest_selection, families = plan
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
    def execute_host():
        with test_activity.activity(root, host_only=True), test_source.reader(root):
            return _main(host_args, detached=True, checkpoint=Checkpoint(
                root, selections(root, host_args), resume='--resume' in host_args))
    with Control().installed() as control:
        store = test_retention.Store(test_activity.retention_path(root))
        # The inherited owner lease excludes live workers; every VM still
        # separately recovers its own journal and guest state.
        store.reconcile(lambda: queue_output_guard(root, store), completed_guard=lambda paths: None)
        with store.session():
            directory = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-vm-queue-'))
            # Named inputs are VM-bound. Each worker prepares them inside its
            # own retention session, before its independent guest execution.
            # A batch-owned allocation would conflict with that VM's old claim
            # after an interrupted input was removed and recreated.
            output_lock = threading.Lock()
            frames = {name: ['Queued'] for name in snapshot['vms']}

            def publish_frames():
                if hasattr(sys.stdout, 'frame'):
                    lines = [f'VM queue | concurrency {snapshot["concurrency"]}']
                    for index, name in enumerate(snapshot['vms']):
                        if index:
                            lines.append('')
                        lines.extend([f'VM: {name}', *frames[name]])
                    sys.stdout.frame(lines)

            def execute_worker(worker, assignment, inherited, recovering):
                vm, receipt = worker.vm, worker.receipt
                work = assignment.get('execution', assignment['work'])
                if launcher_reload.pending():
                    return dict(status=launcher_reload.STATUS, handoffs=[])
                environment = test_launcher.environment(root)
                if launcher_reload.current is not None:
                    launcher_reload.current.inherit(environment)
                environment.pop(BATCH, None)
                # A worker starts its own retention session, never another VM's.
                environment.pop(test_retention.VARIABLE, None)
                environment[VARIABLE] = vm.name
                environment[WORKER] = '1'
                from vm_pool import VARIABLE as CHECKOUT
                environment[CHECKOUT] = receipt
                environment.pop('ONPC_RUNNER_INVOCATION', None)
                request = directory / (vm.name + '-work.json')
                attempt = assignment['attempt']
                request.write_text(json.dumps(dict(selection=guest_args, passed=inherited,
                                                  assignment=assignment, recovering=recovering)))
                request.chmod(0o600)
                environment[FAMILY_WORK] = str(request)
                worker_args = arguments(work)
                if '--stop-on-error' in guest_args:
                    worker_args.insert(0, '--stop-on-error')
                command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                           '--execute-reload' if reloading else '--execute', vm.name, *worker_args]
                pending = b''
                handoffs = []
                ready = False
                with (directory / (vm.name + '.log')).open('ab') as log:
                    os.fchmod(log.fileno(), 0o600)
                    def output(data):
                        nonlocal pending, ready
                        log.write(data)
                        log.flush()
                        pending += data
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            value = line.decode('utf-8', errors='replace')
                            if value == CHECKPOINT_READY + attempt:
                                ready = True
                                continue
                            if value.startswith('Failure handoff: '):
                                handoffs.append(value.removeprefix('Failure handoff: '))
                            with output_lock:
                                if value.startswith(FRAME_PREFIX):
                                    frame = json.loads(value[len(FRAME_PREFIX):])
                                    # Clearing a dashboard does not finish its worker.
                                    frames[vm.name] = frame or ['Running (waiting for progress)']
                                    publish_frames()
                                else:
                                    print(f'[{vm.name}] {value}', flush=True)
                    status = control.run(command, cwd=root, env=environment,
                                         output=output, cooperative=True)
                    if pending:
                        with output_lock:
                            print(f'[{vm.name}] ' + pending.decode('utf-8', errors='replace'), flush=True)
                evidence = None
                if ready:
                    saved = Checkpoint(root, guest_selection, resume=True, binding=vm.name)
                    evidence = saved.state.get('queue_evidence')
                return dict(status=status, handoffs=handoffs, evidence=evidence)

            def execute_case(worker, assignment, inherited, recovering):
                vm = worker.vm
                with output_lock:
                    frames[vm.name] = ['Starting worker']
                    publish_frames()
                try:
                    result = execute_worker(worker, assignment, inherited, recovering)
                except (ValueError, OSError):
                    with output_lock:
                        frames[vm.name] = ['Failed (worker error)']
                        publish_frames()
                    raise
                status = result['status']
                state = {0: 'Finished', 130: 'Stopped',
                         launcher_reload.STATUS: 'Reload pending'}.get(status, f'Failed (exit {status})')
                with output_lock:
                    frames[vm.name] = [state]
                    publish_frames()
                return result

            publish_frames()
            outcome = execute_pass(root, plan, control, execute_case, host=execute_host)
            results = outcome['results']
            if not results:
                return outcome['status']
            # Keep the actual joined results even if failure-detail processing
            # below cannot read a diagnostic handoff.
            (directory / 'results.json').write_text(json.dumps(results, indent=2))
            (directory / 'results.json').chmod(0o600)
            print(f'VM results: {directory / "results.json"}', flush=True)
            if (not control.stopped.is_set() and launcher_reload.pending()
                    and all((result['status'] if isinstance(result, dict) else result)
                            in (0, launcher_reload.STATUS) for result in results.values())):
                launcher_reload.check()
            categories = []
            failures = []
            error_details = []
            for vm in vms:
                result = results[vm.name]
                vm_categories = []
                vm_failures = []
                if isinstance(result, dict) and result['status']:
                    for path in result['handoffs']:
                        try:
                            handoff = json.loads(Path(path).read_text())
                            if (not isinstance(handoff, dict)
                                    or not isinstance(handoff.get('categories'), list)
                                    or any(not isinstance(kind, str) for kind in handoff['categories'])
                                    or not isinstance(handoff.get('failures', []), list)
                                    or any(not isinstance(item, dict)
                                        or not isinstance(item.get('category'), str)
                                        or not isinstance(item.get('case'), str)
                                        for item in handoff.get('failures', []))):
                                raise ValueError('invalid failure handoff')
                        except (OSError, ValueError) as error:
                            print(f'[{vm.name}] Failure details unavailable ({type(error).__name__}); '
                                  f'see {directory / (vm.name + ".log")}.', flush=True)
                            continue
                        vm_categories.extend(handoff['categories'])
                        details = handoff.get('error_details', [])
                        details = details if isinstance(details, list) else []
                        error_details.extend(dict(detail, detail=vm.name + ': ' + detail['detail'])
                            for detail in details
                            if isinstance(detail, dict) and isinstance(detail.get('category'), str)
                            and isinstance(detail.get('detail'), str))
                        vm_failures.extend(dict(item, vm=vm.name)
                                           for item in handoff.get('failures', []))
                if (result['status'] if isinstance(result, dict) else result) != 0:
                    if not vm_categories:
                        vm_categories.extend(kind for kind, _ in guest_selection
                                             if kind in ('system', 'e2e'))
                    for category in dict.fromkeys(vm_categories):
                        if not any(item['category'] == category for item in vm_failures):
                            vm_failures.append(dict(category=category, case='', vm=vm.name))
                categories.extend(vm_categories)
                failures.extend(vm_failures)
            failed = any((result['status'] if isinstance(result, dict) else result) != 0
                         for result in results.values())
            if hasattr(sys.stdout, 'frame'):
                sys.stdout.frame([])
            if failed and not control.stopped.is_set():
                prompt = f'Investigate the VM failures in {directory / "results.json"} and adjacent VM logs. Preserve expected behavior and all unrelated work.'
                handoff = directory / 'failure.json'
                handoff.write_text(json.dumps({'prompt': prompt, 'categories': list(dict.fromkeys(categories)),
                                              'failures': failures, 'error_details': error_details}))
                handoff.chmod(0o600)
                print(f'Failure handoff: {handoff}', flush=True)
            # Each directly spawned worker returns only after its guarded
            # execution and cleanup. Its exit status owns the result; report
            # archives and diagnostic file lifetimes do not qualify it again.
            return outcome['status']


def worker(argv):
    finished = []
    status = _worker(argv, finished)
    # Both the guest controller and this child's enclosing leases have now
    # finished cleanup. A failed context exit publishes no attempt evidence.
    for checkpoint, evidence in finished:
        checkpoint.state['queue_evidence'] = evidence
        checkpoint.save()
    return status


def _worker(argv, finished):
    mode, name, *args = argv
    if mode not in ('--execute', '--execute-reload'):
        raise ValueError('private VM queue entry only')
    vm_config.select(name)
    os.environ.pop(BATCH, None)
    os.environ[WORKER] = '1'
    root = Path(__file__).resolve().parents[1]
    from regression_process import PipeFrameOutput
    sys.stdout = PipeFrameOutput(sys.stdout)
    # The batch's checkout-local gate is not a VM reservation or cleanup proof.
    os.environ.pop(test_activity.VARIABLE, None)
    sys.stdout.frame(['Queued (waiting for VM checkout)'])
    with launcher_reload.watching(), Control().installed(pipe=True) as control, reservation(name, stopped=control.stopped), \
            test_activity.activity(root, named_vm=True), test_source.reader(root, stopped=control.stopped.is_set):
        # Nested aggregate controllers observe the same parent cancellation.
        import regression_process
        regression_process.session_stop = control.stopped
        from test_recovery import cleanup
        if control.stopped.is_set():
            return 130
        sys.stdout.frame(['Preparing tests'])
        status = cleanup(root)
        if status:
            return status
        from test_commands import _main
        from test_checkpoint import Checkpoint
        from test_commands import selections
        work_path = os.environ.pop(FAMILY_WORK, None)
        work = json.loads(Path(work_path).read_text()) if work_path else None
        original = work['selection'] if work else args
        checkpoint = Checkpoint(root, selections(root, original), resume=not work and '--resume' in args)
        if work:
            # The parent owns shared family credit. This VM writes only its
            # private attempt checkpoint; concurrent workers never overwrite it.
            for category in checkpoint.selected:
                passed = work['passed'][category]
                checkpoint.entry(category).update(passed=passed, complete=False)
                checkpoint.excluded[category] = set(passed)
                checkpoint.snapshot(category)
            assignment = work['assignment']
            if assignment['vm'] != name:
                raise ValueError('assignment belongs to another VM')
            checkpoint.state['queue_assignment'] = assignment
            checkpoint.save()
            print(CHECKPOINT_READY + assignment['attempt'], flush=True)
            if work['recovering']:
                finished.append((checkpoint, dict(assignment=assignment, cleanup=True)))
                return 0
            if assignment['source'] != source_identity(root):
                raise ValueError('assignment source inputs changed before execution')
        replay = [arg.partition('=')[2] for arg in args if arg.startswith('--resume-case=')]
        if replay:
            groups = selections(root, args)
            if len(groups) != 1:
                raise ValueError('case retry requires one category')
            if mode == '--execute-reload':
                if '--resume-case-only' in args or '--resume-area-only' in args:
                    checkpoint.retry_case = replay[0]
                    checkpoint.retry_area = replay[0].partition('::')[0] if '--resume-area-only' in args else None
            elif '--resume-case-only' in args or '--resume-area-only' in args:
                if work:
                    checkpoint.retry_case = replay[0]
                    checkpoint.retry_area = replay[0].partition('::')[0] if '--resume-area-only' in args else None
                    checkpoint.event(groups[0][0], dict(kind='failure', nodeid=replay[0]), set())
                else:
                    checkpoint.retry(groups[0][0], replay[0], area='--resume-area-only' in args)
            else:
                checkpoint.event(groups[0][0], dict(kind='failure', nodeid=replay[0]), set())
        try:
            status = _main([*args, '--vm', name], detached=True, checkpoint=checkpoint)
        except launcher_reload.ReloadRequested:
            return launcher_reload.STATUS
        if work:
            # An inherited pass is never evidence that this attempt executed it.
            # The report owns case teardown; main returns through retained-output
            # finalization before this bounded result is made available.
            category = assignment['work']['category']
            executed = assignment.get('execution', assignment['work'])
            observed = checkpoint.passed(category) & set(executed['cases'])
            evidence = dict(assignment, passed=sorted(observed),
                cleanup=bool(getattr(checkpoint, 'queue_finalized', False)),
                diagnostic=assignment['source'] != source_identity(root))
            finished.append((checkpoint, evidence))
        return status


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
