"""VM checkout lifetimes with private locks and explicitly owned children.

No libvirt, VM, external service, shared cache or live coordinator is accessed.
Children are bounded and waited; fixtures never access the live coordinator.
"""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
from contextlib import contextmanager
from dataclasses import replace

import pytest
import vm_pool

A = 'f95890e1-88e7-4779-8ae3-53fdcc34330a'
B = 'f95890e1-88e7-4779-8ae3-53fdcc34330b'


@pytest.fixture
def executor_pool(tmp_path, monkeypatch):
    """Private admission doubles; exercise the real executor and its slots."""
    import test_source
    from types import SimpleNamespace
    from vm_selection import vm_config

    vms = [vm_config.VMConfig(name, tmp_path / name, enabled=True, id=str(index))
           for index, name in enumerate(('first', 'second'), 1)]
    configured = {vm.name: vm for vm in vms}
    monkeypatch.setattr(vm_config, 'load', lambda name: configured[name])
    held, released = set(), []
    local = threading.local()

    @contextmanager
    def reservation(name, *, stopped, bind, wait=True):
        assert bind is False
        assert name in configured
        local.name = name
        held.add(name)
        try:
            yield (A if name == 'first' else B) + ':' + 'a' * 32
        finally:
            held.remove(name)
            released.append(name)

    @contextmanager
    def reader(root, **kwargs):
        assert root == tmp_path
        yield

    real_reader = test_source.reader
    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    monkeypatch.setattr(test_source, 'reader', reader)
    return SimpleNamespace(root=tmp_path, vms=vms, held=held, released=released,
                           local=local, reservation=reservation, reader=real_reader)


def test_executor_refuses_noncanonical_pool_before_checkout(executor_pool, monkeypatch):
    import vm_queue
    from vm_selection import vm_config

    state = executor_pool
    canonical = state.vms[0]
    monkeypatch.setattr(vm_config, 'load', lambda name: canonical)
    for invalid in (replace(canonical, name=canonical.id),
                    replace(canonical, disk_anchor=state.root / 'foreign')):
        with pytest.raises(ValueError):
            with vm_queue.Executor(state.root, [invalid], 1, threading.Event()):
                pytest.fail('noncanonical VM entered the executor')
    assert not state.held and not state.released


def test_executor_ready_attempts_choose_only_available_and_retain_failed_owner(executor_pool, monkeypatch):
    import test_source
    import vm_queue

    state = executor_pool
    completed = []
    readers = set()
    choices = []

    @contextmanager
    def reader(root, **kwargs):
        name = state.local.name
        readers.add(name)
        try:
            yield
        finally:
            readers.discard(name)

    monkeypatch.setattr(test_source, 'reader', reader)

    def choose(ready, active):
        choices.append((ready, active))
        assert not active
        return 'second' if 'second' in ready else ready[0]

    def execute(worker):
        name = worker.vm.name
        assert name in readers and name in state.held
        assert worker.executor._active == 1
        if name == 'first':
            assert 'second' in state.held, 'failed owner released before executor close'
            assert 'second' not in readers, 'failed owner retained source admission'
        completed.append(name)
        return dict(status=2 if name == 'second' else 0, handoffs=[name])

    with vm_queue.Executor(state.root, state.vms, 1, threading.Event()) as executor:
        results = executor.run_ready(execute, choose=choose,
                                     needed=lambda vm: vm.name not in completed)
        assert state.held == {'second'}
    assert completed == ['second', 'first']
    assert set(choices[0][0]) == {'first', 'second'}
    assert results['second']['status'] == 2 and results['first']['status'] == 0
    assert not state.held and not readers


