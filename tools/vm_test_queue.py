"""Run-tests group routing and case passes; vm_queue owns VM workers and leases."""

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
    return flatten(host) if host else [], flatten(guests) if guests else []


@test_source.protected
def _plan(root, argv):
    """Load one coherent inventory before waiting for any VM reservation."""
    from test_commands import selections
    from test_checkpoint import guard_scheduling_checkpoints
    guard_scheduling_checkpoints(root)
    host_args, guest_args = split(root, argv)
    snapshot = json.loads(os.environ[BATCH]) if BATCH in os.environ else dict(concurrency=1, vms=[])
    configured = vm_config.registry() if snapshot['vms'] else {}
    vms = tuple(configured[name] for name in snapshot['vms'])
    if not vms and guest_args:
        raise ValueError('VM work requires its configured allowed pool')
    guest_selection = selections(root, guest_args) if guest_args else []
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
        self.compute = {vm.name: vm.compute_unit for vm in vms}
        self.order = list(dict.fromkeys(self.families.values()))

    def choose(self, ready, active):
        from host_compute import units
        counts = {family: sum((units(self.compute[name]) for name in active
                              if self.families[name] == family), units(0))
                  for family in self.order}
        candidates = {self.families[name] for name in ready}
        family = min((family for family in self.order if family in candidates),
                     key=lambda family: counts[family])
        self.order.remove(family)
        self.order.append(family)
        return next(name for name in ready if self.families[name] == family)


def source_identity(root):
    origin = vm_config.remote_origin()
    if origin is not None and 'source_identity' in origin:
        return dict(origin['source_identity'])
    from regression_inputs import identity
    return dict(digest=identity(root), generation=test_source.SourceProtection(
        test_source.source_directory(root)).generation())


def repair_case_inventory(root, work, control, *, vm=None):
    """Collect bounded retry candidates under the ticket's original selectors."""
    if work['category'] in ('system', 'e2e'):
        return case_inventory(root, work['category'], work['options'], vm=vm,
                              pass_fds=test_source.descriptors())
    if work['category'] not in ('unit', 'component', 'ui', 'fixture-runtime'):
        return None
    from regression_events import PREFIX
    command = [str(root / 'tools/run-tests'), work['category'], '--unattended',
               *work['options'], '--collect-only', '-q']
    output = []
    status = control.run(command, cwd=root, env=test_launcher.environment(root),
                         output=output.append, cooperative=True,
                         pass_fds=test_source.descriptors())
    if status:
        raise ValueError('bounded repair case collection failed with status ' + str(status))
    cases = [case for line in b''.join(output).decode('utf-8', errors='replace').splitlines()
             if line.startswith(PREFIX) for event in [json.loads(line[len(PREFIX):])]
             if event.get('kind') == 'collection' for case in event.get('nodeids', [])]
    if not cases:
        raise ValueError('bounded repair case collection returned no cases')
    return list(dict.fromkeys(cases))


