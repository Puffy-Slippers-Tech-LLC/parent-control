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

import evidence_identity as logical
import test_retention as retention
import test_storage as storage

MAX_FILES = 60000
MAX_SOURCE_BUDGETS = 64
MAX_MANIFEST = 64 * 1024 ** 2
MAX_READ = 16 * 1024 ** 2
MAX_BYTES = 1024 ** 3
SCHEMA = 1


class EvidenceUnavailable(FileNotFoundError):
    """Explicit plan references lack live or exactly archived proof."""

    def __init__(self, paths):
        self.paths = list(paths)
        super().__init__('plan evidence: exact referenced proof is unavailable: '
                         + ', '.join(self.paths)
                         + '. Renew the affected acceptance checks and evidence; '
                           'do not recreate expired reports or weaken acceptance.')

    def payload(self):
        return dict(error='evidence_unavailable', paths=self.paths)


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
    ordinary = path.parent in {base / owner / kind for owner in ('host', 'privileged')
                               for kind in ('allocations', 'reports', 'exports')}
    parts = path.relative_to(base).parts if path.is_relative_to(base) else ()
    plan = (len(parts) in (4, 5) and parts[0] in ('host', 'privileged')
            and parts[1] == 'plans' and re.fullmatch(r'[0-9a-f]{64}', parts[2])
            and ((len(parts) == 4 and re.fullmatch(r'[0-9a-f]{32}', parts[3]))
                 or (len(parts) == 5 and parts[3] == 'evidence'
                     and parts[4].startswith('onpc-evidence-bundle-'))))
    capture = (len(parts) == 4 and parts[0] in ('host', 'privileged')
               and parts[1] == 'captures' and re.fullmatch(r'[0-9a-f]{64}', parts[2])
               and parts[3] == 'snapshot')
    if not ordinary and not plan and not capture:
        raise ValueError('bundle: allocation is outside the trusted checkout storage')