def test_executor_retained_sole_vm_continues_then_borrows_writer_for_recovery(
        executor_pool, monkeypatch):
    import test_source
    import vm_queue

    state = executor_pool
    source = state.root / 'source'
    source.mkdir(mode=0o700)
    run = state.root / 'repair'
    run.mkdir(mode=0o700)
    for name in (test_source.VARIABLE, test_source.WRITER, test_source.IMPORTS,
                 test_source.STARTUP_READER, test_source.STARTUP_WRITER):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(test_source, '_local', threading.local())
    monkeypatch.setattr(test_source, '_generations', {})
    monkeypatch.setattr(test_source, 'source_directory', lambda root, **kwargs: source)
    gate = test_source.RepairGate(run, root=state.root)
    coordinator = threading.get_ident()
    readers, attempts, observations, completions, recoveries = {}, [], [], [], []

    @contextmanager
    def reader(root, **kwargs):
        identity = threading.get_ident()
        with state.reader(root, **kwargs) as descriptor:
            readers.setdefault(identity, []).append(descriptor)
            try:
                yield descriptor
            finally:
                readers[identity].pop()
                if not readers[identity]:
                    del readers[identity]

    monkeypatch.setattr(test_source, 'reader', reader)

    def execute(worker):
        identity = threading.get_ident()
        attempts.append((identity, worker.receipt))
        assert identity != coordinator and worker.vm.name == 'first'
        assert executor._active == 1 and state.held == {'first'}
        assert len(readers[identity]) == 2
        return dict(status=2 if len(attempts) == 1 else 0,
                    handoffs=['failure' if len(attempts) == 1 else 'normal'], cleanup=True)

    def observed(vm, result):
        identity = threading.get_ident()
        observations.append(result['status'])
        assert vm.name == 'first' and len(readers[identity]) == 1
        assert executor._active == 0, 'failure observation retained an execution slot'
        if result['status']:
            with gate.protection.state():
                gate.protection.set_impact(gate.owner, 'untriaged')
            assert not gate.try_acquire(), 'failure observation let edits cross its reader'
            with gate.protection.state():
                gate.protection.set_impact(gate.owner, 'no')

    def completed(vm, result):
        completions.append(result['status'])
        assert threading.get_ident() == coordinator and vm.name == 'first'
        assert not readers and executor._active == 0
        assert state.held == {'first'}, 'isolated failure lost its recovery reservation'

    def recovery(worker):
        identity = threading.get_ident()
        assert (identity, worker.receipt) == attempts[0] == attempts[1]
        assert worker.vm.name == 'first' and state.held == {'first'}
        assert executor._active == 1 and len(readers[identity]) == 1
        descriptor, = test_source.descriptors()
        assert descriptor == gate.fd
        assert test_source.environment()[test_source.WRITER] == gate.owner
        gate.protection.validate(descriptor, held=True, writer=True)
        return dict(status=0, handoffs=['verified'], cleanup=True)

    def service(controller, drained):
        if not attempts and drained and not state.held:
            assert drained and not readers and executor._active == 0
            controller.reserve('first')
            assert state.held == {'first'} and executor._active == 0
        if len(completions) != 2 or recoveries:
            return False
        assert drained and not readers and executor._active == 0
        assert state.held == {'first'}
        assert gate.try_acquire(ready=lambda: drained)
        try:
            with gate.source():
                recoveries.append(controller.attempt('first', recovery))
            assert not readers and executor._active == 0
        finally:
            gate.release()
        with gate.protection.state():
            gate.protection.release_impact(gate.owner)
        return True

    with vm_queue.Executor(state.root, state.vms[:1], 1, threading.Event()) as executor:
        results = executor.run_ready(execute, choose=lambda ready, active: ready[0],
            needed=lambda vm: len(completions) < 2, observed=observed, completed=completed,
            service=service, keep_failed=True)
        assert results['first']['handoffs'] == ['failure', 'normal']
    assert observations == completions == [2, 0]
    assert recoveries == [dict(status=0, handoffs=['verified'], cleanup=True)]
    assert not state.held and not readers and executor._active == 0
    assert state.released == ['first']
    assert gate.fd is None and gate.protection.owner() is None


