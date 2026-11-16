"""Run-tests group routing and case passes; vm_queue owns VM workers and leases."""

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from contextlib import nullcontext

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
from test_results import PENDING_STATUS
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
    """Describe a transferred source snapshot for diagnostics only."""
    origin = vm_config.remote_origin()
    if origin is not None and 'source_identity' in origin:
        return dict(origin['source_identity'])
    from regression_inputs import identity
    return dict(digest=identity(root))


def execute_pass(root, plan, control, execute, *, host=None,
                 checkpoint_scope='ordinary', continue_on_errors=False, sources=None, failed_work=None,
                 progress=None):
    """Run current pending work, stop on failure and join all normal bookings."""
    from test_checkpoint import PassCheckpoint
    from test_results import ResultStore
    from test_commands import selections
    snapshot, vms, host_args, guest_args, guest_selection, families = plan
    lock = threading.RLock()
    admission = FamilyAdmission(vms)
    result_store = ResultStore()
    failed = threading.Event()
    changed = threading.Event()
    inflight, results = {}, {}
    host_completed = []
    replay = next((arg.partition('=')[2] for arg in guest_args if arg.startswith('--resume-case=')), None)
    focused = '--resume-case-only' in guest_args or '--resume-area-only' in guest_args
    focus_finished = set()
    failed_work = set() if failed_work is None else failed_work
    deferred_work = set()
    selection = [['_host', host_args], ['_guest', guest_args]]
    with PassCheckpoint(root, selection, {vm.name: vm.family for vm in vms}, families,
                        resume='--resume' in (*host_args, *guest_args),
                        scope=checkpoint_scope) as checkpoint:
        if replay:
            for family in families:
                checkpoint.retry(family, replay, area='--resume-area-only' in guest_args)

        def publish_counts():
            if progress is None:
                return
            selected = {(family, work['category'], case)
                        for family, items in families.items() for work in items
                        if not focused or replay in work['cases']
                        for case in work['cases']
                        if not focused or '--resume-area-only' in guest_args or case == replay}
            passed = {key for key in selected if key[2] in checkpoint.passed(key[0], key[1])}
            failures = {(record['family'], record['category'], record['case'])
                        for record in result_store.failures()} & selected
            progress(len(passed - failures), len(failures), len(selected))

        publish_counts()

        if host_args:
            value = host() if host is not None else dict(status=2, cleanup=False)
            results['host'] = value
            host_completed = value.get('completed_categories', [])
            if value['status']:
                if value['status'] not in (130, launcher_reload.STATUS) and not continue_on_errors:
                    failed.set()
                for work in value.get('failure_works', []):
                    if not any(record['category'] == work['category'] and record['family'] == 'host'
                               for record in result_store.failures()):
                        result_store.record(work['category'], 'host', work['case'] or '', value['status'],
                                            vm='', options=work['options'],
                                            output_tail=value.get('output_tail', ''),
                                            handoffs=value.get('handoffs', []))
                if not value.get('failure_works') and value['status'] not in (130, launcher_reload.STATUS):
                    category, options = selections(root, host_args)[0]
                    result_store.record(category, 'host', '', value['status'], options=options,
                                        output_tail=value.get('output_tail', ''), handoffs=value.get('handoffs', []))

        def pending(family):
            from vm_case_queue import work_key
            return [work for work in checkpoint.pending(family)
                    if (family, work_key(work)) not in failed_work | deferred_work
                    and (not focused or family not in focus_finished and replay in work['cases'])]

        def needed(vm):
            with lock:
                return (not failed.is_set() and not changed.is_set()
                        and not control.stopped.is_set() and bool(pending(vm.family)))

        def attempt(worker):
            vm = worker.vm
            with lock:
                if sources is not None and sources.source != source_identity(root):
                    changed.set()
                available = pending(vm.family)
                if not available or failed.is_set() or changed.is_set() or control.stopped.is_set():
                    return dict(status=0, handoffs=[])
                work = available[0]
                execution = None
                if focused:
                    area = '--resume-area-only' in guest_args
                    execution = dict(work, case=replay, area=area,
                                     cases=work['cases'] if area else [replay])
                assignment = checkpoint.claim(vm.family, vm.name, work, execution=execution)
                if assignment is None:
                    return dict(status=0, handoffs=[])
                inherited = {kind: sorted(checkpoint.passed(vm.family, kind)) for kind, _ in guest_selection}
                inflight[vm.name] = assignment
            return execute(worker, assignment, inherited)

        def completed(vm, value):
            with lock:
                assignment = inflight.pop(vm.name, None)
                if assignment is None:
                    if value['status'] not in (0, 130, launcher_reload.STATUS):
                        failed.set()
                    return value
                work = assignment['execution']
                evidence = value.get('evidence')
                accepted = checkpoint.accept(assignment, evidence, value['status'])
                observed = evidence if accepted is not None else {}
                for case in set(observed.get('passed', [])) & set(work['cases']):
                    result_store.record(work['category'], vm.family, case, 0, vm=vm.name,
                                        options=work['options'])
                actual_failures = set(observed.get('failed', [])) & set(work['cases'])
                for case in actual_failures:
                    result_store.record(work['category'], vm.family, case, 1, vm=vm.name,
                        options=work['options'], output_tail=value.get('output_tail', ''),
                        handoffs=value.get('handoffs', []))
                interrupted = value.get('interrupted') or value['status'] in (130, launcher_reload.STATUS)
                complete = accepted is not None and (set(work['cases']) <= checkpoint.passed(vm.family, work['category'])
                            if work['cases'] else accepted is True)
                if complete and not work['cases']:
                    result_store.record(work['category'], vm.family, '', 0, vm=vm.name,
                                        options=work['options'], complete=True)
                if complete and not value['status']:
                    result_store.finish_command(work['category'], work['options'], family=vm.family, work=work)
                if not value['status'] and not complete:
                    from vm_case_queue import work_key
                    deferred_work.add((vm.family, work_key(assignment['work'])))
                    value = dict(value, pending=True)
                    interrupted = True
                if actual_failures or value['status'] and not interrupted:
                    from vm_case_queue import work_key
                    failed_work.add((vm.family, work_key(assignment['work'])))
                    if not continue_on_errors or not actual_failures or not observed.get('cleanup'):
                        failed.set()
                    if not actual_failures:
                        result_store.record(work['category'], vm.family, '', value['status'],
                            vm=vm.name, options=work['options'], work=work,
                            output_tail=value.get('output_tail', ''), handoffs=value.get('handoffs', []))
                if focused:
                    focus_finished.add(vm.family)
                if sources is not None and sources.source != source_identity(root):
                    changed.set()
                publish_counts()
                return value

        for family, items in families.items():
            targets = tuple(vm.name for vm in vms if vm.family == family)
            if not failed.is_set() and any(result_store.select_failure(
                    work['category'], family, work['cases'], work['options'], vms=targets)
                    for work in items):
                failed.set()
        if vms and not failed.is_set() and not control.stopped.is_set():
            with Executor(root, vms, snapshot['concurrency'], control.stopped, sources=sources) as executor:
                results.update(executor.run_ready(attempt, choose=admission.choose, needed=needed,
                    completed=completed, **({'stop_on_error': False} if continue_on_errors else {})))
        unfinished = bool(deferred_work) or any(pending(family) for family in families)
        statuses = [value['status'] for value in results.values()]
        failures = result_store.failures()
        status = (1 if failed.is_set() or failed_work or any(
                      status not in (0, 130, launcher_reload.STATUS, PENDING_STATUS) for status in statuses) else
                  130 if control.stopped.is_set() else
                  launcher_reload.STATUS if launcher_reload.STATUS in statuses else
                  130 if 130 in statuses else
                  0 if changed.is_set() else PENDING_STATUS if unfinished else 0)
        return dict(status=status, results=results, failures=failures,
                    cleanup_complete=all(value.get('cleanup', True) for value in results.values()),
                    completed_categories=host_completed, source_changed=changed.is_set(), pending=unfinished,
                    stopped=control.stopped.is_set() and not failed.is_set(),
                    run=checkpoint.state['run'], **{'pass': checkpoint.state['pass']})


