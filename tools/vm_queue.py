"""Shared rolling VM scheduler and isolated preparation workers."""

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager, ExitStack
from pathlib import Path
import os
import sys
import threading

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))


class _NoWork(Exception):
    """A waiting worker's finite work was drained by another worker."""


class _CapacityWait(Exception):
    """Release a speculative reservation instead of parking an idle VM."""


class _Worker:
    def __init__(self, executor, vm, receipt):
        self.executor = executor
        self._vm = vm
        self.receipt = receipt
        self.used = False
        self.source_refused = False

    @property
    def vm(self):
        return self._vm

    @contextmanager
    def operation(self):
        """Admit one operation, keeping source and capacity through its cleanup."""
        import test_source
        from detached_launcher import Stopped
        executor = self.executor
        executor._check(self.vm)
        with ExitStack() as operation:
            try:
                operation.enter_context(test_source.reader(
                    executor.root, stopped=lambda: executor._abort(self.vm), wait=False))
            except Stopped:
                executor._check(self.vm)
                raise
            except test_source.SourceBusy:
                raise
            except (ValueError, OSError):
                # A foreign source fence refuses an idle worker, even after
                # this worker completed an earlier operation successfully.
                self.source_refused = True
                raise
            executor._check(self.vm)
            with executor._capacity:
                if executor._active >= executor.limit:
                    raise _CapacityWait()
                executor._active += 1
            operation.callback(executor._release_slot)
            executor._check(self.vm)
            self.used = True
            yield


