"""Finite configured VM queue; workers use the maintained guarded controllers."""

from concurrent.futures import ThreadPoolExecutor, as_completed
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


def dispatch(vms, concurrency, execute, stopped):
    """Refill free slots until every VM completes, including after failures."""
    def attempt(vm):
        if stopped.is_set():
            return 130
        try:
            return execute(vm)
        except (ValueError, OSError) as error:
            return {'status': 2, 'handoffs': [], 'error': str(error)}

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = {pool.submit(attempt, vm): vm.name for vm in vms}
        results = {}
        for future in as_completed(pending):
            results[pending[future]] = future.result()
    return results


def split(root, argv):
    from test_commands import execution_arguments, selections, AGGREGATES
    args, stop = execution_arguments(argv or ['all'])
    selected = selections(root, args)
    if len(selected) == 1 and selected[0][0] in AGGREGATES:
        selected = [('host', []), ('system', []), ('e2e', [])]
    host = [(kind, options) for kind, options in selected if kind not in ('system', 'e2e', 'integration')]
    guests = [(kind, options) for kind, options in selected if kind in ('system', 'e2e', 'integration')]
    def flatten(groups):
        result = [*(['--stop-on-error'] if stop else []),
                  *(value for kind, options in groups for value in (kind, *options))]
        if '--continue-on-errors' in args and all(kind in ('host', 'system', 'e2e') and not options
                                                for kind, options in groups):
            result.append('--continue-on-errors')
        return result
    return flatten(host) if host else [], flatten(guests)


def run(root, argv):
    from test_commands import _main
    snapshot = json.loads(os.environ[BATCH])
    configured = vm_config.registry()
    vms = tuple(configured[name] for name in snapshot['vms'])
    host_args, guest_args = split(root, argv)
    if host_args:
        status = _main(host_args, detached=True)
        if status:
            return status
    with Control().installed() as control:
        # Recovery is serial and finishes before any live VM attempt starts.
        for vm in vms:
            environment = test_launcher.environment(root)
            environment.pop(BATCH, None)
            environment[VARIABLE] = vm.name
            command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                       '--recover', vm.name]
            status = control.run(command, cwd=root, env=environment, cooperative=True)
            if status:
                return status
        with test_retention.Store(test_activity.retention_path(root)).session():
            # Fixed qualification bundles have shared immutable names. Build
            # missing inputs once, before concurrent consumers can observe a
            # partially prepared directory.
            from test_commands import selections, qualification_artifact_command
            for category, options in selections(root, guest_args):
                preparation = qualification_artifact_command(root, category, options)
                if preparation is not None:
                    status = control.run(preparation, cwd=root,
                                         env=test_launcher.environment(root), cooperative=True)
                    if status:
                        return status
            evidence = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-vm-queue-'))
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
                command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()),
                           '--execute', vm.name, *guest_args]
                pending = b''
                handoffs = []
                with (evidence / (vm.name + '.log')).open('xb') as log:
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
            categories = []
            failures = []
            for vm in vms:
                result = results[vm.name]
                vm_categories = []
                vm_failures = []
                if isinstance(result, dict):
                    for path in result['handoffs']:
                        handoff = json.loads(Path(path).read_text())
                        vm_categories.extend(handoff['categories'])
                        vm_failures.extend(dict(item, vm=vm.name)
                                           for item in handoff.get('failures', []))
                if (result['status'] if isinstance(result, dict) else result) != 0:
                    if not vm_categories:
                        vm_categories.extend(kind for kind, _ in selections(root, guest_args)
                                             if kind in ('system', 'e2e'))
                    for category in dict.fromkeys(vm_categories):
                        if not any(item['category'] == category for item in vm_failures):
                            vm_failures.append(dict(category=category, case='', vm=vm.name))
                categories.extend(vm_categories)
                failures.extend(vm_failures)
            (evidence / 'results.json').write_text(json.dumps(results, indent=2))
            failed = any((result['status'] if isinstance(result, dict) else result) != 0
                         for result in results.values())
            if hasattr(sys.stdout, 'frame'):
                sys.stdout.frame([])
            if failed and not control.stopped.is_set():
                prompt = f'Investigate the VM failures in {evidence / "results.json"} and adjacent VM logs. Preserve expected behavior and all unrelated work.'
                handoff = evidence / 'failure.json'
                handoff.write_text(json.dumps({'prompt': prompt, 'categories': list(dict.fromkeys(categories)),
                                              'failures': failures}))
                print(f'Failure handoff: {handoff}', flush=True)
            print(f'VM results: {evidence / "results.json"}', flush=True)
            return 130 if control.stopped.is_set() else 1 if failed else 0


def worker(argv):
    mode, name, *args = argv
    if mode not in ('--recover', '--execute'):
        raise ValueError('private VM queue entry only')
    vm_config.select(name)
    os.environ.pop(BATCH, None)
    root = Path(__file__).resolve().parents[1]
    from regression_process import PipeFrameOutput
    sys.stdout = PipeFrameOutput(sys.stdout)
    with test_activity.activity(root), Control().installed(pipe=True) as control:
        # Nested aggregate controllers observe the same parent cancellation.
        import regression_process
        regression_process.session_stop = control.stopped
        if mode == '--recover':
            from test_recovery import cleanup
            return cleanup(root)
        from test_commands import _main
        return _main([*args, '--vm', name], detached=True)


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