def execute_pass(root, plan, control, execute, *, host=None, actions=None,
                 pass_identity=None, checkpoint_scope='ordinary', continue_on_errors=False):
    """Own a finite pass; callbacks execute one assignment, never another queue.

    ``actions`` may hold admission and observe accepted/failing attempts. It
    supplies repair policy only; claims, acceptance and recovery stay here.
    A saved run/pass identity may be supplied by the composing repair workflow.
    """
    from test_checkpoint import PassCheckpoint, _repair_impact
    snapshot, vms, host_args, guest_args, guest_selection, families = plan
    actions = actions or {}
    lock = threading.RLock()
    admission = FamilyAdmission(vms)
    accepted, failures = [], []
    repair_status = []
    suspended = False
    changed = False
    repaired_source_changed = False
    inflight = {}
    interrupt_attempts = threading.Event()
    deferred = []
    repair_mode = 'triage' in actions and 'repair' in actions
    def report_error(context, error, **identity):
        from detached_launcher import record_exception
        if 'error' in actions:
            return actions['error'](context, error, **identity)
        return record_exception(None, context, error, **identity)
    protection = test_source.SourceProtection(test_source.source_directory(root))
    failure_results = {}
    triaged = {}
    impacts = {}
    limited = False
    prerequisite = False
    host_cleanup_complete = True
    denied_categories = set()
    reserved_tickets = set()
    reserved_tickets = set()

    def impact_key(ticket):
        return str(protection.directory / ('ticket-' + ticket['id']))

    def hold(ticket, decision):
        with protection.state():
            protection.set_impact(impact_key(ticket), decision)

    def release(ticket):
        with protection.state():
            protection.release_impact(impact_key(ticket))
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
                        resume='--resume' in (*host_args, *guest_args), identity=pass_identity,
                        scope=checkpoint_scope) as checkpoint:
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
                    if (not focused or replay in claim['work']['cases'])
                    and not (repair_mode and any(ticket['assignment'] == claim['assignment']
                            for ticket in checkpoint.repair_tickets()))]

        def pending(family):
            return [work for work in checkpoint.pending(family)
                    if (not focused or family not in focus_finished and replay in work['cases'])
                    and not (repair_mode and any(ticket['family'] == family and ticket['work'] == work
                        and ticket.get('outcome') != 'resolved'
                        for ticket in checkpoint.state.get('repairs', [])))]
        if repair_mode:
            for ticket in checkpoint.repair_tickets():
                hold(ticket, 'untriaged')
        from test_commands import selections
        host_categories = {kind for kind, _ in selections(root, host_args)} if host_args else set()
        if checkpoint.state['host_complete']:
            checkpoint.state['host_passed'] = sorted(host_categories)

        def publish_progress():
            if 'progress' not in actions:
                return
            counts = {}
            for family, items in families.items():
                by_category = {}
                for work in items:
                    by_category.setdefault(work['category'], set()).update(work['cases'])
                counts[family] = {kind: dict(total=len(cases),
                    completed=len(cases & checkpoint.passed(family, kind)))
                    for kind, cases in by_category.items()}
            actions['progress'](dict(run=checkpoint.state['run'], **{'pass': checkpoint.state['pass']},
                families=counts, host_completed=checkpoint.state.get('host_passed', []),
                host_categories=sorted(host_categories), repairs=[dict(
                    id=ticket['id'], attempt=ticket['attempt'], vm=ticket['vm'], case=ticket['case'],
                    category=ticket['work']['category'], impact=impacts.get(ticket['id'], 'untriaged'),
                    reason=(_repair_impact(ticket) or {}).get('decision', {}).get('reason',
                        'Awaiting failure impact assessment.'),
                    blocked=impacts.get(ticket['id']) != 'no' or not ticket['cleanup'])
                    for ticket in checkpoint.repair_tickets()]))

        publish_progress()

        def pending_host():
            blocked = {ticket['work']['category'] for ticket in checkpoint.state.get('repairs', [])
                       if not ticket['vm'] and ticket.get('outcome') != 'resolved'}
            return host_categories - set(checkpoint.state.get('host_passed', [])) - blocked - denied_categories

        def run_host():
            nonlocal limited, suspended, host_cleanup_complete
            categories = pending_host()
            if not categories:
                return False
            with test_source.reader(root, stopped=control.stopped.is_set):
                value = host(categories=categories) if host is not None else dict(status=2)
                status = value['status']
                host_cleanup_complete = bool(value.get('cleanup', True))
                suspended |= not host_cleanup_complete and not repair_mode
                limited |= bool(value.get('limited'))
                denied_categories.update(value.get('denied_categories', []))
                passed = set(value.get('completed_categories', []))
                if not status and value.get('complete', True):
                    passed.update(categories - denied_categories)
                checkpoint.state['host_passed'] = sorted(set(checkpoint.state.get('host_passed', [])) | passed)
                checkpoint.state['host_complete'] = host_categories <= set(checkpoint.state['host_passed'])
                checkpoint.save()
                publish_progress()
                if status:
                    works = value.get('failure_works', [value['failure_work']] if value.get('failure_work') else [])
                    if repair_mode and works:
                        for work in works:
                            ticket = checkpoint.host_failure(work, source_identity(root), status, case=work['case'])
                            failure_results[ticket['id']] = value
                            hold(ticket, 'untriaged')
                    else:
                        failures.append(dict(vm='', status=status))
                        suspended |= repair_mode
            return True

        if not repair_mode and host_args and not checkpoint.state['host_complete']:
            run_host()

        def admitted():
            nonlocal suspended
            if (control.stopped.is_set() or launcher_reload.pending() or changed or suspended
                    or 'admit' in actions and not actions['admit']()):
                suspended = not control.stopped.is_set()
                return False
            if repair_mode and checkpoint.repair_tickets():
                return False
            return True

        def needed(vm):
            with lock:
                unrelated = focused and any(claim['vm'] == vm.name and replay not in claim['work']['cases']
                                            for claim in checkpoint.claims(vm.family))
                return (not unrelated and (not focused or focus_owners.get(vm.family, vm.name) == vm.name)
                        and admitted() and (any(claim['vm'] == vm.name for claim in claims(vm.family))
                                            or bool(eligible_pending(vm.family))))

        def eligible_pending(family):
            return [work for work in pending(family) if work['category'] not in denied_categories]

        def attempt(worker):
            nonlocal limited
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
                    available = eligible_pending(vm.family)
                    while available and 'admit_task' in actions and not actions['admit_task'](
                            available[0]['category']):
                        denied_categories.add(available[0]['category'])
                        limited = True
                        available = eligible_pending(vm.family)
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
                if not recovering:
                    worker.interrupt = interrupt_attempts
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
                if result.get('interrupted'):
                    try:
                        if not isinstance(evidence, dict) or evidence.get('cleanup') is not True:
                            raise ValueError('interrupted attempt lacks verified VM cleanup')
                        checkpoint.accept(assignment, evidence, 130, interrupted=True)
                        checkpoint.recover(assignment, cleanup=True)
                        result = dict(result, status=0, cleanup_complete=True)
                    except ValueError as error:
                        result = dict(result, status=2, error=str(error))
                        suspended = True
                elif recovering:
                    if (not result['status'] and isinstance(evidence, dict)
                            and evidence.get('assignment') == assignment
                            and evidence.get('cleanup') is True):
                        checkpoint.recover(assignment, cleanup=True)
                    elif not result['status']:
                        result = dict(result, status=2, error='missing original-worker cleanup result')
                    if result['status']:
                        # Retain the claim for resume; failed recovery must not
                        # immediately select the same recovery again.
                        suspended = True
                else:
                    changed |= isinstance(evidence, dict) and evidence.get('diagnostic') is True
                    complete = False
                    if result['status']:
                        # Failure notification can precede the retained worker's
                        # final check-in. Save partial credit only after join.
                        if repair_mode and result.get('repair_ticket'):
                            try:
                                checkpoint.accept(assignment, evidence, result['status'])
                                if evidence.get('cleanup') is True:
                                    checkpoint.recover(assignment, cleanup=True)
                            except ValueError as error:
                                result = dict(result, error=str(error))
                                suspended = True
                        else:
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
                if (not repair_mode and result['status'] not in (0, launcher_reload.STATUS)
                        and '--stop-on-error' in guest_args):
                    control.stop()
                publish_progress()
            if 'result' in actions:
                outcome = actions['result'](assignment, result) or {}
                changed |= bool(outcome.get('source_changed'))
                suspended |= bool(outcome.get('suspended'))
                if outcome.get('repair_status') is not None:
                    repair_status.append(outcome['repair_status'])
            return result

        def observed(vm, result):
            nonlocal prerequisite
            # A child can interrupt independently (including in preparation).
            # Only coordinator cancellation excuses it from failure handling.
            if (not repair_mode or not result['status'] or result['status'] == launcher_reload.STATUS
                    or result.get('interrupted')
                    or result['status'] == 130 and control.stopped.is_set()):
                return
            with lock:
                current = inflight.get(vm.name)
                if current is None or current[1]:
                    return
                assignment = current[0]
                if 'prerequisite' in actions and actions['prerequisite'](vm.name, result):
                    # Persist the prerequisite before cancelling admitted work.
                    # Preparation starts only after the executor joins cleanup.
                    prerequisite = True
                    result['prerequisite'] = True
                    control.stop()
                    return
                failed_case = result.get('failure_case')
                ticket = checkpoint.enqueue_failure(assignment, result.get('evidence'), result['status'],
                                                     case=failed_case)
                # The shared gate changes while the failed operation's source
                # reader still protects its inputs and before any refill.
                hold(ticket, 'untriaged')
                result['repair_ticket'] = ticket['id']
                failure_results[ticket['id']] = dict(result)
                interrupt_attempts.set()

        def refresh_impact(ticket, *, writer=False):
            if writer and (not checkpoint.repair_tickets()
                    or checkpoint.repair_tickets()[0]['id'] != ticket['id']
                    or test_source.WRITER not in test_source.environment()):
                raise ValueError('impact reassessment requires the FIFO head owning its source writer')
            if triaged.get(ticket['id']) == source_identity(root):
                return
            try:
                # The head may reassess under its existing exclusive lease
                # after a failed no-edit recheck. Ordinary triage still uses
                # the named reader and cannot borrow another repair's writer.
                with test_source.reader(root, stopped=control.stopped.is_set,
                        impact_ticket=None if writer else impact_key(ticket), wait=False):
                    envelope = actions['triage'](ticket, failure_results.get(ticket['id']))
                    if envelope['source'] != source_identity(root):
                        raise ValueError('triage source changed')
                    with lock:
                        ticket['impact'] = checkpoint.record_impact(ticket['id'], envelope['decision'],
                            source=envelope['source'], evidence_digest=envelope['evidence_digest'])
                    hold(ticket, envelope['decision']['impact'])
                    impacts[ticket['id']] = envelope['decision']['impact']
            except test_source.SourceBusy:
                # Recovery must finish under its original writer before
                # read-only triage can inspect the checkout. Keep the hold
                # and retry later, without caching this as completed triage.
                return
            except Exception as error:
                from detached_launcher import Stopped
                if not isinstance(error, (launcher_reload.ReloadRequested, Stopped)):
                    repair_status.append(dict(ticket=ticket['id'], phase='triage',
                        **report_error('Impact triage', error,
                            ticket=ticket['id'], vm=ticket['vm'], case=ticket['case'])))
                hold(ticket, 'unsure')
                impacts[ticket['id']] = 'unsure'
                if isinstance(error, (launcher_reload.ReloadRequested, Stopped)):
                    raise
            triaged[ticket['id']] = source_identity(root)
            with lock:
                publish_progress()

        class Execution:
            def __init__(self, ticket, executor):
                self.ticket = ticket
                self.failure = failure_results.get(ticket['id'])
                self.executor = executor
                self.drained = True

            def refresh_impact(self):
                """Reassess after a failed no-edit recheck, before repair sessions."""
                refresh_impact(self.ticket, writer=True)

            def prepare_baseline(self):
                """Prepare through the original worker, without granting case credit.

                Native agent command processes do not retain launcher file
                descriptors. Keep preparation with the reserved worker and its
                borrowed source writer instead of forwarding stale FD claims.
                """
                if not self.ticket['vm']:
                    raise ValueError('baseline preparation requires the failed VM')

                def prepare(worker):
                    from vm_pool import VARIABLE as CHECKOUT
                    environment = test_launcher.environment(root)
                    environment.pop(BATCH, None)
                    environment[VARIABLE] = worker.vm.name
                    environment[CHECKOUT] = worker.receipt
                    tail = b''

                    def output(data):
                        nonlocal tail
                        tail = (tail + data)[-16000:]
                        sys.stdout.buffer.write(data)
                        sys.stdout.flush()

                    status = control.run([str(root / 'tools/prepare-vm'), '--vm', worker.vm.name,
                        '--mode', 'auto', '--y'], cwd=root, env=environment,
                        output=output, wait_on_cancel=True)
                    return dict(status=status, output_tail=tail.decode('utf-8', errors='replace'))

                return self.executor.attempt(self.ticket['vm'], prepare)

            def attempt(self, purpose, target=None):
                ticket = self.ticket
                work = dict(ticket.get('execution', ticket['work']))
                cases = repair_case_inventory(root, ticket['work'], control, vm=ticket['vm'] or None)
                if isinstance(target, str):
                    if cases is None or target not in cases:
                        raise ValueError('repair target is outside the original selected work')
                    work.update(case=target, cases=[target], area=False)
                elif isinstance(target, dict):
                    work = target
                elif target is not None:
                    raise ValueError('invalid bounded repair target')
                elif cases is not None:
                    candidates = [ticket['case'], *(attempt['execution']['case']
                                  for attempt in reversed(ticket.get('attempts', [])))]
                    if ticket['case']:
                        candidates.extend(case for case in cases if case.startswith(ticket['case'] + '::'))
                    case = next((case for case in candidates if case in cases), cases[0])
                    work.update(case=case, cases=[case], area=False)
                reference = checkpoint.begin_attempt(ticket['id'], purpose, source_identity(root), work,
                                                       selected_cases=cases)
                assignment = {field: ticket[field] for field in (
                    'run', 'pass', 'selection', 'family', 'vm', 'work', 'assignment')}
                assignment.update(attempt=reference['attempt'], source=reference['source'], execution=work)
                if ticket['vm']:
                    inherited = {kind: sorted(checkpoint.passed(ticket['family'], kind))
                                 for kind, _ in guest_selection}
                    value = self.executor.attempt(ticket['vm'], lambda worker:
                        execute(worker, assignment, inherited, False))
                else:
                    value = host(assignment)
                status = value['status'] if isinstance(value, dict) else value
                evidence = value.get('evidence') if isinstance(value, dict) else None
                accepted_reference = checkpoint.finish_attempt(ticket['id'], reference, evidence, status,
                                                                source=source_identity(root))
                return dict(value if isinstance(value, dict) else {}, status=status,
                            accepted=accepted_reference['accepted'], reference=accepted_reference)

        def service(executor, drained):
            nonlocal repaired_source_changed, suspended, limited
            if not repair_mode or suspended or control.stopped.is_set() or launcher_reload.pending():
                return
            if checkpoint.repair_tickets():
                interrupt_attempts.set()
            for ticket in checkpoint.repair_tickets():
                if ticket['vm'] and ticket['vm'] not in reserved_tickets:
                    if ticket['vm'] in inflight:
                        continue
                    executor.reserve(ticket['vm'])
                    reserved_tickets.add(ticket['vm'])
                if triaged.get(ticket['id']) == source_identity(root):
                    continue
                prior_impact = ticket.get('impact')
                if (drained and isinstance(prior_impact, dict)
                        and isinstance(prior_impact.get('source'), dict)
                        and prior_impact['source'] != source_identity(root)):
                    # A preceding repair may have fixed this queued failure.
                    # Keep admission fenced, but let the FIFO's exact-case
                    # recheck run before spending another triage session.
                    hold(ticket, 'unsure')
                    impacts[ticket['id']] = 'unsure'
                    continue
                refresh_impact(ticket)
            tickets = checkpoint.repair_tickets()
            if drained and admitted() and pending_host():
                return run_host()
            if not drained or not tickets:
                return
            ticket = tickets[0]
            phase = 'repair action'
            try:
                outcome = actions['repair'](ticket, Execution(ticket, executor))
                if not isinstance(outcome, dict):
                    raise ValueError('repair must return an outcome')
                kind = outcome.get('outcome')
                phase = 'repair settlement'
                reason = outcome.get('reason')
                if kind == 'resolved' and (protection.owner() is not None
                        or not ticket['vm'] and outcome.get('attempt', {}).get('source') != source_identity(root)):
                    kind = 'suspended'
                    reason = 'resolved repair retains a writer or stale host qualification'
                if kind == 'leave_failed' and (impacts.get(ticket['id']) != 'no' or protection.owner() is not None):
                    kind = 'suspended'
                    reason = 'failed repair retains shared impact or an unfinished writer'
                # Hold a reader through final validation and release the hold
                # under the same gate. Wait for transient source contention
                # after close-out rather than suspending an accepted repair.
                # VM qualification belongs to its captured inputs; host
                # qualification still checks the live source after admission.
                with test_source.reader(root, stopped=control.stopped.is_set,
                                        impact_ticket=impact_key(ticket)):
                    if kind == 'resolved' and (protection.owner() is not None
                            or not isinstance(outcome.get('attempt'), dict)
                            or not ticket['vm'] and outcome['attempt']['source'] != source_identity(root)):
                        raise ValueError('resolved repair retains a writer or stale qualification')
                    with protection.state():
                        settled = checkpoint.settle_repair(ticket['id'], kind,
                            reference=outcome.get('attempt'), repair_ref=outcome.get('repair_ref'))
                        if kind != 'suspended':
                            protection.release_impact(impact_key(ticket))
                repaired_source_changed |= bool(outcome.get('source_changed'))
                repair_status.append(dict(ticket=ticket['id'], outcome=kind, reason=reason))
                if kind == 'suspended':
                    suspended = True
                    return
                if not checkpoint.repair_tickets():
                    interrupt_attempts.clear()
                if ticket['vm'] and not any(value['vm'] == ticket['vm'] for value in checkpoint.repair_tickets()):
                    executor.release(ticket['vm'])
                    reserved_tickets.discard(ticket['vm'])
                if kind == 'resolved':
                    accepted.append(settled)
                publish_progress()
                return True
            except Exception as error:
                from detached_launcher import Stopped
                if not isinstance(error, (launcher_reload.ReloadRequested, Stopped)):
                    details = report_error(phase, error,
                        ticket=ticket['id'], vm=ticket['vm'], case=ticket['case'])
                else:
                    details = dict(error=str(error))
                checkpoint.settle_repair(ticket['id'], 'suspended')
                repair_status.append(dict(ticket=ticket['id'], outcome='suspended', **details))
                suspended = True
                if isinstance(error, (launcher_reload.ReloadRequested, Stopped)):
                    raise

        def choose(ready, active):
            with lock:
                eligible = [name for name in ready if sum(pool[other] == pool[name]
                    for other in active) < len(eligible_pending(pool[name]))
                    + len(claims(pool[name]))]
                return admission.choose(eligible, active) if eligible and admitted() else None

        if vms:
            with Executor(root, vms, snapshot['concurrency'], control.stopped) as executor:
                options = dict(observed=observed, service=service, keep_failed=True) if repair_mode else {}
                results = executor.run_ready(attempt, choose=choose, needed=needed, completed=completed, **options)
        else:
            results = {}
            while service(None, True):
                pass
        for assignment, evidence, status in deferred:
            try:
                checkpoint.accept(assignment, evidence, status)
                if continue_on_errors and not repair_mode and evidence['cleanup']:
                    # The original worker has joined and supplied qualified
                    # cleanup. Relinquish ownership without passing the failed
                    # case, so independent groups may proceed safely.
                    checkpoint.recover(assignment, cleanup=True)
            except ValueError as error:
                # Missing or unqualified failure evidence leaves its original
                # claim untouched; the terminal worker result already fails.
                repair_status.append(dict(assignment=assignment['assignment'], phase='acceptance',
                    **report_error('Deferred attempt acceptance', error,
                        assignment=assignment['assignment'], vm=assignment['vm'])))
        host_terminal = {ticket['work']['category'] for ticket in checkpoint.state.get('repairs', [])
                         if not ticket['vm'] and ticket.get('outcome') == 'leave_failed'}
        unfinished = bool(host_categories - set(checkpoint.state.get('host_passed', [])) - host_terminal) or any(
            (family not in focus_finished if focused else bool(checkpoint.pending(family)))
            or claims(family) for family in families)
        statuses = [value['status'] for value in results.values()]
        stopped = control.stopped.is_set()
        terminal_failed = any(ticket.get('outcome') == 'leave_failed'
                              for ticket in checkpoint.state.get('repairs', []))
        resolved = {(ticket['assignment'], ticket['attempt'])
                    for ticket in checkpoint.state.get('repairs', []) if ticket.get('outcome') == 'resolved'}
        unhandled_failure = any(not failure.get('assignment') or (
            failure['assignment']['assignment'], failure['assignment']['attempt']) not in resolved
            for failure in failures)
        resolved_tickets = {ticket['id'] for ticket in checkpoint.state.get('repairs', [])
                            if ticket.get('outcome') == 'resolved'}
        unhandled_failure |= any(value['status'] and value.get('repair_ticket') not in resolved_tickets
                                 for value in results.values())
        admitted_pending = bool(host_categories - set(checkpoint.state.get('host_passed', []))
                                - host_terminal - denied_categories) or any(
            work['category'] not in denied_categories
            for family in families for work in pending(family)) or bool(checkpoint.claims())
        clean_limit = (limited and not admitted_pending and not suspended and not terminal_failed
                       and not checkpoint.repair_tickets() and not unhandled_failure)
        status = (130 if stopped else launcher_reload.STATUS if launcher_reload.pending()
                  and all(value in (0, launcher_reload.STATUS) for value in statuses)
                  else 1 if (terminal_failed or checkpoint.repair_tickets() or unfinished and not clean_limit
                             or (unhandled_failure if repair_mode else any(statuses))) else 0)
        if 'settle_task' in actions:
            unresolved = checkpoint.repair_tickets()
            categories = {work['category'] for items in families.values() for work in items}
            from test_commands import selections
            categories.update(kind for kind, _ in (selections(root, host_args) if host_args else []))
            for category in categories:
                if (not any(work['category'] == category for family in families for work in pending(family))
                        and not any(claim['work']['category'] == category for claim in checkpoint.claims())
                        and not any(ticket['work']['category'] == category for ticket in unresolved)
                        and (category not in host_categories
                             or category in set(checkpoint.state.get('host_passed', [])) | host_terminal)):
                    actions['settle_task'](category)
        return dict(status=status, results=results, accepted=accepted, failures=failures,
                    cleanup_complete=host_cleanup_complete and not checkpoint.claims() and not checkpoint.repair_tickets(),
                    stopped=stopped, suspended=suspended or unfinished and not clean_limit
                        and not any(statuses) and not terminal_failed and not unhandled_failure,
                    source_changed=changed or repaired_source_changed, repair_status=repair_status,
                    terminal_failed=terminal_failed, limited=limited,
                    unfinished=unfinished, unhandled_failure=unhandled_failure,
                    clean_limit=clean_limit, denied_categories=sorted(denied_categories),
                    pending_repairs=bool(checkpoint.repair_tickets()),
                    prerequisite=prerequisite,
                    run=checkpoint.state['run'], **{'pass': checkpoint.state['pass']})


