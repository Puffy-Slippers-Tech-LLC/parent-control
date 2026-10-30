"""Explicit checkout-wide restart for the public test and repair launchers."""

from contextlib import ExitStack, contextmanager
import fcntl
import json
import os
import re
import stat
import subprocess
import time
import threading

import detached_launcher as launcher
from test_storage import directory

_startup_lock = threading.RLock()
_startup_fd = None


@contextmanager
def startup(root):
    """Serialize public startup with reset, reentrantly in the same caller."""
    global _startup_fd
    with _startup_lock:
        if _startup_fd is not None:
            yield
            return
        with launcher.lock(directory('state', root=root) / 'test-startup-gate') as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _startup_fd = fd
            try:
                yield
            finally:
                _startup_fd = None


def remove(path):
    """Retire only private regular metadata, never follow a replacement link."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_nlink != 1):
        raise ValueError(f'reset: unsafe metadata: {path}')
    path.unlink()


def succeeded(run, *, repair):
    """A final success is published only after the owner's cleanup completes."""
    try:
        if repair:
            saved = json.loads((run / 'result.json').read_text())
            return isinstance(saved, dict) and type(saved.get('status')) is int and saved['status'] == 0
        return int((run / 'result').read_text()) == 0
    except (OSError, ValueError):
        return False


def reset(root, start, *, host_only, selector=None):
    """Drain owners before recovery; leave source edits and historical logs intact.

    Gates exclude concurrent startup while cleanup retires current pointers and
    progress. Kernel locks remain in place. An interrupted reset is repeatable:
    no pointer or fence is removed until maintained recovery has succeeded.
    """
    import test_activity
    from fix_tests_queue import source_directory
    from vm_selection import vm_config

    if test_activity.descriptors() or any(key in os.environ for key in (
            test_activity.VARIABLE, test_activity.HOST_VARIABLE)):
        raise ValueError('reset: requires an independent public invocation')
    names = set()
    if not host_only:
        names.update(vm.name for vm in vm_config.execution(selector)[1])
    print('Reset: stopping test and repair owners in this checkout; waiting for cleanup.', flush=True)
    while True:
        with startup(root):
            scopes = [directory(kind, root=root) for kind in
                      ('fix-tests', 'fix-tests-host', 'sessions', 'sessions-host')]
            scopes.extend(sorted(scopes[2].glob('vm-*')))
            repair_scopes = set(scopes[:2])
            legacy = root / 'artifacts/fix-tests'
            if legacy.exists():
                scopes.append(legacy)
                repair_scopes.add(legacy)
            scopes = [launcher.private_directory(path) for path in scopes]
            with ExitStack() as stack:
                active = False
                for scope in scopes:
                    gate = stack.enter_context(launcher.lock(scope / 'gate'))
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    run = launcher.current_run(scope)
                    if run is None:
                        if scope in repair_scopes:
                            owner = stack.enter_context(launcher.lock(scope / 'owner'))
                            if launcher.busy(owner):
                                raise ValueError('reset: active repair owner has no valid run record')
                        continue
                    owner_path = scope / 'owner' if scope in repair_scopes else run / 'owner'
                    owner = stack.enter_context(launcher.lock(owner_path))
                    if launcher.busy(owner):
                        (run / 'cancel').touch(mode=0o600)
                        active = True
                    elif succeeded(run, repair=scope in repair_scopes):
                        # Completed history owns no runtime leftovers. Its old
                        # VM may now belong to another branch or leave the registry.
                        continue
                    if scope in repair_scopes:
                        binding = run / 'vm.json'
                        record = json.loads(binding.read_text()) if binding.exists() else {'vm': None}
                        if not isinstance(record, dict) or set(record) != {'vm'}:
                            raise ValueError(f'reset: invalid VM binding: {binding}')
                        value = record['vm']
                        selected_names = value.get('vms') if isinstance(value, dict) else [value] if value else []
                        if not isinstance(selected_names, list) or any(not isinstance(name, str) or not name for name in selected_names):
                            raise ValueError(f'reset: invalid VM selection: {binding}')
                        names.update(selected_names)
                    else:
                        record = json.loads((scope / 'current.json').read_text())
                        if (not isinstance(record, dict) or not isinstance(record.get('argv'), list)
                                or any(not isinstance(arg, str) for arg in record['argv'])):
                            raise ValueError(f'reset: invalid test selection: {scope}')
                        _, selected = vm_config.extract_selector(record.get('argv', []))
                        if selected is not None:
                            names.update(vm.name for vm in vm_config.execution(selected)[1])
                        batch = record.get('vm_batch')
                        if batch:
                            if (not isinstance(batch, dict) or not isinstance(batch.get('vms'), list)
                                    or any(not isinstance(name, str) or not name for name in batch['vms'])):
                                raise ValueError(f'reset: invalid VM queue: {scope}')
                            names.update(batch['vms'])
                if not active:
                    _clean(root, scopes, names, stack, source_directory(root))
            if not active:
                return start()
        time.sleep(.1)