def execution_groups(root, argv, vms):
    """Resolve test routing before shared capacity admission sees candidates."""
    from test_commands import CATEGORIES, selections
    host_args, guest_args = split(root, argv)
    groups = []
    by_key = {}
    if host_args:
        groups.append(dict(key='host', category='host', args=host_args, vm_tags=None, vms=[]))
    controls = [arg for arg in guest_args if arg in ('--stop-on-error',)
                or arg.startswith('--resume-case=')
                or arg in ('--resume-case-only', '--resume-area-only')]
    for category, options in selections(root, guest_args) if guest_args else []:
        spec = CATEGORIES[category]
        children = [(None, spec.vm_tags or 'general', list(options))]
        if spec.subcategories:
            if category != 'e2e':
                raise ValueError('subcategory inventory requires a category case binding')
            import runpy
            runner = runpy.run_path(str(root / 'tests/e2e/runner.py'))
            selected = runner['preflight'](list(options), root=root, allow_missing_artifacts=True)
            if 'cases' in selected or 'subcategory' in selected:
                membership = ({case['subcategory'] for case in selected['cases']}
                              if 'cases' in selected else {selected['subcategory']})
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
                children = [(child.name, child.vm_tags or spec.vm_tags or 'general',
                             [*base, '--subcategory', child.name])
                            for child in spec.subcategories if child.name in membership]
        for name, tag, args in children:
            candidates = [vm for vm in vms if tag in vm.vm_tags]
            missing = {vm.family for vm in vms} - {vm.family for vm in candidates}
            key = category + ('.' + name if name else '')
            if missing:
                raise ValueError(f'{key}: no selected VM with vm_tags={tag} for families: '
                                 + ', '.join(sorted(missing)))
            if not candidates:
                raise ValueError(f'{key}: no selected VM with vm_tags={tag}')
            if key in by_key:
                by_key[key]['args'].extend((category, *args))
            else:
                group = dict(key=key, category=category, args=[*controls, category, *args],
                             vm_tags=tag, vms=[vm.name for vm in candidates])
                groups.append(group)
                by_key[key] = group
    return groups


