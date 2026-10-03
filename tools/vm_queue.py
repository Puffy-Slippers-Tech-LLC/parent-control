"""Shared rolling VM scheduler and isolated preparation workers."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import sys
import threading

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def dispatch(vms, concurrency, execute, stopped):
    """Refill slots as soon as any worker finishes, also after failures."""
    def attempt(vm):
        if stopped.is_set():
            return 130
        try:
            return execute(vm)
        except (ValueError, OSError) as error:
            return {'status': 2, 'handoffs': [], 'error': str(error)}

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = {pool.submit(attempt, vm): vm.name for vm in vms}
        return {pending[future]: future.result() for future in as_completed(pending)}


def preparation(root, tool, args, concurrency, vms):
    """Run already-confirmed preparation in processes with independent VM state.

    Baseline replacement has no cooperative stop protocol: allow in-flight
    replacements to finish while cancellation prevents queued work. App workers
    use their existing signal handler and wait for owned cleanup.
    """
    from regression_process import Control
    from vm_selection import BATCH, VARIABLE
    output_lock = threading.Lock()
    with Control().installed() as control:
        def execute(vm):
            options = ['--vm', vm.name, '--y', '--mode', args.mode]
            if tool == 'prepare-appsnapshot':
                options += ['--overwrite', args.overwrite]
            command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), tool, *options]
            environment = dict(os.environ)
            environment.pop(BATCH, None)
            environment[VARIABLE] = vm.name
            runner = control
            if tool == 'prepare-baseline':
                # Do not interrupt a privileged replacement through an
                # unprivileged intermediary that cannot signal its root child.
                runner = Control()
                runner.stopped = threading.Event()
            pending = b''
            def output(data):
                nonlocal pending
                pending += data
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    with output_lock:
                        print(f'[{vm.name}] ' + line.decode('utf-8', errors='replace'), flush=True)
            status = runner.run(command, cwd=root, env=environment, output=output)
            if pending:
                output(b'\n')
            return status

        results = dispatch(vms, concurrency, execute, control.stopped)
        statuses = {name: result['status'] if isinstance(result, dict) else result
                    for name, result in results.items()}
        for name, status in statuses.items():
            print(f'{tool}: {name}: status {status}', flush=True)
            if isinstance(results[name], dict) and results[name].get('error'):
                print(f'{tool}: {name}: {results[name]["error"]}', file=sys.stderr, flush=True)
        status = 130 if control.stopped.is_set() else next((value for value in statuses.values() if value), 0)
        return statuses, status


def worker(argv):
    import runpy
    tool, *options = argv
    if tool not in ('prepare-baseline', 'prepare-appsnapshot'):
        raise ValueError('private VM preparation entry only')
    launcher = runpy.run_path(str(Path(__file__).resolve().parent / tool))
    # Shared helper installation must happen once in the parent, after all
    # baseline workers release their VM leases.
    return launcher['main'](options, **({'refresh': False} if tool == 'prepare-baseline' else {}))


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
