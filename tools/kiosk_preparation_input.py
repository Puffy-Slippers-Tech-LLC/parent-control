"""Fixed native preparation channel: legacy receiver and closed duplex exchange.

The native parent alone creates/retains this anonymous endpoint and verifies
acquisition, receipt semantics and complete recursive source coverage. The exec
launcher must supply the expected role/backend/M/V and absolute monotonic
deadline from that same transaction through its fixed invocation contract.
Received identity assertions are the native parent's statements, independently
checked against kernel descriptors here; this receiver cannot establish native
provenance from an arbitrary inherited FD. No FD number or path grants authority.
Native must check returned preparation results against its original acquisitions.
Initial V is exactly 32 zero bytes because the view has not been finalized.
Deadline nanoseconds are a checked conversion of the original native absolute
microsecond deadline (multiply by 1000); no phase samples a fresh start time.
"""
import array
from contextlib import AbstractContextManager
import fcntl
import os
import select
import socket
import stat
import struct
import time

MAGIC = b'ONPCPRE1'
HEADER = 96
MAX_FDS = 5
IDENTITY = struct.Struct('!12Q')
MAX_BYTES = HEADER + MAX_FDS * IDENTITY.size
SLOTS = {
    'initial': ('material_receipt', 'copy_directory', 'target_root'),
    'retained': ('material_receipt', 'source_view_receipt', 'source_usr',
                 'copy_directory', 'target_root'),
}

# v1 remains a compatibility-only one-way transport. Production's one child
# uses these three packets, in order, with the very same absolute deadline.
PHASE_MAGIC = b'ONPCPRE2'
# Numbered wire vocabulary shared with kiosk_preparation_channel.h. Unknown
# exceptions collapse to verification; exception text never crosses the socket.
REFUSAL_REASONS = (
    'verification', 'command-failed', 'command-timeout', 'os-error',
    'invalid-caller', 'unowned-account', 'unknown-backend', 'policy-snapshot-not-attested',
    'unexpected-preserved-executable', 'missing-executable', 'untrusted-path',
    'untrusted-ancestor', 'source-changed', 'unexpected-executable-mode',
    'preserved-executable-label', 'non-native-executable')
PHASE_SLOTS = {
    (1, 'manager'): ('material_receipt', 'configuration', 'account'),
    (1, 'gate'): ('material_receipt', 'configuration', 'account'),
    (2, 'manager'): ('target_root',),
    (2, 'gate'): ('source_view_receipt', 'source_usr', 'source_slots', 'target_root'),
    (3, 'manager'): ('result_receipt', 'copy_directory'),
    (3, 'gate'): ('result_receipt',),
}
REGULAR_SLOTS = frozenset(('material_receipt', 'configuration', 'source_view_receipt',
                           'source_slots', 'result_receipt', 'account'))


def _before(deadline_ns):
    if type(deadline_ns) is not int or not 0 < deadline_ns < 2**64:
        raise ValueError('preparation-deadline')
    remaining = deadline_ns - time.monotonic_ns()
    if remaining <= 0:
        raise TimeoutError('preparation-deadline')
    return remaining / 1_000_000_000


def _identity(fd, regular):
    before = os.fstat(fd)
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    if (os.get_inheritable(fd) or flags & os.O_ACCMODE != os.O_RDONLY or
            regular and flags & os.O_PATH or
            not (stat.S_ISREG(before.st_mode) if regular else stat.S_ISDIR(before.st_mode))):
        raise ValueError('preparation-descriptor-kind')
    # Fixed kernel metadata lookup only, never a supplied path or source reopen.
    with open(f'/proc/self/fdinfo/{fd}', encoding='ascii') as stream:
        mounts = [int(line.split(':', 1)[1]) for line in stream if line.startswith('mnt_id:')]
    if len(mounts) != 1 or mounts[0] < 0:
        raise ValueError('preparation-mount-identity')
    if mounts[0] == 0:
        # The internal shmem mount of a memfd can have no visible mount ID.
        # Only immutable anonymous records may use that identity. Directory
        # and named-file identities never inherit this exception or authority.
        required = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        try:
            seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS) if regular and before.st_nlink == 0 else -1
        except OSError:
            seals = -1
        if seals < 0 or seals & required != required:
            raise ValueError('preparation-mount-identity')

    def fields(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                info.st_size, info.st_nlink, info.st_mtime_ns // 10**9,
                info.st_mtime_ns % 10**9, info.st_ctime_ns // 10**9,
                info.st_ctime_ns % 10**9, mounts[0])
    result = fields(before)
    if result != fields(os.fstat(fd)):
        raise ValueError('preparation-descriptor-changed')
    return tuple(value % 2**64 for value in result)


class PreparationInput(AbstractContextManager):
    """Owns only received duplicates; close/context exit is idempotent."""
    def __init__(self, acquisition, descriptors):
        self.descriptors = dict(zip(SLOTS[acquisition], descriptors))

    def close(self):
        descriptors, self.descriptors = self.descriptors, {}
        for fd in descriptors.values():
            os.close(fd)

    def __exit__(self, *_exc):
        self.close()