class Executor:
    """One finite workflow's allowed VM pool, reservations and execution slots.

    Reservation waiters use independent threads, never execution capacity or a
    source reader. Failed workers stay reserved until the joined workflow exits;
    their operation capacity is already available to the remaining workers.
    """

    def __init__(self, root, vms, concurrency, stopped):
        from vm_selection import vm_config
        from vm_pool import check_queue
        self.root = Path(root)
        self.vms = tuple(vms)
        if not self.vms or type(concurrency) is not int or concurrency < 1:
            raise ValueError('vm-queue: a nonempty VM pool and positive concurrency are required')
        names = set()
        for vm in self.vms:
            configured = vm_config.load(vm.name)
            if configured.name != vm.name or configured != vm or vm.name in names:
                raise ValueError('vm-queue: workers require unique canonical targets from the allowed pool')
            names.add(vm.name)
        check_queue(self.vms)
        self.stopped = stopped
        self.limit = min(concurrency, len(self.vms), *(vm.host.concurrency for vm in self.vms))
        self._capacity = threading.Condition()
        self._active = 0
        self._closing = threading.Event()
        self._pool = None
        self._futures = []
        self._needed = lambda vm: True
        self._ran = False

    def __enter__(self):
        if self._pool is not None or self._closing.is_set():
            raise ValueError('vm-queue: executor cannot be reopened')
        self._pool = ThreadPoolExecutor(max_workers=len(self.vms))
        return self

    def __exit__(self, *_):
        self._closing.set()
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            # A published failure still owns its reservation until this join.
            # Surface check-in failures rather than treating an event as cleanup.
            for future in self._futures:
                future.result()

    def _cancelled(self):
        return self.stopped() if callable(self.stopped) else self.stopped.is_set()

    def _release_slot(self):
        with self._capacity:
            self._active -= 1
            self._capacity.notify_all()

    def _full(self):
        with self._capacity:
            return self._active >= self.limit

    def _wait_capacity(self, vm):
        with self._capacity:
            while self._active >= self.limit:
                self._check(vm)
                self._capacity.wait(.1)
        self._check(vm)

    def _abort(self, vm):
        import launcher_reload
        return (self._closing.is_set() or self._cancelled()
                or launcher_reload.pending() or not self._needed(vm))

    def _check(self, vm):
        import launcher_reload
        from detached_launcher import Stopped
        if launcher_reload.pending():
            raise launcher_reload.ReloadRequested()
        if self._closing.is_set() or self._cancelled():
            raise Stopped()
        if not self._needed(vm):
            raise _NoWork()

    def _execute(self, vm, execute, result):
        import launcher_reload
        import test_source
        from detached_launcher import Stopped
        from vm_pool import reservation
        try:
            while True:
                self._wait_capacity(vm)
                capacity_cancelled = False
                def pause_reservation():
                    nonlocal capacity_cancelled
                    if self._full():
                        capacity_cancelled = True
                    return capacity_cancelled or self._abort(vm)
                try:
                    with reservation(vm.name, stopped=pause_reservation, bind=False) as receipt:
                        self._check(vm)
                        if self._full():
                            raise _CapacityWait()
                        worker = _Worker(self, vm, receipt)
                        try:
                            value = execute(worker)
                        except (_NoWork, _CapacityWait, test_source.SourceBusy,
                                Stopped, launcher_reload.ReloadRequested):
                            raise
                        except Exception as error:
                            value = dict(status=2, handoffs=[], error=str(error))
                        status = value.get('status', 0) if isinstance(value, dict) else value
                        if status and worker.used and not worker.source_refused:
                            result.set_result(value)
                            self._closing.wait()
                            return
                except KeyboardInterrupt:
                    self._check(vm)
                    if capacity_cancelled:
                        continue
                    raise
                except _CapacityWait:
                    continue
                except test_source.SourceBusy:
                    # Wait without a VM or execution slot, then recheck the
                    # source after obtaining the next reservation.
                    try:
                        with test_source.reader(self.root, stopped=lambda: self._abort(vm)):
                            pass
                    except Stopped:
                        self._check(vm)
                        raise
                    continue
                result.set_result(value)
                return
        except _NoWork:
            result.set_result(dict(status=0, handoffs=[]))
        except Stopped:
            result.set_result(dict(status=130, handoffs=[]))
        except launcher_reload.ReloadRequested:
            result.set_result(dict(status=launcher_reload.STATUS, handoffs=[]))
        except (ValueError, OSError) as error:
            if result.done():
                raise
            result.set_result(dict(status=2, handoffs=[], error=str(error)))
        except BaseException as error:
            if result.done():
                raise
            result.set_exception(error)

    def run_each(self, execute, *, needed=None):
        """Run one callback per needed canonical VM and return results by name."""
        if self._pool is None or self._ran or self._closing.is_set():
            raise ValueError('vm-queue: run_each requires a fresh active executor')
        self._ran = True
        self._needed = needed if needed is not None else lambda vm: True
        results = {}
        pending = {}
        for vm in self.vms:
            if not self._needed(vm):
                results[vm.name] = dict(status=0, handoffs=[])
                continue
            result = Future()
            pending[result] = vm.name
            future = self._pool.submit(self._execute, vm, execute, result)
            self._futures.append(future)
            def finished(future, result=result):
                # Even a bootstrap failure before _execute's error boundary
                # must finish the public result rather than strand the join.
                if not result.done():
                    result.set_exception(future.exception() or RuntimeError(
                        'vm-queue: worker exited without a result'))
            future.add_done_callback(finished)
        for future in as_completed(pending):
            results[pending[future]] = future.result()
        return results


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
    import test_source
    with test_source.reader(root):
        from regression_process import Control
        from vm_selection import BATCH, VARIABLE
    output_lock = threading.Lock()
    with Control().installed() as control:
        def execute(worker):
            vm = worker.vm
            options = ['--vm', vm.name, '--y']
            if tool == 'prepare-appsnapshot':
                options += ['--overwrite', args.overwrite]
                if args.release_notes_upgrade:
                    options.append('--release-notes-upgrade')
            else:
                options += ['--mode', args.mode]
            command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), tool, *options]
            environment = dict(os.environ)
            environment.pop(BATCH, None)
            environment[VARIABLE] = vm.name
            from vm_pool import VARIABLE as CHECKOUT
            environment[CHECKOUT] = worker.receipt
            runner = control
            if tool == 'prepare-vm':
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
            with worker.operation():
                status = runner.run(command, cwd=root, env=environment, output=output)
            if pending:
                output(b'\n')
            return status

        with Executor(root, vms, concurrency, control.stopped) as executor:
            results = executor.run_each(execute)
        statuses = {name: result['status'] if isinstance(result, dict) else result
                    for name, result in results.items()}
        for name, status in statuses.items():
            message = f'{tool}: {name}: status {status}'
            print('\033[31m' + message + '\033[0m' if status else message, flush=True)
            if isinstance(results[name], dict) and results[name].get('error'):
                print(f'\033[31m{tool}: {name}: {results[name]["error"]}\033[0m',
                      file=sys.stderr, flush=True)
        status = 130 if control.stopped.is_set() else next((value for value in statuses.values() if value), 0)
        return statuses, status


def worker(argv):
    import runpy
    import test_source
    tool, *options = argv
    if tool not in ('prepare-vm', 'prepare-appsnapshot'):
        raise ValueError('private VM preparation entry only')
    with test_source.admission(Path(__file__).resolve().parents[1], options):
        launcher = runpy.run_path(str(Path(__file__).resolve().parent / tool))
        # Shared helper installation happens once after baseline workers exit.
        return launcher['main'](options, _worker=True,
                                **({'refresh': False} if tool == 'prepare-vm' else {}))


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
