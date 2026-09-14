"""Own one fresh native witness until the caller proves lifecycle settlement.

No dispatch, process signaling, policy receipt or restart adoption lives here.
The fixed runtime root must already exist. Production callers run as root;
tests relocate the constants and use their own UID. Same-UID privileged mutation
is outside the trust boundary: checks detect observed replacement, not atomic
filesystem transactions against hostile root.
"""

from dataclasses import dataclass
import hashlib
import os
import secrets
import stat
import threading

from common.oh_no_parent_control_ui.diagnostic_events import get_logger


LOG = get_logger("execution-probe")
RUNTIME_ROOT = "/run/oh-no-parent-control/probes"
WITNESS_SOURCE = "/usr/libexec/oh-no-parent-control-execution-probe-witness"
MAX_WITNESS_BYTES = 1024 * 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


class GenerationRefused(Exception):
    """Fixed diagnostics only; never include paths or source contents."""


def _identity(info):
    return info.st_dev, info.st_ino


def _content_identity(info):
    return (_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _private_directory(info):
    return (stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and
            stat.S_IMODE(info.st_mode) == 0o700)


@dataclass(frozen=True)
class GenerationIdentity:
    token: str
    directory: str
    witness: str
    device: int
    inode: int
    sha256: str
    size: int


class ProbeGeneration:
    """Single-use, serialized directory/witness ownership, with explicit retry.

    Retain this object before prepare(). After any failure, close(settled=True)
    is allowed only once the caller has proved no dispatch is possible and all
    unit/client/channel work has settled. False preserves cleanup coordinates;
    never reconstruct ownership from a token or scan for renamed objects.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._started = False
        self._closing = False
        self._failure = None
        self._root = None
        self._directory = None
        self._writer = None
        self._witness = None
        self._token = None
        self._directory_created = False
        self._witness_created = False
        self._directory_identity = None
        self._witness_identity = None
        self._content = None
        self._identity = None

    @property
    def identity(self):
        return self._identity

    @property
    def failure(self):
        return self._failure

    @property
    def cleanup_complete(self):
        return (self._closing and self._root is None and self._directory is None
                and self._writer is None and self._witness is None)

    def _enter(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("probe generation operation already running")

    def _fail(self, category):
        if self._failure is None:
            self._failure = category
            LOG.info("execution-probe.009", outcome=category)

    @staticmethod
    def _source_bytes():
        descriptor = os.open(WITNESS_SOURCE, READ_FLAGS)
        try:
            before = os.fstat(descriptor)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid() or
                    stat.S_IMODE(before.st_mode) & 0o7022 or
                    not before.st_mode & stat.S_IXUSR or
                    not 0 < before.st_size <= MAX_WITNESS_BYTES):
                raise GenerationRefused("unsafe-source")
            chunks = bytearray()
            while len(chunks) <= MAX_WITNESS_BYTES:
                part = os.read(descriptor, min(65536, MAX_WITNESS_BYTES + 1 - len(chunks)))
                if not part:
                    break
                chunks.extend(part)
            if (len(chunks) != before.st_size or
                    _content_identity(os.fstat(descriptor)) != _content_identity(before)):
                raise GenerationRefused("source-changed")
            return bytes(chunks)
        finally:
            os.close(descriptor)

    def prepare(self):
        """Create exclusively; publish identity only after all writers close."""
        self._enter()
        try:
            if self._started or self._closing:
                raise RuntimeError("probe generation is single-use")
            self._started = True
            payload = self._source_bytes()
            self._root = os.open(RUNTIME_ROOT, DIRECTORY_FLAGS)
            if not _private_directory(os.fstat(self._root)):
                raise GenerationRefused("unsafe-root")
            self._token = secrets.token_hex(16)
            if self._token == "0" * 32:
                raise GenerationRefused("invalid-token")
            os.mkdir(self._token, mode=0o700, dir_fd=self._root)
            self._directory_created = True
            self._directory = os.open(self._token, DIRECTORY_FLAGS, dir_fd=self._root)
            info = os.fstat(self._directory)
            self._directory_identity = _identity(info)
            if not _private_directory(info):
                raise GenerationRefused("unsafe-directory")
            self._writer = os.open("witness", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                   os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                                   dir_fd=self._directory)
            self._witness_created = True
            self._witness_identity = _identity(os.fstat(self._writer))
            offset = 0
            while offset < len(payload):
                count = os.write(self._writer, payload[offset:])
                if count <= 0:
                    raise GenerationRefused("write-failed")
                offset += count
            os.fchmod(self._writer, 0o500)
            self._witness = os.open("witness", READ_FLAGS, dir_fd=self._directory)
            info = os.fstat(self._witness)
            if _identity(info) != self._witness_identity:
                raise GenerationRefused("witness-replaced")
            os.close(self._writer)
            self._writer = None
            self._content = _content_identity(info)
            directory = os.path.join(RUNTIME_ROOT, self._token)
            self._identity = GenerationIdentity(
                self._token, directory, os.path.join(directory, "witness"),
                info.st_dev, info.st_ino, hashlib.sha256(payload).hexdigest(), len(payload))
            self._verify()
            return self._identity
        except BaseException:
            self._fail("prepare-refused")
            raise
        finally:
            self._lock.release()

    def _verify(self):
        if self._identity is None or self._failure or self._closing or self._writer is not None:
            raise GenerationRefused("generation-unavailable")
        root = os.stat(RUNTIME_ROOT, follow_symlinks=False)
        directory = os.stat(self._token, dir_fd=self._root, follow_symlinks=False)
        witness = os.stat("witness", dir_fd=self._directory, follow_symlinks=False)
        if (not _private_directory(root) or _identity(root) != _identity(os.fstat(self._root)) or
                not _private_directory(directory) or
                _identity(directory) != self._directory_identity or
                not stat.S_ISREG(witness.st_mode) or witness.st_uid != os.geteuid() or
                stat.S_IMODE(witness.st_mode) != 0o500 or witness.st_nlink != 1 or
                _content_identity(witness) != self._content or
                _content_identity(os.fstat(self._witness)) != self._content):
            raise GenerationRefused("generation-changed")
        payload = os.pread(self._witness, MAX_WITNESS_BYTES + 1, 0)
        if (len(payload) != self._identity.size or
                hashlib.sha256(payload).hexdigest() != self._identity.sha256 or
                _content_identity(os.fstat(self._witness)) != self._content):
            raise GenerationRefused("content-changed")
        return self._identity

    def verify(self):
        """Recheck before admission and terminal comparison; failure is sticky."""
        self._enter()
        try:
            return self._verify()
        except BaseException:
            self._fail("verification-refused")
            raise
        finally:
            self._lock.release()

    @staticmethod
    def _remove_owned(name, parent, descriptor, identity, *, directory=False):
        try:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            # Missing pathname is not proof of removal: it may have been renamed.
            return descriptor is not None and os.fstat(descriptor).st_nlink == 0
        if identity is None or _identity(info) != identity:
            return False
        if directory:
            os.rmdir(name, dir_fd=parent)
        else:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return False
            os.unlink(name, dir_fd=parent)
        return True

    def close(self, *, settled):
        """Caller attests unit/client/channel settlement; never recursively clean.

        A remaining channel or foreign child prevents rmdir. Replaced or renamed
        owned paths and unknown identities refuse until explicitly reconciled.
        Successful filesystem cleanup is not evidence that a service has exited.
        """
        self._enter()
        try:
            if settled is not True:
                return False
            self._closing = True
            if self._directory_created:
                if self._directory_identity is None:
                    return False
                try:
                    info = os.stat(self._token, dir_fd=self._root, follow_symlinks=False)
                except FileNotFoundError:
                    if os.fstat(self._directory).st_nlink != 0:
                        return False
                else:
                    if _identity(info) != self._directory_identity:
                        return False
                if self._witness_created:
                    # A failed prepare may have only the writer. Keep that fd
                    # pinned too: closing it before unlink could allow inode reuse.
                    descriptor = self._writer if self._writer is not None else self._witness
                    if not self._remove_owned("witness", self._directory, descriptor,
                                              self._witness_identity):
                        return False
                    self._witness_created = False
                if not self._remove_owned(self._token, self._root, self._directory,
                                          self._directory_identity, directory=True):
                    return False
                self._directory_created = False
            for attribute in ("_writer", "_witness", "_directory", "_root"):
                descriptor = getattr(self, attribute)
                if descriptor is not None:
                    os.close(descriptor)
                    setattr(self, attribute, None)
            return True
        except OSError:
            LOG.info("execution-probe.010")
            return False
        finally:
            self._lock.release()