def _channel(channel):
    if (channel.family != socket.AF_UNIX or channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
            != socket.SOCK_SEQPACKET or channel.getsockname() or channel.getpeername()):
        raise ValueError('preparation-channel')


def _phase_packet(phase, role, backend, material, view, descriptors, deadline_ns):
    slots = PHASE_SLOTS.get((phase, role))
    role_number = {'manager': 1, 'gate': 2}.get(role)
    backend_number = {'apparmor': 1, 'selinux': 2}.get(backend)
    if (slots is None or role_number is None or backend_number is None or
            type(material) is not bytes or len(material) != 32 or
            type(view) is not bytes or len(view) != 32 or
            (phase == 1 or role == 'manager') and view != bytes(32) or
            len(descriptors) != len(slots)):
        raise ValueError('preparation-expected-binding')
    _before(deadline_ns)
    identities = [_identity(fd, slot in REGULAR_SLOTS)
                  for slot, fd in zip(slots, descriptors)]
    if len({identity[:2] for identity in identities}) != len(identities):
        raise ValueError('preparation-descriptor-identity')
    packet = (PHASE_MAGIC + bytes((phase, role_number, backend_number, len(slots))) +
              bytes(4) + struct.pack('!Q', deadline_ns) + material + view + bytes(8) +
              b''.join(IDENTITY.pack(*identity) for identity in identities))
    for slot, fd, identity in zip(slots, descriptors, identities):
        if _identity(fd, slot in REGULAR_SLOTS) != identity:
            raise ValueError('preparation-descriptor-changed')
    return packet


def _send_phase(channel, phase, role, backend, material, view, descriptors, deadline_ns):
    _channel(channel)
    packet = _phase_packet(phase, role, backend, material, view, descriptors, deadline_ns)
    rights = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', descriptors))]
    while True:
        remaining = _before(deadline_ns)
        try:
            # Recheck the original objects after a blocked send, without issuing
            # a fresh assertion for changed objects.
            if packet != _phase_packet(phase, role, backend, material, view, descriptors, deadline_ns):
                raise ValueError('preparation-descriptor-changed')
            sent = channel.sendmsg([packet], rights, socket.MSG_NOSIGNAL | socket.MSG_DONTWAIT)
            if sent != len(packet):
                raise ValueError('preparation-short-send')
            _before(deadline_ns)
            return
        except InterruptedError:
            continue
        except BlockingIOError:
            _, writable, _ = select.select([], [channel], [], remaining)
            if not writable:
                raise TimeoutError('preparation-deadline')


def _receive_selection(channel, role, backend, material, deadline_ns):
    owned = []
    try:
        _channel(channel)
        while True:
            try:
                readable, _, _ = select.select([channel], [], [], _before(deadline_ns))
                if not readable:
                    raise TimeoutError('preparation-deadline')
                packet, ancillary, flags, _ = channel.recvmsg(
                    MAX_BYTES, socket.CMSG_SPACE(MAX_FDS * array.array('i').itemsize),
                    socket.MSG_CMSG_CLOEXEC | socket.MSG_DONTWAIT)
                break
            except (InterruptedError, BlockingIOError):
                continue
        valid = True
        for level, kind, data in ancillary:
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                valid = False
                continue
            rights = array.array('i')
            rights.frombytes(data[:len(data) - len(data) % rights.itemsize])
            owned.extend(rights)
            valid &= len(data) % rights.itemsize == 0
        slots = PHASE_SLOTS[2, role]
        if (not valid or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or
                len(ancillary) != 1 or len(owned) != len(slots) or len(packet) < HEADER):
            raise ValueError('preparation-packet')
        view = packet[56:88]
        expected = _phase_packet(2, role, backend, material, view, owned, deadline_ns)
        if packet != expected:
            raise ValueError('preparation-packet')
        result = PreparationInput.__new__(PreparationInput)
        result.descriptors = dict(zip(slots, owned))
        result.view, result.material, result.backend = view, material, backend
        owned = []
        return result
    finally:
        for fd in owned:
            os.close(fd)