def test_executor_ready_success_reenters_and_rejects_unready_choices(executor_pool):
    import vm_queue

    state = executor_pool
    attempts = []

    def execute(worker):
        attempts.append(worker.vm.name)
        return dict(status=0, handoffs=[str(len(attempts))])

    def completed(vm, result):
        assert not state.held, 'success notified before reservation teardown'
        if len(attempts) == 2:
            return dict(result, status=2, error='acceptance refused')

    with vm_queue.Executor(state.root, state.vms[:1], 1, threading.Event()) as executor:
        result = executor.run_ready(execute, choose=lambda ready, active: ready[0],
                                    needed=lambda vm: True, completed=completed)
    assert attempts == ['first', 'first']
    assert result['first']['handoffs'] == ['1', '2']
    assert result['first']['status'] == 2
    attempts.clear()
    def reject_completion(vm, result):
        raise ValueError('completion rejected after execution')
    with vm_queue.Executor(state.root, state.vms[:1], 1, threading.Event()) as executor:
        result = executor.run_ready(execute, choose=lambda ready, active: ready[0],
                                    needed=lambda vm: len(attempts) < 2,
                                    completed=reject_completion, keep_failed=True)
    assert attempts == ['first'], 'later work must not erase an unowned completion error'
    assert result['first']['status'] == 2
    assert result['first']['cleanup'] is False
    with pytest.raises(ValueError, match='not ready'):
        with vm_queue.Executor(state.root, state.vms, 1, threading.Event()) as executor:
            executor.run_ready(execute, choose=lambda ready, active: 'foreign', needed=lambda vm: True)
    assert not state.held


def test_executor_ready_busy_vm_has_no_source_and_late_checkin_cannot_pass(executor_pool, monkeypatch):
    import test_source
    import vm_queue

    state = executor_pool
    attempted = []
    notifications = []
    coordinator = threading.get_ident()

    @contextmanager
    def reservation(name, *, stopped, bind, wait):
        assert wait is False
        if name == 'first':
            raise vm_pool.Busy('controlled occupied VM')
        with state.reservation(name, stopped=stopped, bind=bind) as receipt:
            yield receipt
        raise ValueError('controlled late checkin failure')

    @contextmanager
    def reader(root, **kwargs):
        assert state.local.name == 'second', 'busy VM acquired source admission'
        yield

    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    monkeypatch.setattr(test_source, 'reader', reader)

    def execute(worker):
        attempted.append(worker.vm.name)
        return dict(status=0, handoffs=[], evidence='attempt evidence', cleanup=True)

    def completed(vm, result):
        assert threading.get_ident() == coordinator
        assert vm.name == 'second'
        assert not state.held
        notifications.append(result)

    with vm_queue.Executor(state.root, state.vms, 1, threading.Event()) as executor:
        result = executor.run_ready(execute, choose=lambda ready, active: ready[0],
                                    needed=lambda vm: not attempted, completed=completed)
    assert attempted == ['second']
    assert result['second']['status'] == 2
    assert 'controlled late checkin failure' in result['second']['error']
    assert len(notifications) == 1
    assert notifications[0]['status'] == 2 and notifications[0]['cleanup'] is False
    assert 'evidence' not in notifications[0]
    assert not state.held