@contextmanager
def idle_resources(root, source):
    """Exclude independent host tests, VM workers and checkout repair writers."""
    activity = root / 'artifacts/test-activity'
    if any(path.is_symlink() for path in (activity, *activity.parents)):
        raise ValueError('reset: test activity path contains a symlink')
    activity.mkdir(parents=True, exist_ok=True)
    launcher.private_directory(source)
    with ExitStack() as locks:
        for path in (activity / 'host.lock', activity / 'lock', source / 'repair-owner',
                     source / 'repair-queue-gate'):
            fd = locks.enter_context(launcher.lock(path))
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('reset: another workflow still owns checkout resources; retry after its cleanup') from error
        yield


def _clean(root, scopes, names, stack, source):
    from test_storage import reset_orphan_scratch
    with idle_resources(root, source):
        removed = reset_orphan_scratch(root=root)
    if removed:
        print(f'Reset: removed {removed} empty orphan scratch allocation(s).', flush=True)
    state = directory('state', root=root)
    # A former queue may retain claims for VMs no longer in a current pointer.
    # Recover those exact VM owners before retiring their claim checkpoints.
    for path in sorted(state.glob('run-tests-family-vm-*')):
        if not re.fullmatch(r'run-tests-family-vm-[0-9a-f]{24}', path.name):
            continue
        launcher.private_directory(path)
        record = path / 'current.json'
        if record.exists():
            saved = json.loads(record.read_text())
            if not isinstance(saved, dict):
                raise ValueError(f'reset: invalid retained VM checkpoint: {record}')
            claims = saved.get('queue_claims', {})
            if not isinstance(claims, dict) or any(not isinstance(name, str) or not name for name in claims.values()):
                raise ValueError(f'reset: invalid retained VM claims: {record}')
            names.update(claims.values())
    # Reuse recovery's VM leases, lifecycle guards, journals and claim recovery.
    command = [str(root / 'tools/cleanup-e2e')]
    command += ['--vm', ','.join(sorted(names))] if names else ['--host-only']
    status = subprocess.run(command, cwd=root, env=launcher.environment(),
                            stdin=subprocess.DEVNULL,
                            pass_fds=launcher.scratch_descriptors(), check=False).returncode
    if status:
        raise ValueError(f'reset: owned recovery failed (status={status}); state preserved; retry --reset')
    # Recovery borrows/acquires its own activity locks; exclude others again
    # before changing checkpoints, without holding those locks across recovery.
    stack.enter_context(idle_resources(root, source))
    for path in sorted(state.iterdir()):
        if re.fullmatch(r'(?:run-tests(?:-family)?|fix-tests)-(?:host|vm)-[0-9a-f]{24}|(?:run-tests|fix-tests)-request', path.name):
            launcher.private_directory(path)
            for record in path.iterdir():
                if record.suffix in ('.json', '.tmp'):
                    remove(record)
    # Abandon the previous repair transaction, preserving its edits as input to
    # the new verification. Old checkpoints remain historical, unreachable by resume.
    for scope in scopes:
        remove(scope / 'current.json')
        remove(scope / 'current.tmp')
    launcher.atomic(source / 'repair-generation.json', 0)
    remove(source / 'repair-source-pending.json')
    print('Reset: recovery complete; saved test and repair progress cleared; starting fresh.', flush=True)
