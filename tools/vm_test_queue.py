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

import test_activity
import test_launcher
import test_retention
from regression_process import Control, FRAME_PREFIX
from vm_selection import BATCH, VARIABLE, vm_config
from vm_queue import dispatch


def split(root, argv):
    from test_commands import execution_arguments, selections, AGGREGATES
    args, stop = execution_arguments(argv or ['all'])
    selected = selections(root, args)
    if len(selected) == 1 and selected[0][0] in AGGREGATES:
        selected = [('host', []), ('system', []), ('e2e', [])]
    host = [(kind, options) for kind, options in selected if kind not in ('system', 'e2e', 'integration')]
    guests = [(kind, options) for kind, options in selected if kind in ('system', 'e2e', 'integration')]
    def flatten(groups):
        result = [*(['--resume'] if '--resume' in argv else []),
                  *(['--resume-case-only'] if '--resume-case-only' in argv else []),
                  *[arg for arg in argv if arg.startswith('--resume-case=')],
                  *(['--stop-on-error'] if stop else []),
                  *(value for kind, options in groups for value in (kind, *options))]
        if '--continue-on-errors' in args and all(kind in ('host', 'system', 'e2e') and not options
                                                for kind, options in groups):
            result.append('--continue-on-errors')
        return result
    return flatten(host) if host else [], flatten(guests)


def run(root, argv):
    from test_commands import _main, selections
    from test_checkpoint import Checkpoint
    snapshot = json.loads(os.environ[BATCH])
    configured = vm_config.registry()
    vms = tuple(configured[name] for name in snapshot['vms'])
    host_args, guest_args = split(root, argv)
    # Reset the entire requested queue before any category can fail or stop.
    # Queued VMs must not inherit older passes merely because they never start.
    guest_selection = selections(root, guest_args)
    for vm in vms:
        Checkpoint(root, guest_selection, resume='--resume' in argv, binding=vm.name)
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
            frames = {}

            def publish_frames():
                if hasattr(sys.stdout, 'frame'):
                    sys.stdout.frame([f'VM queue | concurrency {snapshot["concurrency"]}',
                                      *(line for name in snapshot['vms']
                                        for line in ([f'VM: {name}', *frames.get(name, ['Queued'])]))])

            def execute(vm):
                environment = test_launcher.environment(root)
                environment.pop(BATCH, None)
                # A worker starts its own retention session, never another VM's.
                environment.pop(test_retention.VARIABLE, None)
                environment[VARIABLE] = vm.name
                environment.pop('ONPC_RUNNER_INVOCATION', None)
                command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                           '--execute', vm.name, *guest_args]
                pending = b''
                handoffs = []
                with (directory / (vm.name + '.log')).open('xb') as log:
                    os.fchmod(log.fileno(), 0o600)
                    def output(data):
                        nonlocal pending
                        log.write(data)
                        log.flush()
                        pending += data
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            value = line.decode('utf-8', errors='replace')
                            if value.startswith('Failure handoff: '):
                                handoffs.append(value.removeprefix('Failure handoff: '))
                            with output_lock:
                                if value.startswith(FRAME_PREFIX):
                                    frames[vm.name] = json.loads(value[len(FRAME_PREFIX):])
                                    publish_frames()
                                else:
                                    print(f'[{vm.name}] {value}', flush=True)
                    status = control.run(command, cwd=root, env=environment,
                                         output=output, cooperative=True)
                    if pending:
                        with output_lock:
                            print(f'[{vm.name}] ' + pending.decode('utf-8', errors='replace'), flush=True)
                return {'status': status, 'handoffs': handoffs}

            results = dispatch(vms, snapshot['concurrency'], execute, control.stopped)
            # Keep the actual joined results even if failure-detail processing
            # below cannot read a diagnostic handoff.
            (directory / 'results.json').write_text(json.dumps(results, indent=2))
            (directory / 'results.json').chmod(0o600)
            print(f'VM results: {directory / "results.json"}', flush=True)
            categories = []
            failures = []
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
                                              'failures': failures}))
                handoff.chmod(0o600)
                print(f'Failure handoff: {handoff}', flush=True)
            # Each directly spawned worker returns only after its guarded
            # execution and cleanup. Its exit status owns the result; report
            # archives and diagnostic file lifetimes do not qualify it again.
            return 130 if control.stopped.is_set() else 1 if failed else 0


def worker(argv):
    mode, name, *args = argv
    if mode != '--execute':
        raise ValueError('private VM queue entry only')
    vm_config.select(name)
    os.environ.pop(BATCH, None)
    root = Path(__file__).resolve().parents[1]
    from regression_process import PipeFrameOutput
    sys.stdout = PipeFrameOutput(sys.stdout)
    # The batch's checkout-local gate is not a VM reservation or cleanup proof.
    os.environ.pop(test_activity.VARIABLE, None)
    from vm_pool import reservation
    with Control().installed(pipe=True) as control, reservation(name, stopped=control.stopped), \
            test_activity.activity(root, named_vm=True):
        # Nested aggregate controllers observe the same parent cancellation.
        import regression_process
        regression_process.session_stop = control.stopped
        from test_recovery import cleanup
        if control.stopped.is_set():
            return 130
        status = cleanup(root)
        if status:
            return status
        from test_commands import _main
        from test_checkpoint import Checkpoint
        from test_commands import selections
        checkpoint = Checkpoint(root, selections(root, args), resume='--resume' in args)
        replay = [arg.partition('=')[2] for arg in args if arg.startswith('--resume-case=')]
        if replay:
            groups = selections(root, args)
            if len(groups) != 1:
                raise ValueError('case retry requires one category')
            if '--resume-case-only' in args:
                checkpoint.retry(groups[0][0], replay[0])
            else:
                checkpoint.event(groups[0][0], dict(kind='failure', nodeid=replay[0]), set())
        return _main([*args, '--vm', name], detached=True, checkpoint=checkpoint)


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