def execution_groups(root, argv, vms):
    """Resolve test routing before shared capacity admission sees candidates."""
    from test_commands import CATEGORIES, selections
    host_args, guest_args = split(root, argv)
    groups = []
    by_key = {}
    if host_args:
        groups.append(dict(key='host', category='host', args=host_args, vm_tag=None, vms=[]))
    controls = [arg for arg in guest_args if arg in ('--stop-on-error',)
                or arg.startswith('--resume-case=')
                or arg in ('--resume-case-only', '--resume-area-only')]
    for category, options in selections(root, guest_args) if guest_args else []:
        spec = CATEGORIES[category]
        children = [(None, spec.vm_tag or 'general', list(options))]
        if spec.subcategories:
            if category != 'e2e':
                raise ValueError('subcategory inventory requires a category case binding')
            import runpy
            runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
            selected = runner['preflight'](list(options), root=root, allow_missing_artifacts=True)
            if 'cases' in selected:
                membership = {case['subcategory'] for case in selected['cases']}
                if not membership <= {child.name for child in spec.subcategories}:
                    raise ValueError('E2E case belongs to an unregistered test subcategory')
                # An exact selector can name a case from a later group. Do not
                # manufacture an empty earlier group or rerun another selection.
                base = []
                tokens = iter(options)
                for token in tokens:
                    if token == '--subcategory':
                        next(tokens, None)
                    elif not token.startswith('--subcategory='):
                        base.append(token)
                children = [(child.name, child.vm_tag or spec.vm_tag or 'general',
                             [*base, '--subcategory', child.name])
                            for child in spec.subcategories if child.name in membership]
        for name, tag, args in children:
            candidates = [vm for vm in vms if tag in vm.vm_tags]
            missing = {vm.family for vm in vms} - {vm.family for vm in candidates}
            key = category + ('.' + name if name else '')
            if missing:
                raise ValueError(f'{key}: no selected VM with vm_tag={tag} for families: '
                                 + ', '.join(sorted(missing)))
            if not candidates:
                raise ValueError(f'{key}: no selected VM with vm_tag={tag}')
            if key in by_key:
                by_key[key]['args'].extend((category, *args))
            else:
                group = dict(key=key, category=category, args=[*controls, category, *args],
                             vm_tag=tag, vms=[vm.name for vm in candidates])
                groups.append(group)
                by_key[key] = group
    return groups


