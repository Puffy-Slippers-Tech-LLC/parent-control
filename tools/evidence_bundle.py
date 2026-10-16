"""Finite, checksummed qualification bundles; no extraction or selected output paths.

The installed artifact helper supplies the trusted checkout and authenticated
caller. Source journals remain locked while their exact selected files are read.
Retention owns publication, recovery and every deletion.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import grp
import json
import os
from pathlib import Path
import pwd
import re
import stat
import struct
import tempfile
import zipfile

import test_retention as retention
import test_storage as storage

MAX_FILES = 60000
MAX_MANIFEST = 64 * 1024 ** 2
MAX_READ = 16 * 1024 ** 2
MAX_BYTES = 1024 ** 3
SCHEMA = 1


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def decoded(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('bundle: ambiguous JSON keys')
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=unique)


@contextmanager
def identity(uid, gid):
    old_uid, old_gid = os.geteuid(), os.getegid()
    def switch(target_uid, target_gid):
        if (os.geteuid(), os.getegid()) == (target_uid, target_gid):
            return
        # Restore the helper's saved root identity before changing groups; drop
        # it only after the target group is installed. Nested reads use this too.
        if os.geteuid() != 0:
            os.seteuid(0)
        os.setegid(target_gid)
        os.seteuid(target_uid)
    try:
        switch(uid, gid)
        yield
    finally:
        switch(old_uid, old_gid)


def path_text(value):
    if (not isinstance(value, str) or not value.startswith('/') or len(value) > 4096
            or any(part in ('', '.', '..') for part in value.split('/')[1:])
            or any(ord(c) < 32 for c in value)):
        raise ValueError('bundle: invalid absolute source path')
    return Path(value)


def privacy(path):
    for part in Path(path).parts:
        if (part in ('snapshot.json', '.ssh', 'ssh-key', 'ssh-key.pub', 'id_rsa',
                     'id_ed25519', 'id_ecdsa', 'credentials.json')
                or part.endswith(('.pem', '.key'))):
            raise ValueError('bundle: credentials are not evidence')


def checkout_allocation(checkout, record):
    path = path_text(record['path'])
    base = Path(checkout) / 'output/test-runs'
    if path.parent not in {base / owner / kind for owner in ('host', 'privileged')
                           for kind in ('allocations', 'reports', 'exports')}:
        raise ValueError('bundle: allocation is outside the trusted checkout storage')


def fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_blocks]


def safe(info, uid, *, directory=False):
    if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or info.st_uid not in (0, uid) or info.st_mode & 0o002
            or (not directory and info.st_nlink != 1)):
        raise ValueError('bundle: unsafe source type, owner, links or mode')
    if info.st_mode & 0o020:
        allowed = {'root', pwd.getpwuid(uid).pw_name}
        members = set(grp.getgrgid(info.st_gid).gr_mem)
        members.update(user.pw_name for user in pwd.getpwall() if user.pw_gid == info.st_gid)
        if not members <= allowed:
            raise ValueError('bundle: source has an unsafe writable group')


def stream_bytes(stream, size, output=None):
    if type(size) is not int or not 0 <= size <= MAX_BYTES:
        raise ValueError('bundle: file size exceeds the finite selection limit')
    result = hashlib.sha256()
    remaining, previous = size, b''
    while remaining:
        chunk = stream.read(min(65536, remaining))
        if not chunk:
            raise ValueError('bundle: incomplete source')
        probe = previous + chunk
        if re.search(rb'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----', probe):
            raise ValueError('bundle: SSH or private key material is refused')
        previous = probe[-256:]
        result.update(chunk)
        if output is not None:
            output.write(chunk)
        remaining -= len(chunk)
    if stream.read(1):
        raise ValueError('bundle: source grew during copying')
    return result.hexdigest()


class Selection:
    def __init__(self, checkout, uid, gid, targets, sources, bundles):
        self.checkout, self.uid, self.gid = Path(checkout), uid, gid
        self.targets, self.sources, self.bundles = targets, sources, bundles
        self.stack = ExitStack()
        self.export_stack = self.stack.enter_context(ExitStack())
        self.reader_uid, self.reader_gid = os.geteuid(), os.getegid()
        self.records, self.files, self.archives = {}, {}, {}
        self.directories = {}
        self.bundle_identities = {}
        self.source_budgets, self.previous = [], []
        self.total_bytes = 0

    def __enter__(self):
        try:
            self.load()
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def catalogue(self):
        # Only fixed shared journals and registered canonical targets are read.
        import sys
        sys.path.insert(0, str(self.checkout / 'tests/integration'))
        import vm_config
        registry = vm_config.registry()
        if (len(self.targets) != len(set(self.targets))
                or any(target not in registry for target in self.targets)):
            raise ValueError('bundle: expected registered canonical targets')
        result = []
        if self.targets:
            if os.geteuid() != 0:
                raise ValueError('bundle: target evidence requires the installed helper')
            parent = storage.directory('state', root=self.checkout, create=False)
            result += [(parent / f'retention-{self.uid}-{target}', 0, 0)
                       for target in sorted(self.targets)]
        with identity(self.uid, self.gid):
            parent = storage.directory('state', root=self.checkout, create=False)
            names = ('retention-host', 'retention-batch', 'retention', 'standalone-reports',
                     *(f'retention-{target}' for target in sorted(self.targets)))
            for name in names:
                if (parent / name).exists():
                    result.append((parent / name, self.uid, self.gid))
            exports = storage.directory('exports', root=self.checkout, create=False)
            if (exports / 'retention').exists():
                result.append((exports / 'retention', self.uid, self.gid))
        return result

    def load(self):
        if (not self.sources and not self.bundles) or len(self.sources) + len(self.bundles) > 256:
            raise ValueError('bundle: select between one and 256 explicit sources')
        if len(set(self.sources + self.bundles)) != len(self.sources + self.bundles):
            raise ValueError('bundle: duplicate selected source')
        for journal, uid, gid in self.catalogue():
            with identity(uid, gid):
                owner = self.export_stack if journal.parent.name == 'exports' else self.stack
                state = owner.enter_context(retention.Store(journal).inspection())
                if state is None:
                    continue
                entries = [*state['history'], state]
                measured = 0
                for index, record in retention.latest_allocations(entries):
                    retention.remove(record, validate_only=True)
                    measured += retention.allocation_bytes(record)
                    if record['path'] in self.records:
                        raise ValueError('bundle: source allocation has ambiguous journal ownership')
                    self.records[record['path']] = dict(record, journal=str(journal),
                                                       run=entries[index]['run'])
                if measured > retention.MAX_RETAINED_BYTES:
                    raise ValueError('bundle: source journal exceeds its existing budget')
                self.source_budgets.append(dict(journal=str(journal), allocated_bytes=measured))
        for value in self.sources:
            path = path_text(value)
            privacy(path)
            record = self.record(path)
            with self.open(path) as (fd, info):
                if stat.S_ISDIR(info.st_mode):
                    self.walk(fd, path, record, depth=0)
                else:
                    self.add_file(fd, info, path, record)
        for value in self.bundles:
            path = path_text(value)
            if path.name != 'evidence.zip' or not path.parent.name.startswith('onpc-evidence-bundle-'):
                raise ValueError('bundle: expected a retained evidence bundle')
            self.record(path)
            with self.open(path.parent / 'receipt.json') as (receipt_fd, receipt_info):
                if receipt_info.st_size > 4096:
                    raise ValueError('bundle: invalid receipt size')
                receipt = decoded(os.read(receipt_fd, 4096))
            with self.open(path) as (fd, info):
                before = fingerprint(info)
                checksum = file_digest(fd, info.st_size)
                if (not isinstance(receipt, dict) or set(receipt) != {
                        'sha256', 'bytes', 'selection_sha256', 'identity'}
                        or receipt['bytes'] != info.st_size or receipt['sha256'] != checksum
                        or receipt['identity'] != before):
                    raise ValueError('bundle: publication checksum mismatch')
                stream = self.stack.enter_context(os.fdopen(os.dup(fd), 'rb'))
                archive, manifest = verify_stream(stream)
                self.stack.callback(archive.close)
                if (digest(encoded(manifest)) != receipt['selection_sha256']
                        or fingerprint(os.fstat(fd)) != before):
                    raise ValueError('bundle: inherited bundle changed')
                self.archives[value] = archive
                self.bundle_identities[value] = before
                self.previous.append(dict(path=value, sha256=checksum,
                                          files=len(manifest['files'])))
                for entry in manifest['files']:
                    self.add_entry(entry, ('bundle', value, entry['member']))
        if not self.files:
            raise ValueError('bundle: selection contains no evidence files')
        self.manifest = dict(schema=SCHEMA, files=[], inherited=self.previous,
                             source_budgets=self.source_budgets)
        for index, (path, (entry, origin)) in enumerate(sorted(self.files.items())):
            entry = dict(entry, member=f'files/{index:08d}')
            self.files[path] = (entry, origin)
            self.manifest['files'].append(entry)
        data = encoded(self.manifest)
        if len(data) > MAX_MANIFEST:
            raise ValueError('bundle: manifest exceeds the finite selection limit')
        self.logical_bytes = sum(item['bytes'] for item in self.manifest['files'])
        # ZIP_STORED, names, two manifest members, blocks and directory metadata.
        self.projected_bytes = self.logical_bytes + len(data) + len(self.files) * 512 + 65536
        if self.projected_bytes > MAX_BYTES:
            raise ValueError('bundle: selection exceeds the 1 GiB bundle limit')
        self.selection_sha256 = digest(data)
        export_bytes = sum(item['allocated_bytes'] for item in self.source_budgets
                           if Path(item['journal']).parent.name == 'exports')
        self.export_budget = dict(existing_allocated_bytes=export_bytes,
                                 projected_bytes=self.projected_bytes,
                                 simultaneous_bytes=export_bytes + self.projected_bytes,
                                 limit_bytes=retention.MAX_RETAINED_BYTES)
        if self.export_budget['simultaneous_bytes'] > retention.MAX_RETAINED_BYTES:
            raise ValueError('bundle: selected export and retained exports exceed the existing budget')

    def record(self, path):
        matches = [record for root, record in self.records.items() if path.is_relative_to(root)]
        if len(matches) != 1:
            raise ValueError('bundle: source must belong to one recorded allocation')
        checkout_allocation(self.checkout, matches[0])
        return matches[0]

    @contextmanager
    def open(self, path):
        record = self.record(path)
        with ExitStack() as stack:
            parent = retention.directory(Path(record['path']).parent)
            stack.callback(os.close, parent)
            fd = os.open(Path(record['path']).name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=parent)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            safe(info, self.uid, directory=True)
            if ((info.st_dev, info.st_ino) != (record['device'], record['inode'])
                    or stat.S_IMODE(info.st_mode) != record.get('mode', 0o700)
                    or retention.mount_id(fd) != retention.mount_id(parent)):
                raise ValueError('bundle: allocation identity or mount changed')
            self.check_directory(Path(record['path']), info)
            current_path = Path(record['path'])
            for part in path.relative_to(record['path']).parts:
                child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                stack.callback(os.close, child)
                current = os.fstat(child)
                safe(current, self.uid, directory=stat.S_ISDIR(current.st_mode))
                if (current.st_dev != info.st_dev
                        or retention.mount_id(child) != retention.mount_id(fd)):
                    raise ValueError('bundle: mounted evidence is refused')
                current_path = current_path / part
                if stat.S_ISDIR(current.st_mode):
                    self.check_directory(current_path, current)
                fd = child
            yield fd, os.fstat(fd)

    def check_directory(self, path, info):
        previous = self.directories.setdefault(str(path), fingerprint(info))
        if fingerprint(info) != previous:
            raise ValueError('bundle: source directory changed after inventory')

    def walk(self, fd, path, record, *, depth):
        if depth > 32:
            raise ValueError('bundle: selection nesting exceeds limit')
        before, names = fingerprint(os.fstat(fd)), sorted(os.listdir(fd))
        for name in names:
            child_path = path / name
            privacy(child_path)
            with self.open(child_path) as (child, info):
                if stat.S_ISDIR(info.st_mode):
                    self.walk(child, child_path, record, depth=depth + 1)
                else:
                    self.add_file(child, info, child_path, record)
        if before != fingerprint(os.fstat(fd)) or names != sorted(os.listdir(fd)):
            raise ValueError('bundle: selected directory changed')

    def add_file(self, fd, info, path, record):
        before = fingerprint(info)
        hashed = file_digest(fd, info.st_size)
        if before != fingerprint(os.fstat(fd)):
            raise ValueError('bundle: source changed during inventory')
        entry = dict(path=str(path), bytes=info.st_size, allocated_bytes=info.st_blocks * 512, sha256=hashed,
                     identity=before, allocation=record)
        self.add_entry(entry, ('source', str(path), None))

    def add_entry(self, entry, origin):
        checkout_allocation(self.checkout, entry['allocation'])
        old = self.files.get(entry['path'])
        if old:
            if {k: v for k, v in old[0].items() if k != 'member'} != {
                    k: v for k, v in entry.items() if k != 'member'}:
                raise ValueError('bundle: conflicting evidence for an original path')
            return
        self.files[entry['path']] = (entry, origin)
        self.total_bytes += entry['bytes']
        if len(self.files) > MAX_FILES or self.total_bytes > MAX_BYTES:
            raise ValueError('bundle: finite selection limit exceeded')

    def plan(self):
        return dict(selection_sha256=self.selection_sha256, files=len(self.files),
                    logical_bytes=self.logical_bytes, projected_bytes=self.projected_bytes,
                    export_budget=self.export_budget, manifest=self.manifest)

    def write(self, destination):
        self.revalidate()
        os.fchmod(destination.fileno(), 0o600)
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_STORED) as archive:
            for entry, origin in self.files.values():
                with archive.open(entry['member'], 'w', force_zip64=True) as output:
                    if origin[0] == 'source':
                        with self.open(Path(origin[1])) as (fd, info):
                            if fingerprint(info) != entry['identity']:
                                raise ValueError('bundle: source identity changed after inventory')
                            with os.fdopen(os.dup(fd), 'rb') as source:
                                hashed = stream_bytes(source, entry['bytes'], output)
                            if fingerprint(os.fstat(fd)) != entry['identity']:
                                raise ValueError('bundle: source changed during copying')
                    else:
                        with self.archives[origin[1]].open(origin[2]) as source:
                            hashed = stream_bytes(source, entry['bytes'], output)
                    if hashed != entry['sha256']:
                        raise ValueError('bundle: source digest changed')
            data = encoded(self.manifest)
            archive.writestr('manifest.json', data)
            archive.writestr('manifest.sha256', digest(data).encode())
        destination.flush()
        os.fsync(destination.fileno())
        archive, _ = verify_stream(destination)
        archive.close()
        self.revalidate()

    def revalidate(self):
        for path in self.directories.copy():
            with self.open(Path(path)):
                pass
        for entry, origin in self.files.values():
            if origin[0] == 'source':
                with self.open(Path(origin[1])) as (_, info):
                    if fingerprint(info) != entry['identity']:
                        raise ValueError('bundle: source identity changed after inventory')
        for path, before in self.bundle_identities.items():
            with self.open(Path(path)) as (_, info):
                if fingerprint(info) != before:
                    raise ValueError('bundle: inherited bundle identity changed')


def file_digest(fd, size):
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(fd), 'rb') as stream:
        return stream_bytes(stream, size)


def verify_stream(stream):
    """Verify every stored member; never extract archive paths."""
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    if size > MAX_BYTES:
        raise ValueError('bundle: archive exceeds limit')
    if size < 22:
        raise ValueError('bundle: incomplete archive directory')
    stream.seek(-22, os.SEEK_END)
    signature, disk, cd_disk, disk_entries, entries, cd_size, cd_offset, comment = struct.unpack(
        '<4s4H2LH', stream.read(22))
    if (signature != b'PK\x05\x06' or disk or cd_disk or comment
            or entries != disk_entries or not 3 <= entries <= MAX_FILES + 2
            or cd_size > (MAX_FILES + 2) * 512 or cd_offset + cd_size != size - 22):
        raise ValueError('bundle: oversized or unsupported archive directory')
    stream.seek(0)
    archive = zipfile.ZipFile(stream, 'r')
    try:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if (len(infos) > MAX_FILES + 2 or len(names) != len(set(names))
                or any(item.compress_type != zipfile.ZIP_STORED or item.flag_bits & 1
                       or item.is_dir() or stat.S_IFMT(item.external_attr >> 16) not in
                       (0, stat.S_IFREG) for item in infos)):
            raise ValueError('bundle: ambiguous or unsupported archive members')
        if archive.getinfo('manifest.json').file_size > MAX_MANIFEST:
            raise ValueError('bundle: manifest exceeds limit')
        if archive.getinfo('manifest.sha256').file_size != 64:
            raise ValueError('bundle: invalid manifest checksum')
        data = archive.read('manifest.json')
        if archive.read('manifest.sha256').decode('ascii') != digest(data):
            raise ValueError('bundle: manifest checksum mismatch')
        manifest = decoded(data)
        if (not isinstance(manifest, dict) or set(manifest) != {
                'schema', 'files', 'inherited', 'source_budgets'} or manifest['schema'] != SCHEMA
                or not isinstance(manifest['files'], list) or not 0 < len(manifest['files']) <= MAX_FILES):
            raise ValueError('bundle: invalid manifest')
        if (not isinstance(manifest['inherited'], list) or len(manifest['inherited']) > 256
                or not isinstance(manifest['source_budgets'], list)
                or len(manifest['source_budgets']) > 64):
            raise ValueError('bundle: invalid provenance inventory')
        for item in manifest['inherited']:
            if (not isinstance(item, dict) or set(item) != {'path', 'sha256', 'files'}
                    or not isinstance(item['sha256'], str)
                    or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None
                    or type(item['files']) is not int or not 0 < item['files'] <= MAX_FILES):
                raise ValueError('bundle: invalid inherited provenance')
            privacy(path_text(item['path']))
        for item in manifest['source_budgets']:
            if (not isinstance(item, dict) or set(item) != {'journal', 'allocated_bytes'}
                    or type(item['allocated_bytes']) is not int
                    or not 0 <= item['allocated_bytes'] <= retention.MAX_RETAINED_BYTES):
                raise ValueError('bundle: invalid source budget provenance')
            path_text(item['journal'])
        expected, paths, total = ['manifest.json', 'manifest.sha256'], set(), 0
        for index, entry in enumerate(manifest['files']):
            if not isinstance(entry, dict) or set(entry) != {
                    'path', 'bytes', 'allocated_bytes', 'sha256', 'identity', 'allocation', 'member'}:
                raise ValueError('bundle: invalid file manifest')
            path = path_text(entry['path'])
            privacy(path)
            if (str(path) in paths or entry['member'] != f'files/{index:08d}'
                    or not isinstance(entry['sha256'], str)
                    or re.fullmatch('[0-9a-f]{64}', entry['sha256']) is None
                    or type(entry['bytes']) is not int or not 0 <= entry['bytes'] <= MAX_BYTES):
                raise ValueError('bundle: ambiguous file manifest')
            record, identity_value = entry['allocation'], entry['identity']
            if (not isinstance(record, dict) or set(record) != {
                    'path', 'device', 'inode', 'mode', 'journal', 'run'}
                    or not path.is_relative_to(path_text(record['path']))
                    or not retention.valid_token(record['run']) or record['mode'] != 0o700
                    or any(type(record[key]) is not int or record[key] <= 0 for key in ('device', 'inode'))
                    or not isinstance(identity_value, list) or len(identity_value) != 10
                    or any(type(value) is not int or value < 0 for value in identity_value)
                    or not stat.S_ISREG(identity_value[2]) or identity_value[2] & 0o002
                    or identity_value[0] != record['device']
                    or identity_value[5] != 1 or identity_value[6] != entry['bytes']
                    or type(entry['allocated_bytes']) is not int
                    or entry['allocated_bytes'] != identity_value[9] * 512):
                raise ValueError('bundle: invalid allocation or file provenance')
            path_text(record['journal'])
            allocation = path_text(record['path'])
            journal = path_text(record['journal'])
            if (allocation.parent.name not in ('allocations', 'reports', 'exports')
                    or allocation.parent.parent.name not in ('host', 'privileged')
                    or journal.parent not in (allocation.parent.parent / 'state',
                                              allocation.parent.parent / 'exports')
                    or not (journal.name.startswith('retention') or journal.name == 'standalone-reports')
                    or path == allocation):
                raise ValueError('bundle: inconsistent storage provenance')
            paths.add(str(path))
            expected.append(entry['member'])
            total += entry['bytes']
            if total > MAX_BYTES or archive.getinfo(entry['member']).file_size != entry['bytes']:
                raise ValueError('bundle: invalid member size')
            with archive.open(entry['member']) as source:
                if stream_bytes(source, entry['bytes']) != entry['sha256']:
                    raise ValueError('bundle: member checksum mismatch')
        if set(names) != set(expected):
            raise ValueError('bundle: undeclared archive members')
        return archive, manifest
    except BaseException:
        archive.close()
        raise


def export(selection, *, expected, defer_cleanup=False):
    if expected != selection.selection_sha256:
        raise ValueError('bundle: selection changed; inspect a fresh plan before exporting')
    # Release only the export read lease; other source owners stay pinned.
    # Publication takes that same owner before any selected export can rotate.
    selection.export_stack.close()
    with identity(selection.uid, selection.gid):
        parent = storage.directory('exports', root=selection.checkout)
        with retention.Store(parent / 'retention').publication(
                projected_bytes=selection.projected_bytes,
                verify=lambda record: inspect_record(record, selection.uid)) as transaction:
            directory = transaction.allocate(tempfile.mkdtemp, prefix='onpc-evidence-bundle-', dir=parent)
            fd = retention.directory(directory)
            try:
                descriptor = os.open('evidence.zip', os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=fd)
                with os.fdopen(descriptor, 'w+b') as destination:
                    with identity(selection.reader_uid, selection.reader_gid):
                        selection.write(destination)
                    size = os.fstat(destination.fileno()).st_size
                    checksum = file_digest(destination.fileno(), size)
                    output_identity = fingerprint(os.fstat(destination.fileno()))
                receipt = dict(sha256=checksum, bytes=size, identity=output_identity,
                               selection_sha256=selection.selection_sha256)
                descriptor = os.open('receipt.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=fd)
                with os.fdopen(descriptor, 'wb') as output:
                    output.write(encoded(receipt))
                    output.flush()
                    os.fsync(output.fileno())
                os.fsync(fd)
                transaction.commit(defer_cleanup=defer_cleanup)
            finally:
                os.close(fd)
        return dict(receipt, path=str(directory / 'evidence.zip'), files=len(selection.files),
                    cleanup_complete=not defer_cleanup)


def inspect(checkout, uid, gid, path, *, member=None, offset=0, count=8000):
    """Verify all bytes, then return the manifest or a bounded original-file slice."""
    path = path_text(path)
    if path.name != 'evidence.zip' or not path.parent.name.startswith('onpc-evidence-bundle-'):
        raise ValueError('bundle: expected a published evidence bundle')
    if type(offset) is not int or type(count) is not int or offset < 0 or not 0 <= count <= MAX_READ:
        raise ValueError('bundle: invalid inspection byte range')
    with identity(uid, gid):
        parent = storage.directory('exports', root=checkout, create=False)
        if path.parent.parent != parent:
            raise ValueError('bundle: bundle must be in retained exports')
        with retention.Store(parent / 'retention').inspection(include_committed=True) as state:
            if state is None:
                raise ValueError('bundle: bundle has no recorded owner')
            records = [record for _, record in retention.latest_allocations([*state['history'], state])
                       if record['path'] == str(path.parent)]
            if len(records) != 1:
                raise ValueError('bundle: bundle has no unique recorded owner')
            return inspect_record(records[0], uid, member=member, offset=offset, count=count)


def inspect_record(record, uid, *, member=None, offset=0, count=8000):
    """Already owner-locked publication verification, including deferred recovery."""
    directory = path_text(record['path'])
    if not directory.name.startswith('onpc-evidence-bundle-'):
        raise ValueError('bundle: expected a recorded evidence bundle allocation')
    selection = Selection(directory.parents[4], uid, os.getegid(), [], [], [])
    selection.records = {str(directory): record}
    with selection.open(directory / 'receipt.json') as (fd, info):
        receipt_identity = fingerprint(info)
        if info.st_size > 4096:
            raise ValueError('bundle: invalid receipt size')
        receipt = decoded(os.read(fd, 4096))
    with selection.open(directory / 'evidence.zip') as (fd, info):
        before = fingerprint(info)
        if (not isinstance(receipt, dict) or set(receipt) != {
                'sha256', 'bytes', 'selection_sha256', 'identity'} or receipt['bytes'] != info.st_size
                or file_digest(fd, info.st_size) != receipt['sha256']
                or receipt['identity'] != before):
            raise ValueError('bundle: publication checksum mismatch')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            archive, manifest = verify_stream(stream)
            try:
                for entry in manifest['files']:
                    checkout_allocation(directory.parents[4], entry['allocation'])
                if digest(encoded(manifest)) != receipt['selection_sha256']:
                    raise ValueError('bundle: selection checksum mismatch')
                if member is None:
                    result = dict(receipt, files=len(manifest['files']), manifest=manifest)
                else:
                    entries = [entry for entry in manifest['files'] if entry['path'] == member]
                    if len(entries) != 1:
                        raise ValueError('bundle: original path is not in the manifest')
                    with archive.open(entries[0]['member']) as source:
                        source.seek(offset)
                        result = source.read(count)
            finally:
                archive.close()
        if fingerprint(os.fstat(fd)) != before:
            raise ValueError('bundle: archive changed during inspection')
    with selection.open(directory / 'receipt.json') as (_, current):
        if fingerprint(current) != receipt_identity:
            raise ValueError('bundle: receipt changed during inspection')
    with selection.open(directory) as (fd, _):
        if set(os.listdir(fd)) != {'receipt.json', 'evidence.zip'}:
            raise ValueError('bundle: incomplete or unexpected publication files')
    return result


def finish(checkout, uid, gid):
    with identity(uid, gid):
        parent = storage.directory('exports', root=checkout, create=False)
        return retention.Store(parent / 'retention').finish_publication(
            verify=lambda record: inspect_record(record, uid))


def recover(checkout, uid, gid):
    """Recover only the export journal's recorded interrupted publication."""
    with identity(uid, gid):
        parent = storage.directory('exports', root=checkout, create=False)
        with retention.Store(parent / 'retention').publication(
                projected_bytes=0, verify=lambda record: inspect_record(record, uid)):
            pass
