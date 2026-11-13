"""Host-owned compute reservations; selection policy never grants capacity.

Kernel-held tickets charge a launcher's immutable VM subset until its last
descendant exits. The privileged admission guard independently validates the
chooser's output. VM checkout borrows a ticket only for a declared member;
standalone work competes for capacity through the same guard.
"""
from contextlib import contextmanager, ExitStack
from fractions import Fraction
from decimal import Decimal, localcontext
import fcntl
import json
import os
from pathlib import Path
import random
import re
import select
import stat
import subprocess
import sys
import threading
import uuid

VARIABLE = 'ONPC_HOST_COMPUTE'
TOKENS = 'ONPC_HOST_COMPUTE_TOKENS'
OPTION = '--host-compute='
_ticket = re.compile('[0-9a-f]{32}')


def units(value):
    # Rational arithmetic preserves decimal boundaries (e.g. .1 + .2 <= .3).
    return Fraction(str(value))


def number(value):
    value = value if isinstance(value, Fraction) else units(value)
    with localcontext() as context:
        context.prec = len(str(abs(value.numerator))) + 2 * len(str(value.denominator)) + 1
        return format(Decimal(value.numerator) / Decimal(value.denominator), 'f')


def choose(vms, available, *, required=()):
    """Maximize coverage, then approach equal compute shares before utilization.

    VM-sized rounding minimizes squared distance from the equal share of the
    budget. Equal scores prefer utilization, then earlier configured families.
    Shuffle workers before finding attainable family totals: equal-cost subsets
    remain random, without sacrificing a fairer allocation to a random draw.
    """
    if sum((units(vm.compute_unit) for vm in vms), Fraction()) <= available:
        return list(vms)
    families = {}
    for vm in vms:
        families.setdefault(vm.family, []).append(vm)
    options = []
    visited = 0
    for workers in families.values():
        random.shuffle(workers)
        fixed = tuple(vm for vm in workers if vm.name in required)
        fixed_cost = sum((units(vm.compute_unit) for vm in fixed), Fraction())
        totals = {fixed_cost: fixed} if fixed_cost <= available else {}
        for vm in workers:
            if vm.name in required:
                continue
            for cost, subset in list(totals.items()):
                visited += 1
                if visited > 50000:
                    raise ValueError('host-compute: selection is too complex; narrow --vm before retrying')
                total = cost + units(vm.compute_unit)
                if total <= available:
                    totals.setdefault(total, (*subset, vm))
        options.append(totals)
    best, selected = None, ()

    def allocate(index, costs, workers, used):
        nonlocal best, selected, visited
        visited += 1
        if visited > 50000:
            raise ValueError('host-compute: selection is too complex; narrow --vm before retrying')
        if index == len(options):
            coverage = sum(cost > 0 for cost in costs)
            if not coverage:
                return
            # An exhausted family limits the common fair share. Do not spend
            # its unused share by making another family unnecessarily larger.
            share = min(available / coverage,
                        min(max(options[i]) for i, cost in enumerate(costs) if cost))
            imbalance = sum((cost - share) ** 2 for cost in costs if cost)
            score = (coverage, -imbalance, used, costs)
            if best is None or score > best:
                best, selected = score, workers
            return
        for cost, subset in options[index].items():
            if used + cost <= available:
                allocate(index + 1, (*costs, cost), (*workers, *subset), used + cost)

    allocate(0, (), (), Fraction())
    names = {vm.name for vm in selected}
    return [vm for vm in vms if vm.name in names]