def test_executor_busy_waiter_uses_no_slot_and_cancels_when_work_drains(executor_pool, monkeypatch):
    import test_source
    import vm_queue

    state = executor_pool
    waiting = threading.Event()
    cancelled = threading.Event()
    drained = threading.Event()
    readers = []
    callbacks = []

    @contextmanager
    def reservation(name, *, stopped, bind):
        if name == 'first':
            assert bind is False
            waiting.set()
            for _ in range(500):
                if stopped():
                    cancelled.set()
                    raise KeyboardInterrupt
                cancelled.wait(.01)
            pytest.fail('obsolete occupied-VM waiter did not cancel')
        with state.reservation(name, stopped=stopped, bind=bind) as receipt:
            yield receipt

    @contextmanager
    def reader(root, **kwargs):
        readers.append(state.local.name)
        yield

    monkeypatch.setattr(vm_pool, 'reservation', reservation)
    monkeypatch.setattr(test_source, 'reader', reader)

    def execute(worker):
        assert waiting.wait(5)
        callbacks.append(worker.vm.name)
        with worker.operation():
            assert worker.receipt == B + ':' + 'a' * 32
            drained.set()
        return 0

    with vm_queue.Executor(state.root, state.vms, 1, threading.Event()) as executor:
        results = executor.run_each(execute, needed=lambda vm: not drained.is_set())
        assert results['second'] == 0
        assert cancelled.is_set()
    assert callbacks == ['second'] and readers == ['second']
    assert not state.held


def test_executor_foreign_source_fence_releases_idle_checkout(executor_pool, monkeypatch):
    import test_source
    import vm_queue

    state = executor_pool

    @contextmanager
    def reader(root, **kwargs):
        assert state.held == {'first'}
        raise ValueError('foreign retained source writer')
        yield

    monkeypatch.setattr(test_source, 'reader', reader)

    def execute(worker):
        with worker.operation():
            pytest.fail('foreign source writer permitted VM activity')

    with vm_queue.Executor(state.root, state.vms[:1], 1, threading.Event()) as executor:
        results = executor.run_each(execute)
        assert results['first']['status'] != 0
        assert 'foreign retained source writer' in results['first']['error']
        assert not state.held, 'source refusal retained an unused checkout'
    assert state.released == ['first']


def test_executor_releases_excess_free_vms_while_capacity_is_full(executor_pool, monkeypatch):
    import vm_queue

    state = executor_pool
    ready = threading.Barrier(2)
    first_requests = set()
    idle_released = threading.Event()
    executed = []

    @contextmanager
    def reservation(name, *, stopped, bind):
        try:
            with state.reservation(name, stopped=stopped, bind=bind) as receipt:
                if name not in first_requests:
                    first_requests.add(name)
                    ready.wait(timeout=5)  # Both free VMs become ready together.
                yield receipt
        finally:
            idle_released.set()

    monkeypatch.setattr(vm_pool, 'reservation', reservation)

    def execute(worker):
        with worker.operation():
            executed.append(worker.vm.name)
            if len(executed) == 1:
                assert idle_released.wait(5), 'spare free VM stayed reserved behind capacity'
                assert state.held == {worker.vm.name}
        return 0

    with vm_queue.Executor(state.root, state.vms, 1, threading.Event()) as executor:
        results = executor.run_each(execute)
    assert results == {'first': 0, 'second': 0}
    assert sorted(executed) == ['first', 'second'] and not state.held


