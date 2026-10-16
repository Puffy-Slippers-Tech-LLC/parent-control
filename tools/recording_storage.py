"""Identity-owned latest recordings, separate from ordinary run retention.

One private stable directory contains human-readable WebMs and small per-case
manifests. A case lock spans capture and publication. Only identities recorded
by that case can be replaced or removed; unknown entries are never swept.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

if __package__:
    from . import test_storage, test_retention
else:
    import test_storage
    import test_retention


def _token(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9]*', value)


def _identity(info, name):
    test_retention.private(info, regular=True)
    return dict(name=name, device=info.st_dev, inode=info.st_ino)


def _same(info, record):
    return (info.st_dev, info.st_ino) == (record['device'], record['inode'])


def _record(value, *, complete=False):
    fields = {'name', 'device', 'inode'} | ({'size', 'sha256'} if complete else set())
    if (not isinstance(value, dict) or set(value) != fields
            or not isinstance(value['name'], str) or '/' in value['name']
            or not value['name'].endswith('.webm')
            or any(type(value[key]) is not int or value[key] < 0 for key in ('device', 'inode'))
            or (complete and (type(value['size']) is not int or value['size'] <= 0
                             or not isinstance(value['sha256'], str)
                             or re.fullmatch(r'[a-f0-9]{64}', value['sha256']) is None))):
        raise ValueError('recordings: invalid file identity')


class Store:
    """Use root only for isolated storage-library tests (a checkout root)."""

    def __init__(self, *, root=None):
        self.path = test_storage.recordings_directory(root=root)
        self.directory = self.path

    def begin(self, category, case_id):
        """Acquire a nonblocking per-case lease and reserve an empty WebM.

        Use as a context manager. Encoders must write the existing path in
        place, preserve mode 0600, and finish before publish or context exit.
        """
        if not _token(category) or type(case_id) is not int or case_id <= 0:
            raise ValueError('recordings: invalid category or numeric case ID')
        return Recording(self, category, case_id)


class Recording:
    def __init__(self, store, category, case_id):
        self.store, self.category, self.case_id = store, category, case_id
        self.key = f'{category}-{case_id}'
        self.fd = self.lock = None
        self.state = None
        self.path = None
        self.published = None
        try:
            self.fd = test_retention.directory(store.path)
            test_retention.private(os.fstat(self.fd))
            self.root_identity = os.fstat(self.fd)
            self.lock = os.open('.' + self.key + '.lock',
                                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                                0o600, dir_fd=self.fd)
            test_retention.private(os.fstat(self.lock), regular=True)
            if test_retention.mount_id(self.lock) != test_retention.mount_id(self.fd):
                raise ValueError('recordings: mounted case lock refused')
            self.lock_identity = _identity(os.fstat(self.lock), '.' + self.key + '.lock')
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('recordings: another recorder owns this case') from error
            self.state = self._load()
            self._recover()
            name = '.' + self.key + '-' + uuid.uuid4().hex + '.webm'
            stage = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=self.fd)
            try:
                self.state['staging'] = _identity(os.fstat(stage), name)
                os.fsync(stage)
            finally:
                os.close(stage)
            self._save()
            self.path = store.path / name
        except BaseException:
            self.close(abort=False)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def descriptors(self):
        """Forward as subprocess pass_fds while descendants write the stage.

        An encoder surviving abrupt coordinator exit keeps the case lease,
        preventing a new recorder from reclaiming its still-active output.
        """
        return () if self.lock is None else (self.lock,)

    def _root_guard(self):
        with self._opened_root() as fd:
            info = os.fstat(fd)
            if ((info.st_dev, info.st_ino) !=
                    (self.root_identity.st_dev, self.root_identity.st_ino)
                    or test_retention.mount_id(fd) != test_retention.mount_id(self.fd)):
                raise ValueError('recordings: storage root changed')
        if getattr(self, 'lock_identity', None) is not None:
            info = os.stat(self.lock_identity['name'], dir_fd=self.fd, follow_symlinks=False)
            test_retention.private(info, regular=True)
            if not _same(info, self.lock_identity):
                raise ValueError('recordings: case lock changed')

    @contextmanager
    def _opened_root(self):
        fd = test_retention.directory(self.store.path)
        try:
            test_retention.private(os.fstat(fd))
            yield fd
        finally:
            os.close(fd)

    def _open(self, record, *, missing=False):
        self._root_guard()
        try:
            fd = os.open(record['name'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self.fd)
        except FileNotFoundError:
            if missing:
                return None
            raise ValueError('recordings: recorded file is missing') from None
        try:
            test_retention.private(os.fstat(fd), regular=True)
            if not _same(os.fstat(fd), record):
                raise ValueError('recordings: file identity changed')
            if test_retention.mount_id(fd) != test_retention.mount_id(self.fd):
                raise ValueError('recordings: mounted file refused')
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _verify(self, record):
        fd = self._open(record)
        try:
            with os.fdopen(os.dup(fd), 'rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if os.fstat(fd).st_size != record['size'] or digest != record['sha256']:
                raise ValueError('recordings: verified recording bytes changed')
        finally:
            os.close(fd)

    def _load(self):
        name = '.' + self.key + '.json'
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        except FileNotFoundError:
            return dict(version=1, category=self.category, case_id=self.case_id,
                        current=None, staging=None, pending=None, provenance=None)
        with os.fdopen(fd) as stream:
            self.manifest_identity = _identity(os.fstat(stream.fileno()), name)
            if os.fstat(stream.fileno()).st_size > 65536:
                raise ValueError('recordings: oversized manifest')
            value = json.load(stream)
        if (not isinstance(value, dict)
                or set(value) != {'version', 'category', 'case_id', 'current', 'staging', 'pending', 'provenance'}
                or value['version'] != 1 or value['category'] != self.category
                or value['case_id'] != self.case_id):
            raise ValueError('recordings: invalid case manifest')
        for key in ('current', 'staging'):
            if value[key] is not None:
                _record(value[key], complete=key == 'current')
                prefix = self.key + '-' if key == 'current' else '.' + self.key + '-'
                if not value[key]['name'].startswith(prefix):
                    raise ValueError('recordings: manifest case path changed')
        pending = value['pending']
        if pending is not None:
            if (not isinstance(pending, dict) or set(pending) != {'candidate', 'target', 'previous', 'provenance'}
                    or not isinstance(pending['target'], str)
                    or re.fullmatch(re.escape(self.key) + r'-[A-Za-z0-9_.-]+\.webm', pending['target']) is None):
                raise ValueError('recordings: invalid publication intent')
            _record(pending['candidate'], complete=True)
            if (value['staging'] is None or any(pending['candidate'][key] != value['staging'][key]
                                               for key in ('name', 'device', 'inode'))):
                raise ValueError('recordings: publication staging changed')
            if pending['previous'] is not None:
                _record(pending['previous'], complete=True)
                if not pending['previous']['name'].startswith(self.key + '-'):
                    raise ValueError('recordings: publication previous case changed')
            published = dict(pending['candidate'], name=pending['target'])
            if value['current'] not in (pending['previous'], published):
                raise ValueError('recordings: publication current changed')
        return value

    def _save(self):
        self._root_guard()
        manifest = '.' + self.key + '.json'
        old = getattr(self, 'manifest_identity', None)
        if old:
            fd = self._open(old)
            os.close(fd)
        else:
            try:
                os.stat(manifest, dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('recordings: unowned manifest exists')
        temp = '.' + self.key + '-' + uuid.uuid4().hex + '.json.tmp'
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        with os.fdopen(fd, 'w') as stream:
            identity = _identity(os.fstat(stream.fileno()), manifest)
            json.dump(self.state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, manifest, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        self.manifest_identity = identity
        os.fsync(self.fd)

    def _remove(self, record):
        fd = self._open(record, missing=True)
        if fd is None:
            return
        try:
            info = os.stat(record['name'], dir_fd=self.fd, follow_symlinks=False)
            if not _same(info, record):
                raise ValueError('recordings: cleanup identity changed')
            os.unlink(record['name'], dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            os.close(fd)

    def _publish_rename(self, source, target, *, replace):
        self._root_guard()
        if replace:
            os.replace(source, target, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        else:
            # The destination can appear after preflight. Linux's no-replace
            # rename atomically preserves that unknown entry instead of
            # overwriting it. Supported development hosts are Linux.
            rename = ctypes.CDLL(None, use_errno=True).renameat2
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                               ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            if rename(self.fd, os.fsencode(source), self.fd, os.fsencode(target), 1):
                raise OSError(ctypes.get_errno(), 'recordings: atomic publication refused')
        os.fsync(self.fd)

    def _recover(self):
        pending = self.state['pending']
        if pending is not None:
            candidate = pending['candidate']
            target = dict(candidate, name=pending['target'])
            previous = pending['previous']
            source = self._open(candidate, missing=True)
            if source is not None:
                os.close(source)
                self._verify(candidate)
                try:
                    existing = os.stat(target['name'], dir_fd=self.fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    if previous is None or previous['name'] != target['name'] or not _same(existing, previous):
                        raise ValueError('recordings: unowned destination exists')
                    self._verify(previous)
                if previous and previous['name'] != target['name']:
                    self._verify(previous)
                self._publish_rename(candidate['name'], target['name'],
                                     replace=bool(previous and previous['name'] == target['name']))
            self._verify(target)
            self.state['current'] = target
            self.state['provenance'] = pending['provenance']
            self._save()
            if previous and previous['name'] != target['name']:
                old = self._open(previous, missing=True)
                if old is not None:
                    os.close(old)
                    self._verify(previous)
                    self._remove(previous)
            self.state['pending'] = self.state['staging'] = None
            self._save()
        elif self.state['staging'] is not None:
            self._remove(self.state['staging'])
            self.state['staging'] = None
            self._save()
        if self.state['current'] is not None:
            self._verify(self.state['current'])

    def publish(self, vm_names, *, validate):
        """Publish after encoder shutdown and a caller-supplied playback check.

        vm_names are canonical registry names in numeric registry-ID order,
        including every VM actually shown. A consistent onpc- prefix is removed
        for the filename; full names remain in provenance. validate(path) must
        return truthy only for a complete playable WebM, or raise.
        """
        if self.fd is None or self.path is None or self.published is not None:
            raise ValueError('recordings: no active recording')
        names = list(vm_names)
        if (not names
                or any(not isinstance(name, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) is None
                       for name in names) or len(names) != len(set(names))):
            raise ValueError('recordings: invalid VM names')
        labels = [name.removeprefix('onpc-') for name in names]
        target = self.key + '-' + '-'.join(labels) + '.webm'
        if not all(labels) or len(target.encode()) > 240 or len(set(labels)) != len(labels):
            raise ValueError('recordings: invalid filename labels')
        record = self.state['staging']
        fd = self._open(record)
        try:
            os.fsync(fd)
            if not validate(self.path):
                raise ValueError('recordings: candidate is not playable')
            if not _same(os.stat(record['name'], dir_fd=self.fd, follow_symlinks=False), record):
                raise ValueError('recordings: candidate identity changed during validation')
            with os.fdopen(os.dup(fd), 'rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            candidate = dict(record, size=os.fstat(fd).st_size, sha256=digest)
            _record(candidate, complete=True)
        finally:
            os.close(fd)
        self.state['pending'] = dict(candidate=candidate, target=target,
                                     previous=self.state['current'], provenance=dict(
                                         vm_names=names, published_at=datetime.now(timezone.utc).isoformat()))
        self._save()
        self._recover()
        self.published = self.store.path / target
        return self.published

    def abort(self):
        """Remove only this case's recorded incomplete stage; preserve previous."""
        if self.fd is not None and self.state is not None and self.state['pending'] is None:
            if self.state['staging'] is not None:
                self._remove(self.state['staging'])
                self.state['staging'] = None
                self._save()

    def close(self, *, abort=True):
        try:
            if abort:
                self.abort()
        finally:
            if self.lock is not None:
                os.close(self.lock)
                self.lock = None
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
