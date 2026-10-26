"""Identity-owned latest recordings, separate from ordinary run retention.

One private stable directory contains human-readable WebMs and small per-case
manifests. A case lock spans capture and publication. Only identities recorded
by that case can be replaced or removed; unknown entries are never swept.
"""
from contextlib import contextmanager
import copy
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

    def __init__(self, *, root=None, create=True):
        self.path = test_storage.recordings_directory(root=root, create=create)
        self.directory = self.path

    def begin(self, category, case_id):
        """Acquire a nonblocking per-case lease and reserve an empty WebM.

        Use as a context manager. Encoders must write the existing path in
        place, preserve mode 0600, and finish before publish or context exit.
        """
        if not _token(category) or type(case_id) is not int or case_id <= 0:
            raise ValueError('recordings: invalid category or numeric case ID')
        return Recording(self, category, case_id)

    def owner(self, category, case_id):
        """Hold a case for capture recovery without retiring or allocating media."""
        if not _token(category) or type(case_id) is not int or case_id <= 0:
            raise ValueError('recordings: invalid category or numeric case ID')
        return Recording(self, category, case_id, reserve=False)


class Recording:
    def __init__(self, store, category, case_id, *, reserve=True):
        self.store, self.category, self.case_id = store, category, case_id
        self.reserve = reserve
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
                                os.O_RDWR | (os.O_CREAT if reserve else 0) | os.O_NOFOLLOW | os.O_CLOEXEC,
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
            if not reserve:
                return
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
        self.close(abort=self.reserve)

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
                        current=None, staging=None, pending=None, provenance=None, required=None)
        with os.fdopen(fd) as stream:
            self.manifest_identity = _identity(os.fstat(stream.fileno()), name)
            size = os.fstat(stream.fileno()).st_size
            if size > self._capture_module().logical.MAX_METADATA:
                raise ValueError('recordings: oversized manifest')
            value = json.load(stream)
        if isinstance(value, dict) and value.get('version') == 1 and size > 65536:
            raise ValueError('recordings: oversized legacy manifest')
        if (not isinstance(value, dict)
                or set(value) - {'version', 'category', 'case_id', 'current', 'staging', 'pending', 'provenance', 'required'}
                or not {'version', 'category', 'case_id', 'current', 'staging', 'pending', 'provenance'} <= set(value)
                or value['version'] not in (1, 2)
                or (value['version'] == 2 and 'required' not in value)
                or value['category'] != self.category
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
        value.setdefault('required', None)
        self._validate_required(value['required'])
        return value

    def _capture_module(self):
        if __package__:
            from . import evidence_capture
        else:
            import evidence_capture
        return evidence_capture

    def _validate_required(self, required):
        if required is None:
            return
        capture = self._capture_module()
        logical = capture.logical
        logical._object(required, {'id', 'original', 'origin', 'context', 'consumers', 'dependencies',
            'record', 'capture_id', 'acknowledgement', 'parent_acknowledged', 'retired'},
            'required recording')
        logical._hex(required['id'])
        _record(required['original'], complete=True)
        if not required['original']['name'].startswith(self.key + '-'):
            raise ValueError('recordings: required case changed')
        logical.validate_context(required['context'])
        capture._consumers(required['consumers'])
        if not isinstance(required['dependencies'], list):
            raise ValueError('recordings: invalid required dependencies')
        for dependency in required['dependencies']:
            logical._record(dependency)
        if type(required['retired']) is not bool or type(required['parent_acknowledged']) is not bool:
            raise ValueError('recordings: invalid required recording acknowledgement')
        origin = required['origin']
        logical._object(origin, {'file', 'payload'}, 'recording origin')
        logical._object(origin['file'], {'name', 'device', 'inode'}, 'recording witness identity')
        name = origin['file']['name']
        if (not isinstance(name, str) or not name.startswith('.' + self.key + '-origin-')
                or '/' in name or not name.endswith('.json')):
            raise ValueError('recordings: invalid origin witness path')
        for key in ('device', 'inode'):
            logical._integer(origin['file'][key], minimum=1)
        logical._object(origin['payload'], {'schema', 'category', 'case_id', 'path', 'identity',
            'sha256', 'provenance', 'context', 'root', 'lock'}, 'recording origin witness')
        payload = origin['payload']
        if (payload['schema'] != 'onpc-recording-origin-v1'
                or payload['category'] != self.category or payload['case_id'] != self.case_id
                or payload['path'] != str(self.store.path / required['original']['name'])
                or payload['sha256'] != required['original']['sha256']
                or payload['context'] != required['context']):
            raise ValueError('recordings: origin witness context changed')
        identity = payload['identity']
        if (not isinstance(identity, list) or len(identity) != 10
                or any(type(item) is not int or item < 0 for item in identity)
                or identity[0:2] != [required['original']['device'], required['original']['inode']]
                or identity[6] != required['original']['size'] or identity[5] != 1
                or identity[2] != 0o100600):
            raise ValueError('recordings: origin witness file identity changed')
        logical._hex(required['id'])
        if required['id'] != logical.digest(dict(context=required['context'],
                consumers=required['consumers'], dependencies=required['dependencies'], origin=payload)):
            raise ValueError('recordings: required identity changed')
        if required['record'] is not None:
            record = required['record']
            logical._record(record)
            if record['context'] != required['context']:
                raise ValueError('recordings: required capture attempt changed')
            capture._validate_recording_source(self._source_binding(required), record)
            expected = {
                'media': (payload['path'], required['original']['size'], payload['sha256']),
                'diagnostic': (str(self.store.path / origin['file']['name']),
                    len(logical.encoded(payload)), hashlib.sha256(logical.encoded(payload)).hexdigest())}
            for member in record['members']:
                if (member['original_path'], member['bytes'], member['sha256']) != expected[member['role']]:
                    raise ValueError('recordings: required media or origin changed')
                allocation = member['source_allocation']
                if (allocation['device'] != payload['root']['device']
                        or allocation['inode'] != payload['root']['inode']
                        or allocation['journal'] != required['context']['owner']['journal']
                        or allocation['run'] != required['context']['run']):
                    raise ValueError('recordings: required recording workflow changed')
        if required['capture_id'] is not None:
            logical._hex(required['capture_id'])
        acknowledgement = required['acknowledgement']
        if acknowledgement is not None:
            logical._object(acknowledgement, {'schema', 'version', 'request', 'delivery', 'caller_slot'},
                            'recording acknowledgement')
            request = acknowledgement['request']
            capture._validate_request(request)
            if (request['record'] != required['record']
                    or request['consumers'] != required['consumers']
                    or request['capture_id'] != required['capture_id']):
                raise ValueError('recordings: recording acknowledgement changed')
        if required['parent_acknowledged'] and acknowledgement is None:
            raise ValueError('recordings: required receipt is missing')
        if required['retired'] and not required['parent_acknowledged']:
            raise ValueError('recordings: unacknowledged recording retirement')

    def _source_binding(self, required):
        return dict(category=self.category, case_id=self.case_id,
            required_id=required['id'], path=str(self.store.path),
            root=copy.deepcopy(required['origin']['payload']['root']),
            lock=copy.deepcopy(required['origin']['payload']['lock']))

    def _check_source_binding(self, binding):
        self._root_guard()
        manifest = self._open(self.manifest_identity)
        try:
            with os.fdopen(os.dup(manifest)) as stream:
                if json.load(stream) != self.state:
                    raise ValueError('recordings: required owner journal changed')
        finally:
            os.close(manifest)
        required = self.state['required']
        if required is None or binding != self._source_binding(required):
            raise ValueError('recordings: required source declaration changed')
        if (binding['root'] != self._capture_module()._directory_identity(os.fstat(self.fd))
                or binding['lock'] != self.lock_identity):
            raise ValueError('recordings: required source ownership changed')
        return required

    @contextmanager
    def _capture_source(self, member, binding, *, guards=None):
        required = self._check_source_binding(binding)
        if required['retired']:
            raise FileNotFoundError('recordings: required original already retired')
        capture = self._capture_module()
        record = required['record']
        if record is None or member not in record['members']:
            raise ValueError('recordings: member is not in the required closure')
        original = required['original']
        witness = required['origin']['file']
        expected = original if member['original_path'] == str(self.store.path / original['name']) else witness
        if member['original_path'] != str(self.store.path / expected['name']):
            raise ValueError('recordings: foreign finalized member')
        fd = self._open(expected)
        try:
            before = capture._fingerprint(os.fstat(fd))
            if expected is original and before != required['origin']['payload']['identity']:
                raise ValueError('recordings: original recording identity changed')
            if capture._hash(fd, member['bytes']) != member['sha256']:
                raise ValueError('recordings: required source bytes changed')
            def validate():
                self._check_source_binding(binding)
                info = os.stat(expected['name'], dir_fd=self.fd, follow_symlinks=False)
                if (capture._fingerprint(info) != before
                        or capture._fingerprint(os.fstat(fd)) != before):
                    raise ValueError('recordings: required source identity changed')
            if guards is not None:
                guards.append(validate)
            yield fd, os.fstat(fd)
            validate()
        finally:
            os.close(fd)

    def require_capture(self, session_handle, *, consumer_ids):
        """Declare and seal current media plus its machine-issued origin witness.

        The case lease and a live workflow session jointly issue authority.
        Failure keeps the declaration and original; retry with the same issued
        attempt (or its normal capture resume handle).
        """
        capture = self._capture_module()
        return capture.finalize_recording_capture(session_handle, self,
                                                  consumer_ids=consumer_ids)

    def resume_capture_session(self, store):
        """Reissue the saved attempt under its exact live workflow and case."""
        return self._capture_module().resume_recording_session(store, self)

    def acknowledge_required(self, *, session_handle=None):
        capture = self._capture_module()
        required = self.state['required']
        if required is None or required['capture_id'] is None:
            raise ValueError('recordings: no sealed required capture')
        context = required['context']
        caller = context['owner']['caller']
        request = capture.inspect_capture(context['repository']['root'], caller['uid'], caller['gid'],
                                          required['capture_id'])
        return capture.acknowledge_capture(context['repository']['root'], caller['uid'], caller['gid'],
            required['capture_id'], expected=request['request_sha256'], session_handle=session_handle,
            _recording_owner=self)

    @contextmanager
    def _required_retirement(self, original):
        required = self.state['required']
        if required is None or required['original'] != original:
            yield
            return
        if not required['parent_acknowledged']:
            raise ValueError('recordings: required capture is not durably acknowledged')
        capture = self._capture_module()
        acknowledgement = required['acknowledgement']
        request = acknowledgement['request']
        caller = request['producer']['caller']
        with capture._publication_module().verified_delivery(
                required['context']['repository']['root'], caller['uid'], caller['gid'],
                required['capture_id'], request, acknowledgement['delivery']):
            self._validate_required(required)
            self._check_source_binding(self._source_binding(required))
            yield

    def _save(self):
        self._root_guard()
        limit = self._capture_module().logical.MAX_METADATA if self.state['version'] == 2 else 65536
        if len(json.dumps(self.state, sort_keys=True).encode()) > limit:
            raise ValueError('recordings: required manifest capacity exceeded; original preserved')
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
            with self._required_retirement(pending['previous']):
                self._recover_publication(pending)
        elif self.state['staging'] is not None:
            self._remove(self.state['staging'])
            self.state['staging'] = None
            self._save()
        if self.state['current'] is not None:
            current = self._open(self.state['current'], missing=True)
            required = self.state['required']
            ordinary = required is None or (required['retired'] and
                                             required['original'] != self.state['current'])
            if current is None and ordinary:
                # Ordinary review clips may be deleted outside the recorder.
                # Retire only the stale claim, under this case's existing lease;
                # required evidence and replaced/corrupt files still refuse.
                self.state['current'] = self.state['provenance'] = None
                self._save()
                return
            if current is not None:
                os.close(current)
            self._verify(self.state['current'])

    def _recover_publication(self, pending):
        # The independently verified required destination remains pinned across
        # both same-name overwrite and differently named source unlink.
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
            required = self.state['required']
            if required is not None and required['original'] == previous:
                required['retired'] = True
            self._save()

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

    def close(self, *, abort=None):
        try:
            if abort is None:
                abort = self.reserve
            if abort:
                self.abort()
        finally:
            if self.lock is not None:
                os.close(self.lock)
                self.lock = None
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