def run(root, argv, *, reloading=False, actions=None, pass_identity=None, return_outcome=False,
        checkpoint_scope='ordinary'):
    """Run sequential test groups; the scheduler only receives eligible pools."""
    import host_compute
    from contextlib import nullcontext
    from test_checkpoint import GroupCheckpoint, PassCheckpoint, guard_scheduling_checkpoints
    actions = actions or {}
    original = {key: os.environ.get(key) for key in (BATCH, VARIABLE)}
    with test_source.startup(root, argv, repair='repair' in actions):
        guard_scheduling_checkpoints(root)
        snapshot = json.loads(os.environ[BATCH]) if BATCH in os.environ else dict(vms=[])
        configured = vm_config.registry() if snapshot['vms'] else {}
        vms = [configured[name] for name in snapshot['vms']]
        groups = execution_groups(root, argv, vms)
        host_args, guest_args = split(root, argv)
    # Resume/transport controls do not change the selected work's identity.
    for group in groups:
        group['args'] = [arg for arg in group['args'] if arg not in (
            '--resume', '--resume-case-only', '--resume-area-only') and not arg.startswith('--resume-case=')]
    replay = next((arg.partition('=')[2] for arg in argv if arg.startswith('--resume-case=')), None)
    # Continuation is a run-wide scheduling policy, not a leaf-case option.
    continue_on_errors = '--continue-on-errors' in argv
    matched = False
    last = dict(status=0, results={}, source_changed=False, terminal_failed=False)
    ungrouped_selection = [[kind, [arg for arg in args if arg not in (
        '--resume', '--resume-case-only', '--resume-area-only') and not arg.startswith('--resume-case=')]]
        for kind, args in (('_host', host_args), ('_guest', guest_args))]
    with GroupCheckpoint(root, groups, snapshot['vms'], resume='--resume' in argv,
                         identity=pass_identity, scope=checkpoint_scope,
                         ungrouped_selection=ungrouped_selection) as saved:
        def settled(index):
            outcome = saved.state['outcomes'][index]
            return outcome is not None and (outcome['status'] == 0 or outcome['terminal_failed'])

        for index, group in enumerate(groups):
            from launcher_control import CancellationEvent
            if CancellationEvent().is_set():
                last = dict(status=130, stopped=True)
                break
            launcher_reload.check()
            if replay is None and settled(index):
                if (group['category'] != 'host' and 'settle_task' in actions
                        and all(settled(n)
                            for n, other in enumerate(groups) if other['category'] == group['category'])):
                    actions['settle_task'](group['category'])
                continue
            scope = saved.group_scope(index)
            identity = saved.group_identity(index)
            # Routing may add a subcategory selector. An in-place legacy
            # owner must still receive its original checkpoint selection.
            group_args = (dict(ungrouped_selection)['_host' if group['category'] == 'host' else '_guest']
                          if saved.state.get('ungrouped') else group['args'])
            with PassCheckpoint.saved(root, scope=scope) as previous:
                resume = previous is not None and identity == {
                    key: previous.state[key] for key in ('run', 'pass')}
                if replay is not None and (previous is None or not any(replay in work['cases']
                        for partition in previous.state['families'].values()
                        for work in partition['items'].values())):
                    continue
                matched = True
            if replay is not None:
                saved.state['outcomes'][index] = None
                saved.save()
            targets = saved.state['workers'][index]
            exact = targets is not None
            if exact and not set(targets) <= set(group['vms']):
                raise ValueError(f'{group["key"]}: resume requires its original admitted VMs '
                                 'to remain eligible for this group')
            candidates = [configured[name] for name in (targets if exact else group['vms'])]
            reservation = host_compute.launch(candidates, exact=exact, handoff=False) if candidates else nullcontext([])
            try:
                with reservation as admitted:
                    if admitted:
                        host_compute.bind(admitted)
                    else:
                        if original[BATCH] is not None:
                            os.environ[BATCH] = json.dumps(dict(concurrency=0, vms=[]))
                        else:
                            os.environ.pop(BATCH, None)
                        os.environ.pop(VARIABLE, None)
                    saved.state['workers'][index] = [vm.name for vm in admitted]
                    saved.save()
                    owner_run = launcher_reload.current.run if launcher_reload.current is not None else None
                    if admitted and owner_run is not None:
                        from detached_launcher import atomic
                        host_compute.save_admitted(owner_run, admitted)
                    if hasattr(sys.stdout, 'controller'):
                        sys.stdout.controller('test-group', [f'Test group: {group["key"]}'
                            + (f' | VM tag: {group["vm_tag"]}' if group['vm_tag'] else '')])
                    group_actions = dict(actions)
                    # Category budgets settle after all its children, never
                    # after the first successful child alone.
                    if group['category'] != 'host':
                        group_actions.pop('settle_task', None)
                    from vm_recording import recording
                    media, media_status = None, 1
                    try:
                        with recording(root, enabled=bool(admitted), run=owner_run) as media:
                            while True:
                                if 'resume_prerequisite' in actions:
                                    status = actions['resume_prerequisite']()
                                    if status:
                                        last = dict(status=status, suspended=True)
                                        break
                                args = [*(['--resume'] if resume else []), *group_args]
                                if replay is not None:
                                    args = [*([arg for arg in argv if arg.startswith('--resume-case=')
                                        or arg in ('--resume-case-only', '--resume-area-only')]), *args]
                                last = _run_group(root, args, reloading=reloading, actions=group_actions,
                                    pass_identity=identity, return_outcome=True, checkpoint_scope=scope,
                                    continue_on_errors=continue_on_errors)
                                if not last.get('prerequisite') or 'resume_prerequisite' not in actions:
                                    break
                                resume = True
                        media_status = last['status']
                    except launcher_reload.ReloadRequested:
                        media_status = launcher_reload.STATUS
                        raise
                    finally:
                        if media is not None and owner_run is not None:
                            media.write_index(owner_run, media_status)
                    if admitted and owner_run is not None and last.get('cleanup_complete'):
                        atomic(owner_run / 'admitted-vms.json', [])
                    if not last.get('cleanup_complete'):
                        last['suspended'] = True
                        last['status'] = last['status'] or 1
            finally:
                for key, value in original.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            if (last.get('stopped') or last.get('suspended') or last.get('pending_repairs')
                    or last.get('limited') or last.get('prerequisite') or last['status'] not in (0, 1)):
                break
            if replay is not None:
                # A focused attempt grants only its actual case credit. It
                # cannot settle the whole group or advance to another group.
                break
            saved.state['outcomes'][index] = {key: last.get(key, False) for key in (
                'status', 'source_changed', 'terminal_failed')}
            saved.save()
            if last['status'] and not last.get('terminal_failed') and not continue_on_errors:
                break
            category = group['category']
            if category != 'host' and 'settle_task' in actions and not any(other['category'] == category
                    and not settled(n) for n, other in enumerate(groups)):
                actions['settle_task'](category)
        completed = [outcome for outcome in saved.state['outcomes'] if outcome is not None]
        last['source_changed'] = bool(last.get('source_changed') or any(value['source_changed'] for value in completed))
        last['terminal_failed'] = bool(last.get('terminal_failed') or any(value['terminal_failed'] for value in completed))
        if any(value['status'] for value in completed) and not last['status']:
            last['status'] = 1
        if replay is not None and not matched:
            raise ValueError('case retry is outside the retained test groups')
        last.update(run=saved.state['run'], **{'pass': saved.state['pass']},
                    groups=[dict(group=group['key'], outcome=outcome)
                            for group, outcome in zip(groups, saved.state['outcomes'], strict=True)])
        return last if return_outcome else last['status']