def run(root, argv, *, reloading=False, return_outcome=False):
    """Run current ordered groups with ordinary capacity and VM ownership."""
    import host_compute
    from test_commands import selections
    from test_results import ResultStore
    with test_source.startup(root, argv):
        snapshot = json.loads(os.environ[BATCH]) if BATCH in os.environ else dict(vms=[])
        configured = vm_config.registry() if snapshot['vms'] else {}
        vms = [configured[name] for name in snapshot['vms']]
        groups = execution_groups(root, argv, vms)
        selection = selections(root, argv)
    original = {key: os.environ.get(key) for key in (BATCH, VARIABLE)}
    continue_on_errors = '--continue-on-errors' in argv
    outcomes = []
    last = dict(status=0, results={}, failures=[], cleanup_complete=True)
    try:
        for group in groups:
            from launcher_control import CancellationEvent
            if CancellationEvent().is_set():
                last = dict(status=130, stopped=True, cleanup_complete=True)
                break
            launcher_reload.check()
            candidates = [configured[name] for name in group['vms']]
            allocation = host_compute.launch(candidates, handoff=False) if candidates else nullcontext([])
            with allocation as admitted:
                if admitted:
                    host_compute.bind(admitted)
                else:
                    os.environ.pop(BATCH, None)
                    os.environ.pop(VARIABLE, None)
                owner = launcher_reload.current.run if launcher_reload.current is not None else None
                if admitted and owner is not None:
                    host_compute.save_admitted(owner, admitted)
                if hasattr(sys.stdout, 'controller'):
                    sys.stdout.controller('test-group', [f'Test group: {group["key"]}'])
                from vm_recording import recording
                with recording(root, enabled=bool(admitted), run=owner) as media:
                    args = list(group['args'])
                    if '--resume' in argv and '--resume' not in args:
                        args.insert(0, '--resume')
                    last = _run_group(root, args, reloading=reloading, return_outcome=True,
                                      checkpoint_scope='ordinary/' + group['key'],
                                      continue_on_errors=continue_on_errors)
                if media is not None and owner is not None:
                    media.write_index(owner, last['status'])
                if admitted and owner is not None and last.get('cleanup_complete'):
                    from detached_launcher import atomic
                    atomic(owner / 'admitted-vms.json', [])
            outcomes.append(dict(group=group['key'], category=group['category'], outcome=last))
            if last['status'] and (not continue_on_errors or last['status'] != 1):
                break
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    last = dict(last)
    completed = []
    retry = any(arg.startswith('--resume-case=') for arg in argv)
    for item in outcomes:
        if item['category'] == 'host':
            completed.extend(item['outcome'].get('completed_categories', []))
        elif not retry and not item['outcome']['status'] and all(
                any(done['group'] == group['key'] and not done['outcome']['status'] for done in outcomes)
                for group in groups if group['category'] == item['category']):
            completed.append(item['category'])
    last['completed_categories'] = list(dict.fromkeys(completed))
    results = ResultStore()
    for category, options in selection:
        if category in completed:
            results.finish_command(category, options)
    if not last['status'] and any(item['outcome']['status'] for item in outcomes):
        last['status'] = 1
    last['groups'] = outcomes
    last['failures'] = results.failures()
    return last if return_outcome else last['status']