def _open(directory, name, *, create=True):
    fd = os.open(directory / name, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
                 | (os.O_CREAT if create else 0), 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError('host-compute: unsafe reservation file')
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def gate():
    import vm_pool
    directory = vm_pool.RUNTIME / 'compute'
    for path in (vm_pool.RUNTIME, directory):
        path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('host-compute: unsafe runtime directory')
    fd = _open(directory, 'gate')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield directory
    finally:
        os.close(fd)


def _record(fd):
    value = json.loads(os.pread(fd, 65537, 0))
    if (not isinstance(value, dict) or set(value) != {'host', 'uid', 'vms'}
            or not isinstance(value['vms'], dict) or not value['vms']
            or any(units(cost) <= 0 for cost in value['vms'].values())):
        raise ValueError('host-compute: invalid reservation record')
    return value


def _usage(directory):
    used = Fraction()
    reserved = set()
    for path in directory.iterdir():
        if not _ticket.fullmatch(path.name):
            continue
        fd = _open(directory, path.name, create=False)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                record = _record(fd)
                used += sum((units(cost) for cost in record['vms'].values()), Fraction())
                reserved.update(record['vms'])
            else:
                # Only an unlocked, identity-checked operational ticket retires.
                path.unlink()
        finally:
            os.close(fd)
    return used, reserved


def _running(configured, host):
    """A running registered guest still occupies compute after its owner exits.

    This is a read-only census, not another capacity ledger. Manual libvirt
    mutations remain outside the participating tools' admission gate.
    """
    import libvirt
    connection = libvirt.open('qemu:///system')
    if connection is None:
        raise ValueError('host-compute: cannot inspect running guests; refusing admission')
    try:
        names = {domain.name() for domain in connection.listAllDomains() if domain.isActive()}
        return {vm.name for vm in configured.values() if vm.host.name == host.name and vm.name in names}
    finally:
        connection.close()


def _insufficient(host, used, minimum):
    available = units(host.max_compute_unit) - used
    return ValueError('\033[31mhost-compute: host ' + host.name +
        f': max_compute_unit={number(host.max_compute_unit)}, total_used_compute={number(used)}, '
        f'available_compute={number(available)}, minimum vm.compute_unit={number(minimum)}. '
        'Available compute units are insufficient to support the smallest selected VM.\033[0m')


def admit(vms, *, subset=True):
    """Independent, atomic validate-and-commit guard. Returns a locked ticket.

    The chooser cannot supply costs or totals, add foreign VMs, duplicate a VM,
    or exceed availability. All costs are reloaded from the canonical registry.
    """
    from vm_selection import vm_config
    host = vm_config.host_registry(vm_config.read_document(validate_agent=False))[
        vm_config.execution_host()]
    canonical = vm_config.registry()
    requested = []
    for vm in vms:
        current = canonical[vm.name]
        vm_config.require_online(current)
        vm_config.require_branch(current, vm_config.current_branch())
        if current != vm or current.host != host or current.name in {v.name for v in requested}:
            raise ValueError('host-compute: noncanonical or duplicate VM selection')
        requested.append(current)
    requested = [vm for vm in canonical.values() if vm.name in {v.name for v in requested}]
    if not requested:
        raise ValueError('host-compute: empty selection')
    with gate() as directory:
        used, reserved = _usage(directory)
        # Admission transfers requested, already-running guests from observed
        # occupancy to a locked reservation. Count every other unreserved guest.
        running = _running(canonical, host) - reserved
        required = running & {vm.name for vm in requested}
        external = running - required
        used += sum((units(canonical[name].compute_unit) for name in external), Fraction())
        available = units(host.max_compute_unit) - used
        minimum = min(units(vm.compute_unit) for vm in requested)
        if available < minimum:
            raise _insufficient(host, used, minimum)
        occupied = sum((units(canonical[name].compute_unit) for name in required), Fraction())
        if occupied > available:
            raise _insufficient(host, used + occupied, minimum)
        if subset:
            proposed = (choose(requested, available, required=required) if required
                        else choose(requested, available))
        else:
            proposed = requested
        names = [vm.name for vm in proposed]
        allowed = {vm.name for vm in requested}
        if not names or len(set(names)) != len(names) or not set(names) <= allowed:
            raise ValueError('host-compute: guard refused invalid scheduler selection')
        selected = [canonical[name] for name in names]
        cost = sum((units(vm.compute_unit) for vm in selected), Fraction())
        # Independently account for running guests omitted by a buggy chooser.
        omitted = required - set(names)
        untransferred = sum((units(canonical[name].compute_unit) for name in omitted), Fraction())
        if cost + untransferred > available:
            raise ValueError('\033[31mhost-compute: capacity guard refused scheduler request: '
                             f'{number(cost + untransferred)} compute units '
                             f'(selected={number(cost)}, omitted_running={number(untransferred)}) '
                             f'exceed available_compute={number(available)} '
                             f'on host {host.name} (max={number(host.max_compute_unit)}, '
                             f'used={number(used)}).\033[0m')
        token = uuid.uuid4().hex
        fd = _open(directory, token)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            value = dict(host=host.name, uid=int(os.environ.get('PKEXEC_UID', str(os.geteuid()))),
                         vms={vm.name: str(vm.compute_unit) for vm in selected})
            os.write(fd, json.dumps(value).encode())
            fcntl.flock(fd, fcntl.LOCK_SH)
            return fd, token, selected
        except BaseException:
            os.close(fd)
            raise


def borrow(vm, token):
    """Fail closed on stale proofs, foreign callers, changed costs or nonmembers."""
    if not isinstance(token, str) or not _ticket.fullmatch(token):
        raise ValueError('host-compute: invalid reservation token')
    with gate() as directory:
        fd = _open(directory, token, create=False)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise ValueError('host-compute: reservation has exited')
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            record = _record(fd)
            caller = int(os.environ.get('PKEXEC_UID', str(os.geteuid())))
            if (record['host'] != vm.host.name or record['uid'] != caller
                    or vm.name not in record['vms']
                    or units(vm.compute_unit) > units(record['vms'][vm.name])):
                raise ValueError('host-compute: VM is outside its guaranteed reservation')
            from vm_selection import vm_config
            canonical = vm_config.registry()
            used, reserved = _usage(directory)
            external = _running(canonical, vm.host) - reserved
            used += sum((units(canonical[name].compute_unit) for name in external), Fraction())
            if used > units(vm.host.max_compute_unit):
                raise ValueError('\033[31mhost-compute: capacity guard refused VM admission: '
                                 f'used_compute={number(used)} exceeds '
                                 f'max_compute_unit={number(vm.host.max_compute_unit)} '
                                 f'on host {vm.host.name}. Drain active work before reducing '
                                 'the host limit.\033[0m')
            return fd
        except BaseException:
            os.close(fd)
            raise


def claims():
    value = json.loads(os.environ.get(VARIABLE, '{}'))
    if not isinstance(value, dict):
        raise ValueError('host-compute: invalid reservation claims')
    for claim in value.values():
        if (not isinstance(claim, dict) or not _ticket.fullmatch(claim.get('token', ''))
                or not isinstance(claim.get('vms'), list)):
            raise ValueError('host-compute: invalid reservation claims')
    return value


def descriptors():
    result = []
    for claim in claims().values():
        fd = claim.get('fd')
        if type(fd) is not int or fd < 3:
            continue
        try:
            info = os.fstat(fd)
        except OSError:
            continue  # Agent shells carry membership, while their owner holds EOF.
        if (stat.S_ISFIFO(info.st_mode)
                and (info.st_dev, info.st_ino) == (claim['device'], claim['inode'])
                and fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_WRONLY):
            result.append(fd)
    return tuple(result)


def bind(vms):
    """Bind worker selection to the admitted subset; retain the original request separately."""
    from vm_selection import BATCH, select
    select(vms[0].name)
    os.environ[BATCH] = json.dumps(dict(concurrency=len(vms), vms=[vm.name for vm in vms]))


def admitted_names(run, *, fallback=None):
    """Read canonical names only; expired reservation tokens are never persisted."""
    from test_source import _read
    names = _read(run / 'admitted-vms.json', fallback)
    if names is not None and (not isinstance(names, list) or not names
            or any(not isinstance(name, str) or not name for name in names)
            or len(set(names)) != len(names)):
        raise ValueError('host-compute: invalid admitted VM selection')
    return names


def save_admitted(run, vms):
    from detached_launcher import atomic
    atomic(run / 'admitted-vms.json', [vm.name for vm in vms])


def resume_selection(vms, previous, *, fallback=None):
    names = admitted_names(previous, fallback=fallback) if previous is not None else None
    if names is None:
        return tuple(vms), False
    configured = {vm.name: vm for vm in vms}
    if not set(names) <= set(configured):
        raise ValueError('host-compute: resume requires its original admitted VMs; '
                         'the current request or availability differs')
    return tuple(configured[name] for name in names), True


def arguments():
    values = claims()
    tokens = ({host: claim['token'] for host, claim in values.items()} if values else
              json.loads(os.environ.get(TOKENS, '{}')))
    return [OPTION + json.dumps(tokens)] if tokens else []


def consume(argv):
    if argv and argv[0].startswith(OPTION):
        tokens = json.loads(argv[0][len(OPTION):])
        if (not isinstance(tokens, dict) or not tokens
                or any(not isinstance(host, str) or not isinstance(token, str)
                       or not _ticket.fullmatch(token) for host, token in tokens.items())):
            raise ValueError('host-compute: invalid reservation proofs')
        os.environ[TOKENS] = json.dumps(tokens)
        return argv[1:]
    return argv


def acquire_vm(vm):
    """The VM checkout boundary enforces membership independently of scheduling."""
    tokens = json.loads(os.environ.get(TOKENS, '{}'))
    if tokens:
        if vm.host.name not in tokens:
            raise ValueError('host-compute: VM host is outside the launcher reservation')
        token = tokens[vm.host.name]
        return borrow(vm, token), token
    fd, token, _ = admit([vm], subset=False)
    return fd, token


def restrict(vms):
    held = claims()
    if not held:
        return tuple(vms)
    result = tuple(vm for vm in vms if vm.host.name in held and vm.name in held[vm.host.name]['vms'])
    if not result:
        raise ValueError('host-compute: selection is outside the launcher reservation')
    return result


@contextmanager
def launch(vms, *, exact=False):
    """Acquire all hosts before starting; unwind every earlier host on refusal."""
    if claims():
        admitted = restrict(vms)
        if exact and {vm.name for vm in admitted} != {vm.name for vm in vms}:
            raise ValueError('host-compute: resume requires its entire original admitted VM selection')
        yield admitted
        return
    from vm_selection import vm_config
    from host_dispatch import tool_host
    root = Path(__file__).resolve().parents[1]
    groups = {}
    for vm in vms:
        groups.setdefault(vm.host, []).append(vm)
    previous = os.environ.get(VARIABLE)
    held = {}
    handed_off = False
    with ExitStack() as resources:
        def close(child):
            child.stdin.close()
            child.stdout.close()
            if handed_off:
                # Detached descendants now own EOF; reap without waiting for
                # their workflow in the admitting terminal.
                threading.Thread(target=child.wait, daemon=True).start()
            else:
                child.wait(timeout=30)
        try:
            for host, targets in groups.items():
                helper = '/usr/local/libexec/onpc-test-runner'
                command = ['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', helper,
                           'compute', *(['--exact'] if exact else []),
                           '--vm', ','.join(vm.name for vm in targets)]
                environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}
                if host.name == tool_host(root).name:
                    from dev_privileges import check
                    check(helper)
                    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             env=environment, start_new_session=True)
                else:
                    from remote_sources import RemoteVM
                    child = RemoteVM(root, host=host).pool_process(command, environment)
                resources.callback(close, child)
                if not select.select([child.stdout], [], [], 30)[0]:
                    raise ValueError('host-compute: admission timed out on ' + host.name)
                response = child.stdout.readline(65537)
                if not response:
                    raise ValueError('host-compute: host admission failed on ' + host.name +
                                     f' (status {child.wait()})')
                record = json.loads(response)
                info = os.fstat(child.stdin.fileno())
                held[host.name] = dict(record, fd=child.stdin.fileno(), device=info.st_dev, inode=info.st_ino)
                os.environ[VARIABLE] = json.dumps(held)
                print(f'host-compute: {host.name}: reserved {record["compute_unit"]} compute units; '
                      f'VMs: {", ".join(record["vms"])}', flush=True)
            yield restrict(vms)
            handed_off = True
        finally:
            if previous is None:
                os.environ.pop(VARIABLE, None)
            else:
                os.environ[VARIABLE] = previous


def keep(selector, *, exact=False):
    from vm_selection import vm_config
    _, vms = vm_config.execution(selector)
    fd, token, selected = admit(vms, subset=not exact)
    try:
        print(json.dumps(dict(token=token, vms=[vm.name for vm in selected],
                              compute_unit=number(sum((units(vm.compute_unit) for vm in selected), Fraction())))),
              flush=True)
        while os.read(0, 1):
            pass
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        options = sys.argv[1:]
        exact = options[:1] == ['--exact']
        options = options[1:] if exact else options
        if os.geteuid() != 0 or len(options) != 1:
            raise ValueError('host-compute: invoke through the test dispatcher')
        keep(options[0], exact=exact)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr, flush=True)
        sys.exit(2)