def test_executor_source_wait_uses_no_slot_and_failure_retains_checkout(executor_pool, monkeypatch):
    import test_source
    import vm_queue

    state = executor_pool
    source_waiting = threading.Event()
    source_ready = threading.Event()
    release_source = threading.Event()
    first_running = threading.Event()
    second_failed = threading.Event()
    cleanup_finished = threading.Event()
    readers = set()

    @contextmanager
    def reader(root, **kwargs):
        name = state.local.name
        if name == 'first':
            if kwargs.get('wait') is False and not release_source.is_set():
                source_waiting.set()
                raise test_source.SourceBusy('controlled live source writer')
            if kwargs.get('wait') is not False:
                assert name not in state.held, 'source wait retained an idle VM'
                assert release_source.wait(5), 'other VM could not progress during source wait'
                source_ready.set()
        else:
            assert source_waiting.wait(5)
        if kwargs.get('wait') is False:
            assert name in state.held
        readers.add(name)
        try:
            yield
        finally:
            if name == 'second':
                assert first_running.wait(5), 'source reader closed before releasing the execution slot'
            readers.remove(name)

    monkeypatch.setattr(test_source, 'reader', reader)

    def execute(worker):
        name = worker.vm.name
        with worker.operation():
            assert name in readers
            if name == 'second':
                try:
                    release_source.set()
                    assert source_ready.wait(5)
                    assert not first_running.wait(.05), 'source waiter bypassed the capacity limit'
                finally:
                    # Owned cleanup remains inside the finite operation's slot.
                    cleanup_finished.set()
            else:
                first_running.set()
                assert cleanup_finished.is_set()
                assert second_failed.wait(5)
                assert 'second' in state.held, 'failed worker checked in before its peers finished'
        if name == 'second':
            second_failed.set()
            raise RuntimeError('controlled operation failure')
        return 0

    with vm_queue.Executor(state.root, state.vms, 4, threading.Event()) as executor:
        results = executor.run_each(execute)
        assert results['first'] == 0
        assert results['second']['status'] != 0
        assert 'controlled operation failure' in results['second']['error']
        assert 'second' in state.held
    assert not state.held and not readers
    assert set(state.released) == {'first', 'second'}
    assert state.released.count('second') == 1
    # Source waiting checks in the idle VM, then reacquires it for execution.
    # An admission race may likewise check it in again before capacity opens.
    assert state.released.count('first') >= 2


@pytest.fixture
def pool(tmp_path, monkeypatch):
    monkeypatch.setattr(vm_pool, 'RUNTIME', tmp_path / 'pool')
    return vm_pool.RUNTIME


@pytest.mark.parametrize('invalid', [None, 'unfinished', 'foreign-uuid', 'symlink'])
def test_provisioning_retires_only_completed_private_vm_state(pool, tmp_path, monkeypatch, invalid):
    import prepare_baseline as baseline
    import vm_config
    from types import SimpleNamespace
    state_root = tmp_path / 'state'
    state_root.mkdir(mode=0o700)
    directory = state_root / 'vm'
    directory.mkdir(mode=0o700)
    monkeypatch.setattr(vm_config, 'STATE_ROOT', state_root)
    monkeypatch.setattr(vm_config, 'load', lambda name: SimpleNamespace(owning_branch=''))
    phase = directory / 'phase.json'
    phase.write_text(json.dumps({'phase': 'finalized', 'source': {'layout': {
        'uuid': B if invalid == 'foreign-uuid' else A}}}))
    phase.chmod(0o600)
    attempt = directory / 'system-run.json'
    attempt.write_text(json.dumps({'phase': 'running' if invalid == 'unfinished' else 'complete'}))
    attempt.chmod(0o600)
    unrelated = state_root / 'other-vm'
    unrelated.mkdir(mode=0o700)
    if invalid == 'symlink':
        (directory / 'unexpected').symlink_to(unrelated, target_is_directory=True)
    original = phase.read_bytes()
    with vm_pool.checkout(A):
        if invalid:
            with pytest.raises(baseline.CaptureError):
                vm_pool.retire_domain_state('vm', A)
            assert phase.read_bytes() == original
            assert not list(state_root.glob('.retired-newvm-*'))
        else:
            vm_pool.retire_domain_state('vm', A)
            assert not directory.exists()
            retired, = state_root.glob('.retired-newvm-vm-*')
            assert (retired / 'phase.json').read_bytes() == original
            # Retrying after retirement neither adopts nor touches another VM.
            vm_pool.retire_domain_state('vm', A)
    assert unrelated.is_dir()