def plan_parent(checkout, namespace, *, create=False):
    """A plan's bounded publication owner, isolated from ordinary exports."""
    if not isinstance(namespace, str) or not re.fullmatch(r'[0-9a-f]{64}', namespace):
        raise ValueError('bundle: invalid plan namespace')
    parent = storage.directory('plans', root=checkout, create=create) / namespace
    if create:
        retention.ensure_directory(parent)
        retention.ensure_directory(parent / 'evidence')
    return parent / 'evidence'


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
        # A quoted header in source is not key material. Refuse actual header
        # lines and serialized keys with a base64 body line, preserving quoted
        # test source verbatim. A read-chunk boundary is never file EOF; the
        # overlap also covers serialized line endings split between reads.
        endings = rb'[\r\n]|(?:\\r)?\\n[A-Za-z0-9+/=]+(?:\\r)?\\n'
        boundary = b'(?=' + endings + (rb'|\Z)' if len(chunk) == remaining else b')')
        if re.search(rb'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----' + boundary, probe):
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
    def __init__(self, checkout, uid, gid, targets, sources, bundles, *, plan_namespace=None,
                 references=(), logical_records=(), record_references=(), consumer=None, captures=()):
        self.checkout, self.uid, self.gid = Path(checkout), uid, gid
        self.targets, self.sources, self.bundles = targets, sources, bundles
        self.references = list(references)
        self.logical_records = list(logical_records)
        self.record_references, self.consumer = list(record_references), consumer
        self.captures = list(captures)
        self.capture_requests = []
        self.logical_origins = {}
        self.logical_storage = {}
        self.stack = ExitStack()
        self.export_stack = self.stack.enter_context(ExitStack())
        self.reader_uid, self.reader_gid = os.geteuid(), os.getegid()
        self.records, self.files, self.archives = {}, {}, {}
        self.directories = {}
        self.bundle_identities = {}
        self.source_budgets, self.previous = [], []
        self.total_bytes = 0
        self.plan_namespace = plan_namespace

    def publication_parent(self, *, create=False):
        # The installed reader inventories privileged sources as root, while
        # every publication belongs to its authenticated unprivileged caller.
        # Resolve under that identity even after catalogue() restores root.
        with identity(self.uid, self.gid):
            namespace = getattr(self, 'capture_namespace', self.plan_namespace)
            return (plan_parent(self.checkout, namespace, create=create)
                    if namespace is not None else
                    storage.directory('exports', root=self.checkout, create=create))

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
        if self.targets:
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
            result += [(parent / f'recovery-diagnostics-{self.uid}-{target}', 0, 0)
                       for target in sorted(self.targets)
                       if (parent / f'recovery-diagnostics-{self.uid}-{target}').exists()]
        if os.geteuid() == 0:
            try:
                parent = storage.directory('state', root=self.checkout, create=False)
            except FileNotFoundError:
                pass  # Host-only checkouts may have no privileged storage yet.
            else:
                diagnostics = parent / f'recovery-diagnostics-{self.uid}'
                if diagnostics.exists():
                    result.append((diagnostics, 0, 0))
        with identity(self.uid, self.gid):
            try:
                parent = storage.directory('state', root=self.checkout, create=False)
            except FileNotFoundError:
                parent = None  # A plan can precede its first host test run.
            names = ('retention-host', 'retention-batch', 'retention', 'standalone-reports',
                     *(f'retention-{target}' for target in sorted(self.targets)))
            for name in names:
                if parent is not None and (parent / name).exists():
                    result.append((parent / name, self.uid, self.gid))
            if self.plan_namespace is not None:
                proof = self.publication_parent()
                result.append((proof.parent / 'retention', self.uid, self.gid))
                if (proof / 'retention').exists():
                    result.append((proof / 'retention', self.uid, self.gid))
            try:
                exports = storage.directory('exports', root=self.checkout, create=False)
            except FileNotFoundError:
                return result  # The first bundle has no existing export journal.
            if (exports / 'retention').exists():
                result.append((exports / 'retention', self.uid, self.gid))
        return result

    def load(self):
        values = [*self.sources, *self.bundles, *self.references, *self.record_references, *self.captures]
        if not values or len(values) > 256:
            raise ValueError('bundle: select between one and 256 explicit sources')
        if len(set(values)) != len(values):
            raise ValueError('bundle: duplicate selected source')
        if self.references and self.plan_namespace is None:
            raise ValueError('bundle: renewable references require a validated plan')
        self.structured_references()
        # Capture-only reads consult finite finished-slot registrations. Opening
        # the producer catalogue here would inspect an unrelated active parent.
        journals = self.catalogue() if self.sources or self.bundles or self.references else ()
        if self.captures and not journals:
            import evidence_capture
            evidence_capture.validate_targets(self.checkout, self.targets)
        for journal, uid, gid in journals:
            with identity(uid, gid):
                publication = (journal.parent.name == 'exports' if self.plan_namespace is None else
                               journal == self.publication_parent() / 'retention')
                owner = self.export_stack if publication else self.stack
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
                if len(self.source_budgets) > MAX_SOURCE_BUDGETS:
                    raise ValueError('bundle: source budget entry limit exceeded')
        if self.captures:
            import evidence_capture
            for capture_id in self.captures:
                metadata = {}
                request = self.stack.enter_context(evidence_capture.capture_scope(
                    self.checkout, self.uid, self.gid, capture_id, metadata=metadata))
                self.capture_requests.append(request)
                target = request['record']['context']['target']
                if (target and target not in self.targets) or (not target and self.targets):
                    raise ValueError('bundle: capture target does not match explicit selection')
                allocation = request['sealed']['allocation']
                if allocation['path'] in self.records:
                    raise ValueError('bundle: duplicate capture allocation')
                self.records[allocation['path']] = allocation
                self.logical_records.append(request['record'])
                # Original identity is authenticated by the same pinned private
                # registration, never recovered by reopening a live original.
                producer_uid = request['producer']['owner']['identity']['uid']
                with identity(producer_uid, 0 if producer_uid == 0 else self.gid):
                    originals = {item['member_id']: item['identity'] for item in metadata['originals']}
                    for mapping in request['sealed']['mappings']:
                        path = Path(mapping['sealed_path'])
                        self.load_source(path)
                        key = request['record']['record_id'], mapping['member_id']
                        self.logical_storage[key] = str(path)
                        self.logical_origins[key] = dict(original_path=mapping['original_path'],
                            source_allocation=mapping['source_allocation'], identity=originals[mapping['member_id']])
                measured = retention.allocation_bytes(allocation)
                self.source_budgets.append(dict(journal=allocation['journal'], allocated_bytes=measured))
                if len(self.source_budgets) > MAX_SOURCE_BUDGETS:
                    raise ValueError('bundle: source budget entry limit exceeded')
            import capture_publication
            capture_publication.prepare_selection(self)
        missing, archived = [], []
        for value in self.references:
            path = path_text(value)
            privacy(path)
            if path.name == 'evidence.zip':
                if not path.parent.name.startswith('onpc-evidence-bundle-'):
                    raise ValueError('bundle: expected a retained evidence bundle')
                (archived if self.reference_present(path) else missing).append(value)
        for value in [*self.bundles, *archived]:
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
                verify_receipt(receipt, info, checksum)
                stream = self.stack.enter_context(os.fdopen(os.dup(fd), 'rb'))
                archive, manifest = verify_stream(stream)
                self.stack.callback(archive.close)
                if (digest(encoded(manifest)) != receipt['selection_sha256']
                        or fingerprint(os.fstat(fd)) != before
                        or receipt.get('schema', 1) != manifest['schema']):
                    raise ValueError('bundle: inherited bundle changed')
                if manifest['schema'] == 2:
                    logical.validate_records(manifest['records'], manifest['member_map'],
                                             manifest['files'], repository=self.repository())
                    self.logical_records.extend(manifest['records'])
                    physical_files = {item['member']: item for item in manifest['files']}
                    for mapping in manifest['member_map']:
                        key = (mapping['record_id'], mapping['member_id'])
                        origin = mapping['original_provenance']
                        if key in self.logical_origins and self.logical_origins[key] != origin:
                            raise ValueError('bundle: conflicting logical member provenance')
                        self.logical_origins[key] = origin
                        physical = physical_files[mapping['physical_member']]
                        self.logical_storage[key] = physical['path']
                self.archives[value] = archive
                self.bundle_identities[value] = before
                self.previous.append(dict(path=value, sha256=checksum,
                                          files=len(manifest['files'])))
                for entry in manifest['files']:
                    self.add_entry(entry, ('bundle', value, entry['member']))
        for value in self.sources:
            self.load_source(path_text(value))
        for value in self.references:
            path = path_text(value)
            if path.name == 'evidence.zip':
                continue
            if self.reference_present(path):
                self.load_source(path)
            elif value not in self.files:
                missing.append(value)
        if missing:
            raise EvidenceUnavailable(missing)
        if not self.files:
            raise ValueError('bundle: selection contains no evidence files')
        self.manifest = dict(schema=SCHEMA, files=[], inherited=self.previous,
                             source_budgets=self.source_budgets)
        for index, (path, (entry, origin)) in enumerate(sorted(self.files.items())):
            entry = dict(entry, member=f'files/{index:08d}')
            self.files[path] = (entry, origin)
            self.manifest['files'].append(entry)
        self.logical_manifest()
        data = encoded(self.manifest)
        if len(data) > MAX_MANIFEST:
            raise ValueError('bundle: manifest exceeds the finite selection limit')
        self.logical_bytes = sum(item['bytes'] for item in self.manifest['files'])
        # ZIP_STORED, names, two manifest members, blocks and directory metadata.
        self.projected_bytes = self.logical_bytes + len(data) + len(self.files) * 512 + 65536
        if self.projected_bytes > MAX_BYTES:
            raise ValueError('bundle: selection exceeds the 1 GiB bundle limit')
        self.selection_sha256 = digest(data)
        namespace = getattr(self, 'capture_namespace', self.plan_namespace)
        export_journal = None
        if namespace is not None:
            try:
                export_journal = self.publication_parent() / 'retention'
            except FileNotFoundError:
                pass  # First capture planning creates no destination storage.
        export_bytes = sum(item['allocated_bytes'] for item in self.source_budgets
                           if (Path(item['journal']).parent.name == 'exports'
                               if namespace is None else
                               Path(item['journal']) == export_journal))
        projected = 0 if getattr(self, 'capture_reuse', None) is not None else self.projected_bytes
        self.export_budget = dict(existing_allocated_bytes=export_bytes,
                                 projected_bytes=projected,
                                 simultaneous_bytes=export_bytes + projected,
                                 limit_bytes=retention.MAX_RETAINED_BYTES)
        # Publication checks simultaneous capacity under its owner lock, after
        # attempting reuse. A verified existing copy needs no staging budget.
        if getattr(self, 'capture_reuse', None) is not None:
            self.manifest = self.capture_reuse['manifest']
            self.selection_sha256 = digest(encoded(self.manifest))

    def repository(self):
        with retention.directory_descriptor(self.checkout) as fd:
            info = os.fstat(fd)
            return dict(root=str(self.checkout), device=info.st_dev, inode=info.st_ino, uid=self.uid)

    def structured_references(self):
        """Reader-before-writer activation gate for authenticated declarations.

        E02 registers the wire syntax, not a consumer catalogue. Caller JSON
        cannot authenticate a claim revision or its required input assertions.
        The custody owner must register that authority before selection activates.
        Trusted host code can already resolve with an explicit reference_scope.
        """
        if bool(self.record_references) != (self.consumer is not None):
            raise ValueError('bundle: structured references require exactly one consumer')
        if not self.record_references:
            return
        logical.validate_consumer(self.consumer)
        context = self.consumer['expected_context']
        if context['repository'] != self.repository():
            raise logical.EvidenceContextError('bundle: consumer belongs to another checkout')
        from execution_plan import Plan, plan_namespace
        plan = Plan.load(self.checkout, context['workflow'])
        if self.plan_namespace != plan_namespace(plan.path):
            raise logical.EvidenceContextError('bundle: consumer belongs to another plan')
        for reference in self.record_references:
            logical.parse_reference(reference)
        raise logical.EvidenceContextError('bundle: structured selection requires an '
                                           'owner-registered consumer; activation is pending')

    def logical_manifest(self):
        if not self.logical_records:
            return
        records = {}
        for record in self.logical_records:
            key = record['record_id']
            if key in records and records[key] != record:
                raise logical.EvidenceIntegrityError('bundle: conflicting logical record closure')
            records[key] = record
        mappings = []
        for record_id, record in sorted(records.items()):
            for member in record['members']:
                key = (record_id, member['member_id'])
                entry = self.files.get(self.logical_storage.get(key, member['original_path']))
                if entry is None:
                    raise ValueError('bundle: logical member has no selected original')
                entry = entry[0]
                provenance = self.logical_origins.get(key, dict(original_path=entry['path'],
                    source_allocation=entry['allocation'], identity=entry['identity']))
                mappings.append(dict(record_id=record_id, member_id=member['member_id'],
                                     physical_member=entry['member'], original_provenance=provenance))
        mappings.sort(key=lambda item: (item['record_id'], item['member_id']))
        self.manifest.update(schema=2, records=[records[key] for key in sorted(records)], member_map=mappings)
        logical.validate_records(self.manifest['records'], mappings, self.manifest['files'],
                                 repository=self.repository())
        for reference in self.record_references:
            _, selector = logical.parse_reference(reference)
            resolve_member(self.manifest, **selector, consumer=self.consumer)

    def reference_present(self, path):
        """Probe only checkout evidence without traversing a source symlink.

        This runs under the reader's identity and pinned journal leases. Missing
        paths are renewable, while inaccessible or unsafe paths still refuse.
        Existing files must subsequently pass recorded-allocation validation.
        """
        for ancestor in (path, *path.parents):
            try:
                checkout_allocation(self.checkout, dict(path=str(ancestor)))
            except ValueError:
                continue
            break
        else:
            raise ValueError('bundle: reference is outside checkout evidence storage')
        try:
            with retention.directory_descriptor(path.parent) as parent:
                os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def load_source(self, path):
        privacy(path)
        record = self.record(path)
        # A plan accepts the complete host report and its exact supporting
        # records. Missing named reports must never be replaced by siblings.
        if self.plan_namespace is not None and Path(record['path']).parent.name == 'reports':
            with self.open(path):
                pass
            path = Path(record['path'])
        with self.open(path) as (fd, info):
            if stat.S_ISDIR(info.st_mode):
                self.walk(fd, path, record, depth=0)
            else:
                self.add_file(fd, info, path, record)

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
            if old[1][0] == 'bundle' and origin[0] == 'source':
                self.files[entry['path']] = (entry, origin)
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


