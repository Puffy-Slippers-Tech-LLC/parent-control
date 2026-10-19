"""Unwired transport controls using anonymous SCM_RIGHTS and private inodes.

No mounts, services, VM, shared path or product launch. The bounded compiler and
native sender are synchronously reaped; pytest owns disk scratch. Identity
controls use independently opened private files rather than trusting a receipt.
"""
import array
import builtins
from contextlib import contextmanager
import fcntl
import io
import os
from pathlib import Path
import socket
import struct
import subprocess
import time

import pytest

from tools import kiosk_preparation_input as channel_input
from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]
MATERIAL = bytes(range(32))
VIEW = bytes(reversed(range(32)))


@pytest.fixture(scope='module')
def native_anonymous_identity(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-anonymous-identity')
    source = directory / 'identity.c'
    binary = directory / 'identity'
    source.write_text(r'''
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdarg.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
static int record_fd;
static const char *fdinfo;
static int identity_open(const char *path, int flags, ...) {
    char expected[64]; snprintf(expected, sizeof(expected), "/proc/self/fdinfo/%d", record_fd);
    mode_t mode = 0;
    if (flags & O_CREAT) { va_list args; va_start(args, flags); mode = va_arg(args, int); va_end(args); }
    return open(!strcmp(path, expected) ? fdinfo : path, flags, mode);
}
#define open identity_open
#include "kiosk_preparation_channel.h"
#undef open
int main(int argc, char **argv) {
    if (argc != 7) return 90;
    record_fd = atoi(argv[1]); fdinfo = argv[2];
    if (atoi(argv[6]) && fcntl(record_fd, F_SETFD, FD_CLOEXEC)) return 91;
    unsigned char identity[96];
    int accepted = kiosk_preparation_identity(record_fd, identity, atoi(argv[3])) == 0;
    if (accepted != atoi(argv[4])) return 92;
    if (accepted) {
        for (unsigned i = 88; i < 96; i++) if (identity[i]) return 93;
        struct stat actual;
        if (fstat(record_fd, &actual) || actual.st_nlink || !S_ISREG(actual.st_mode)) return 94;
        if (fcntl(record_fd, F_GET_SEALS) != atoi(argv[5])) return 95;
    }
    return 0;
}
''', encoding='utf-8')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-I', str(ROOT / 'tools'), str(source),
                    '-o', str(binary)], check=True, timeout=30, capture_output=True,
                   pass_fds=test_storage.scratch_descriptors())
    return binary


@pytest.mark.parametrize('kind', [
    'sealed', 'unsealed', 'missing-write', 'missing-grow', 'missing-shrink', 'missing-seal',
    'unlinked-file', 'named-file', 'directory', 'writable', 'inheritable',
])
def test_zero_mount_identity_only_admits_completely_sealed_anonymous_records(
        native_anonymous_identity, tmp_path, monkeypatch, kind):
    required = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    missing = {'missing-write': fcntl.F_SEAL_WRITE, 'missing-grow': fcntl.F_SEAL_GROW,
               'missing-shrink': fcntl.F_SEAL_SHRINK, 'missing-seal': fcntl.F_SEAL_SEAL}
    writer = reader = -1
    regular = kind != 'directory'
    try:
        if kind in ('unlinked-file', 'named-file', 'directory'):
            path = tmp_path / 'object'
            if regular:
                path.write_bytes(b'ordinary-record')
            else:
                path.mkdir()
            reader = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
            if kind == 'unlinked-file':
                path.unlink()
            seals = -1
        else:
            writer = os.memfd_create('onpc-identity-control', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
            os.write(writer, b'independently-observed-record')
            requested_seals = 0 if kind == 'unsealed' else required & ~missing.get(kind, 0)
            fcntl.fcntl(writer, fcntl.F_ADD_SEALS, requested_seals)
            reader = os.open(f'/proc/self/fd/{writer}',
                             (os.O_RDWR if kind == 'writable' else os.O_RDONLY) | os.O_CLOEXEC)
            os.close(writer)
            writer = -1
            assert os.fstat(reader).st_nlink == 0
            seals = fcntl.fcntl(reader, fcntl.F_GET_SEALS)
            assert seals & required == requested_seals
        if kind == 'inheritable':
            os.set_inheritable(reader, True)
        actual = independent_identity(reader)
        # Exercise the zero-ID branch on every supported kernel. All object,
        # access-mode, seal and descriptor observations remain actual kernel
        # observations. The full fresh transaction separately witnesses its
        # real anonymous mount ID, without this finite fdinfo double.
        zero_info = tmp_path / 'zero-fdinfo'
        zero_info.write_text('mnt_id:\t0\n', encoding='ascii')
        fdinfo_path = f'/proc/self/fdinfo/{reader}'
        original_open = builtins.open

        def zero_mount_info(path, *args, **kwargs):
            if path == fdinfo_path:
                return io.StringIO('mnt_id:\t0\n')
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, 'open', zero_mount_info)
        accepted = kind == 'sealed'
        if accepted:
            assert channel_input._identity(reader, regular) == (*actual[:-1], 0)
        else:
            with pytest.raises(ValueError, match='preparation-(mount-identity|descriptor-kind)'):
                channel_input._identity(reader, regular)
        completed = subprocess.run(
            [str(native_anonymous_identity), str(reader), str(zero_info), str(int(regular)),
             str(int(accepted)), str(seals), str(int(kind != 'inheritable'))],
            capture_output=True, timeout=5,
            pass_fds=(reader, *test_storage.scratch_descriptors()))
        assert completed.returncode == 0, (kind, completed.stdout, completed.stderr)
        assert independent_identity(reader) == (*actual[:-1], 0)
    finally:
        if reader >= 0:
            os.close(reader)
        if writer >= 0:
            os.close(writer)