def launch(pool, vm=A, *, keeper=False, cwd=None, hold_fds=(), wait=True):
    code = '''import os,sys,pathlib
sys.path.insert(0,sys.argv[1])
import vm_pool
vm_pool.RUNTIME=pathlib.Path(sys.argv[2])
if sys.argv[4]=='keep':
    sys.exit(vm_pool.keep(sys.argv[3],wait=sys.argv[5]=='wait'))
if sys.argv[4]=='hold':
    print('retaining',flush=True)
    sys.stdin.buffer.read(1)
    sys.exit(0)
fd=vm_pool.acquire(sys.argv[3])
print('acquired',flush=True)
sys.stdin.buffer.read(1)
os.close(fd)
'''
    return subprocess.Popen([sys.executable, '-B', '-c', code,
        str(Path(vm_pool.__file__).parent), str(pool), vm,
        'hold' if hold_fds else 'keep' if keeper else 'take', 'wait' if wait else 'no-wait'],
        cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        pass_fds=hold_fds,
        env={key: value for key, value in os.environ.items() if key != vm_pool.VARIABLE})


def ready(child):
    assert select.select([child.stdout], [], [], 5)[0], 'checkout did not finish'
    line = child.stdout.readline()
    assert line, child.stderr.read().decode()
    return line


def finish(child):
    if child.stdin is not None:
        child.stdin.close()
        child.stdin = None
    try:
        assert child.wait(timeout=5) == 0, child.stderr.read().decode()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stdout.close()
        child.stderr.close()


def test_same_vm_queues_across_checkout_paths_and_other_vm_proceeds(pool, tmp_path):
    first_root, second_root = tmp_path / 'branch-a', tmp_path / 'worktree-b'
    first_root.mkdir()
    second_root.mkdir()
    first = launch(pool, cwd=first_root)
    second = third = None
    try:
        assert ready(first) == b'acquired\n'
        second = launch(pool, cwd=second_root)
        assert select.select([second.stderr], [], [], 5)[0]
        assert b'queued for VM' in second.stderr.readline()
        assert not select.select([second.stdout], [], [], 0.1)[0]
        # The queued waiter holds admission. Shutdown recovery must decline
        # atomically, leaving both the owner and queued driver untouched.
        refused = launch(pool, keeper=True, wait=False)
        stdout, stderr = refused.communicate(timeout=5)
        assert refused.returncode == vm_pool.Busy.status and not stdout
        assert b'VM busy' in stderr
        third = launch(pool, B, cwd=second_root)
        assert ready(third) == b'acquired\n'
        finish(first)
        first = None
        assert ready(second) == b'acquired\n'
        # Admission is now free, but the lifetime lock is still occupied.
        refused = launch(pool, keeper=True, wait=False)
        stdout, stderr = refused.communicate(timeout=5)
        assert refused.returncode == vm_pool.Busy.status and not stdout
        assert b'VM busy' in stderr
    finally:
        for child in (first, third, second):
            if child is not None:
                finish(child)


@pytest.mark.parametrize('crash', [False, True])
def test_reservation_survives_commands_and_keeper_exit_until_last_borrower(pool, monkeypatch, crash):
    keeper = launch(pool, keeper=True, wait=False)
    waiter = None
    borrowed = None
    try:
        receipt = json.loads(ready(keeper))['checkout']
        monkeypatch.setenv(vm_pool.VARIABLE, receipt)
        borrowed = vm_pool.acquire(A, wait=False)
        # Finishing a command checks in only its borrowed description.
        os.close(borrowed)
        borrowed = None
        waiter = launch(pool)
        assert select.select([waiter.stderr], [], [], 5)[0]
        assert b'queued for VM' in waiter.stderr.readline()
        assert not select.select([waiter.stdout], [], [], 0.1)[0]
        borrowed = vm_pool.acquire(A)
        if crash:
            keeper.kill()
            keeper.communicate(timeout=5)
            assert keeper.returncode < 0
        else:
            finish(keeper)
        keeper = None
        assert not select.select([waiter.stdout], [], [], 0.1)[0]
        os.close(borrowed)
        borrowed = None
        assert ready(waiter) == b'acquired\n'
    finally:
        if borrowed is not None:
            os.close(borrowed)
        for child in (keeper, waiter):
            if child is not None:
                finish(child)


