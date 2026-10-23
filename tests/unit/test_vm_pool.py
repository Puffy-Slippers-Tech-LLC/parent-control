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

import pytest
import vm_pool

A = 'f95890e1-88e7-4779-8ae3-53fdcc34330a'
B = 'f95890e1-88e7-4779-8ae3-53fdcc34330b'


@pytest.fixture
def pool(tmp_path, monkeypatch):
    monkeypatch.setattr(vm_pool, 'RUNTIME', tmp_path / 'pool')
    return vm_pool.RUNTIME


def launch(pool, vm=A, *, keeper=False, cwd=None, hold_fds=()):
    code = '''import os,sys,pathlib
sys.path.insert(0,sys.argv[1])
import vm_pool
vm_pool.RUNTIME=pathlib.Path(sys.argv[2])
if sys.argv[4]=='keep':
    sys.exit(vm_pool.keep(sys.argv[3]))
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
        'hold' if hold_fds else 'keep' if keeper else 'take'],
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
        third = launch(pool, B, cwd=second_root)
        assert ready(third) == b'acquired\n'
        finish(first)
        first = None
        assert ready(second) == b'acquired\n'
    finally:
        for child in (first, third, second):
            if child is not None:
                finish(child)


@pytest.mark.parametrize('crash', [False, True])
def test_reservation_survives_commands_and_keeper_exit_until_last_borrower(pool, monkeypatch, crash):
    keeper = launch(pool, keeper=True)
    waiter = None
    borrowed = None
    try:
        receipt = json.loads(ready(keeper))['checkout']
        monkeypatch.setenv(vm_pool.VARIABLE, receipt)
        borrowed = vm_pool.acquire(A)
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
    from vm_selection import BATCH
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
    from vm_selection import selected, BATCH
    name = selected().name
    request = ['artifacts', 'prepare', '--for-vm']
    assert not test_commands.host_only_request(request)
    with pytest.raises(ValueError, match='explicit --vm'):
        test_commands.vm_request(request)
    args, vm = test_commands.vm_request([*request, '--vm', name])
    assert args == request and vm.name == name
    assert BATCH not in os.environ


@pytest.mark.parametrize(('requested', 'enabled'), [(['unit'], False), (['system'], True), ([], True)])
@pytest.mark.parametrize('cancelled', [False, True])
def test_repair_worker_retains_reservation_and_finishes_queued_cancellation(
        tmp_path, monkeypatch, requested, enabled, cancelled):
    from contextlib import contextmanager
    import fix_tests
    active = []
    @contextmanager
    def reserve(**kwargs):
        assert kwargs['enabled'] is enabled
        active.append(True)
        try:
            if cancelled:
                raise KeyboardInterrupt
            yield
        finally:
            active.pop()
    monkeypatch.setattr(vm_pool, 'selected_reservation', reserve)
    def execute(*args, reloading=False):
        assert reloading is False
        assert active == [True]
        assert not (tmp_path / 'result.json').exists()
        return 7
    monkeypatch.setattr(fix_tests, 'reserved_worker', execute)
    fix_tests.TaskBudget(tmp_path).initialize(None)
    owner = os.open(tmp_path / 'owner', os.O_RDWR | os.O_CREAT, 0o600)
    expected = 130 if cancelled else 7
    assert fix_tests.worker(tmp_path, tmp_path, owner, 'model', 'high', 'model',
                            json.dumps(requested)) == expected
    assert active == []
    assert json.loads((tmp_path / 'result.json').read_text()) == {'status': expected, 'tasks': 0}
    with pytest.raises(OSError):
        os.fstat(owner)


@pytest.mark.parametrize('at_grant', [False, True])
def test_cancelled_reservation_never_enters_work_even_when_grant_is_ready(monkeypatch, at_grant):
    import io
    from types import SimpleNamespace
    import dev_privileges
    from vm_selection import selected
    receipt = A + ':' + 'a' * 32
    process = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO(
        json.dumps({'checkout': receipt}).encode() + b'\n'), wait=lambda: 0)
    spawns = []
    monkeypatch.setattr(dev_privileges, 'check', lambda _: None)
    monkeypatch.setattr(vm_pool.subprocess, 'Popen', lambda *a, **k: spawns.append(a) or process)
    monkeypatch.setattr(vm_pool.select, 'select', lambda readers, *args: (readers, [], []))
    cancellations = iter([False, True] if at_grant else [True])
    with pytest.raises(KeyboardInterrupt):
        with vm_pool.reservation(selected().name, stopped=lambda: next(cancellations)):
            pytest.fail('cancelled request entered the driver workflow')
    assert len(spawns) == int(at_grant)
    assert vm_pool.VARIABLE not in os.environ
    if at_grant:
        assert process.stdin.closed and process.stdout.closed


@pytest.mark.parametrize('cleanup_status, run_status', [(0, 0), (0, 1), (1, None)])
def test_vm_worker_recovers_under_its_reservation_before_testing(monkeypatch, cleanup_status, run_status):
    from contextlib import contextmanager, nullcontext
    from unittest.mock import Mock
    import test_commands
    import test_checkpoint
    import test_recovery
    import vm_test_queue
    from vm_selection import selected
    events = []
    @contextmanager
    def reserve(*args, **kwargs):
        events.append('checkout')
        try:
            yield
        finally:
            events.append('checkin')
    monkeypatch.setattr(vm_pool, 'reservation', reserve)
    control = Mock()
    control.stopped.is_set.return_value = False
    control.installed.return_value = nullcontext(control)
    monkeypatch.setattr(vm_test_queue, 'Control', lambda: control)
    monkeypatch.setattr(vm_test_queue.test_activity, 'activity', lambda *a, **k: nullcontext())
    monkeypatch.setattr(test_recovery, 'cleanup', lambda root: events.append('recovery') or cleanup_status)
    monkeypatch.setattr(test_checkpoint, 'Checkpoint', Mock())
    monkeypatch.setattr(test_commands, '_main', lambda *a, **k: events.append('test') or run_status)
    # worker replaces stdout with its frame adapter; restore it after the call.
    monkeypatch.setattr(sys, 'stdout', sys.stdout)
    assert vm_test_queue.worker(['--execute', selected().name, 'system']) == (cleanup_status or run_status)
    assert events == ['checkout', 'recovery', *(['test'] if not cleanup_status else []), 'checkin']