def _run_group(root, argv, *, reloading=False, actions=None, pass_identity=None, return_outcome=False,
        checkpoint_scope='ordinary', continue_on_errors=False):
    # Recovery must inspect the original inventory even when its durable impact
    # hold blocks normal readers. Release this finite bootstrap before waits.
    with test_source.startup(root, argv, repair=bool(actions and 'repair' in actions)):
        plan = _plan(root, argv)
    snapshot, vms, host_args, guest_args, guest_selection, families = plan
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
    host_ran = '--resume' in host_args
    def execute_host(assignment=None, *, categories=None):
        nonlocal host_ran
        with test_activity.activity(root, host_only=True), test_source.reader(root):
            groups = selections(root, host_args)
            selected_groups = [group for group in groups if categories is None or group[0] in categories]
            admitted_groups = [group for group in selected_groups if assignment is not None
                               or not actions or 'admit_task' not in actions
                               or actions['admit_task'](group[0])]
            options = [*(['--resume'] if host_ran else []),
                       *(['--stop-on-error'] if '--stop-on-error' in host_args else []),
                       *(value for kind, args in admitted_groups for value in (kind, *args))]
            if admitted_groups == groups:
                options = list(host_args)
            if assignment is not None:
                options = arguments(assignment.get('execution', assignment['work']))
            if not admitted_groups and assignment is None:
                return dict(status=0, handoffs=[], complete=False, limited=True,
                            denied_categories=[kind for kind, _ in selected_groups])
            saved = Checkpoint(root, groups, resume=host_ran or assignment is not None)
            host_ran = True
            if assignment is not None and assignment['execution']['case'] is not None:
                saved.retry_case = assignment['execution']['case']
                saved.event(assignment['work']['category'], dict(kind='failure', nodeid=saved.retry_case), set())
            stream = sys.stdout
            handoffs, output_tail = [], ''
            class Output:
                def __getattr__(self, name):
                    return getattr(stream, name)
                def write(self, value):
                    nonlocal output_tail
                    output_tail = (output_tail + value)[-16000:]
                    for line in value.splitlines():
                        if line.startswith('Failure handoff: '):
                            handoffs.append(line.removeprefix('Failure handoff: '))
                    return stream.write(value)
            try:
                sys.stdout = Output()
                status = _main(options, detached=True, checkpoint=saved)
            finally:
                sys.stdout = stream
            result = dict(status=status, handoffs=handoffs, output_tail=output_tail,
                          cleanup=bool(getattr(saved, 'queue_finalized', False)),
                          complete=len(admitted_groups) == len(selected_groups),
                          limited=len(admitted_groups) != len(selected_groups),
                          denied_categories=[group[0] for group in selected_groups if group not in admitted_groups],
                          completed_categories=[kind for kind, _ in admitted_groups if saved.complete(kind)])
            if assignment is not None:
                work = assignment['execution']
                result['evidence'] = dict(assignment, passed=sorted(saved.passed(work['category']) & set(work['cases'])),
                    cleanup=bool(getattr(saved, 'queue_finalized', False)),
                    diagnostic=assignment['source'] != source_identity(root))
            elif status:
                failures = []
                for path in handoffs:
                    try:
                        failures.extend(json.loads(Path(path).read_text()).get('failures', []))
                    except (OSError, ValueError):
                        continue
                works = []
                for failure in failures or [{}]:
                    kind, selected = next((group for group in admitted_groups
                        if group[0] == failure.get('category')), admitted_groups[0])
                    case = failure.get('case') or None
                    work = dict(category=kind, options=selected, case=case,
                                cases=[case] if case else [], area=False)
                    if work not in works:
                        works.append(work)
                result['failure_works'] = works
            return result
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
                    log.seek(0, os.SEEK_END)
                    attempt_output_start = log.tell()
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
                    attempt_control = Control()
                    attempt_control.stopped = threading.Event()
                    spawned = False
                    def started():
                        nonlocal spawned
                        spawned = True
                    def interrupt():
                        if (control.stopped.is_set() or launcher_reload.pending()
                                or worker.interrupt.is_set()):
                            attempt_control.stop()
                    interrupt()
                    refused_start = attempt_control.stopped.is_set()
                    status = (130 if refused_start else attempt_control.run(
                        command, cwd=root, env=environment, output=output,
                        cooperative=True, tick=interrupt, started=started))
                    if pending:
                        with output_lock:
                            print(f'[{vm.name}] ' + pending.decode('utf-8', errors='replace'), flush=True)
                evidence = None
                from vm_pool import remote
                route = remote()
                if route is not None:
                    evidence = route.result.get('evidence')
                    handoffs = []
                    for index, received in enumerate(route.result.get('handoffs', [])):
                        handoff = dict(received['failure'])
                        path = directory / (vm.name + '-remote-' + attempt + '-' + str(index) + '.json')
                        context = received.get('context')
                        prefix = ('This failure ran on VM host ' + received['host'] +
                                  '; original artifact paths below belong to that host. ')
                        if context is not None:
                            context_path = path.with_name(path.stem + '-context.json')
                            context_path.write_text(json.dumps(context))
                            context_path.chmod(0o600)
                            prefix += 'Read the retained bounded failure context at ' + str(context_path) + '. '
                        handoff['prompt'] = prefix + '\n' + handoff['prompt']
                        path.write_text(json.dumps(handoff))
                        path.chmod(0o600)
                        handoffs.append(str(path))
                elif ready:
                    saved = Checkpoint(root, guest_selection, resume=True, binding=vm.name)
                    evidence = saved.state.get('queue_evidence')
                if refused_start or (route is None and attempt_control.stopped.is_set() and not spawned):
                    # A refused invocation or a local Popen that never happened
                    # proves no start. Missing remote acknowledgement does not.
                    evidence = dict(assignment, passed=[], failed=[], cleanup=True,
                                    interrupted=True, diagnostic=False)
                with (directory / (vm.name + '.log')).open('rb') as log:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(attempt_output_start, log.tell() - 16000))
                    output_tail = log.read(16000).decode('utf-8', errors='replace')
                result = dict(status=status, handoffs=handoffs, evidence=evidence, output_tail=output_tail)
                if attempt_control.stopped.is_set() and evidence is None:
                    result.update(status=130, interrupted=True)
                if (attempt_control.stopped.is_set() and isinstance(evidence, dict)
                        and evidence.get('interrupted') is True and not evidence.get('failed', [])):
                    # The coordinator validates the exact assignment and cleanup
                    # before returning unfinished work to pending. No synthetic
                    # failure or passing attempt is created by preemption.
                    result.update(status=130, interrupted=True, handoffs=[])
                for path in handoffs:
                    try:
                        failed = json.loads(Path(path).read_text()).get('failures', [])
                        case = next((item.get('case') for item in failed
                                     if item.get('case') in work['cases']), None)
                        if case is not None:
                            result['failure_case'] = case
                            break
                    except (OSError, ValueError):
                        continue
                return result

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
            try:
                outcome = execute_pass(root, plan, control, execute_case, host=execute_host,
                                       actions=actions, pass_identity=pass_identity,
                                       checkpoint_scope=checkpoint_scope,
                                       continue_on_errors=continue_on_errors)
            except Exception as error:
                from detached_launcher import Stopped, record_exception
                if not isinstance(error, (launcher_reload.ReloadRequested, Stopped)):
                    record_exception(directory, 'VM pass coordinator', error)
                raise
            results = outcome['results']
            from detached_launcher import atomic
            try:
                atomic(directory / 'outcome.json', outcome)
                (directory / 'outcome.json').chmod(0o600)
            except OSError as error:
                from detached_launcher import record_exception
                record_exception(directory, 'Saving VM pass outcome', error)
            if not results:
                return outcome if return_outcome else outcome['status']
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
            return outcome if return_outcome else outcome['status']


