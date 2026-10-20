"""Two-phase preparation intent, with native-owned acquisition and publication.

This service never admits a session or writes V, I, or ready. Native must check
every returned record against its independently captured authority. A successful
manager response transfers the exact incomplete-copy cleanup ticket to native;
unsent responses retain Python's ordinary identity-owned scratch cleanup.
"""
from contextlib import contextmanager
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import time

import kiosk_confinement as confinement
import kiosk_view_receipt as receipt
from kiosk_preparation_input import PreparationExchange, REFUSAL_REASONS


MAX_BYTES = receipt.MAX_BYTES
MAX_ACCOUNT_GROUPS = 128


def _before(deadline_ns):
    if type(deadline_ns) is not int or not 0 < deadline_ns < 2**64:
        raise ValueError('preparation-deadline')
    remaining = deadline_ns - time.monotonic_ns()
    if remaining <= 0:
        raise TimeoutError('preparation-deadline')
    return remaining / 1_000_000_000


@contextmanager
def _deadline(deadline_ns):
    """Bound legacy measurement/copy walks by the same original deadline.

    The dedicated single-thread preparation process owns its alarm. An existing
    timer is refused rather than replaced or renewed. Explicit I/O and skeleton
    loops additionally check the absolute monotonic clock.
    """
    remaining = _before(deadline_ns)
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError('preparation-existing-timer')
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signal, _frame):
        raise TimeoutError('preparation-deadline')

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, remaining)
        yield
        _before(deadline_ns)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _canonical(record, deadline_ns):
    parts, length = [], 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                               allow_nan=False)
    for part in encoder.iterencode(record):
        _before(deadline_ns)
        data = part.encode('ascii')
        length += len(data)
        if length > MAX_BYTES:
            raise ValueError('preparation-record-limit')
        parts.append(data)
    return b''.join(parts)


def _read(fd, deadline_ns):
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_BYTES:
        raise ValueError('preparation-record-limit')
    parts, offset = [], 0
    while offset < before.st_size:
        _before(deadline_ns)
        data = os.pread(fd, min(65536, before.st_size - offset), offset)
        if not data:
            raise ValueError('preparation-record-changed')
        parts.append(data)
        offset += len(data)
    if confinement.file_identity(os.fstat(fd)) != confinement.file_identity(before):
        raise ValueError('preparation-record-changed')
    _before(deadline_ns)
    return b''.join(parts)


def _json(fd, deadline_ns):
    data = _read(fd, deadline_ns)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('preparation-record-schema')
            result[key] = value
        return result

    record = json.loads(data, object_pairs_hook=unique)
    if _canonical(record, deadline_ns) != data:
        raise ValueError('preparation-record-canonical')
    return record


