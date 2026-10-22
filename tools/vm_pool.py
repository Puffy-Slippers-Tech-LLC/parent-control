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
import subprocess
import sys
import uuid

RUNTIME = Path('/run/onpc-vm-pool')
VARIABLE = 'ONPC_VM_CHECKOUT'
OPTION = '--vm-checkout='
_local = ContextVar('vm_checkout', default=None)


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


def _wait(fd, vm, incoming=None):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
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


def _take(vm, incoming=None, token=None):
    """New checkouts take gate then lifetime; borrowers take lifetime only."""
    gate = _open(vm, '.gate')
    fd = None
    try:
        _wait(gate, vm, incoming)
        fd = _open(vm)
        _wait(fd, vm, incoming)
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


def acquire(vm):
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
            fcntl.flock(fd, fcntl.LOCK_SH)
            if os.pread(fd, 33, 0) == held[1].encode('ascii'):
                return fd
            raise ValueError('vm-pool: reservation is no longer available')
        except BaseException:
            os.close(fd)
            raise
    return _take(vm)


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


def keep(vm, *, incoming=0, output=sys.stdout):
    """Privileged keeper. EOF checks in; active commands retain their locks."""
    fd = None
    try:
        held = binding()
        token = held[1] if held else uuid.uuid4().hex
        fd = acquire(vm) if held else _take(vm, incoming, token)
        print(json.dumps({'checkout': vm + ':' + token}), file=output, flush=True)
        while os.read(incoming, 1):
            pass
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def reservation(name, *, stopped=None):
    """Caller-side lifetime: keep checkout across builds, failures and probing."""
    from vm_selection import vm_config
    configured = vm_config.load(name)
    held = binding()
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
               *arguments(), 'pool', '--vm', configured.name]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
    previous = os.environ.get(VARIABLE)
    try:
        while not select.select([process.stdout], [], [], 0.1)[0]:
            if cancelled():
                raise KeyboardInterrupt
        line = process.stdout.readline(1024)
        if not line:
            raise ValueError('vm-pool: checkout failed (status ' + str(process.wait()) + ')')
        receipt = json.loads(line)['checkout']
        binding(receipt)
        if held is not None and receipt != previous:
            raise ValueError('vm-pool: nested checkout changed VM')
        if cancelled():
            raise KeyboardInterrupt
        os.environ[VARIABLE] = receipt
        yield
    finally:
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
    if vm is None or batch is not None and len(batch['vms']) > 1:
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
    argv, vm = vm_config.extract(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--expected-uuid')
    args = parser.parse_args(argv)
    import libvirt
    connection = libvirt.open(vm_config.URI)
    try:
        vm_uuid = identity(connection.lookupByName(vm.name).UUIDString())
        if args.expected_uuid is not None and vm_uuid != args.expected_uuid:
            raise ValueError('vm-pool: configured VM identity changed')
    finally:
        connection.close()
    return keep(vm_uuid)


if __name__ == '__main__':
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