def test_cross_vm_nested_request_refuses_before_waiting(pool, monkeypatch):
    keeper = launch(pool, keeper=True)
    other = launch(pool, B, keeper=True)
    try:
        first = json.loads(ready(keeper))['checkout']
        second = json.loads(ready(other))['checkout']
        monkeypatch.setenv(vm_pool.VARIABLE, first)
        with pytest.raises(ValueError, match='check in the reserved VM'):
            vm_pool.acquire(B)
        monkeypatch.setenv(vm_pool.VARIABLE, second)
        with pytest.raises(ValueError, match='check in the reserved VM'):
            vm_pool.acquire(A)
    finally:
        finish(keeper)
        finish(other)


def test_cancelled_queued_keeper_leaves_existing_owner_and_other_vms_alone(pool):
    owner = launch(pool)
    waiting = other = None
    try:
        ready(owner)
        waiting = launch(pool, keeper=True)
        assert select.select([waiting.stderr], [], [], 5)[0]
        assert b'queued for VM' in waiting.stderr.readline()
        waiting.stdin.close()
        waiting.stdin = None
        assert waiting.wait(timeout=5) == 130
        waiting.stdout.close()
        waiting.stderr.close()
        waiting = None
        other = launch(pool, B)
        assert ready(other) == b'acquired\n'
    finally:
        for child in (waiting, other, owner):
            if child is not None:
                finish(child)


def test_receipt_can_rejoin_idle_vm_but_never_a_newer_checkout(pool, monkeypatch):
    keeper = launch(pool, keeper=True)
    receipt = json.loads(ready(keeper))['checkout']
    finish(keeper)
    monkeypatch.setenv(vm_pool.VARIABLE, receipt)
    os.close(vm_pool.acquire(A))
    replacement = launch(pool, keeper=True)
    try:
        current = json.loads(ready(replacement))['checkout']
        with pytest.raises(ValueError, match='no longer available'):
            vm_pool.acquire(A)
        monkeypatch.setenv(vm_pool.VARIABLE, current)
        os.close(vm_pool.acquire(A))
    finally:
        finish(replacement)
    import io
    output = io.StringIO()
    incoming, writer = os.pipe()
    os.close(writer)
    def refused():
        raise ValueError('offline after admission')
    try:
        with pytest.raises(ValueError, match='offline after admission'):
            vm_pool.keep(A, incoming=incoming, output=output, ready=refused)
        assert output.getvalue() == ''
    finally:
        os.close(incoming)
    successor = launch(pool)
    try:
        assert ready(successor) == b'acquired\n'
    finally:
        finish(successor)


def test_owned_host_command_retains_checkout_after_controller_exit(pool, tmp_path):
    import prepare_baseline as baseline
    fd = baseline.open_controller_lock(tmp_path / 'controller.lock', vm_uuid=A)
    child = waiter = None
    try:
        child = launch(pool, hold_fds=baseline.controller_descriptors(fd))
        assert ready(child) == b'retaining\n'
        baseline.close_controller_lock(fd)
        fd = None
        waiter = launch(pool)
        assert select.select([waiter.stderr], [], [], 5)[0]
        assert b'queued for VM' in waiter.stderr.readline()
        assert not select.select([waiter.stdout], [], [], 0.1)[0]
        finish(child)
        child = None
        assert ready(waiter) == b'acquired\n'
    finally:
        if fd is not None:
            baseline.close_controller_lock(fd)
        for process in (child, waiter):
            if process is not None:
                finish(process)


