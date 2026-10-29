"""Finite configured VM queue; workers use the maintained guarded controllers."""

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid

# Workers use isolated Python; restore only this checkout's sibling modules.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_activity
import test_launcher
import test_retention
from regression_process import Control, FRAME_PREFIX
from vm_selection import BATCH, VARIABLE, WORKER, vm_config
from vm_queue import dispatch
import launcher_reload
from vm_case_queue import (case_inventory, work_items, work_key, claim, arguments,
                           family_binding, available_worker)

FAMILY_WORK = 'ONPC_TEST_FAMILY_WORK'
CHECKPOINT_READY = 'Family checkpoint ready: '


def split(root, argv):
    from test_commands import execution_arguments, selections, AGGREGATES, PHASES
    args, stop = execution_arguments(argv or ['all'])
    selected = selections(root, args)
    if len(selected) == 1 and selected[0][0] in AGGREGATES:
        selected = [(kind, []) for kind in PHASES]
    host = [(kind, options) for kind, options in selected if kind not in ('system', 'e2e', 'integration')]
    guests = [(kind, options) for kind, options in selected if kind in ('system', 'e2e', 'integration')]
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


def run(root, argv, *, reloading=False):
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
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
            names = {worker.name for worker in vms if worker.family == vm.family}
            checkpoint = Checkpoint(root, guest_selection, resume='--resume' in argv,
                                    binding=family_binding(vm.family, names), namespace='run-tests-family')
            items = [work for category, options in guest_selection
                     for work in work_items(category, options, case_inventory(
                         root, category, options, vm=vm.name))]
            all_items = items
            replay = [arg.partition('=')[2] for arg in guest_args if arg.startswith('--resume-case=')]
            if replay:
                category = guest_selection[0][0]
                checkpoint.event(category, dict(kind='failure', nodeid=replay[0]), set())
                if '--resume-case-only' in guest_args or '--resume-area-only' in guest_args:
                    area = '--resume-area-only' in guest_args
                    checkpoint.retry(category, replay[0], area=area)
                    items = [dict(work, case=replay[0], area=area,
                                  credit=work['cases'],
                                  cases=work['cases'] if area else [replay[0]])
                             for work in items if replay[0] in work['cases']]
                    if not items:
                        raise ValueError('case retry is outside the selected VM inventory')
            claims = checkpoint.state.get('queue_claims', {})
            retained = checkpoint.state.get('queue_items', {})
            if (not isinstance(claims, dict) or not isinstance(retained, dict)
                    or any(not isinstance(key, str) or not isinstance(owner, str)
                           or key not in retained or not isinstance(retained[key], dict)
                           or work_key(retained[key]) != key for key, owner in claims.items())):
                raise ValueError('invalid retained family case claims')
            if any(owner not in names for owner in claims.values()):
                raise ValueError('family case recovery requires its original VM owner in the selection')
            scoped = '--resume-case-only' in guest_args or '--resume-area-only' in guest_args
            retained_items = [retained[key] for key in claims
                              if retained[key]['category'] in checkpoint.selected
                              and (not scoped or replay[0] in retained[key]['cases'])]
            views = {work_key(item): next(work for work in items
                                         if replay[0] in work['cases'])
                     for item in retained_items} if scoped else {}
            items = list({work_key(item): item for item in (
                *retained_items, *items)}.values())
            families[vm.family] = dict(checkpoint=checkpoint, items=items, all_items=all_items,
                                      claims=dict(claims), views=views, scoped=scoped)
    finally:
        if original_vm is None:
            os.environ.pop(VARIABLE, None)
        else:
            vm_config.select(original_vm)
    if host_args:
        status = _main(host_args, detached=True, checkpoint=Checkpoint(
            root, selections(root, host_args), resume='--resume' in host_args))
        if status:
            return status
    with Control().installed() as control:
        store = test_retention.Store(test_activity.retention_path(root))
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

            def execute_worker(vm, work, inherited, receipt):
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
                attempt = uuid.uuid4().hex
                request.write_text(json.dumps(dict(selection=guest_args, passed=inherited, attempt=attempt)))
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
                return {'status': status, 'handoffs': handoffs, 'attempt': attempt, 'ready': ready}

            def execute_case(vm, work, inherited, receipt):
                with output_lock:
                    frames[vm.name] = ['Starting worker']
                    publish_frames()
                try:
                    result = execute_worker(vm, work, inherited, receipt)
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

            queue_lock = threading.Lock()
            slots = threading.Semaphore(snapshot['concurrency'])

            def completed(family):
                checkpoint = family['checkpoint']
                items = [*family['all_items'], *family['items']]
                saved = set(checkpoint.state.get('queue_completed', []))
                return {work_key(work) for work in items if work_key(work) in saved
                        and set(work['cases']) <= checkpoint.passed(work['category'])}

            def execute_claims(vm, receipt):
                family = families[vm.family]
                handoffs = []
                while not control.stopped.is_set() and not launcher_reload.pending():
                    with queue_lock:
                        unit = next((item for item in family['items']
                                     if family['claims'].get(work_key(item)) == vm.name), None)
                        unit = unit or claim(family['items'], completed(family), family['claims'], vm.name)
                        if unit is None:
                            return dict(status=0, handoffs=handoffs)
                        key = work_key(unit)
                        work = family['views'].get(key, unit)
                        checkpoint = family['checkpoint']
                        inherited = {category: sorted(checkpoint.passed(category))
                                     for category in checkpoint.selected}
                        checkpoint.state['queue_claims'] = dict(family['claims'])
                        checkpoint.state.setdefault('queue_items', {})[key] = unit
                        checkpoint.save()
                    result = execute_case(vm, work, inherited, receipt)
                    handoffs.extend(result['handoffs'])
                    # The child has returned after its reservation and owned
                    # cleanup. No other worker can write this VM checkpoint.
                    with queue_lock:
                        saved = (Checkpoint(root, guest_selection, resume=True, binding=vm.name)
                                 if result.get('ready') else None)
                        current = saved is not None and saved.state.get('queue_attempt') == result.get('attempt')
                        credited = set(work.get('credit', work['cases']))
                        for case in (credited & saved.passed(work['category']) if current else set()):
                            checkpoint.event(work['category'], dict(kind='finished', nodeid=case), set())
                        if not result['status']:
                            if not current or work['cases'] and not set(work['cases']) <= checkpoint.passed(work['category']):
                                raise ValueError('case runner returned success without teardown-complete case evidence')
                            checkpoint.state['queue_completed'] = sorted(
                                set(checkpoint.state.get('queue_completed', [])) | {work_key(work)} | {
                                    work_key(item) for item in family['all_items']
                                    if item['category'] == work['category']
                                    and set(item['cases']) & credited
                                    and set(item['cases']) <= checkpoint.passed(item['category'])})
                            # Release only successful claims. Failed histories
                            # remain owned for the remainder of this run.
                            if set(unit['cases']) <= checkpoint.passed(unit['category']):
                                del family['claims'][key]
                        elif work['case'] is not None:
                            # A final report, recording or cleanup audit can
                            # fail after case events were saved. Its terminal
                            # target must run again before the unit gets credit.
                            checkpoint.event(work['category'],
                                dict(kind='failure', nodeid=work['case']), set())
                        checkpoint.state['queue_claims'] = dict(family['claims'])
                        checkpoint.save()
                    if result['status']:
                        if '--stop-on-error' in guest_args and result['status'] != launcher_reload.STATUS:
                            control.stop()
                        return dict(status=result['status'], handoffs=handoffs)
                    if family['scoped']:
                        return dict(status=0, handoffs=handoffs)
                return dict(status=130 if control.stopped.is_set() else launcher_reload.STATUS,
                            handoffs=handoffs)

            def execute(vm):
                family = families[vm.family]
                def needed():
                    with queue_lock:
                        done = completed(family)
                        return (any(family['claims'].get(work_key(item)) == vm.name for item in family['items']) or any(
                            work_key(item) not in done and work_key(item) not in family['claims']
                            for item in family['items']))
                from detached_launcher import Stopped
                try:
                    with available_worker(vm, slots, control.stopped, needed=needed) as receipt:
                        return (dict(status=0, handoffs=[]) if receipt is None else
                                execute_claims(vm, receipt))
                except Stopped:
                    return dict(status=130, handoffs=[])
                except launcher_reload.ReloadRequested:
                    return dict(status=launcher_reload.STATUS, handoffs=[])

            publish_frames()
            results = dispatch(vms, len(vms), execute, control.stopped)
            for family in families.values():
                checkpoint = family['checkpoint']
                done = completed(family)
                for category in checkpoint.selected:
                    selected = [work for work in family['all_items'] if work['category'] == category]
                    if selected and all(work_key(work) in done for work in selected):
                        checkpoint.entry(category)['complete'] = True
                checkpoint.save()
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
                                             if kind in ('system', 'integration', 'e2e'))
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
            return 130 if control.stopped.is_set() else 1 if failed else 0


def worker(argv):
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
    from vm_pool import reservation
    sys.stdout.frame(['Queued (waiting for VM checkout)'])
    with launcher_reload.watching(), Control().installed(pipe=True) as control, reservation(name, stopped=control.stopped), \
            test_activity.activity(root, named_vm=True):
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
            checkpoint.state['queue_attempt'] = work['attempt']
            checkpoint.save()
            print(CHECKPOINT_READY + work['attempt'], flush=True)
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
            return _main([*args, '--vm', name], detached=True, checkpoint=checkpoint)
        except launcher_reload.ReloadRequested:
            return launcher_reload.STATUS


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