def verify_receipt(receipt, info, checksum):
    keys = {'sha256', 'bytes', 'selection_sha256', 'identity'}
    if isinstance(receipt, dict) and 'schema' in receipt:
        keys.add('schema')
        if type(receipt['schema']) is not int or receipt['schema'] != 2:
            raise ValueError('bundle: unsupported receipt schema')
    if (not isinstance(receipt, dict) or set(receipt) != keys
            or type(receipt['bytes']) is not int or receipt['bytes'] != info.st_size
            or type(receipt['identity']) is not list or len(receipt['identity']) != 10
            or any(type(value) is not int or value < 0 for value in receipt['identity'])
            or receipt['sha256'] != checksum or receipt['identity'] != fingerprint(info)
            or not isinstance(receipt['selection_sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', receipt['selection_sha256']) is None):
        raise ValueError('bundle: publication checksum mismatch')


def resolve_member(manifest, *, record_id, member_id, closure_sha256, consumer=None):
    """Select an exact immutable claim after the complete manifest was verified."""
    # Use the shared parser for strict ID types and syntax, including direct API
    # calls which did not originate in a Markdown destination.
    logical.parse_reference('accepted-evidence.json#onpc-evidence-v1:'
                            f'{record_id}:{member_id}:{closure_sha256}')
    if manifest['schema'] != 2:
        raise logical.EvidenceContextError('bundle: legacy navigation has no logical claim')
    records = {item['record_id']: item for item in manifest['records']}
    record = records.get(record_id)
    if record is None:
        raise LogicalEvidenceUnavailable([dict(record_id=record_id, member_id=member_id,
                                               closure_sha256=closure_sha256)])
    if record['closure_sha256'] != closure_sha256:
        raise logical.EvidenceIntegrityError('bundle: requested closure does not match')
    if consumer is not None:
        logical.match_context(record, consumer)
        selector = dict(kind='evidence', record_id=record_id, member_id=member_id,
                        closure_sha256=closure_sha256)
        if selector not in consumer['references']:
            raise logical.EvidenceContextError('bundle: member is not declared by the consumer')
    matches = [item for item in record['members'] if item['member_id'] == member_id]
    if not matches:
        raise LogicalEvidenceUnavailable([dict(record_id=record_id, member_id=member_id,
                                               closure_sha256=closure_sha256)])
    return record, matches[0]


class LogicalEvidenceUnavailable(EvidenceUnavailable):
    def __init__(self, references):
        self.references = references
        super().__init__([encoded(item).decode() for item in references])

    def payload(self):
        return dict(error='evidence_unavailable', schema=1, references=self.references)


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
        keys = {'schema', 'files', 'inherited', 'source_budgets'}
        if isinstance(manifest, dict) and manifest.get('schema') == 2:
            keys.update(('records', 'member_map'))
        if (not isinstance(manifest, dict) or set(manifest) != keys
                or type(manifest['schema']) is not int or manifest['schema'] not in (1, 2)
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
            ordinary = (allocation.parent.name in ('allocations', 'reports', 'exports')
                        and allocation.parent.parent.name in ('host', 'privileged')
                        and journal.parent in (allocation.parent.parent / 'state',
                                               allocation.parent.parent / 'exports')
                        and (journal.name.startswith('retention') or journal.name == 'standalone-reports'
                             or re.fullmatch(r'recovery-diagnostics-[0-9]+(?:-[A-Za-z0-9._-]+)?',
                                             journal.name)))
            plan_run = (re.fullmatch(r'[0-9a-f]{32}', allocation.name)
                        and re.fullmatch(r'[0-9a-f]{64}', allocation.parent.name)
                        and allocation.parent.parent.name == 'plans'
                        and allocation.parent.parent.parent.name in ('host', 'privileged')
                        and journal == allocation.parent / 'retention')
            plan_export = (allocation.name.startswith('onpc-evidence-bundle-')
                           and allocation.parent.name == 'evidence'
                           and re.fullmatch(r'[0-9a-f]{64}', allocation.parent.parent.name)
                           and allocation.parent.parent.parent.name == 'plans'
                           and allocation.parents[3].name in ('host', 'privileged')
                           and journal == allocation.parent / 'retention')
            capture = (allocation.name == 'snapshot'
                       and re.fullmatch(r'[0-9a-f]{64}', allocation.parent.name)
                       and allocation.parent.parent.name == 'captures'
                       and allocation.parents[2].name in ('host', 'privileged')
                       and journal == allocation.parent / 'retention-sealed')
            if not (ordinary or plan_run or plan_export or capture) or path == allocation:
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
        if manifest['schema'] == 2:
            logical.validate_records(manifest['records'], manifest['member_map'], manifest['files'])
        return archive, manifest
    except BaseException:
        archive.close()
        raise


def export(selection, *, expected, defer_cleanup=False):
    if selection.captures:
        import capture_publication
        return capture_publication.publish(selection, expected=expected, defer_cleanup=defer_cleanup)
    if expected != selection.selection_sha256:
        raise ValueError('bundle: selection changed; inspect a fresh plan before exporting')
    # Release only the export read lease; other source owners stay pinned.
    # Publication takes that same owner before any selected export can rotate.
    selection.export_stack.close()
    with identity(selection.uid, selection.gid):
        parent = selection.publication_parent(create=True)
        with retention.Store(parent / 'retention').publication(
                projected_bytes=selection.projected_bytes,
                verify=lambda record: inspect_publication(record, selection.uid, checkout=selection.checkout),
                reuse=lambda state: reuse_export(selection, state), wait=True) as transaction:
            if transaction.reused is not None:
                return transaction.reused
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
                if selection.manifest['schema'] == 2:
                    receipt['schema'] = 2
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


def reuse_export(selection, state):
    """Reuse only an owner-locked, freshly verified complete publication.

    Journal usage is an operational snapshot, not selected source provenance.
    Everything else, including original identities, owner/run, inherited copies
    and logical claims, must match the newly authenticated inventory exactly.
    """
    if state is None:
        return None
    selected = {key: value for key, value in selection.manifest.items() if key != 'source_budgets'}
    with identity(selection.reader_uid, selection.reader_gid):
        selection.revalidate()
    records = retention.latest_allocations([*state['history'], state])
    for _, record in reversed(records):
        directory = Path(record['path'])
        if not directory.name.startswith('onpc-evidence-bundle-'):
            continue
        with verified_record(record, selection.uid, checkout=selection.checkout) as (verified, _):
            manifest = verified['manifest']
            if {key: value for key, value in manifest.items() if key != 'source_budgets'} != selected:
                continue
            with identity(selection.reader_uid, selection.reader_gid):
                selection.revalidate()
            receipt = {key: value for key, value in verified.items() if key != 'manifest'}
            return dict(receipt, path=str(directory / 'evidence.zip'), cleanup_complete=True)
    return None


def inspect_publication(record, uid, *, checkout=None):
    """Verify either established export format in the shared owning journal."""
    if Path(record['path']).name.startswith('onpc-artifact-export-'):
        import artifact_export
        return artifact_export.verify(record, uid, checkout=checkout)
    return inspect_record(record, uid, checkout=checkout)


def inspect(checkout, uid, gid, path, *, member=None, offset=0, count=8000,
            record_id=None, member_id=None, closure_sha256=None):
    """Verify all bytes, then return the manifest or a bounded original-file slice."""
    path = path_text(path)
    if path.name != 'evidence.zip' or not path.parent.name.startswith('onpc-evidence-bundle-'):
        raise ValueError('bundle: expected a published evidence bundle')
    if type(offset) is not int or type(count) is not int or offset < 0 or not 0 <= count <= MAX_READ:
        raise ValueError('bundle: invalid inspection byte range')
    with identity(uid, gid):
        base = Path(checkout) / 'output/test-runs'
        parts = path.relative_to(base).parts if path.is_relative_to(base) else ()
        if len(parts) == 6 and parts[0] in ('host', 'privileged') and parts[1] == 'plans' and parts[3] == 'evidence':
            parent = plan_parent(checkout, parts[2])
        else:
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
            return inspect_record(records[0], uid, checkout=checkout, member=member, offset=offset, count=count,
                                  record_id=record_id, member_id=member_id, closure_sha256=closure_sha256)


def inspect_record(record, uid, *, checkout=None, member=None, offset=0, count=8000,
                   record_id=None, member_id=None, closure_sha256=None):
    """Already owner-locked publication verification, including deferred recovery."""
    if type(offset) is not int or type(count) is not int or offset < 0 or not 0 <= count <= MAX_READ:
        raise ValueError('bundle: invalid inspection byte range')
    with verified_record(record, uid, checkout=checkout) as (verified, read):
        structured = any(value is not None for value in (record_id, member_id, closure_sha256))
        if structured:
            return read(member, offset=offset, count=count, record_id=record_id,
                        member_id=member_id, closure_sha256=closure_sha256)
        return verified if member is None else read(member, offset=offset, count=count)


@contextmanager
def verified_record(record, uid, *, checkout=None):
    """Verify once, then read bounded members while the caller holds ownership.

    Keep the archive descriptor open and check its identity throughout the read
    scope. No verification result is cached across scopes or publications.
    """
    directory = path_text(record['path'])
    if not directory.name.startswith('onpc-evidence-bundle-'):
        raise ValueError('bundle: expected a recorded evidence bundle allocation')
    checkout = Path(checkout) if checkout is not None else directory.parents[4]
    selection = Selection(checkout, uid, os.getegid(), [], [], [])
    selection.records = {str(directory): record}
    with selection.open(directory / 'receipt.json') as (fd, info):
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('bundle: publication is not private to its caller')
        receipt_identity = fingerprint(info)
        if info.st_size > 4096:
            raise ValueError('bundle: invalid receipt size')
        receipt = decoded(os.read(fd, 4096))
    with selection.open(directory / 'evidence.zip') as (fd, info):
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('bundle: publication is not private to its caller')
        before = fingerprint(info)
        verify_receipt(receipt, info, file_digest(fd, info.st_size))
        with os.fdopen(os.dup(fd), 'rb') as stream:
            archive, manifest = verify_stream(stream)
            try:
                for entry in manifest['files']:
                    checkout_allocation(checkout, entry['allocation'])
                if (digest(encoded(manifest)) != receipt['selection_sha256']
                        or receipt.get('schema', 1) != manifest['schema']):
                    raise ValueError('bundle: selection checksum mismatch')
                if manifest['schema'] == 2:
                    logical.validate_records(manifest['records'], manifest['member_map'],
                                             manifest['files'], repository=selection.repository())
                members = {entry['path']: entry for entry in manifest['files']}
                physical_members = {entry['member']: entry for entry in manifest['files']}
                logical_mappings = {(entry['record_id'], entry['member_id']): entry
                                    for entry in manifest.get('member_map', [])}

                def unchanged():
                    if fingerprint(os.fstat(fd)) != before:
                        raise ValueError('bundle: archive changed during inspection')
                    with selection.open(directory / 'receipt.json') as (_, current):
                        if fingerprint(current) != receipt_identity:
                            raise ValueError('bundle: receipt changed during inspection')
                    with selection.open(directory / 'evidence.zip') as (_, current):
                        if fingerprint(current) != before:
                            raise ValueError('bundle: archive changed during inspection')

                def read(member=None, *, offset=0, count=8000, record_id=None,
                         member_id=None, closure_sha256=None):
                    if (type(offset) is not int or type(count) is not int or offset < 0
                            or not 0 <= count <= MAX_READ):
                        raise ValueError('bundle: invalid inspection byte range')
                    if archive.fp is None:
                        raise ValueError('bundle: verified archive is closed')
                    unchanged()
                    selectors = (record_id, member_id, closure_sha256)
                    if any(value is not None for value in selectors):
                        if member is not None or any(value is None for value in selectors):
                            raise ValueError('bundle: select an original path or one complete logical member')
                        resolve_member(manifest, record_id=record_id,
                            member_id=member_id, closure_sha256=closure_sha256)
                        mapping = logical_mappings[(record_id, member_id)]
                        selected = physical_members[mapping['physical_member']]
                        member = selected['path']
                    if member not in members:
                        raise ValueError('bundle: original path is not in the manifest')
                    with archive.open(members[member]['member']) as source:
                        source.seek(offset)
                        result = source.read(count)
                    unchanged()
                    return result

                unchanged()
                yield dict(receipt, files=len(manifest['files']), manifest=manifest), read
                unchanged()
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


def finish(checkout, uid, gid):
    with identity(uid, gid):
        parent = storage.directory('exports', root=checkout, create=False)
        return retention.Store(parent / 'retention').finish_publication(
            verify=lambda record: inspect_publication(record, uid, checkout=checkout))


def recover(checkout, uid, gid):
    """Recover only the export journal's recorded interrupted publication."""
    with identity(uid, gid):
        parent = storage.directory('exports', root=checkout, create=False)
        with retention.Store(parent / 'retention').publication(
                projected_bytes=0, verify=lambda record: inspect_publication(record, uid, checkout=checkout)):
            pass