def test_receipt_crosses_dispatch_prefix_and_host_work_keeps_it(monkeypatch):
    import runpy
    from vm_selection import BATCH
    from tests.support.vm_registry import vm_name
    from tests.support.paths import ROOT
    dispatch = runpy.run_path(str(ROOT / 'tools/onpc-test-runner'))['selection']
    command = dispatch(ROOT, ['pool', '--no-wait', '--vm', vm_name()])
    assert command[:3] == ['/usr/bin/python3', '-B', str(ROOT / 'tools/vm_pool.py')]
    assert '--no-wait' in command and vm_name() in command
    receipt = A + ':' + 'a' * 32
    monkeypatch.setenv(vm_pool.VARIABLE, receipt)
    assert vm_pool.arguments() == [vm_pool.OPTION + receipt]
    assert vm_pool.consume([vm_pool.OPTION + receipt, '--unattended', 'system']) == [
        '--unattended', 'system']
    monkeypatch.setenv(BATCH, json.dumps({'vms': ['first', 'second']}))
    with vm_pool.selected_reservation(enabled=False):
        assert vm_pool.binding() == (A, 'a' * 32)
    with pytest.raises(ValueError, match='multi-VM batch'):
        vm_pool.check_queue(['first', 'second'])


def test_vm_artifact_helper_uses_vm_scope_before_host_activity(monkeypatch):
    import test_commands
    from vm_selection import selected, BATCH, vm_config
    branch = selected().owning_branch
    monkeypatch.setattr(vm_config, 'current_branch', lambda: branch)
    name = selected().name
    request = ['artifacts', 'prepare', '--for-vm']
    assert not test_commands.host_only_request(request)
    with pytest.raises(ValueError, match='explicit --vm'):
        test_commands.vm_request(request)
    args, vm = test_commands.vm_request([*request, '--vm', name])
    assert args == request and vm.name == name
    assert BATCH not in os.environ


@pytest.mark.parametrize('at_grant', [None, False, True, 'busy'])
@pytest.mark.parametrize('bind', [False, True])
def test_cancelled_reservation_never_enters_work_even_when_grant_is_ready(monkeypatch, at_grant, bind):
    import io
    from types import SimpleNamespace
    import dev_privileges
    import host_dispatch
    from vm_selection import selected, vm_config
    branch = selected().owning_branch
    host = selected().host
    monkeypatch.setattr(host_dispatch, 'tool_host', lambda _: host)
    monkeypatch.setattr(vm_config, 'current_branch', lambda: branch)
    receipt = A + ':' + 'a' * 32
    process = SimpleNamespace(pid=42, stdin=io.BytesIO(), stdout=io.BytesIO(
        b'' if at_grant == 'busy' else json.dumps({'checkout': receipt}).encode() + b'\n'),
        wait=lambda: vm_pool.Busy.status if at_grant == 'busy' else 0)
    process.stdin.fileno = lambda: 101
    process.stdout.fileno = lambda: 102
    spawns = []
    monkeypatch.setattr(dev_privileges, 'check', lambda _: None)
    monkeypatch.setattr(vm_pool.subprocess, 'Popen', lambda *a, **k: spawns.append(a) or process)
    monkeypatch.setattr(vm_pool.select, 'select', lambda readers, *args: (readers, [], []))
    if at_grant == 'busy':
        with pytest.raises(vm_pool.Busy):
            with vm_pool.reservation(selected().name, bind=bind, wait=False):
                pytest.fail('busy VM entered recovery')
        assert '--no-wait' in spawns[0][0]
    elif at_grant is None:
        with vm_pool.reservation(selected().name, bind=bind) as granted:
            assert granted == receipt
            assert os.environ.get(vm_pool.VARIABLE) == (receipt if bind else None)
    else:
        cancellations = iter([False, True] if at_grant else [True])
        with pytest.raises(KeyboardInterrupt):
            with vm_pool.reservation(selected().name, stopped=lambda: next(cancellations), bind=bind):
                pytest.fail('cancelled request entered the driver workflow')
    assert len(spawns) == (1 if at_grant in (None, 'busy') else int(at_grant))
    assert vm_pool.VARIABLE not in os.environ
    if at_grant is None or at_grant:
        assert process.stdin.closed and process.stdout.closed