@pytest.fixture(scope='module')
def native_sender(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-preparation-channel')
    source = directory / 'sender.c'
    binary = directory / 'sender'
    source.write_text(r'''
#define _GNU_SOURCE
#include <stdlib.h>
#include "kiosk_preparation_channel.h"
int main(int argc, char **argv) {
    if (argc < 8) return 90;
    int channel = atoi(argv[1]), acquisition = atoi(argv[2]);
    unsigned count = acquisition == 1 ? 3 : 5;
    if (argc != (int) count + 5) return 91;
    uint64_t deadline = strtoull(argv[3], NULL, 10);
    unsigned char material[32], view[32]; int fds[5];
    for (unsigned i = 0; i < 32; i++) { material[i] = i; view[i] = acquisition == 1 ? 0 : 31 - i; }
    if (!strcmp(argv[4], "initial-view")) view[0] = 1;
    for (unsigned i = 0; i < count; i++) {
        int regular = i == 0 || (acquisition == 2 && i == 1);
        fds[i] = open(argv[5 + i], O_RDONLY | O_CLOEXEC | (regular ? 0 : O_DIRECTORY));
        if (fds[i] < 0) return 92;
    }
    struct kiosk_preparation_input input;
    int captured = kiosk_preparation_capture(&input, acquisition, acquisition, 1,
        material, view, fds, count, deadline);
    int result = -1;
    if (captured == 0) {
        if (!strcmp(argv[4], "changed-identity")) input.packet[96 + 15] ^= 1;
        if (!strcmp(argv[4], "changed-field")) input.packet[12] = 1;
        if (!strcmp(argv[4], "changed-fd")) { close(fds[0]); fds[0] = open(argv[6], O_RDONLY | O_CLOEXEC); }
        if (!strcmp(argv[4], "lost-cloexec")) fcntl(fds[0], F_SETFD, 0);
        if (!strcmp(argv[4], "new-deadline")) deadline++;
        result = kiosk_preparation_send(channel, &input, fds, deadline);
    }
    for (unsigned i = 0; i < count; i++) close(fds[i]);
    close(channel);
    return result == 0 ? 0 : 1;
}
''', encoding='utf-8')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-I', str(ROOT / 'tools'),
                    str(source), '-o', str(binary)], check=True, timeout=30,
                   capture_output=True, pass_fds=test_storage.scratch_descriptors())
    return binary


