"""Host-wide VM checkout bookkeeping, independent of checkout paths and drivers.

The VM host owns one checkout per domain UUID. A reservation and its commands
hold shared lifetime locks; a new checkout waits for exclusive ownership.
An admission gate serializes new checkouts without blocking nested commands.
There is no daemon, persistent queue database, timeout stealing or stale-lock
cleanup. The kernel releases a checkout when its last owner closes it.
This coordinates participating drivers only; manual virt-manager use is unrestricted.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import fcntl
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import uuid

RUNTIME = Path('/run/onpc-vm-pool')
VARIABLE = 'ONPC_VM_CHECKOUT'
OPTION = '--vm-checkout='
_local = ContextVar('vm_checkout', default=None)
_keeper = ContextVar('vm_checkout_keeper', default=None)
RELOAD_KEEPER = 'ONPC_VM_RELOAD_KEEPER'


class Busy(ValueError):
    """A nonwaiting checkout found an occupied VM or admission gate."""

    status = 75


def reload_keeper():
    """The current owner can exec while its existing checkout helper stays alive."""
    return _keeper.get()


def identity(value):
    try:
        result = str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError) as error:
        raise ValueError('vm-pool: invalid VM UUID') from error
    if result != value:
        raise ValueError('vm-pool: noncanonical VM UUID')
    return result


def binding(value=None):
    value = os.environ.get(VARIABLE) if value is None else value
    if value is None:
        return None
    vm, separator, token = value.partition(':')
    identity(vm)
    if not separator or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('vm-pool: invalid checkout receipt')
    return vm, token


def arguments():
    value = os.environ.get(VARIABLE)
    if value is None:
        return []
    binding(value)
    return [OPTION + value]


def check_queue(vms):
    if binding() is not None and len(vms) > 1:
        raise ValueError('vm-pool: a reserved driver cannot request a multi-VM batch')


def check_attachment(record):
    """Never join a workflow that may be queued behind this driver itself."""
    if binding() is not None and record.get('vm_checkout') != os.environ[VARIABLE]:
        raise ValueError('vm-pool: active workflow belongs to another reservation; '
                         'check in before attaching, or cancel it outside this reservation')


def consume(argv):
    """pkexec deliberately clears environment; dispatchers carry one receipt."""
    if argv and argv[0].startswith(OPTION):
        value = argv[0][len(OPTION):]
        binding(value)
        os.environ[VARIABLE] = value
        return argv[1:]
    return argv


def _open(vm, suffix='.lock'):
    identity(vm)
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    return os.open(RUNTIME / (vm + suffix),
                   os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)


def _wait(fd, vm, incoming=None, *, wait=True):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if not wait:
            raise Busy('vm-pool: VM busy: ' + vm)
        print('vm-pool: queued for VM ' + vm, file=sys.stderr, flush=True)
        if incoming is None:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return
        while True:
            if select.select([incoming], [], [], 0.1)[0] and not os.read(incoming, 1):
                raise KeyboardInterrupt
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                pass


def _take(vm, incoming=None, token=None, *, wait=True):
    """New checkouts take gate then lifetime; borrowers take lifetime only."""
    gate = _open(vm, '.gate')
    fd = None
    try:
        _wait(gate, vm, incoming, wait=wait)
        fd = _open(vm)
        _wait(fd, vm, incoming, wait=wait)
        os.ftruncate(fd, 0)
        if token is not None:
            os.pwrite(fd, token.encode('ascii'), 0)
            # Hold admission through the conversion: flock conversion itself
            # may release exclusive ownership before granting shared ownership.
            fcntl.flock(fd, fcntl.LOCK_SH)
        return fd
    except BaseException:
        if fd is not None:
            os.close(fd)
        raise
    finally:
        os.close(gate)


def acquire(vm, *, wait=True):
    """Checkout one VM, or borrow this driver's existing reservation.

    A request hierarchy may reserve exactly one VM. Refusing a cross-VM nested
    checkout before waiting rules out A-holds-X/waits-Y versus B-holds-Y/waits-X.
    Parallel VM workers use separate reservations, never a batch-wide checkout.
    """
    identity(vm)
    local = _local.get()
    if local is not None and local[2] == os.getpid():
        if local[0] != vm:
            raise ValueError('vm-pool: check in the reserved VM before requesting another VM')
        return os.dup(local[1])
    held = binding()
    if held is not None:
        if held[0] != vm:
            raise ValueError('vm-pool: check in the reserved VM before requesting another VM')
        fd = _open(vm)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | (0 if wait else fcntl.LOCK_NB))
            except BlockingIOError:
                raise Busy('vm-pool: VM busy: ' + vm)
            if os.pread(fd, 33, 0) == held[1].encode('ascii'):
                return fd
            raise ValueError('vm-pool: reservation is no longer available')
        except BaseException:
            os.close(fd)
            raise
    return _take(vm, wait=wait)


@contextmanager
def checkout(vm):
    """Keep preprocessing and controller acquisition within one checkout."""
    fd = acquire(vm)
    token = _local.set((vm, fd, os.getpid()))
    try:
        yield
    finally:
        _local.reset(token)
        os.close(fd)


def keep(vm, *, incoming=0, output=sys.stdout, wait=True, ready=None):
    """Privileged keeper. EOF checks in; active commands retain their locks."""
    fd = None
    try:
        held = binding()
        token = held[1] if held else uuid.uuid4().hex
        fd = acquire(vm, wait=wait) if held else _take(vm, incoming, token, wait=wait)
        if ready is not None:
            ready()
        print(json.dumps({'checkout': vm + ':' + token}), file=output, flush=True)
        while os.read(incoming, 1):
            pass
        return 0
    except Busy as error:
        print(str(error), file=sys.stderr, flush=True)
        return Busy.status
    except KeyboardInterrupt:
        return 130
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def reservation(name, *, stopped=None, bind=True, wait=True):
    """Caller-side lifetime: keep checkout across builds, failures and probing."""
    from vm_selection import vm_config
    configured = vm_config.load(name)
    held = binding()
    if held is None:
        vm_config.require_online(configured)
    if held is None and configured.owning_branch:
        vm_config.require_branch(configured, vm_config.current_branch())
    def cancelled():
        return stopped is not None and (stopped() if callable(stopped) else stopped.is_set())
    if cancelled():
        raise KeyboardInterrupt
    # Root stages resolve/compare UUIDs in acquire(); a nested caller must still
    # ask the host to verify that a selector names its reserved VM.
    helper = '/usr/local/libexec/onpc-test-runner'
    from dev_privileges import check
    check(helper)
    command = ['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
               *arguments(), 'pool', *([] if wait else ['--no-wait']), '--vm', configured.name]
    inherited = os.environ.pop(RELOAD_KEEPER, None)
    if inherited is not None:
        saved = json.loads(inherited)
        if (saved['name'] != configured.name or saved['receipt'] != os.environ.get(VARIABLE)
                or saved['pid'] <= 1 or saved['input'] < 3 or saved['output'] < 3
                or saved['input'] == saved['output']):
            raise ValueError('vm-pool: invalid inherited checkout keeper')
        if any(not stat.S_ISFIFO(os.fstat(saved[key]).st_mode) for key in ('input', 'output')):
            raise ValueError('vm-pool: inherited checkout keeper is not a pipe')
        if os.waitpid(saved['pid'], os.WNOHANG) != (0, 0):
            raise ValueError('vm-pool: inherited checkout keeper exited')
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
    previous = os.environ.get(VARIABLE)
    token = None
    try:
        while not select.select([process.stdout], [], [], 0.1)[0]:
            if cancelled():
                raise KeyboardInterrupt
        line = process.stdout.readline(1024)
        if not line:
            status = process.wait()
            if status == Busy.status:
                raise Busy('vm-pool: VM busy: ' + configured.name)
            raise ValueError('vm-pool: checkout failed (status ' + str(status) + ')')
        receipt = json.loads(line)['checkout']
        binding(receipt)
        if held is not None and receipt != previous:
            raise ValueError('vm-pool: nested checkout changed VM')
        if cancelled():
            raise KeyboardInterrupt
        if bind:
            os.environ[VARIABLE] = receipt
        token = _keeper.set(dict(name=configured.name, receipt=receipt, pid=process.pid,
                                 input=process.stdin.fileno(), output=process.stdout.fileno()))
        if inherited is not None:
            # Borrow and verify through the ordinary host helper before joining
            # the pre-exec helper. At least one keeper holds the same checkout.
            os.close(saved['input'])
            os.close(saved['output'])
            if os.waitstatus_to_exitcode(os.waitpid(saved['pid'], 0)[1]):
                raise ValueError('vm-pool: inherited checkout checkin failed')
        yield receipt
    finally:
        if token is not None:
            _keeper.reset(token)
        if bind:
            if previous is None:
                os.environ.pop(VARIABLE, None)
            else:
                os.environ[VARIABLE] = previous
        process.stdin.close()
        process.stdout.close()
        status = process.wait()
        if status and sys.exc_info()[0] is None:
            raise ValueError('vm-pool: checkin failed (status ' + str(status) + ')')


@contextmanager
def selected_reservation(*, enabled=True, stopped=None):
    """Batches reserve nothing; each independently scheduled worker checks out."""
    from vm_selection import BATCH, selected
    batch = json.loads(os.environ[BATCH]) if BATCH in os.environ else None
    vm = selected(required=False) if enabled else None
    if vm is None or batch is not None:
        if enabled and binding() is not None and batch is not None and len(batch['vms']) > 1:
            raise ValueError('vm-pool: a reserved driver cannot request a multi-VM batch')
        yield
    else:
        with reservation(vm.name, stopped=stopped):
            yield


def host_main(argv=None):
    """Fixed dispatcher action; VM identity is resolved on the VM host."""
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
    import vm_config
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['--retire-domain-state']:
        parser = argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument('--retire-domain-state', required=True)
        parser.add_argument('--expected-uuid')
        args = parser.parse_args(argv)
        name = vm_config.validate_name(args.retire_domain_state)
        import prepare_baseline as base
        directory = vm_config.STATE_ROOT / name
        phase = directory / 'phase.json'
        if not os.path.lexists(directory):
            return 0
        base.private_baseline_directory(directory)
        expected = None
        if os.path.lexists(phase):
            base.identity(phase, private=True, mode=0o600)
            expected = json.loads(phase.read_bytes())['source']['layout']['uuid']
        elif set(path.name for path in directory.iterdir()) - {'.lock'}:
            raise ValueError('vm-pool: missing baseline identity; preserve state')
        import libvirt
        connection = libvirt.open(vm_config.URI)
        try:
            current = identity(connection.lookupByName(name).UUIDString())
        finally:
            connection.close()
        if args.expected_uuid is not None and identity(args.expected_uuid) != current:
            raise ValueError('vm-pool: provisioning VM identity changed')
        expected = identity(expected if expected is not None else current)
        def retire():
            connection = libvirt.open(vm_config.URI)
            try:
                domain = connection.lookupByName(name)
                if domain.UUIDString() != current or domain.isActive():
                    raise ValueError('vm-pool: state retirement requires the same powered-off VM')
                if expected != current:
                    try:
                        connection.lookupByUUIDString(expected)
                    except libvirt.libvirtError as error:
                        if error.get_error_code() != libvirt.VIR_ERR_NO_DOMAIN:
                            raise
                    else:
                        raise ValueError('vm-pool: old VM still exists; preserve its state')
                retire_domain_state(name, expected, checkout_uuid=current)
            finally:
                connection.close()
        from types import SimpleNamespace
        from e2e_watch import begin
        from watch_activity import operation
        vm_config.select(name)
        with operation('Retiring completed state for a recreated VM'), checkout(current):
            holder = SimpleNamespace(watch=None)
            begin(holder)
            try:
                retire()
            finally:
                if holder.watch is not None:
                    holder.watch.close()
        return 0
    if argv[:1] == ['--provision-domain']:
        parser = argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument('--provision-domain', required=True)
        parser.add_argument('--expected-uuid', required=True)
        args = parser.parse_args(argv)
        name = vm_config.validate_name(args.provision_domain)
        expected = identity(args.expected_uuid)
        import libvirt
        def ready():
            connection = libvirt.open(vm_config.URI)
            try:
                domain = connection.lookupByName(name)
                if domain.UUIDString() != expected or domain.isActive():
                    raise ValueError('vm-pool: provisioning requires the same powered-off VM')
            finally:
                connection.close()
        ready()
        return keep(expected, ready=ready)
    argv, vm = vm_config.extract(argv)
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--expected-uuid')
    parser.add_argument('--no-wait', action='store_true')
    args = parser.parse_args(argv)
    if binding() is None:
        vm_config.require_online(vm)
    import libvirt
    connection = libvirt.open(vm_config.URI)
    try:
        vm_uuid = identity(connection.lookupByName(vm.name).UUIDString())
        if args.expected_uuid is not None and vm_uuid != args.expected_uuid:
            raise ValueError('vm-pool: configured VM identity changed')
    finally:
        connection.close()
    def ready():
        # Queueing is not acquisition: recheck eligibility before granting work.
        current = vm_config.load(vm.name)
        if binding() is None:
            vm_config.require_online(current)
            if current.owning_branch:
                vm_config.require_branch(current, vm_config.current_branch())
        verified = libvirt.open(vm_config.URI)
        try:
            if identity(verified.lookupByName(current.name).UUIDString()) != vm_uuid:
                raise ValueError('vm-pool: configured VM identity changed while queued')
        finally:
            verified.close()
    return keep(vm_uuid, wait=not args.no_wait, ready=ready)


def retire_domain_state(name, expected, *, checkout_uuid=None):
    """Retire completed provenance, preserving it outside the active VM name.

    Called only by the fixed provisioning dispatcher under the current VM checkout.
    Keep the old directory intact for diagnosis; never delete test artifacts.
    """
    import prepare_baseline as base
    import vm_config
    directory = vm_config.STATE_ROOT / vm_config.validate_name(name)
    if not os.path.lexists(directory):
        return
    original = base.private_baseline_directory(directory)
    configured = vm_config.load(name)
    vm_config.require_branch(configured, vm_config.current_branch())
    compatibility = base.compatibility_lock(directory)
    descriptor = None
    try:
        descriptor = base.open_controller_lock(directory / '.lock', vm_uuid=checkout_uuid or expected)
        base.Capture(None, None, None, anchor=Path('/unused'),
                     directory=directory).require_idle_attempt()
        phase = directory / 'phase.json'
        if os.path.lexists(phase):
            base.identity(phase, private=True, mode=0o600)
            state = json.loads(phase.read_bytes())
            base.require(state.get('phase') == 'finalized' and
                         state['source']['layout']['uuid'] == expected,
                         'state:provisioning-baseline-identity')
        else:
            base.require(set(path.name for path in directory.iterdir()) <= {'.lock'},
                         'state:provisioning-missing-baseline')
        for path in directory.rglob('*'):
            if path.is_dir() and not path.is_symlink():
                base.private_baseline_directory(path)
            else:
                base.identity(path, private=True, mode=0o600)
        base.require(base.private_baseline_directory(directory) == original,
                     'state:provisioning-directory-changed')
        retired = directory.with_name('.retired-newvm-' + name + '-' + uuid.uuid4().hex)
        os.rename(directory, retired)
        base.sync_directory(directory.parent)
        print('vm-pool: retired old VM state to ' + str(retired), file=sys.stderr, flush=True)
    finally:
        if descriptor is not None:
            base.close_controller_lock(descriptor)
        if compatibility is not None:
            os.close(compatibility)


if __name__ == '__main__':
    # Controller helpers import this module to borrow our in-process checkout.
    # Share the running instance rather than creating a second set of ContextVars.
    sys.modules['vm_pool'] = sys.modules[__name__]
    import signal
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        sys.exit(host_main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (ValueError, OSError) as error:
        print('vm-pool: ' + str(error), file=sys.stderr)
        sys.exit(2)
