"""Shared rolling VM scheduler and isolated preparation workers."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, ExitStack, nullcontext
from pathlib import Path
import os
import queue
import re
import sys
import threading

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import launcher_control
from detached_launcher import record_exception


class _NoWork(Exception):
    """A waiting worker's finite work was drained by another worker."""


class _CapacityWait(Exception):
    """Release a speculative reservation instead of parking an idle VM."""


@contextmanager
def _preparation_checkout(vm, stopped):
    """Probe the ordinary nonwaiting checkout and retry only temporary refusals."""
    from host_compute import units
    from vm_pool import Busy, reservation

    # Capture the existing helper diagnostic without changing the privileged
    # protocol or letting a full stderr pipe block the checkout.
    with os.fdopen(os.memfd_create('onpc-preparation-checkout', os.MFD_CLOEXEC), 'rb') as stderr, \
            ExitStack() as checkout:
        try:
            receipt = checkout.enter_context(reservation(vm.name, stopped=stopped, bind=False,
                                                         wait=False, stderr=stderr))
        except Busy:
            raise
        except ValueError as error:
            detail = os.pread(stderr.fileno(), 8192, 0).decode('utf-8', errors='replace').strip()
            capacity = re.search(r'host-compute: host .*: max_compute_unit=([^,]+), .*'
                                 r'minimum vm\.compute_unit=(\S+)\. Available compute units are insufficient',
                                 detail)
            if capacity and units(capacity[2]) <= units(capacity[1]):
                raise Busy('waiting for host compute') from error
            if detail:
                raise ValueError(detail) from error
            raise
        yield receipt


class _Worker:
    def __init__(self, executor, vm, receipt):
        self.executor = executor
        self._vm = vm
        self.receipt = receipt
        self.interrupt = threading.Event()

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
                    executor.root if executor.sources is None else executor.sources.lease_root,
                    stopped=lambda: executor._abort(self.vm), wait=False))
            except Stopped:
                executor._check(self.vm)
                raise
            executor._check(self.vm)
            with executor._capacity:
                if executor._full(self.vm):
                    raise _CapacityWait()
                executor._active += 1
                from host_compute import units
                executor._host_active[self.vm.host.name] += units(self.vm.compute_unit)
            operation.callback(executor._release_slot, self.vm)
            executor._check(self.vm)
            yield


