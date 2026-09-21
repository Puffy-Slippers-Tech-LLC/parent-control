"""Per-checkout UI spectators: sealed frame copies, never compositor access."""

import array
import errno
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import struct
import time
import uuid

from e2e_watch_protocol import Frames, read_frame, receive_frames, require

ROOT = Path(__file__).resolve().parents[1]
FRESH_NS = 3_000_000_000


def private_directory(path, *, create=False):
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and info.st_mode & 0o077 == 0 and path.resolve() == path,
            'ui-registry-owner')
    return path


def registry(root=ROOT, *, create=False):
    base = private_directory(Path('/tmp') / f'onpc-ui-watch-{os.getuid()}', create=create)
    identity = hashlib.sha256(os.fsencode(root.resolve())).hexdigest()[:16]
    return private_directory(base / identity, create=create)


def label(value, limit=700):
    return ''.join(char for char in str(value) if char.isprintable())[:limit]


class Publication:
    """One nonblocking handshake gives each reader a sealed read-only memfd.

    Viewer sockets are closed immediately; readers can stall, send arbitrary
    bytes or disappear without influencing the producer's lifetime or rate.
    """

    def __init__(self, directory):
        private_directory(directory)
        self.run = uuid.uuid4().hex
        self.path = directory / (self.run + '.sock')
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.frames = None
        self.identity = None
        try:
            self.server.bind(str(self.path))
            info = self.path.lstat()
            self.identity = (info.st_dev, info.st_ino)
            self.server.listen(8)
            self.server.setblocking(False)
            self.frames = Frames(self.run)
        except BaseException:
            self.close()
            raise

    def serve(self):
        # Bound each tick even when a spectator repeatedly reconnects.
        for _ in range(8):
            try:
                peer, _address = self.server.accept()
            except BlockingIOError:
                break
            with peer:
                peer.setblocking(False)
                try:
                    owner = struct.unpack('3i', peer.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
                    if owner == os.getuid():
                        peer.sendmsg([b'ONPC-WATCH-1'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                      array.array('i', [self.frames.read_fd]))])
                except OSError:
                    pass

    def close(self):
        self.server.close()
        if self.frames is not None:
            self.frames.close()
            self.frames = None
        if self.identity is not None:
            try:
                info = self.path.lstat()
                if (info.st_dev, info.st_ino) == self.identity and stat.S_ISSOCK(info.st_mode):
                    self.path.unlink()
            except FileNotFoundError:
                pass
            self.identity = None


class Feeds:
    """Discover concurrent workers; stale/crashed publications never show pixels."""

    def __init__(self, directory=None):
        self.directory = directory
        self.connections = {}
        self.pending = {}
        self.next_scan = 0

    def poll(self):
        now = time.monotonic()
        if now >= self.next_scan:
            self.next_scan = now + .5
            try:
                directory = private_directory(self.directory) if self.directory else registry()
                # Only our fixed random socket names, never metadata-supplied paths.
                paths = sorted(directory.iterdir())
                for path in paths:
                    if (not re.fullmatch('[0-9a-f]{32}\\.sock', path.name)
                            or path.stem in self.connections or path.stem in self.pending):
                        continue
                    if len(self.connections) + len(self.pending) >= 16:
                        break
                    info = path.lstat()
                    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                        continue
                    peer = None
                    try:
                        peer = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                        peer.setblocking(False)
                        if peer.connect_ex(str(path)) not in (0, errno.EINPROGRESS):
                            peer.close()
                            continue
                        self.pending[path.stem] = (peer, now)
                    except (OSError, ValueError):
                        if peer is not None:
                            peer.close()
                        continue
            except (OSError, ValueError):
                pass
        for run, (peer, started) in tuple(self.pending.items()):
            try:
                require(now - started < 1, 'ui-handshake-expired')
                memory = receive_frames(peer, owner=os.getuid())
                self.connections[run] = [memory, 0, None, now]
            except BlockingIOError:
                continue
            except (OSError, ValueError):
                pass
            peer.close()
            del self.pending[run]
        result = {}
        for run, connection in tuple(self.connections.items()):
            memory, sequence, frame, last_read = connection
            try:
                new = read_frame(memory, sequence)
                if new is not None:
                    require(new[1]['run'] == run, 'ui-run-identity')
                    require(new[1]['state'] in ('live', 'waiting', 'unavailable'), 'ui-state')
                    require(0 <= time.monotonic_ns() - new[1]['updated_ns'] < FRESH_NS,
                            'ui-stale')
                    frame, last_read = new, now
                    connection[:] = [memory, new[0], frame, last_read]
                require(now - last_read < 3, 'ui-stalled')
                if frame is not None:
                    result[run] = frame
            except (OSError, ValueError, KeyError, TypeError):
                memory.close()
                del self.connections[run]
        return result

    def close(self):
        for peer, _started in self.pending.values():
            peer.close()
        self.pending.clear()
        for memory, *_rest in self.connections.values():
            memory.close()
        self.connections.clear()