@contextmanager
def objects(tmp_path, acquisition='initial'):
    paths, fds = [], []
    try:
        for name in channel_input.SLOTS[acquisition]:
            path = tmp_path / name
            regular = 'receipt' in name
            if regular:
                path.write_bytes(name.encode())
                path.chmod(0o600)
            else:
                path.mkdir(mode=0o700)
            paths.append(path)
            fds.append(os.open(path, os.O_RDONLY | os.O_CLOEXEC))
        yield paths, fds
    finally:
        for fd in fds:
            os.close(fd)


def independent_identity(fd):
    info = os.fstat(fd)
    with open(f'/proc/self/fdinfo/{fd}', encoding='ascii') as stream:
        mount = next(int(line.split(':')[1]) for line in stream if line.startswith('mnt_id:'))
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_nlink, info.st_mtime_ns // 10**9,
            info.st_mtime_ns % 10**9, info.st_ctime_ns // 10**9,
            info.st_ctime_ns % 10**9, mount)


def packet_for(fds, deadline, acquisition='initial', backend=1):
    kind = 1 if acquisition == 'initial' else 2
    packet = (b'ONPCPRE1' + bytes((kind, kind, backend, len(fds))) + bytes(4) +
              struct.pack('!Q', deadline) + MATERIAL +
              (bytes(32) if acquisition == 'initial' else VIEW) + bytes(8))
    return packet + b''.join(struct.pack('!12Q', *independent_identity(fd)) for fd in fds)


def receive(sock, deadline, acquisition='initial', **overrides):
    expected = dict(acquisition=acquisition, role='manager' if acquisition == 'initial' else 'gate',
                    backend='apparmor', material=MATERIAL,
                    view=bytes(32) if acquisition == 'initial' else VIEW, deadline_ns=deadline)
    expected.update(overrides)
    return channel_input.receive(sock, **expected)


def send(sock, packet, fds):
    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', fds))] if fds else []
    assert sock.sendmsg([packet], ancillary) == len(packet)


def fd_count():
    return len(os.listdir('/proc/self/fd'))