class Executor:
    """One finite workflow's allowed VM pool, reservations and execution slots.

    Reservation waiters use independent threads, never execution capacity or a
    source reader.
    """

    def __init__(self, root, vms, concurrency, stopped, *, sources=None):
        from vm_selection import vm_config
        from vm_pool import check_queue
        self.root = Path(root)
        self.sources = sources
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
        self.limit = min(concurrency, len(self.vms))
        self._capacity = threading.Condition()
        self._active = 0
        self._host_active = {vm.host.name: 0 for vm in self.vms}
        self._probes = {host: threading.Lock() for host in self._host_active}
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
            # Join check-in before returning from the executor.
            for future in self._futures:
                future.result()

    def _cancelled(self):
        return self.stopped() if callable(self.stopped) else self.stopped.is_set()

    def _release_slot(self, vm):
        with self._capacity:
            self._active -= 1
            from host_compute import units
            self._host_active[vm.host.name] -= units(vm.compute_unit)
            self._capacity.notify_all()

    def _full(self, vm):
        from host_compute import units
        with self._capacity:
            return (self._active >= self.limit
                    or self._host_active[vm.host.name] + units(vm.compute_unit)
                        > units(vm.host.max_compute_unit))

    def _wait_capacity(self, vm):
        with self._capacity:
            while self._full(vm):
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

    def _execute(self, vm, execute):
        import launcher_reload
        import test_source
        from detached_launcher import Stopped
        from host_compute import units
        from vm_pool import Busy
        try:
            if units(vm.compute_unit) > units(vm.host.max_compute_unit):
                raise ValueError(f'vm-queue: {vm.name} needs {vm.compute_unit} compute units, '
                                 f'exceeding max_compute_unit={vm.host.max_compute_unit} on {vm.host.name}')
            queued = False
            while True:
                self._wait_capacity(vm)
                with ExitStack() as operation, ExitStack() as checkout:
                    try:
                        with self._probes[vm.host.name]:
                            self._check(vm)
                            if self._full(vm):
                                continue
                            try:
                                receipt = checkout.enter_context(
                                    _preparation_checkout(vm, lambda: self._abort(vm)))
                            except Busy:
                                # Bound failed probes across the whole host even
                                # when all pending VMs are competing to retry.
                                self._closing.wait(.25)
                                raise
                            worker = _Worker(self, vm, receipt)
                            operation.enter_context(worker.operation())
                    except _CapacityWait:
                        continue
                    except Busy as error:
                        if not queued:
                            print(f'vm-queue: {vm.name} queued ({error})', flush=True)
                            queued = True
                        with self._capacity:
                            self._check(vm)
                            self._capacity.wait(1)
                    except test_source.SourceBusy:
                        # A pending worker waits for source without owning a VM.
                        checkout.close()
                        try:
                            with test_source.reader(self.root, stopped=lambda: self._abort(vm)):
                                pass
                        except Stopped:
                            self._check(vm)
                            raise
                    except KeyboardInterrupt:
                        self._check(vm)
                        raise
                    else:
                        self._check(vm)
                        return execute(worker)
        except _NoWork:
            return dict(status=0, handoffs=[])
        except Stopped:
            return dict(status=130, handoffs=[])
        except launcher_reload.ReloadRequested:
            return dict(status=launcher_reload.STATUS, handoffs=[])
        except Exception as error:
            return dict(status=2, handoffs=[],
                **record_exception(launcher_control.current_run, f'VM worker {vm.name}', error))

    def run_each(self, execute, *, needed=None):
        """Queue each needed VM and return results after its checkout closes."""
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
            future = self._pool.submit(self._execute, vm, execute)
            pending[future] = vm.name
            self._futures.append(future)
        for future in as_completed(pending):
            results[pending[future]] = future.result()
        return results

    def run_ready(self, execute, *, choose, needed, completed=None, stop_on_error=True):
        """Dispatch admitted work and join every worker before releasing control.

        A failure closes admission immediately. Each reservation, source lease
        and operation remains on its owning thread through guarded cleanup.
        """
        import launcher_reload
        import test_source
        from detached_launcher import Stopped
        from vm_pool import Busy, reservation
        if self._pool is None or self._ran or self._closing.is_set():
            raise ValueError('vm-queue: run_ready requires a fresh active executor')
        self._ran, self._needed = True, needed
        events = queue.Queue()
        commands = {vm.name: queue.Queue() for vm in self.vms}
        results = {vm.name: dict(status=0, handoffs=[]) for vm in self.vms}
        targets = {vm.name: vm for vm in self.vms}

        def worker_loop(vm):
            inbox = commands[vm.name]
            with self.sources.use() if self.sources is not None else nullcontext():
                while True:
                    if inbox.get() == 'close':
                        return
                    published = False
                    value = None
                    terminal = False
                    try:
                        self._check(vm)
                        with reservation(vm.name, stopped=lambda: self._abort(vm),
                                         bind=False, wait=False) as receipt:
                            with test_source.reader(
                                    self.root if self.sources is None else self.sources.lease_root,
                                    stopped=lambda: self._abort(vm), wait=False):
                                self._check(vm)
                                events.put(('ready', vm.name, None))
                                published = True
                                command = inbox.get()
                                if command == 'close':
                                    return
                                if command != 'run':
                                    # Release before reading the next queued probe.
                                    # No execution took place, so publish no result.
                                    continue
                                worker = _Worker(self, vm, receipt)
                                worker.interrupt = self._closing
                                try:
                                    with worker.operation():
                                        value = execute(worker)
                                    if not isinstance(value, dict) or type(value.get('status')) is not int:
                                        raise ValueError('vm-queue: attempt must return integer status')
                                except (_NoWork, _CapacityWait):
                                    value = None
                    except (Busy, test_source.SourceBusy, _NoWork, _CapacityWait):
                        pass
                    except (Stopped, KeyboardInterrupt):
                        value, terminal = dict(status=130, handoffs=[], interrupted=True), True
                    except launcher_reload.ReloadRequested:
                        value, terminal = dict(status=launcher_reload.STATUS, handoffs=[]), True
                    except BaseException as error:
                        value, terminal = dict(status=2, handoffs=[], cleanup=False,
                            **record_exception(launcher_control.current_run, f'VM worker {vm.name}', error)), True
                    # The operation and reservation have both exited before
                    # the coordinator receives an actual execution result.
                    events.put(('terminal' if terminal else 'done' if published else 'idle', vm.name, value))
                    if terminal:
                        return

        for vm in self.vms:
            future = self._pool.submit(worker_loop, vm)
            self._futures.append(future)
            def finished(future, name=vm.name):
                error = future.exception()
                if error is not None:
                    events.put(('terminal', name, dict(status=2, handoffs=[], cleanup=False,
                        **record_exception(launcher_control.current_run, f'VM worker {name}', error))))
            future.add_done_callback(finished)
        active, retired = set(), set()

        def receive(timeout=None):
            try:
                kind, name, value = events.get(timeout=timeout)
            except queue.Empty:
                return None, None
            if kind in ('done', 'terminal'):
                active.discard(name)
                if value is not None:
                    if completed is not None:
                        try:
                            replacement = completed(targets[name], dict(value))
                            if replacement is not None:
                                if (not isinstance(replacement, dict) or type(replacement.get('status')) is not int
                                        or value['status'] and not replacement['status']):
                                    raise ValueError('completion cannot accept a failed attempt')
                                value = replacement
                        except Exception as error:
                            value = dict(status=2, cleanup=False, handoffs=value.get('handoffs', []),
                                attempt_result=value, **record_exception(launcher_control.current_run,
                                    f'VM completion {name}', error))
                    previous = results[name]
                    results[name] = dict(value, status=previous['status'] or value['status'],
                                        handoffs=[*previous.get('handoffs', []),
                                                         *value.get('handoffs', [])])
                    if value['status'] and (stop_on_error or value['status'] == 130
                                            or value.get('cleanup') is False):
                        self._closing.set()
                if kind == 'terminal':
                    retired.add(name)
            return kind, name

        try:
            while True:
                if self._cancelled() or launcher_reload.pending():
                    self._closing.set()
                candidates = [vm for vm in self.vms if vm.name not in active | retired
                              and not self._closing.is_set() and needed(vm)]
                if not candidates and not active:
                    break
                if len(active) >= self.limit or not candidates:
                    receive(.1)
                    continue
                for vm in candidates:
                    commands[vm.name].put('probe')
                waiting = {vm.name for vm in candidates}
                ready = set()
                while waiting:
                    kind, name = receive()
                    if name in waiting:
                        waiting.remove(name)
                        if kind == 'ready':
                            ready.add(name)
                selected = []
                try:
                    while ready and len(active) + len(selected) < self.limit and not self._closing.is_set():
                        admitted = active | set(selected)
                        from host_compute import units
                        available = tuple(vm.name for vm in self.vms if vm.name in ready and needed(vm)
                            and sum((units(targets[name].compute_unit) for name in admitted
                                     if targets[name].host.name == vm.host.name), units(0))
                                + units(vm.compute_unit) <= units(vm.host.max_compute_unit))
                        if not available:
                            break
                        name = choose(available, tuple(name for name in targets if name in admitted))
                        if name is None:
                            break
                        if name not in available:
                            raise ValueError('vm-queue: chooser selected an unavailable VM')
                        selected.append(name)
                        ready.remove(name)
                finally:
                    for name in ready:
                        commands[name].put('release')
                for name in selected:
                    active.add(name)
                    commands[name].put('run')
                if not selected:
                    self._closing.wait(.1)
        finally:
            self._closing.set()
            while active:
                receive()
            for inbox in commands.values():
                inbox.put('close')
            for future in self._futures:
                future.result()
        return results