@contextmanager
def _record(data, deadline_ns):
    """A sealed, read-only CLOEXEC anonymous record; never a pathname result."""
    if type(data) is not bytes or not 0 < len(data) <= MAX_BYTES:
        raise ValueError('preparation-record-limit')
    writer = os.memfd_create('onpc-preparation', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    reader = -1
    try:
        offset = 0
        while offset < len(data):
            _before(deadline_ns)
            count = os.write(writer, data[offset:offset + 65536])
            if count <= 0:
                raise OSError('preparation-record-write')
            offset += count
        fcntl.fcntl(writer, fcntl.F_ADD_SEALS, fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                    fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        reader = os.open('/proc/self/fd/' + str(writer), os.O_RDONLY | os.O_CLOEXEC)
        os.close(writer)
        writer = -1
        _before(deadline_ns)
        yield reader
    finally:
        if reader >= 0:
            os.close(reader)
        if writer >= 0:
            os.close(writer)


def _account(deadline_ns):
    """Resolve NSS only in this bounded child; export one finite canonical set."""
    _before(deadline_ns)
    account = pwd.getpwnam(confinement.ACCOUNT)
    marker = confinement.trusted('/var/lib/oh-no-parent-control/package-created-kiosk-uid')
    info = marker.stat()
    if (account.pw_uid == 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or
            marker.read_text().strip() != str(account.pw_uid)):
        raise ValueError('unowned-account')
    groups = sorted(set(os.getgrouplist(confinement.ACCOUNT, account.pw_gid)))
    _before(deadline_ns)
    if (not 0 < account.pw_uid < 2**32 - 1 or not 0 < account.pw_gid < 2**32 - 1 or
            not 0 < len(groups) <= MAX_ACCOUNT_GROUPS or account.pw_gid not in groups or
            any(type(group) is not int or not 0 < group < 2**32 - 1 for group in groups)):
        raise ValueError('preparation-account')
    # Match provisioning's ADMIN_GROUPS contract, plus the root group. Resolve
    # only this already bounded set through NSS under the original child alarm;
    # unknown/error results refuse rather than produce a partial identity.
    for group in groups:
        _before(deadline_ns)
        entry = grp.getgrgid(group)
        _before(deadline_ns)
        if entry.gr_gid != group or entry.gr_name in ('root', 'sudo', 'adm', 'wheel'):
            raise ValueError('preparation-account')
    return (f'ONPC-KIOSK-ACCOUNT\t1\t{account.pw_uid}\t{account.pw_gid}\t{len(groups)}\n' +
            ''.join(f'{group}\n' for group in groups)).encode('ascii')


def measure(role, deadline_ns):
    """Use the established owned-account, attestation and enforcement checks."""
    _before(deadline_ns)
    if os.geteuid() != 0 or role not in ('manager', 'gate'):
        raise ValueError('invalid-caller')
    identity = _account(deadline_ns)
    try:
        attestation = subprocess.run(
            ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'verify'],
            env=confinement.ENV, check=True, capture_output=True, text=True,
            timeout=min(5, _before(deadline_ns)))
    except subprocess.CalledProcessError as error:
        # Only this actual attestation call owns the specific closed cause.
        raise ValueError('attestation-command-failed') from error
    paths = [confinement.PAYLOAD / 'config.json']
    fd = confinement.runtime_open(confinement.trusted(paths[0]))
    try:
        config_bytes = _read(fd, deadline_ns)
    finally:
        os.close(fd)
    config = json.loads(config_bytes)
    if config.get('backend') not in ('apparmor', 'selinux'):
        raise ValueError('unknown-backend')
    policy_path = confinement.PAYLOAD / ('onpc-kiosk.cil' if config['backend'] == 'selinux'
                                       else 'onpc-kiosk.apparmor')
    fd = confinement.runtime_open(confinement.trusted(policy_path))
    try:
        policy_bytes = _read(fd, deadline_ns)
    finally:
        os.close(fd)
    snapshot = confinement.required_material(config_bytes, policy_bytes, attestation.stdout)
    _before(deadline_ns)
    return snapshot, config_bytes, identity


def _view(fd, deadline_ns):
    data = _read(fd, deadline_ns)
    lines = data.decode('utf-8').splitlines()
    if not lines or len(lines) > receipt.MAX_ROWS + 1:
        raise ValueError('preparation-view-schema')
    header = lines[0].split('\t')
    if len(header) != 8 or header[:3] != ['ONPC-KIOSK-RECEIPT', '2', 'V']:
        raise ValueError('preparation-view-schema')
    value = dict(format=2, kind='V', backend=header[3], role=header[4],
                 material=header[5], source=header[6], acquisition=header[7], nodes=[], coverage=[])
    for line in lines[1:]:
        _before(deadline_ns)
        fields = line.split('\t')
        if fields[0] == 'N':
            names, target = receipt.NODE_FIELDS, value['nodes']
            numeric = set(names[6:18]) | {'required', 'mountpoint'}
        elif fields[0] == 'C':
            names, target = receipt.COVERAGE_FIELDS, value['coverage']
            numeric = set(names) - {'path'}
        else:
            raise ValueError('preparation-view-schema')
        if len(fields) != len(names) + 1:
            raise ValueError('preparation-view-schema')
        target.append({name: int(part) if name in numeric else part
                       for name, part in zip(names, fields[1:])})
    receipt.validate_receipt(value)
    if receipt.encode_receipt(value) != data:
        raise ValueError('preparation-view-canonical')
    return value


def retained_plan(snapshot, selection, deadline_ns):
    """Project only the native-selected clone and original V slot domain."""
    source = _view(selection.descriptors['source_view_receipt'], deadline_ns)
    view = receipt.receipt_digest(source)
    if (source['backend'] != selection.backend or source['material'] != snapshot['digest'] or
            selection.material.hex() != snapshot['digest'] or selection.view.hex() != view):
        raise ValueError('preparation-view-binding')
    slots = _json(selection.descriptors['source_slots'], deadline_ns)
    expected = {node['path']: node['source_index'] for node in source['nodes']}
    if (not isinstance(slots, dict) or set(slots) != {'format', 'material', 'source', 'slots'} or
            type(slots['format']) is not int or slots['format'] != 1 or
            slots['material'] != snapshot['digest'] or slots['source'] != view or
            slots['slots'] != expected or
            any(type(index) is not int for index in slots['slots'].values())):
        raise ValueError('preparation-slots-binding')
    layout, entries = [], {}
    for node in source['nodes']:
        _before(deadline_ns)
        path, kind = node['path'], node['kind']
        if path != '/usr':
            entry = dict(path=path, kind=kind)
            if kind == 'link':
                entry['link'] = node['link']
            layout.append(entry)
        if kind not in ('absent', 'empty-directory'):
            entries[path] = dict(kind=kind, identity=[node['device'], node['inode']])
    with confinement.RetainedSourceProjection(selection.descriptors['source_usr'], entries) as pins:
        plan = confinement.select_retained_material(snapshot, snapshot['record'], layout, pins,
                                                    source_slots=slots['slots'])
    # Keep the complete original domain, including absences and local narrowing.
    # Native derives the realized I from this intent and actual bind outcomes.
    plan.update(source_nodes=source['nodes'], source_coverage=source['coverage'])
    _before(deadline_ns)
    return plan


def make_skeleton(target_root, layout, backend, deadline_ns):
    """Create a fresh tree only beneath the native-owned target descriptor."""
    _before(deadline_ns)
    info = os.fstat(target_root)
    confinement.runtime_owned_stat(info, 'directory', private=True)
    if os.listdir(target_root):
        raise ValueError('preparation-target-not-empty')
    if not isinstance(layout, list) or len(layout) > receipt.MAX_ROWS:
        raise ValueError('retained-layout')
    nodes = {}
    for node in layout:
        _before(deadline_ns)
        if not isinstance(node, dict):
            raise ValueError('retained-layout')
        path, kind = receipt._path(node.get('path')), node.get('kind')
        if (path == '/usr' or path in nodes or kind not in receipt.KINDS or
                set(node) != ({'path', 'kind', 'link'} if kind == 'link' else {'path', 'kind'})):
            raise ValueError('retained-layout')
        if kind == 'link':
            receipt._text(node['link'])
        nodes[path] = node
    for path in nodes:
        if any(nodes.get(str(parent), {}).get('kind') != 'tree' for parent in Path(path).parents
               if parent not in (Path('/usr'), Path('/'))):
            raise ValueError('retained-layout')
    os.mkdir('tree', mode=0o700, dir_fd=target_root)
    tree = os.open('tree', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                   dir_fd=target_root)
    try:
        _label(tree, backend)
        os.fchmod(tree, 0o755)
        for path, node in sorted(nodes.items(), key=lambda item: (item[0].count('/'), item[0])):
            _before(deadline_ns)
            if node['kind'] == 'absent':
                continue
            parent = os.dup(tree)
            try:
                parts = path.split('/')[2:]
                for part in parts[:-1]:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                                    os.O_CLOEXEC, dir_fd=parent)
                    os.close(parent)
                    parent = child
                name, kind = parts[-1], node['kind']
                if kind == 'link':
                    os.symlink(node['link'], name, dir_fd=parent)
                    confinement.runtime_label('/proc/self/fd/' + str(parent) + '/' + name, backend)
                else:
                    directory = kind in ('tree', 'directory', 'empty-directory')
                    if directory:
                        os.mkdir(name, mode=0o700, dir_fd=parent)
                    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
                    flags |= os.O_DIRECTORY if directory else os.O_CREAT | os.O_EXCL
                    child = os.open(name, flags, 0o600, dir_fd=parent)
                    try:
                        _label(child, backend)
                        os.fchmod(child, 0o755 if directory else 0o644)
                    finally:
                        os.close(child)
            finally:
                os.close(parent)
        _before(deadline_ns)
    finally:
        os.close(tree)