@pytest.mark.parametrize('acquisition', ['initial', 'retained'])
def test_native_transfer_has_independent_kernel_identities(native_sender, tmp_path, acquisition):
    with objects(tmp_path, acquisition) as (paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            baseline = fd_count()
            deadline = time.monotonic_ns() + 5_000_000_000
            subprocess.run([str(native_sender), str(left.fileno()),
                            '1' if acquisition == 'initial' else '2', str(deadline),
                            'valid', *(str(path) for path in paths)],
                           check=True, timeout=5, capture_output=True,
                           pass_fds=(left.fileno(), *test_storage.scratch_descriptors()))
            with receive(right, deadline, acquisition) as received:
                for original, duplicate in zip(fds, received.descriptors.values()):
                    assert independent_identity(original) == independent_identity(duplicate)
                    assert not os.get_inheritable(duplicate)
                assert os.pread(received.descriptors['material_receipt'], 32, 0) == b'material_receipt'
            assert fd_count() == baseline
        finally:
            left.close()
            right.close()


@pytest.mark.parametrize('fault', ['changed-identity', 'changed-field', 'changed-fd',
                                'lost-cloexec', 'new-deadline', 'expired', 'initial-view'])
def test_native_sender_rechecks_original_authority(native_sender, tmp_path, fault):
    with objects(tmp_path) as (paths, _fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            baseline = fd_count()
            deadline = time.monotonic_ns() + (-1 if fault == 'expired' else 5_000_000_000)
            completed = subprocess.run([str(native_sender), str(left.fileno()), '1',
                                        str(deadline), fault, *(str(path) for path in paths)],
                                       timeout=5, capture_output=True,
                                       pass_fds=(left.fileno(), *test_storage.scratch_descriptors()))
            assert completed.returncode == 1, completed.stderr
            right.setblocking(False)
            with pytest.raises(BlockingIOError):
                right.recv(1)
            assert fd_count() == baseline
        finally:
            left.close()
            right.close()


@pytest.mark.parametrize('acquisition', ['initial', 'retained'])
def test_python_transfer_closes_duplicates(tmp_path, acquisition):
    with objects(tmp_path, acquisition) as (_paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            baseline = fd_count()
            deadline = time.monotonic_ns() + 2_000_000_000
            send(left, packet_for(fds, deadline, acquisition), fds)
            with receive(right, deadline, acquisition) as received:
                assert fd_count() == baseline + len(fds)
                for original, duplicate in zip(fds, received.descriptors.values()):
                    assert original != duplicate
                    assert independent_identity(original) == independent_identity(duplicate)
                    assert not os.get_inheritable(duplicate)
            received.close()
            assert fd_count() == baseline
            assert all(os.fstat(fd) for fd in fds)
        finally:
            left.close()
            right.close()


@pytest.mark.parametrize('fault', [
    'magic', 'version', 'class', 'role', 'backend', 'count', 'reserved', 'tail-reserved',
    'material', 'view', 'deadline', 'short', 'extra-field', 'truncated',
    'missing-rights', 'extra-rights', 'many-rights', 'wrong-inode', 'duplicate-inode',
    'mode', 'uid', 'gid', 'size', 'links', 'mtime', 'ctime', 'mount', 'wrong-kind',
    'writable-receipt', 'path-only-receipt',
])
def test_malformed_packets_close_every_received_right(tmp_path, fault):
    with objects(tmp_path) as (_paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        extra_path = tmp_path / 'other'
        extra_path.write_bytes(b'independent')
        extra_flags = (os.O_RDWR if fault == 'writable-receipt' else
                       os.O_PATH if fault == 'path-only-receipt' else os.O_RDONLY)
        extra = os.open(extra_path, extra_flags | os.O_CLOEXEC)
        try:
            baseline = fd_count()
            deadline = time.monotonic_ns() + 2_000_000_000
            packet = bytearray(packet_for(fds, deadline))
            sent_fds = list(fds)
            offsets = dict(magic=0, version=7, **{'class': 8}, role=9, backend=10,
                           count=11, reserved=12, **{'tail-reserved': 88}, material=24,
                           view=56, deadline=23, mode=96 + 23, uid=96 + 31,
                           gid=96 + 39, size=96 + 47, links=96 + 55,
                           mtime=96 + 71, ctime=96 + 87, mount=96 + 95)
            if fault in offsets:
                packet[offsets[fault]] ^= 1
            elif fault == 'short':
                packet = packet[:-1]
            elif fault == 'extra-field':
                packet.extend(b'x')
            elif fault == 'truncated':
                packet.extend(bytes(channel_input.MAX_BYTES))
            elif fault == 'missing-rights':
                sent_fds = []
            elif fault == 'extra-rights':
                sent_fds.append(extra)
            elif fault == 'many-rights':
                sent_fds = [extra] * 32
            elif fault == 'wrong-inode':
                sent_fds[0] = extra
            elif fault == 'duplicate-inode':
                sent_fds[2] = sent_fds[1]
                packet[96 + 192:96 + 288] = packet[96 + 96:96 + 192]
            elif fault == 'wrong-kind':
                sent_fds[1] = extra
                packet[192:288] = struct.pack('!12Q', *independent_identity(extra))
            elif fault in ('writable-receipt', 'path-only-receipt'):
                sent_fds[0] = extra
                packet[96:192] = struct.pack('!12Q', *independent_identity(extra))
            send(left, packet, sent_fds)
            with pytest.raises(ValueError):
                receive(right, deadline)
            assert fd_count() == baseline
            assert all(os.fstat(fd) for fd in fds)
        finally:
            os.close(extra)
            left.close()
            right.close()


@pytest.mark.parametrize('field,value', [('material', bytes(32)), ('view', VIEW),
                                        ('backend', 'selinux')])
def test_expected_binding_is_external_to_packet(tmp_path, field, value):
    with objects(tmp_path) as (_paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            baseline = fd_count()
            deadline = time.monotonic_ns() + 2_000_000_000
            send(left, packet_for(fds, deadline), fds)
            with pytest.raises(ValueError):
                receive(right, deadline, **{field: value})
            assert fd_count() == baseline
        finally:
            left.close()
            right.close()


def test_deadline_is_absolute_and_never_renewed():
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        with pytest.raises(TimeoutError):
            receive(right, time.monotonic_ns() - 1)
        deadline = time.monotonic_ns() + 10_000_000
        with pytest.raises(TimeoutError):
            receive(right, deadline)
        with pytest.raises(TimeoutError):
            receive(right, deadline)
    finally:
        left.close()
        right.close()


@pytest.fixture(scope='module')
def native_exchange(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-preparation-duplex')
    source, binary = directory / 'exchange.c', directory / 'exchange'
    source.write_text(r'''
#define _GNU_SOURCE
#include <dirent.h>
#include <stdlib.h>
#include "kiosk_preparation_channel.h"
static int descriptors(void) {
    DIR *d = opendir("/proc/self/fd"); if (!d) return -1;
    int n = 0; while (readdir(d)) n++; closedir(d); return n;
}
static int identity(int a, int b, int regular) {
    unsigned char x[96], y[96];
    return kiosk_preparation_identity(a, x, regular) ||
        kiosk_preparation_identity(b, y, regular) || memcmp(x, y, 96);
}
int main(int argc, char **argv) {
    if (argc != 13) return 90;
    int channel = atoi(argv[1]); unsigned role = atoi(argv[2]);
    uint64_t deadline = strtoull(argv[3], NULL, 10);
    int originals[8];
    for (unsigned i = 0; i < 8; i++) {
        originals[i] = open(argv[5 + i], O_RDONLY | O_CLOEXEC);
        if (originals[i] < 0) return 91;
    }
    int before = descriptors();
    struct kiosk_preparation_response response; kiosk_preparation_response_init(&response);
    int measured = kiosk_preparation_receive_phase(channel, 1, role, 0, NULL, NULL, deadline, &response);
    if (!strcmp(argv[4], "refuse")) {
        if (!measured || response.count || before != descriptors()) return 92;
        puts("refused no-leak"); return 0;
    }
    if (measured || response.count != 2 || identity(originals[0], response.fds[0], 1) ||
        identity(originals[1], response.fds[1], 1)) return 93;
    unsigned char material[32], view[32];
    memcpy(material, response.input.packet + 24, 32);
    for (unsigned i = 0; i < 32; i++) {
        if (material[i] != i) return 94;
        view[i] = role == 1 ? 0 : 31 - i;
    }
    kiosk_preparation_response_close(&response);
    if (before != descriptors()) return 95;
    int selection[4] = {originals[5], originals[6], originals[7], originals[2]};
    unsigned count = role == 1 ? 1 : 4;
    if (role == 1) selection[0] = originals[2];
    struct kiosk_preparation_input input;
    if (kiosk_preparation_capture_phase(&input, 2, role, 1, material, view, selection, count, deadline)) return 96;
    if (!strcmp(argv[4], "selection-drift")) input.packet[96 + 15] ^= 1;
    if (!strcmp(argv[4], "selection-drift")) {
        if (kiosk_preparation_send_phase(channel, &input, selection, deadline) == 0) return 97;
        puts("refused no-leak"); return 0;
    }
    if (kiosk_preparation_send_phase(channel, &input, selection, deadline)) return 98;
    int final = kiosk_preparation_receive_phase(channel, 3, role, 1, material, view, deadline, &response);
    if (!strcmp(argv[4], "result-refuse")) {
        if (!final || response.count || before != descriptors()) return 102;
        puts("refused no-leak"); return 0;
    }
    if (final) return 99;
    if (identity(originals[3], response.fds[0], 1) ||
        (role == 1 && identity(originals[4], response.fds[1], 0))) return 100;
    kiosk_preparation_response_close(&response);
    if (before != descriptors()) return 101;
    for (unsigned i = 0; i < 8; i++) close(originals[i]);
    close(channel); puts("complete no-leak"); return 0;
}
''', encoding='utf-8')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-I', str(ROOT / 'tools'),
                    str(source), '-o', str(binary)], check=True, timeout=30,
                   capture_output=True, pass_fds=test_storage.scratch_descriptors())
    return binary


@contextmanager
def duplex_objects(tmp_path):
    names = ('material_receipt', 'configuration', 'target_root', 'result_receipt',
             'copy_directory', 'source_view_receipt', 'source_usr', 'source_slots')
    paths, fds = [], []
    try:
        for name in names:
            path = tmp_path / name
            if name in channel_input.REGULAR_SLOTS:
                path.write_bytes(name.encode())
            else:
                path.mkdir(mode=0o700)
            paths.append(path)
            fds.append(os.open(path, os.O_RDONLY | os.O_CLOEXEC))
        yield paths, dict(zip(names, fds))
    finally:
        for fd in fds:
            os.close(fd)


def phase_packet(phase, role, fds, deadline, view=bytes(32)):
    # Deliberately independent of the production encoder.
    return (b'ONPCPRE2' + bytes((phase, 1 if role == 'manager' else 2, 1, len(fds))) +
            bytes(4) + struct.pack('!Q', deadline) + MATERIAL + view + bytes(8) +
            b''.join(struct.pack('!12Q', *independent_identity(fd)) for fd in fds))


@pytest.mark.parametrize('role', ['manager', 'gate'])
def test_one_duplex_exchange_matches_independently_opened_native_objects(native_exchange, tmp_path, role):
    with duplex_objects(tmp_path) as (paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        deadline = time.monotonic_ns() + 5_000_000_000
        baseline = fd_count()
        process = subprocess.Popen([str(native_exchange), str(left.fileno()),
                                    '1' if role == 'manager' else '2', str(deadline), 'valid',
                                    *(str(path) for path in paths)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pass_fds=(left.fileno(), *test_storage.scratch_descriptors()))
        try:
            exchange = channel_input.PreparationExchange(right, role=role, deadline_ns=deadline)
            exchange.send_measurement(backend='apparmor', material=MATERIAL,
                                      material_receipt=fds['material_receipt'], configuration=fds['configuration'])
            with exchange.receive_selection() as selection:
                assert selection.view == (bytes(32) if role == 'manager' else VIEW)
                assert tuple(selection.descriptors) == channel_input.PHASE_SLOTS[2, role]
                for name, duplicate in selection.descriptors.items():
                    assert independent_identity(duplicate) == independent_identity(fds[name])
            exchange.send_result(fds['result_receipt'],
                                 copy_directory=fds['copy_directory'] if role == 'manager' else None)
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 0, (stdout, stderr)
            assert stdout == b'complete no-leak\n'
            with pytest.raises(ValueError, match='preparation-phase'):
                exchange.receive_selection()
            with pytest.raises(ValueError, match='preparation-phase'):
                exchange.send_result(fds['result_receipt'])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            left.close()
            right.close()
        assert fd_count() == baseline - 2


@pytest.mark.parametrize('fault', ['version', 'phase', 'role', 'backend', 'reserved', 'deadline',
                                'view', 'identity', 'short', 'extra', 'missing-rights',
                                'extra-rights', 'many-rights', 'duplicate-inode', 'wrong-kind'])
def test_native_measurement_refusal_closes_received_descriptors(native_exchange, tmp_path, fault):
    with duplex_objects(tmp_path) as (paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        deadline = time.monotonic_ns() + 3_000_000_000
        descriptors = [fds['material_receipt'], fds['configuration']]
        packet = bytearray(phase_packet(1, 'manager', descriptors, deadline))
        offsets = dict(version=7, phase=8, role=9, backend=10, reserved=12,
                       deadline=23, view=56, identity=96 + 15)
        if fault in offsets:
            packet[offsets[fault]] ^= 1
        elif fault == 'short':
            packet = packet[:-1]
        elif fault == 'extra':
            packet.extend(bytes(channel_input.MAX_BYTES))
        elif fault == 'missing-rights':
            descriptors = []
        elif fault == 'extra-rights':
            descriptors.append(fds['result_receipt'])
        elif fault == 'many-rights':
            descriptors = [fds['result_receipt']] * 32
        elif fault == 'duplicate-inode':
            descriptors[1] = descriptors[0]
            packet[192:288] = packet[96:192]
        elif fault == 'wrong-kind':
            descriptors[0] = fds['target_root']
            packet[96:192] = struct.pack('!12Q', *independent_identity(descriptors[0]))
        try:
            send(left, packet, descriptors)
            completed = subprocess.run([str(native_exchange), str(right.fileno()), '1', str(deadline),
                                        'refuse', *(str(path) for path in paths)],
                                       timeout=5, capture_output=True,
                                       pass_fds=(right.fileno(), *test_storage.scratch_descriptors()))
            assert completed.returncode == 0, (completed.returncode, completed.stdout, completed.stderr)
            assert completed.stdout == b'refused no-leak\n'
        finally:
            left.close()
            right.close()


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('fault', ['material', 'view', 'phase', 'deadline', 'slots', 'truncated'])
def test_python_selection_refusal_closes_received_descriptors(tmp_path, role, fault):
    with duplex_objects(tmp_path) as (_paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            deadline = time.monotonic_ns() + 2_000_000_000
            exchange = channel_input.PreparationExchange(right, role=role, deadline_ns=deadline)
            exchange.send_measurement(backend='apparmor', material=MATERIAL,
                                      material_receipt=fds['material_receipt'], configuration=fds['configuration'])
            # Consume measurement rights so only selection ownership is counted.
            packet, rights, _flags, _address = left.recvmsg(channel_input.MAX_BYTES, socket.CMSG_SPACE(8))
            for _level, _kind, data in rights:
                for fd in array.array('i', data):
                    os.close(fd)
            slots = [fds[name] for name in channel_input.PHASE_SLOTS[2, role]]
            packet = bytearray(phase_packet(2, role, slots, deadline,
                                           bytes(32) if role == 'manager' else VIEW))
            offsets = dict(material=24, phase=8, deadline=23)
            if fault in offsets:
                packet[offsets[fault]] ^= 1
            elif fault == 'view':
                if role == 'gate':
                    # Native owns selected gate V; arbitrary V is valid here.
                    # A wrong descriptor binding must still refuse it.
                    packet[96 + 15] ^= 1
                else:
                    packet[56] ^= 1
            elif fault == 'slots':
                slots[0] = fds['configuration'] if role == 'manager' else fds['target_root']
                packet[96:192] = struct.pack('!12Q', *independent_identity(slots[0]))
            else:
                packet.extend(bytes(channel_input.MAX_BYTES))
            baseline = fd_count()
            send(left, packet, slots)
            with pytest.raises(ValueError):
                exchange.receive_selection()
            assert fd_count() == baseline
            with pytest.raises(ValueError, match='preparation-phase'):
                exchange.receive_selection()
        finally:
            left.close()
            right.close()


@pytest.mark.parametrize('role', ['manager', 'gate'])
@pytest.mark.parametrize('fault', ['material', 'view', 'backend', 'phase', 'rights', 'kind'])
def test_native_result_requires_exact_selected_bindings(native_exchange, tmp_path, role, fault):
    with duplex_objects(tmp_path) as (paths, fds):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        deadline = time.monotonic_ns() + 3_000_000_000
        process = subprocess.Popen([str(native_exchange), str(left.fileno()),
                                    '1' if role == 'manager' else '2', str(deadline), 'result-refuse',
                                    *(str(path) for path in paths)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   pass_fds=(left.fileno(), *test_storage.scratch_descriptors()))
        try:
            exchange = channel_input.PreparationExchange(right, role=role, deadline_ns=deadline)
            exchange.send_measurement(backend='apparmor', material=MATERIAL,
                                      material_receipt=fds['material_receipt'], configuration=fds['configuration'])
            with exchange.receive_selection() as selection:
                view = selection.view
            descriptors = [fds[name] for name in channel_input.PHASE_SLOTS[3, role]]
            packet = bytearray(phase_packet(3, role, descriptors, deadline, view))
            offsets = dict(material=24, view=56, backend=10, phase=8)
            if fault in offsets:
                packet[offsets[fault]] ^= 1
            elif fault == 'rights':
                descriptors.append(fds['configuration'])
            else:
                descriptors[0] = fds['target_root']
                packet[96:192] = struct.pack('!12Q', *independent_identity(descriptors[0]))
            send(right, packet, descriptors)
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 0, (process.returncode, stdout, stderr)
            assert stdout == b'refused no-leak\n'
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            left.close()
            right.close()
