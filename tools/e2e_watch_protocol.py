"""Local, output-only E2E display copies. No guest input or VM operations."""

import array
import fcntl
import json
import mmap
import os
from pathlib import Path
import socket
import stat
import struct
import time

BASE = Path('/run/onpc-e2e-watch')
HEADER = 4096
MAX_SIDE = 2048
PIXELS = MAX_SIDE * MAX_SIDE * 4
CURSOR = 256 * 256 * 4
SIZE = HEADER + PIXELS + CURSOR
PREFIX = struct.Struct('<QQ')
FORMATS = (0x20020888, 0x20028888, 0x20030888, 0x20038888)
SEALS = fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL | 0x0010  # FUTURE_WRITE


def progress_packet(value):
    """Bound display prose independently of private logs and frame dimensions."""
    require(type(value) is dict, 'progress-fields')
    if not value:
        return b'{}'
    fields = {'current', 'total', 'case_id', 'title', 'step', 'operation'}
    timing = {'started_ns', 'case_started_ns'}
    require(set(value) in (fields, fields | timing,
                          fields | timing | {'operation_started_ns'}), 'progress-fields')
    require(type(value['current']) is int and type(value['total']) is int
            and 0 < value['current'] <= value['total'] <= 100000, 'progress-count')
    result = {key: value[key] for key in ('current', 'total')}
    if timing <= value.keys():
        require(all(type(value[key]) is int and 0 <= value[key] < 2**63 for key in timing)
                and value['started_ns'] <= value['case_started_ns'], 'progress-time')
        result.update({key: value[key] for key in timing})
    if 'operation_started_ns' in value:
        started = value['operation_started_ns']
        require(type(started) is int and value['case_started_ns'] <= started < 2**63,
                'progress-time')
        result['operation_started_ns'] = started
    for key, limit in (('case_id', 64), ('title', 384), ('step', 2304), ('operation', 384)):
        require(type(value[key]) is str, 'progress-text')
        text = ' '.join(value[key].split())
        text = ''.join(char for char in text if char.isprintable())
        # Account for JSON quoting within each field's wire budget.
        while len(json.dumps(text, ensure_ascii=False).encode('utf-8')) > limit:
            text = text[:max(0, len(text) - max(1, (len(text.encode('utf-8')) - limit) // 4))]
        result[key] = text
    packet = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()
    # Quotes/backslashes may expand even otherwise bounded printable text.
    require(len(packet) <= 3500, 'progress-size')
    return packet


def require(condition, code):
    if not condition:
        raise ValueError('watch:' + code)


def layout(width, height, stride, format_):
    require(all(type(n) is int for n in (width, height, stride, format_)), 'layout-type')
    require(0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE
            and width * 4 <= stride <= MAX_SIDE * 4 and format_ in FORMATS, 'layout')
    return stride * height


class Frames:
    """Bounded shared memory; readers receive a kernel read-only descriptor."""

    def __init__(self, run):
        self.fd = os.memfd_create('onpc-e2e-watch', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        os.ftruncate(self.fd, SIZE)
        self.memory = mmap.mmap(self.fd, SIZE)
        # Keep this existing writable mapping; forbid all future writes/maps,
        # including reopening a received descriptor through /proc/self/fd.
        os.fchmod(self.fd, 0o400)
        fcntl.fcntl(self.fd, fcntl.F_ADD_SEALS, SEALS)
        self.read_fd = os.open(f'/proc/self/fd/{self.fd}', os.O_RDONLY | os.O_CLOEXEC)
        self.sequence = 0
        self.meta = {'run': run, 'state': 'waiting', 'width': 0, 'height': 0,
                     'stride': 0, 'format': 0, 'cursor_x': 0, 'cursor_y': 0,
                     'cursor_on': False, 'cursor_width': 0, 'cursor_height': 0,
                     'hot_x': 0, 'hot_y': 0}
        self.publish()

    def publish(self, pixels=None, cursor=None, **meta):
        self.meta.update(meta, updated_ns=time.monotonic_ns())
        data = json.dumps(self.meta, ensure_ascii=False, separators=(',', ':')).encode()
        require(len(data) < HEADER - PREFIX.size, 'metadata-size')
        self.sequence += 2
        self.memory[:PREFIX.size] = PREFIX.pack(self.sequence - 1, len(data))
        self.memory[PREFIX.size:PREFIX.size + len(data)] = data
        if pixels is not None:
            require(len(pixels) <= PIXELS, 'frame-size')
            self.memory[HEADER:HEADER + len(pixels)] = pixels
        if cursor is not None:
            require(len(cursor) <= CURSOR, 'cursor-size')
            self.memory[HEADER + PIXELS:HEADER + PIXELS + len(cursor)] = cursor
        self.memory[:PREFIX.size] = PREFIX.pack(self.sequence, len(data))

    def close(self):
        self.publish(state='stopped', width=0, height=0, cursor_on=False)
        self.memory.close()
        os.close(self.read_fd)
        os.close(self.fd)


def read_frame(memory, previous=0):
    prefix = memory[:PREFIX.size]
    sequence, length = PREFIX.unpack(prefix)
    if sequence == previous or sequence % 2 or not 0 < length < HEADER - PREFIX.size:
        return None
    metadata = memory[PREFIX.size:PREFIX.size + length]
    # A concurrent publication may have changed the JSON length/content.
    # Retry a torn sample without disconnecting a perfectly healthy feed.
    if memory[:PREFIX.size] != prefix:
        return None
    meta = json.loads(metadata)
    pixels = cursor = b''
    if meta['state'] == 'live':
        count = layout(meta['width'], meta['height'], meta['stride'], meta['format'])
        pixels = memory[HEADER:HEADER + count]
        width, height = meta['cursor_width'], meta['cursor_height']
        require(type(width) is int and type(height) is int
                and 0 <= width <= 256 and 0 <= height <= 256, 'cursor-layout')
        cursor = memory[HEADER + PIXELS:HEADER + PIXELS + width * height * 4]
    if memory[:PREFIX.size] != prefix:
        return None
    return sequence, meta, pixels, cursor


def receive_frames(peer, *, owner=0):
    require(struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            == owner, 'server-owner')
    descriptors = array.array('i')
    try:
        packet, controls, flags, _ = peer.recvmsg(16, socket.CMSG_SPACE(16), socket.MSG_CMSG_CLOEXEC)
        for level, kind, data in controls:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                descriptors.frombytes(data[:len(data) - len(data) % descriptors.itemsize])
        require(packet == b'ONPC-WATCH-1' and len(descriptors) == 1
                and not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC), 'descriptor-packet')
        fd = descriptors[0]
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size == SIZE
                and fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY,
                'read-only-frame-required')
        seals = fcntl.fcntl(fd, fcntl.F_GET_SEALS)
        require(seals & SEALS == SEALS, 'frame-unsealed')
        return mmap.mmap(fd, SIZE, access=mmap.ACCESS_READ)
    finally:
        for fd in descriptors:
            os.close(fd)