def prepare_hosts(root, tool, options, vms, local, run_local):
    """Run one joined preparation queue per host, with one transfer per remote host."""
    from detached_launcher import Stopped
    from host_dispatch import vm_tool
    from regression_process import Control
    import test_source

    groups = {}
    for vm in vms:
        groups.setdefault(vm.host.name, []).append(vm)
    test_source.leave_checkout()
    with Control().installed() as control, ThreadPoolExecutor(max_workers=len(groups)) as remotes:
        def run(host, targets):
            options_for_host = ['--vm', ','.join(vm.name for vm in targets), '--y', *options]
            try:
                if control.stopped.is_set():
                    return 130
                if host == local:
                    with test_source.admission(root, options_for_host, stopped=control.stopped.is_set):
                        return run_local(options_for_host, control, targets)
                return vm_tool(root, targets[0], tool, [*options_for_host, '--queue-host', host],
                               control=control)
            except Stopped:
                return 130
            except (ValueError, OSError) as error:
                print(f'{tool}: {host}: {error}', file=sys.stderr, flush=True)
                return 2

        results = {host: remotes.submit(run, host, targets) for host, targets in groups.items()
                   if host != local}
        local_status = run(local, groups[local]) if local in groups else 0
        statuses = [local_status if host == local else results[host].result() for host in groups]
    return 130 if control.stopped.is_set() or 130 in statuses else next((s for s in statuses if s), 0)