class PreparationExchange:
    """One poisoned-on-failure measurement/selection/result exchange.

    The socket and sent originals remain borrowed. receive_selection() returns
    independently owned duplicates and the native-selected V; its caller must
    close that context. A final result is an intended plan, never completed V/I.
    """
    def __init__(self, channel, *, role, deadline_ns):
        if role not in ('manager', 'gate'):
            raise ValueError('preparation-role')
        _channel(channel)
        _before(deadline_ns)
        self.channel, self.role, self.deadline_ns = channel, role, deadline_ns
        self._phase = 1

    def send_measurement(self, *, backend, material, material_receipt, configuration, account):
        if self._phase != 1:
            raise ValueError('preparation-phase')
        self._phase = -1
        _send_phase(self.channel, 1, self.role, backend, material, bytes(32),
                    (material_receipt, configuration, account), self.deadline_ns)
        self.backend, self.material = backend, material
        self._phase = 2

    def send_refusal(self, reason):
        """End measurement with one bounded diagnostic and no descriptors."""
        if self._phase != 1:
            raise ValueError('preparation-phase')
        self._phase = -1
        if type(reason) is not str or reason not in REFUSAL_REASONS:
            raise ValueError('preparation-refusal')
        _channel(self.channel)
        packet = (b'ONPCERR1' + bytes(({'manager': 1, 'gate': 2}[self.role], 1)) +
                  struct.pack('!H', REFUSAL_REASONS.index(reason) + 1) + bytes(4) +
                  struct.pack('!Q', self.deadline_ns) + bytes(8))
        while True:
            remaining = _before(self.deadline_ns)
            try:
                sent = self.channel.send(packet, socket.MSG_NOSIGNAL | socket.MSG_DONTWAIT)
                if sent != len(packet):
                    raise ValueError('preparation-short-send')
                _before(self.deadline_ns)
                return
            except InterruptedError:
                continue
            except BlockingIOError:
                _, writable, _ = select.select([], [self.channel], [], remaining)
                if not writable:
                    raise TimeoutError('preparation-deadline')

    def receive_selection(self):
        if self._phase != 2:
            raise ValueError('preparation-phase')
        self._phase = -1
        result = _receive_selection(self.channel, self.role, self.backend,
                                    self.material, self.deadline_ns)
        self.view = result.view
        self._phase = 3
        return result

    def send_result(self, result_receipt, *, copy_directory=None):
        if self._phase != 3:
            raise ValueError('preparation-phase')
        self._phase = -1
        if (self.role == 'manager') != (copy_directory is not None):
            raise ValueError('preparation-result-descriptors')
        descriptors = (result_receipt, copy_directory) if self.role == 'manager' else (result_receipt,)
        _send_phase(self.channel, 3, self.role, self.backend, self.material, self.view,
                    descriptors, self.deadline_ns)
        self._phase = 4


def receive(channel, *, acquisition, role, backend, material, view, deadline_ns):
    """Borrow a native-owned socket object and adopt exactly one checked packet.

    Caller closes channel on every outcome, including cancellation; a second
    receive is not a retry of this transaction. Original native FDs stay native.
    Only the returned context owns received duplicates. No pathname API exists.
    """
    owned = []
    try:
        expected_class = {'initial': 1, 'retained': 2}.get(acquisition)
        expected_role = {'manager': 1, 'gate': 2}.get(role)
        expected_backend = {'apparmor': 1, 'selinux': 2}.get(backend)
        if (expected_class is None or expected_role != expected_class or expected_backend is None or
                type(material) is not bytes or len(material) != 32 or
                type(view) is not bytes or len(view) != 32 or
                acquisition == 'initial' and view != bytes(32)):
            raise ValueError('preparation-expected-binding')
        if (channel.family != socket.AF_UNIX or channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
                != socket.SOCK_SEQPACKET or channel.getsockname() or channel.getpeername()):
            raise ValueError('preparation-channel')
        while True:
            remaining = _before(deadline_ns)
            try:
                readable, _, _ = select.select([channel], [], [], remaining)
                if not readable:
                    raise TimeoutError('preparation-deadline')
                packet, ancillary, flags, _ = channel.recvmsg(
                    MAX_BYTES, socket.CMSG_SPACE(MAX_FDS * array.array('i').itemsize),
                    socket.MSG_CMSG_CLOEXEC | socket.MSG_DONTWAIT)
                break
            except (InterruptedError, BlockingIOError):
                continue
        valid_rights = True
        for level, kind, data in ancillary:
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                valid_rights = False
                continue
            rights = array.array('i')
            size = rights.itemsize
            rights.frombytes(data[:len(data) - len(data) % size])
            owned.extend(rights)
            valid_rights &= len(data) % size == 0
        count = len(SLOTS[acquisition])
        if (flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or not valid_rights or
                len(ancillary) != 1 or len(owned) != count or len(packet) != HEADER + count * IDENTITY.size or
                packet[:8] != MAGIC or packet[8:12] != bytes((expected_class, expected_role, expected_backend, count)) or
                packet[12:16] != bytes(4) or packet[16:24] != struct.pack('!Q', deadline_ns) or
                packet[24:56] != material or packet[56:88] != view or packet[88:96] != bytes(8)):
            raise ValueError('preparation-packet')
        seen = set()
        identities = []
        for index, fd in enumerate(owned):
            regular = index == 0 or acquisition == 'retained' and index == 1
            identity = _identity(fd, regular)
            if identity != IDENTITY.unpack_from(packet, HEADER + index * IDENTITY.size) or identity[:2] in seen:
                raise ValueError('preparation-descriptor-identity')
            seen.add(identity[:2])
            identities.append(identity)
        for index, fd in enumerate(owned):
            regular = index == 0 or acquisition == 'retained' and index == 1
            if _identity(fd, regular) != identities[index]:
                raise ValueError('preparation-descriptor-changed')
        _before(deadline_ns)
        result = PreparationInput(acquisition, owned)
        owned = []
        return result
    finally:
        for fd in owned:
            os.close(fd)
