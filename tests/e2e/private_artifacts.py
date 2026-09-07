"""Private, bounded evidence copies. Never import a worker or control a guest."""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import quote


KINDS = {'action-trace', 'screen', 'backend', 'other-user', 'continuity',
         'input-provenance', 'outcomes', 'cleanup', 'intervention', 'delivery'}
MAX_BYTES = 16 * 1024 * 1024


class EvidenceError(ValueError):
    """Only fixed error codes may cross the private evidence boundary."""


def require(condition, code):
    if not condition:
        raise EvidenceError(code)


def token(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value)


def _directory(path):
    """Pin every component; Path.resolve followed by open would permit races."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'artifact:directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                            | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'artifact:private-directory')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read(fd, name):
    """Only single-component, caller-owned, private, singly linked files."""
    require(isinstance(name, str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,127}', name)
            and name not in ('.', '..'), 'artifact:name')
    source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=fd)
    try:
        before = os.fstat(source)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600,
                'artifact:private-file')
        require(0 < before.st_size <= MAX_BYTES, 'artifact:size')
        chunks, size = [], 0
        while True:
            chunk = os.read(source, min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            require(size <= MAX_BYTES, 'artifact:size')
        after = os.fstat(source)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                 before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size,
                 after.st_mtime_ns, after.st_ctime_ns) and size == before.st_size,
                'artifact:changed-during-copy')
        return b''.join(chunks)
    finally:
        os.close(source)


class PrivateCollector:
    """Copy only reviewed evidence, into a new 0700 directory and 0600 files.

    The controller supplies *all* fixture secrets before capture. Scanning is
    defense in depth, not redaction/OCR: a trusted producer must first exclude
    PII, authentication screens and raw vars/logs. No recursive worker export.
    Keep this object and its pinned directory open through final validation.
    """

    def __init__(self, *, run_id, secrets, parent=Path('/tmp')):
        require(token(run_id), 'artifact:run-id')
        require(isinstance(secrets, (tuple, list)) and all(
            isinstance(value, str) and value for value in secrets), 'artifact:secret-registry')
        self.run_id = run_id
        self._secrets = set()
        for value in secrets:
            raw = value.encode('utf-8')
            self._secrets.update((raw, base64.b64encode(raw), quote(value, safe='').encode(),
                                 json.dumps(value, ensure_ascii=True)[1:-1].encode(),
                                 value.encode('utf-16-le'), value.encode('utf-16-be')))
        self.check_secrets(run_id.encode())
        self.path = Path(tempfile.mkdtemp(prefix='onpc-e2e-evidence-', dir=parent))
        self._fd = _directory(self.path)
        self._records = {}
        self._reports = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def check_secrets(self, data):
        require(not any(value in data for value in self._secrets), 'artifact:secret-detected')

    def _check_directory(self):
        require(self._fd is not None, 'artifact:collector-closed')
        reopened = None
        try:
            reopened = _directory(self.path)
            current, pinned = os.fstat(reopened), os.fstat(self._fd)
            require((current.st_dev, current.st_ino) == (pinned.st_dev, pinned.st_ino),
                    'artifact:directory-replaced')
        except OSError:
            raise EvidenceError('artifact:unsafe-directory') from None
        finally:
            if reopened is not None:
                os.close(reopened)

    def _write(self, name, data):
        self._check_directory()
        require(0 < len(data) <= MAX_BYTES, 'artifact:size')
        self.check_secrets(name.encode())
        self.check_secrets(data)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                         | os.O_CLOEXEC, 0o600, dir_fd=self._fd)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(self._fd)
        except OSError:
            # A failed partial copy stays private and cannot enter the manifest.
            raise EvidenceError('artifact:write-failed') from None

    def add(self, artifact_id, kind, data, *, reviewed=False):
        require(token(artifact_id) and artifact_id not in self._records, 'artifact:duplicate-or-id')
        require(isinstance(kind, str) and kind in KINDS, 'artifact:kind')
        require(reviewed is True, 'artifact:review-required')
        require(isinstance(data, bytes), 'artifact:bytes-required')
        name = artifact_id + '.evidence'
        self._write(name, data)
        record = {'artifact_id': artifact_id, 'kind': kind, 'path': name,
                  'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
                  'run_id': self.run_id, 'redaction': 'reviewed-secret-checked-v1'}
        self._records[artifact_id] = record
        return dict(record)

    def copy(self, source_directory, name, artifact_id, kind, *, reviewed=False):
        require(reviewed is True, 'artifact:review-required')
        fd = None
        try:
            fd = _directory(source_directory)
            data = _read(fd, name)
        except OSError:
            raise EvidenceError('artifact:unsafe-source') from None
        finally:
            if fd is not None:
                os.close(fd)
        return self.add(artifact_id, kind, data, reviewed=reviewed)

    def verify(self, records):
        """Require this collector's exact manifest and rehash its retained bytes."""
        self._check_directory()
        require(isinstance(records, list) and all(isinstance(r, dict) for r in records),
                'artifact:manifest')
        require(len(records) == len(self._records), 'artifact:manifest')
        seen = set()
        try:
            for record in records:
                aid = record.get('artifact_id')
                require(isinstance(aid, str) and aid not in seen
                        and record == self._records.get(aid), 'artifact:manifest')
                seen.add(aid)
                data = _read(self._fd, record['path'])
                self.check_secrets(data)
                require(hashlib.sha256(data).hexdigest() == record['sha256'], 'artifact:digest')
            for name, digest in self._reports.items():
                data = _read(self._fd, name)
                self.check_secrets(data)
                require(hashlib.sha256(data).hexdigest() == digest, 'artifact:report-digest')
            require(set(os.listdir(self._fd)) == {r['path'] for r in records} | set(self._reports),
                    'artifact:unregistered-file')
        except OSError:
            raise EvidenceError('artifact:unsafe-copy') from None

    def save_report(self, report_id, document):
        """Retain a controller's structured result, even a failed attempt, once.

        This is private diagnostic storage, never a passing-result validator.
        Callers must supply redacted structured fields, not exception messages.
        """
        require(token(report_id), 'artifact:report-id')
        try:
            data = json.dumps(document, sort_keys=True, allow_nan=False).encode('utf-8')
        except (TypeError, ValueError, UnicodeError):
            raise EvidenceError('artifact:report-json') from None
        name = report_id + '.json'
        self._write(name, data)
        self._reports[name] = hashlib.sha256(data).hexdigest()
        return self.path / name