def require_host_queue(expected_host, host, argv, vms):
    """Refuse a changed or partial selection before a transferred queue runs."""
    if expected_host is None:
        return
    from vm_selection import vm_config
    _, selector = vm_config.extract_selector(sys.argv[1:] if argv is None else argv)
    if (expected_host != host or selector != ','.join(vm.name for vm in vms)
            or any(vm.host.name != host for vm in vms)):
        raise ValueError(f'confirmed VM selection changed before preparation on {expected_host}')


def preparation(root, tool, args, concurrency, vms, *, control=None):
    """Run already-confirmed preparation in processes with independent VM state.

    Baseline replacement has no cooperative stop protocol: allow in-flight
    replacements to finish while cancellation prevents queued work. App workers
    use their existing signal handler and wait for owned cleanup.
    """
    import test_source
    from host_compute import units
    with test_source.reader(root, stopped=lambda: control is not None and control.stopped.is_set()):
        from regression_process import Control
        from vm_selection import BATCH, VARIABLE
    output_lock = threading.Lock()
    snapshot_only = tool == 'prepare-appsnapshot' and sum(units(vm.compute_unit) for vm in vms) > units(
        vms[0].host.max_compute_unit)
    with Control().installed() if control is None else nullcontext(control) as control:
        def execute(worker):
            vm = worker.vm
            options = ['--vm', vm.name, '--y']
            worker_options = []
            if tool == 'prepare-appsnapshot':
                if snapshot_only:
                    worker_options.append('--snapshot-only')
                options += ['--overwrite', args.overwrite]
                if args.release_notes_upgrade:
                    options.append('--release-notes-upgrade')
            else:
                options += ['--mode', args.mode]
            command = ['/usr/bin/python3', '-IBu', str(Path(__file__).resolve()), tool,
                       *worker_options, *options]
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
        if tool == 'prepare-vm':
            return launcher['main'](options, _worker=True, refresh=False)
        snapshot_only = options[:1] == ['--snapshot-only']
        return launcher['main'](options[1:] if snapshot_only else options,
                                _worker=True, _snapshot_only=snapshot_only)


if __name__ == '__main__':
    sys.exit(worker(sys.argv[1:]))