def worker(argv):
    from detached_launcher import Stopped
    finished = []
    request = os.environ.get(FAMILY_WORK)
    try:
        status = _worker(argv, finished)
    except (Stopped, KeyboardInterrupt):
        status = 130
    except ValueError as error:
        if str(error) != 'Snap baseline readiness failed (status 130)':
            raise
        status = 130
    if status == 130 and not finished:
        # Startup may have been interrupted before its checkpoint existed.
        # Reuse original-VM recovery, without starting preparation or tests,
        # and publish proof only after that recovery and all owners close.
        if request is not None:
            os.environ[FAMILY_WORK] = request
        status = _worker(argv, finished, cleanup_only=True)
    # Both the guest controller and this child's enclosing leases have now
    # finished cleanup. A failed context exit publishes no attempt evidence.
    for checkpoint, evidence in finished:
        checkpoint.state['queue_evidence'] = evidence
        checkpoint.save()
    return status


def _worker(argv, finished, *, cleanup_only=False):
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
    from prepare_appsnapshot import snap_ready_reservation
    from launcher_control import watching
    control = Control()
    if cleanup_only:
        control.stopped = threading.Event()
    owner = (reservation(name, stopped=control.stopped) if cleanup_only else
             snap_ready_reservation(root, name, control))
    with watching(), control.installed(pipe=not cleanup_only), owner, \
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
            if cleanup_only:
                finished.append((checkpoint, dict(assignment, passed=[], failed=[], cleanup=True,
                                                   interrupted=True, diagnostic=False)))
                return 130
            if work['recovering']:
                finished.append((checkpoint, dict(assignment=assignment, cleanup=True)))
                return 0
            if assignment['source'] != source_identity(root):
                raise ValueError('assignment source inputs changed before execution')
        if cleanup_only:
            return 130
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
                cleanup=bool(getattr(checkpoint, 'queue_finalized', False)) and (
                    not control.stopped.is_set() or getattr(checkpoint, 'queue_vm_cleanup', False)
                    or not getattr(checkpoint, 'queue_vm_started', False)),
                failed=getattr(checkpoint, 'queue_failures', []),
                interrupted=getattr(checkpoint, 'queue_vm_interrupted', False) or (
                    control.stopped.is_set() and not getattr(checkpoint, 'queue_vm_started', False)),
                # The controller captures its inputs before execution. Later
                # checkout edits are informational, not a different attempt.
                # Retain the admitted source generation and exact assignment;
                # a managed source replacement still makes this diagnostic.
                diagnostic=assignment['source']['generation'] != source_identity(root)['generation'])
            finished.append((checkpoint, evidence))
        return status


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