def _run_group(root, argv, *, reloading=False, return_outcome=False,
               checkpoint_scope='ordinary', continue_on_errors=False):
    from contextlib import ExitStack
    from remote_sources import FrozenSources
    failed_work = set()
    while True:
        with ExitStack() as inputs:
            with test_source.startup(root, argv):
                plan = _plan(root, argv)
            sources = inputs.enter_context(FrozenSources(root)) if plan[1] else None
            outcome = _execute_group(root, plan, reloading=reloading, return_outcome=True,
                checkpoint_scope=checkpoint_scope, sources=sources,
                continue_on_errors=continue_on_errors, failed_work=failed_work)
        if not (outcome.get('source_changed')
                and (not outcome['status'] or continue_on_errors and outcome['status'] == 1)):
            return outcome if return_outcome else outcome['status']
        argv = ['--resume', *[argument for argument in argv if argument != '--resume']]


def _execute_group(root, plan, *, reloading=False, return_outcome=False,
        checkpoint_scope='ordinary', continue_on_errors=False, sources=None, failed_work=None):
    snapshot, vms, host_args, guest_args, guest_selection, families = plan
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
    def execute_host():
        with test_activity.activity(root, host_only=True), test_source.reader(root):
            groups = selections(root, host_args)
            saved = Checkpoint(root, groups, resume='--resume' in host_args)
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
                status = _main(host_args, detached=True, checkpoint=saved)
            finally:
                sys.stdout = stream
            result = dict(status=status, handoffs=handoffs, output_tail=output_tail,
                          cleanup=bool(getattr(saved, 'queue_finalized', False)),
                          completed_categories=[kind for kind, _ in groups if saved.complete(kind)])
            if status:
                failures = []
                for path in handoffs:
                    try:
                        failures.extend(json.loads(Path(path).read_text()).get('failures', []))
                    except (OSError, ValueError):
                        continue
                works = []
                for failure in failures or [{}]:
                    kind, selected = next((group for group in groups if group[0] == failure.get('category')), groups[0])
                    case = failure.get('case') or None
                    work = dict(category=kind, options=selected, case=case, cases=[case] if case else [], area=False)
                    if work not in works:
                        works.append(work)
                result['failure_works'] = works
            return result
    with Control().installed() as control:
        store = test_retention.Store(test_activity.retention_path(root))
        # The inherited owner lease excludes live workers; every VM still
        # separately recovers its own journal and guest state.
        with store.execution_session():
            directory = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-vm-queue-'))
            # Named inputs are VM-bound. Each worker prepares them inside its
            # own retention session, before its independent guest execution.
            # A batch-owned allocation would conflict with that VM's old claim
            # after an interrupted input was removed and recreated.
            output_lock = threading.Lock()
            frames = {name: ['Queued'] for name in snapshot['vms']}
            case_summary = []

            def publish_frames():
                if hasattr(sys.stdout, 'frame'):
                    lines = [f'VM queue | concurrency {snapshot["concurrency"]}']
                    lines.extend(case_summary)
                    for index, name in enumerate(snapshot['vms']):
                        if index:
                            lines.append('')
                        lines.extend([f'VM: {name}', *frames[name]])
                    sys.stdout.frame(lines)

            def progress(passed, failed, total):
                with output_lock:
                    case_summary[:] = [f'Overall - {int(100 * (passed + failed) / max(total, 1))}% '
                                       f'({passed}/{failed}/{total})']
                    publish_frames()

            def execute_worker(worker, assignment, inherited):
                vm, receipt = worker.vm, worker.receipt
                from vm_pool import remote
                route = remote()
                detached = sources is not None
                if detached:
                    from remote_sources import RemoteVM
                    route = RemoteVM(root, vm, sources=sources)
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
                                                  assignment=assignment)))
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
                            if value.startswith('Runner case failed: '):
                                try:
                                    failure = json.loads(value.removeprefix('Runner case failed: '))
                                    if (failure.get('category') == work['category']
                                            and failure.get('case') in work['cases']):
                                        from test_results import ResultStore
                                        ResultStore().record(work['category'], vm.family, failure['case'], 1,
                                            vm=vm.name, options=work['options'])
                                        if not continue_on_errors:
                                            control.stop()
                                except (TypeError, ValueError):
                                    pass
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
                    if refused_start:
                        status = 130
                    elif detached:
                        status = route.run(attempt_control, command, cwd=root, env=environment,
                            output=output, cooperative=True, tick=interrupt, started=started)
                    else:
                        status = attempt_control.run(command, cwd=root, env=environment, output=output,
                            cooperative=True, tick=interrupt, started=started)
                    if pending:
                        with output_lock:
                            print(f'[{vm.name}] ' + pending.decode('utf-8', errors='replace'), flush=True)
                evidence = None
                if route is not None:
                    evidence = route.result.get('evidence')
                    handoffs = []
                    for index, received in enumerate(route.result.get('handoffs', [])):
                        handoff = dict(received['failure'])
                        path = directory / (vm.name + '-remote-' + attempt + '-' + str(index) + '.json')
                        context = received.get('context')
                        if received.get('context_error'):
                            handoff['evidence_error'] = dict(host=received['host'],
                                                            error=received['context_error'])
                        prefix = ('This failure ran on VM host ' + received['host'] +
                                  '; original artifact paths below belong to that host. ')
                        if context is not None:
                            context_path = path.with_name(path.stem + '-context.json')
                            context_path.write_text(json.dumps(context))
                            context_path.chmod(0o600)
                            handoff['evidence_context'] = dict(file=context_path.name,
                                host=received['host'], vm=vm.name, attempt=attempt,
                                )
                            prefix += 'Read the retained bounded failure context at ' + str(context_path) + '. '
                        handoff['prompt'] = prefix + '\n' + handoff['prompt']
                        path.write_text(json.dumps(handoff))
                        path.chmod(0o600)
                        handoffs.append(str(path))
                elif ready:
                    evidence = Checkpoint.worker_result(root, vm.name)
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

            def execute_case(worker, assignment, inherited):
                vm = worker.vm
                with output_lock:
                    frames[vm.name] = ['Starting worker']
                    publish_frames()
                try:
                    result = execute_worker(worker, assignment, inherited)
                except (ValueError, OSError) as error:
                    if isinstance(error, test_source.SourceBusy):
                        raise
                    from detached_launcher import record_exception
                    reporter = lambda context, error, **identity: record_exception(directory, context, error, **identity)
                    details = reporter('VM case execution', error,
                        vm=vm.name, case=assignment.get('execution', assignment['work'])['case'],
                        attempt=assignment['attempt'])
                    with output_lock:
                        frames[vm.name] = ['Failed (worker error)']
                        publish_frames()
                    # A failed operation reaches repair with its original error;
                    # it does not become an exception in the coordinator.
                    result = dict(status=2, handoffs=[], evidence=None, **details,
                                  output_tail=details.get('traceback', str(error))[-16000:])
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
                                       checkpoint_scope=checkpoint_scope,
                                       continue_on_errors=continue_on_errors, sources=sources, failed_work=failed_work,
                                       progress=progress)
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
        if cleanup_only:
            return 130
        replay = [arg.partition('=')[2] for arg in args if arg.startswith('--resume-case=')]
        if replay:
            groups = selections(root, args)
            if len(groups) != 1:
                raise ValueError('case retry requires one category')
            checkpoint.retry(groups[0][0], replay[0], area='--resume-area-only' in args)
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
            observed = checkpoint.executed_passes.get(category, set()) & set(executed['cases'])
            evidence = dict(assignment, passed=sorted(observed),
                cleanup=bool(getattr(checkpoint, 'queue_finalized', False)) and (
                    not control.stopped.is_set() or getattr(checkpoint, 'queue_vm_cleanup', False)
                    or not getattr(checkpoint, 'queue_vm_started', False)),
                failed=getattr(checkpoint, 'queue_failures', []),
                interrupted=getattr(checkpoint, 'queue_vm_interrupted', False) or (
                    control.stopped.is_set() and not getattr(checkpoint, 'queue_vm_started', False)),
                diagnostic=False)
            finished.append((checkpoint, evidence))
        return status


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