def _label(fd, backend):
    confinement.runtime_file_label(fd, backend, expected=(confinement.RUNTIME_CONTEXT.decode()
                                   if backend == 'selinux' else None), write=backend == 'selinux')


def serve(channel, *, role, deadline_ns):
    """Consume one native-owned transaction; never renew its absolute deadline."""
    with _deadline(deadline_ns):
        exchange = PreparationExchange(channel, role=role, deadline_ns=deadline_ns)
        try:
            snapshot, configuration, account = measure(role, deadline_ns)
            material = receipt.material_canonical(snapshot['record'])
        except Exception as error:
            reason = 'verification'
            if isinstance(error, ValueError) and error.args and type(error.args[0]) is str:
                candidate = confinement.MATERIAL_FAILURE_REASONS.get(error.args[0], error.args[0])
                if candidate in REFUSAL_REASONS:
                    reason = candidate
            elif isinstance(error, subprocess.TimeoutExpired):
                reason = 'command-timeout'
            elif isinstance(error, subprocess.CalledProcessError):
                reason = 'command-failed'
            elif isinstance(error, OSError):
                reason = 'os-error'
            try:
                exchange.send_refusal(reason)
            except Exception:
                pass  # An unavailable/expired channel never replaces the original failure.
            raise
        with _record(material, deadline_ns) as material_fd, _record(configuration, deadline_ns) as config_fd, \
                _record(account, deadline_ns) as account_fd:
            exchange.send_measurement(backend=snapshot['record']['backend'],
                material=bytes.fromhex(snapshot['digest']), material_receipt=material_fd,
                configuration=config_fd, account=account_fd)
        with exchange.receive_selection() as selection:
            if (selection.backend != snapshot['record']['backend'] or
                    selection.material.hex() != snapshot['digest']):
                raise ValueError('preparation-selection-binding')
            if role == 'manager':
                if selection.view != bytes(32):
                    raise ValueError('preparation-selection-binding')
                with confinement.InitialPreparation(confinement.RUNTIME, snapshot) as attempt:
                    plan = attempt.plan()
                    make_skeleton(selection.descriptors['target_root'], plan['layout'], selection.backend,
                                  deadline_ns)
                    result = dict(format=1, role=role, backend=selection.backend,
                                  material=snapshot['digest'], source='-', plan=plan,
                                  ticket=attempt.ticket())
                    with _record(_canonical(result, deadline_ns), deadline_ns) as result_fd:
                        exchange.send_result(result_receipt=result_fd,
                                             copy_directory=attempt.publication.fd)
                    attempt.detach()
            elif role == 'gate':
                plan = retained_plan(snapshot, selection, deadline_ns)
                make_skeleton(selection.descriptors['target_root'], plan['layout'], selection.backend,
                              deadline_ns)
                result = dict(format=1, role=role, backend=selection.backend,
                              material=snapshot['digest'], source=selection.view.hex(), plan=plan,
                              ticket=None)
                with _record(_canonical(result, deadline_ns), deadline_ns) as result_fd:
                    exchange.send_result(result_receipt=result_fd)
            else:
                raise ValueError('invalid-caller')
