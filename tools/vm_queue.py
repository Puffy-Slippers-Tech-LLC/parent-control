"""Shared rolling VM scheduler and isolated preparation workers."""

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager, ExitStack
from pathlib import Path
import os
import queue
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
    def operation(self, *, recovery=False):
        """Admit one operation, keeping source and capacity through its cleanup."""
        import test_source
        from detached_launcher import Stopped
        executor = self.executor
        executor._check(self.vm, recovery=recovery)
        with ExitStack() as operation:
            try:
                operation.enter_context(test_source.reader(
                    executor.root, stopped=lambda: executor._abort(self.vm, recovery=recovery), wait=False))
            except Stopped:
                executor._check(self.vm, recovery=recovery)
                raise
            except test_source.SourceBusy:
                raise
            except (ValueError, OSError):
                # A foreign source fence refuses an idle worker, even after
                # this worker completed an earlier operation successfully.
                self.source_refused = True
                raise
            executor._check(self.vm, recovery=recovery)
            with executor._capacity:
                if executor._full(self.vm):
                    raise _CapacityWait()
                executor._active += 1
                executor._host_active[self.vm.host.name] += 1
            operation.callback(executor._release_slot, self.vm)
            executor._check(self.vm, recovery=recovery)
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
        self.limit = min(concurrency, len(self.vms),
                         sum(host.concurrency for host in {vm.host for vm in self.vms}))
        self._capacity = threading.Condition()
        self._active = 0
        self._host_active = {vm.host.name: 0 for vm in self.vms}
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

    def _release_slot(self, vm):
        with self._capacity:
            self._active -= 1
            self._host_active[vm.host.name] -= 1
            self._capacity.notify_all()

    def _full(self, vm):
        with self._capacity:
            return (self._active >= self.limit
                    or self._host_active[vm.host.name] >= vm.host.concurrency)

    def _wait_capacity(self, vm):
        with self._capacity:
            while self._full(vm):
                self._check(vm)
                self._capacity.wait(.1)
        self._check(vm)

    def _abort(self, vm, *, recovery=False):
        import launcher_reload
        return (self._closing.is_set() or self._cancelled()
                or launcher_reload.pending() or not recovery and not self._needed(vm))

    def _check(self, vm, *, recovery=False):
        import launcher_reload
        from detached_launcher import Stopped
        if launcher_reload.pending():
            raise launcher_reload.ReloadRequested()
        if self._closing.is_set() or self._cancelled():
            raise Stopped()
        if not recovery and not self._needed(vm):
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
                    if self._full(vm):
                        capacity_cancelled = True
                    return capacity_cancelled or self._abort(vm)
                try:
                    with reservation(vm.name, stopped=pause_reservation, bind=False) as receipt:
                        self._check(vm)
                        if self._full(vm):
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

    def run_ready(self, execute, *, choose, needed, completed=None, observed=None,
                  service=None, keep_failed=False):
        """Dispatch one admitted attempt at a time from coordinator-selected VMs.

        ``choose(ready_names, active_names)`` may select only a ready name.
        Returning None pauses new admission until a later readiness round;
        ``needed(vm)`` ends waiting when that VM has no further work.
        Availability is probed without waiting for occupied VMs. Each probe and
        operation stays on its owning thread, including source lease teardown.
        ``observed`` records failures before their source reader exits. In repair
        mode retained reservations may serve more normal work and bounded nested
        attempts. ``service(controller, drained)`` runs between admissions; it
        must request nested attempts only at a drained boundary.
        ``completed(vm, result)`` runs on the coordinator before refill. Success
        is notified only after source and reservation teardown; the callback may
        return a replacement result to reject an attempt's acceptance.
        """
        import launcher_reload
        import test_source
        from detached_launcher import Stopped
        from vm_pool import Busy, reservation
        if self._pool is None or self._ran or self._closing.is_set():
            raise ValueError('vm-queue: run_ready requires a fresh active executor')
        self._ran = True
        self._needed = needed
        events = queue.Queue()
        commands = {vm.name: queue.Queue() for vm in self.vms}
        results = {vm.name: dict(status=0, handoffs=[]) for vm in self.vms}

        def worker_loop(vm):
            inbox = commands[vm.name]
            retained = False
            reservation_stack = ExitStack()
            receipt = None
            while True:
                command = inbox.get()
                if command == 'close':
                    reservation_stack.close()
                    return
                if command == 'release-reservation':
                    reservation_stack.close()
                    reservation_stack = ExitStack()
                    retained, receipt = False, None
                    continue
                if isinstance(command, tuple):
                    callback, environment, result = command
                    try:
                        self._check(vm, recovery=True)
                        if receipt is None:
                            receipt = reservation_stack.enter_context(reservation(
                                vm.name, stopped=lambda: self._abort(vm, recovery=True), bind=False))
                        retained = True
                        if callback is None:
                            result.set_result(None)
                            continue
                        with test_source.borrowed(self.root, environment):
                            worker = _Worker(self, vm, receipt)
                            with worker.operation(recovery=True):
                                value = callback(worker)
                        result.set_result(value)
                    except BaseException as error:
                        result.set_exception(error)
                    continue
                published = False
                result_sent = False
                worker = None
                try:
                    self._check(vm)
                    if receipt is None:
                        receipt = reservation_stack.enter_context(reservation(
                            vm.name, stopped=lambda: self._abort(vm), bind=False, wait=False))
                    try:
                        with test_source.reader(self.root, stopped=lambda: self._abort(vm), wait=False):
                            self._check(vm)
                            worker = _Worker(self, vm, receipt)
                            events.put(('ready', vm.name, None))
                            published = True
                            command = inbox.get()
                            if command == 'close':
                                reservation_stack.close()
                                return
                            if command != 'run':
                                continue
                            try:
                                with worker.operation():
                                    value = execute(worker)
                                    if not isinstance(value, dict) or type(value.get('status')) is not int:
                                        raise ValueError('vm-queue: an attempt must return a dictionary with integer status')
                            except (_NoWork, Stopped, launcher_reload.ReloadRequested):
                                raise
                            except Exception as error:
                                value = dict(status=2, handoffs=[], error=str(error))
                            if observed is not None:
                                observed(vm, value)
                        if value.get('status') and worker.used and not worker.source_refused:
                            retained = True
                            events.put(('done', vm.name, value))
                            result_sent = True
                            if not keep_failed:
                                self._closing.wait()
                                reservation_stack.close()
                                return
                            continue
                    finally:
                        if not retained:
                            reservation_stack.close()
                            reservation_stack = ExitStack()
                            receipt = None
                    events.put(('done', vm.name, value))
                except (Busy, test_source.SourceBusy):
                    events.put(('idle' if not published else 'done', vm.name, None))
                except _NoWork:
                    events.put(('idle' if not published else 'done', vm.name, None))
                except (Stopped, KeyboardInterrupt):
                    events.put(('terminal', vm.name, dict(status=130, handoffs=[])))
                    reservation_stack.close()
                    return
                except launcher_reload.ReloadRequested:
                    events.put(('terminal', vm.name, dict(status=launcher_reload.STATUS, handoffs=[])))
                    reservation_stack.close()
                    return
                except BaseException as error:
                    if result_sent:
                        raise
                    events.put(('terminal', vm.name, dict(status=2, handoffs=[],
                                                         cleanup=False, error=str(error))))
                    reservation_stack.close()
                    return

        for vm in self.vms:
            self._futures.append(self._pool.submit(worker_loop, vm))
        active, retired = set(), set()
        targets = {vm.name: vm for vm in self.vms}

        def receive():
            kind, name, value = events.get()
            if kind in ('done', 'terminal'):
                active.discard(name)
                if value is not None:
                    completion_failed = False
                    if completed is not None:
                        try:
                            replacement = completed(targets[name], dict(value))
                            if replacement is not None:
                                if (not isinstance(replacement, dict)
                                        or type(replacement.get('status')) is not int):
                                    raise ValueError('vm-queue: completion must return an integer-status result')
                                if value['status'] and not replacement['status']:
                                    raise ValueError('vm-queue: completion cannot accept a failed attempt')
                                value = replacement
                        except Exception as error:
                            completion_failed = True
                            value = dict(status=2, handoffs=value.get('handoffs', []),
                                         cleanup=False, error=str(error))
                    previous = results[name]
                    results[name] = dict(value, handoffs=[*previous.get('handoffs', []),
                                                         *value.get('handoffs', [])])
                    if value.get('status') and (not keep_failed or completion_failed):
                        retired.add(name)
                if kind == 'terminal':
                    retired.add(name)
            return kind, name

        class Controller:
            def reserve(inner, name):
                if name not in commands or name in retired or name in active:
                    raise ValueError('vm-queue: recovery target is unavailable')
                result = Future()
                commands[name].put((None, {}, result))
                return result.result()

            def attempt(inner, name, callback):
                if active:
                    raise ValueError('vm-queue: repair attempts require a drained boundary')
                if name not in commands or name in retired:
                    raise ValueError('vm-queue: repair target is unavailable')
                environment = test_source.environment()
                if test_source.WRITER not in environment:
                    raise ValueError('vm-queue: repair attempts require the owning source writer')
                result = Future()
                commands[name].put((callback, environment, result))
                return result.result()

            def release(inner, name):
                if name in commands:
                    commands[name].put('release-reservation')

        controller = Controller()

        try:
            while True:
                if service is not None:
                    if service(controller, not active):
                        continue
                candidates = [vm for vm in self.vms if vm.name not in active | retired and needed(vm)]
                if not candidates and not active:
                    break
                if len(active) >= self.limit or not candidates:
                    receive()
                    continue
                for vm in candidates:
                    commands[vm.name].put('probe')
                probing = {vm.name for vm in candidates}
                ready = set()
                while probing:
                    kind, name = receive()
                    if name in probing:
                        probing.remove(name)
                        if kind == 'ready':
                            ready.add(name)
                selected = []
                try:
                    while ready and len(active) + len(selected) < self.limit:
                        admitted = active | set(selected)
                        available = tuple(vm.name for vm in self.vms
                            if vm.name in ready and needed(vm)
                            and sum(targets[name].host.name == vm.host.name for name in admitted)
                                < vm.host.concurrency)
                        if not available:
                            break
                        name = choose(available, tuple(vm.name for vm in self.vms
                                                       if vm.name in active or vm.name in selected))
                        if name is None:
                            break
                        if name not in available:
                            raise ValueError('vm-queue: chooser selected a VM that is not ready')
                        selected.append(name)
                        ready.remove(name)
                except BaseException:
                    for name in selected:
                        commands[name].put('release')
                    raise
                finally:
                    for name in ready:
                        commands[name].put('release')
                for name in selected:
                    active.add(name)
                    commands[name].put('run')
                if not selected:
                    if self._cancelled() or launcher_reload.pending():
                        # Probes translate cancellation into terminal results.
                        continue
                    self._closing.wait(.1)
        finally:
            for inbox in commands.values():
                inbox.put('close')
        return results


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
