"""Private, leased VM disaster recovery dispatched by onpc-setup.

Each VM has one checksummed archive, atomically replaced after verification.
Restoration publishes files individually under a durable, identity-bound journal;
it never deletes a backup, displaced file, or unfinished controller evidence.
"""
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import stat
import sys
import threading
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/integration'))
sys.path.insert(0, str(ROOT / 'tools'))
import vm_config
import prepare_baseline as base
from watch_activity import operation

JOURNAL = 'restore-vms.json'
SCHEMA = 1


def require(condition, category):
    base.require(condition, 'vm-recovery:' + category)


def private_directory(path, *, create=False):
    if create:
        base.canonical(path.parent)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            # A setgid storage parent otherwise supplies its group and setgid
            # bit even with mkdir(0700). Normalize only our newly created inode.
            info = path.lstat()
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(fd)
                require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino) and
                        opened.st_uid == os.geteuid(), 'directory-changed')
                os.fchown(fd, os.geteuid(), os.getegid())
                os.fchmod(fd, 0o700)
                os.fsync(fd)
            finally:
                os.close(fd)
        base.sync_directory(path.parent)
    base.canonical(path)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and
            info.st_gid == os.getegid() and stat.S_IMODE(info.st_mode) == 0o700,
            'private-directory; use a dedicated root-owned 0700 backup_root')
    return {'device': info.st_dev, 'inode': info.st_ino}


def ensure_parents(path):
    """Create missing host image parents without adopting links or changing modes."""
    for component in reversed((path, *path.parents)):
        if os.path.lexists(component):
            base.canonical(component)
            require(component.is_dir(), 'destination-parent')
        else:
            component.mkdir(mode=0o755)
            base.sync_directory(component.parent)


def atomic(path, value):
    """Publish only in an already validated private directory; retain partial files."""
    private_directory(path.parent)
    if os.path.lexists(path):
        base.identity(path, private=True, mode=0o600)
    temporary = path.with_name('.write-' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(base.encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    base.sync_directory(path.parent)


def read_json(path):
    base.identity(path, private=True, mode=0o600)
    require(path.stat().st_size <= 16 * 1024 * 1024, 'record-too-large')
    return base.parse_json(path.read_bytes())


def checksum(path):
    # Full hashes are intentional for disaster archives, never ordinary VM tests.
    return base.digest(path)


def stamp(path):
    item = base.identity(path)
    info = path.stat()
    return dict(item, size=info.st_size, mtime=info.st_mtime_ns, ctime=info.st_ctime_ns)


def copy_file(source, destination, *, expected=None, guard=lambda: None, created=lambda path: None):
    """Copy a descriptor-pinned regular file, preserving sparse QCOW2 holes.

    Exclusive creation and no reflinks give the generation independent bytes.
    Partial payloads remain unpublished and are retained after interruption.
    """
    before = stamp(source)
    guard()
    require(expected is None or before == expected, 'source-changed')
    base.canonical(destination.parent)
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    destination_fd = None
    try:
        info = os.fstat(source_fd)
        require((info.st_dev, info.st_ino) == (before['device'], before['inode']), 'source-changed')
        destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created(destination)
        offset, size = 0, info.st_size
        sparse = True
        while offset < size:
            if sparse:
                try:
                    start = os.lseek(source_fd, offset, os.SEEK_DATA)
                    end = min(size, os.lseek(source_fd, start, os.SEEK_HOLE))
                except OSError as error:
                    if error.errno == errno.ENXIO:
                        break
                    if error.errno not in (errno.EINVAL, errno.ENOTSUP):
                        raise
                    sparse = False
                    start, end = offset, size
            else:
                start, end = offset, size
            os.lseek(source_fd, start, os.SEEK_SET)
            os.lseek(destination_fd, start, os.SEEK_SET)
            while start < end:
                guard()
                data = os.read(source_fd, min(4 * 1024 * 1024, end - start))
                require(bool(data), 'source-short-read')
                view = memoryview(data)
                while view:
                    written = os.write(destination_fd, view)
                    require(written > 0, 'destination-short-write')
                    view = view[written:]
                start += len(data)
            offset = end
        os.ftruncate(destination_fd, size)
        os.fsync(destination_fd)
        guard()
        require(stamp(source) == before, 'source-changed')
    finally:
        os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)
    base.sync_directory(destination.parent)


def tree_files(root):
    if not os.path.lexists(root):
        return []
    private_directory(root)
    result = []
    for path in sorted(root.rglob('*')):
        # Locks and this workflow's journals/retained displacement directories
        # are not baseline provenance and must never replace a live lease.
        relative = path.relative_to(root)
        if any(part.startswith('.restore-vms-') for part in relative.parts):
            continue
        if relative.as_posix() in ('.lock', JOURNAL):
            continue
        if path.is_dir() and not path.is_symlink():
            private_directory(path)
        else:
            base.identity(path, private=True, mode=0o600)
            require(path.stat().st_size <= 64 * 1024 * 1024, 'state-file-too-large')
            result.append(path)
    return result


def online_directory(identity, *, create=False):
    # Preserve saved-memory SSH credentials through the shared storage route.
    from test_storage import directory
    path = directory('state') / ('online-appsnapshot-' + identity)
    if create:
        private_directory(path, create=True)
    return path


def snapshot_inventory(domain):
    snapshots = [{'name': snap.getName(), 'xml': snap.getXMLDesc(0)}
                 for snap in domain.listAllSnapshots(0)]
    current = domain.snapshotCurrent(0).getName() if domain.hasCurrentSnapshot(0) else None
    return sorted(snapshots, key=lambda item: item['name']), current


def snapshot_order(snapshots):
    remaining = {item['name']: item for item in snapshots}
    require(len(remaining) == len(snapshots), 'duplicate-snapshot')
    require(all(ET.fromstring(item['xml']).findtext('parent/name') in (None, *remaining)
                for item in snapshots), 'missing-snapshot-parent')
    ordered = []
    while remaining:
        ready = [name for name, item in remaining.items()
                 if ET.fromstring(item['xml']).findtext('parent/name') not in remaining]
        require(bool(ready), 'snapshot-parent-cycle')
        ordered.extend(remaining.pop(name) for name in sorted(ready))
    return ordered


def validate_snapshots(snapshots, vm, identity, paths):
    snapshot_order(snapshots)
    for item in snapshots:
        require(isinstance(item['xml'], str) and '<!' not in item['xml'], 'snapshot-xml')
        root = ET.fromstring(item['xml'])
        require(root.tag == 'domainsnapshot' and root.findtext('name') == item['name'], 'snapshot-name')
        memory = root.find('memory')
        require(memory is None or memory.get('snapshot') in ('no', 'internal'), 'external-snapshot-memory')
        for disk in root.findall('disks/disk'):
            require(disk.get('snapshot') in ('no', 'internal'), 'external-snapshot-disk')
        for domain in root.findall('domain') + root.findall('inactiveDomain'):
            # Historical display names are attested by the preserved rename
            # records during final baseline verification.
            domain = ET.fromstring(ET.tostring(domain))
            require(domain.findtext('uuid') == identity, 'snapshot-uuid')
            domain.find('name').text = vm.name
            layout = base.domain_layout(ET.tostring(domain, encoding='unicode'), identity)
            require(layout['disk'] in paths, 'snapshot-disk-outside-chain')


def guard_domain(connection, api, vm, identity=None, *, missing=False):
    require(connection.getURI() == vm_config.URI, 'connection')
    try:
        domain = connection.lookupByName(vm.name)
    except api.libvirtError as error:
        if missing and error.get_error_code() == api.VIR_ERR_NO_DOMAIN:
            if identity is not None:
                try:
                    connection.lookupByUUIDString(identity)
                except api.libvirtError as other:
                    require(other.get_error_code() == api.VIR_ERR_NO_DOMAIN, 'domain-lookup')
                else:
                    require(False, 'uuid-used-by-another-domain')
            return None
        raise
    require(domain.isPersistent() and (identity is None or domain.UUIDString() == identity),
            'domain-identity')
    require(domain.ID() == -1 and domain.state()[0] == api.VIR_DOMAIN_SHUTOFF and
            not domain.hasManagedSaveImage(0) and not domain.autostart(),
            'VM-must-be-off-with-autostart-disabled')
    return domain


@contextmanager
def lease(vm, commands):
    base.prepare_state_root(vm.baseline_directory.parent)
    private_directory(vm.baseline_directory, create=True)
    compatibility = base.compatibility_lock(vm.baseline_directory)
    fd = observer = None
    try:
        fd = os.open(vm.baseline_directory / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        base.identity(vm.baseline_directory / '.lock', private=True, mode=0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise base.CaptureError('state:busy-controller') from error
        commands.lock_fd, commands.compatibility_fd = fd, compatibility
        # Use the normal persistent off-VM display feed. Viewing never controls
        # storage or VM lifetime, and no guest is booted for disaster recovery.
        from e2e_watch import begin
        from types import SimpleNamespace
        holder = SimpleNamespace(watch=None)
        begin(holder)
        observer = holder.watch
        yield
    finally:
        if observer is not None:
            observer.close()
        commands.lock_fd = commands.compatibility_fd = None
        if fd is not None:
            os.close(fd)
        if compatibility is not None:
            os.close(compatibility)


def idle(vm):
    # Reuse the controller's unfinished-attempt and rename checks without
    # connecting to, recovering, or discarding a prior controller's guest.
    capture = base.Capture(None, None, None, directory=vm.baseline_directory)
    capture.require_idle_attempt()
    phase = vm.baseline_directory / 'phase.json'
    if os.path.lexists(phase):
        state = read_json(phase)
        require(state.get('phase') == 'finalized', 'baseline-not-finalized')
        return state
    return None


def archive_preflight(api, vm, commands):
    source = base.LibvirtSource(api)
    try:
        guard_domain(source.connection, api, vm, source.uuid)
        state = idle(vm)
        capture = base.Capture(source, commands, None)
        inventory, off = capture.inventory()
        require(off, 'VM-must-be-off')
        if state is not None:
            capture.directory_identity = capture.private_directory()
            capture.state = capture.read_state()
            capture.revalidate(off=True)
            capture.verify_snapshot()
        xml = source.domain.XMLDesc(api.VIR_DOMAIN_XML_INACTIVE)
        snapshots, current = snapshot_inventory(source.domain)
        validate_snapshots(snapshots, vm, source.uuid, {item['path'] for item in inventory['chain']})
        networks = []
        for name in sorted({element.get('network') for element in
                            ET.fromstring(xml).findall('devices/interface/source') if element.get('network')}):
            network = source.connection.networkLookupByName(name)
            require(network.isPersistent(), 'transient-network')
            networks.append({'name': name, 'xml': network.XMLDesc(api.VIR_NETWORK_XML_INACTIVE),
                             'autostart': bool(network.autostart()), 'active': bool(network.isActive())})
        files = [('disk', str(index), Path(item['path'])) for index, item in enumerate(inventory['chain'])]
        files += [('state', path.relative_to(vm.baseline_directory).as_posix(), path)
                  for path in tree_files(vm.baseline_directory)]
        online = online_directory(source.uuid)
        files += [('online', path.relative_to(online).as_posix(), path) for path in tree_files(online)]
        return source, inventory, xml, snapshots, current, networks, files
    except BaseException:
        source.close()
        raise


def rename_archive(root, source, destination, *, exchange=False):
    """Linux's atomic directory exchange keeps the complete old copy available."""
    private_directory(root)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        # RENAME_EXCHANGE=2; first publication uses RENAME_NOREPLACE=1.
        if rename(fd, os.fsencode(source), fd, os.fsencode(destination), 2 if exchange else 1):
            raise OSError(ctypes.get_errno(), 'atomic archive publication failed')
        os.fsync(fd)
    finally:
        os.close(fd)


def publication_journal(vm, root):
    return root / ('.backup-publication-' + vm.name + '.json')


def verify_archive_file(path, name, expected):
    candidate = path / name
    require(not candidate.is_symlink(), 'publication-file-changed')
    identity = base.identity(candidate, private=True, mode=0o600)
    actual = stamp(candidate) if 'ctime' in expected else identity
    require(actual == dict(expected, path=str(candidate)), 'publication-file-changed')


def verify_archive_files(path, files, *, partial=False):
    require(isinstance(files, dict) and all(len(relative_path(name).parts) == 1 for name in files),
            'publication-record')
    remaining = {item.name for item in path.iterdir()}
    require(remaining <= set(files) if partial else remaining == set(files), 'publication-unknown-file')
    for name in remaining:
        verify_archive_file(path, name, files[name])
    return remaining


def remove_recorded_archive(root, path, directory_identity, files):
    """Delete only a recorded private allocation and its unchanged files."""
    require(path.parent == root and private_directory(path) == directory_identity,
            'publication-directory-changed')
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        require({'device': info.st_dev, 'inode': info.st_ino} == directory_identity,
                'publication-directory-changed')
        remaining = verify_archive_files(path, files, partial=True)
        for name in sorted(remaining):
            verify_archive_file(path, name, files[name])
            os.unlink(name, dir_fd=descriptor)
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    require(private_directory(path) == directory_identity, 'publication-directory-changed')
    path.rmdir()
    base.sync_directory(root)


def staging_journal(vm, root):
    return root / ('.backup-staging-' + vm.name + '.json')


def cleanup_staging(vm, root):
    path = staging_journal(vm, root)
    if not os.path.lexists(path):
        return
    record = read_json(path)
    journal_identity = base.identity(path, private=True, mode=0o600)
    require(record.get('name') == vm.name and isinstance(record.get('staging'), str) and
            record['staging'].startswith('.backup-' + vm.name + '-') and
            len(relative_path(record['staging']).parts) == 1, 'staging-record')
    staged = root / record['staging']
    if os.path.lexists(staged):
        remove_recorded_archive(root, staged, record['directory'], record['files'])
    # Missing staging means publication or an interrupted deletion completed.
    require(base.identity(path, private=True, mode=0o600) == journal_identity, 'staging-record-changed')
    path.unlink()
    base.sync_directory(root)


def finish_publication(vm, root):
    """Resume publication/deletion only with the exact recorded inode identities."""
    journal_path = publication_journal(vm, root)
    if not os.path.lexists(journal_path):
        return
    journal = read_json(journal_path)
    journal_identity = base.identity(journal_path, private=True, mode=0o600)
    require(journal.get('name') == vm.name and isinstance(journal.get('staging'), str) and
            journal['staging'].startswith('.backup-' + vm.name + '-') and
            len(relative_path(journal['staging']).parts) == 1, 'publication-record')
    current, staged = root / vm.name, root / journal['staging']
    current_identity = private_directory(current)
    if current_identity == journal['previous']:
        require(private_directory(staged) == journal['replacement'], 'publication-directory-changed')
        verify_archive_files(current, journal['files'])
        verify_archive_files(staged, journal['replacement_files'])
        rename_archive(root, staged.name, current.name, exchange=True)
    require(private_directory(current) == journal['replacement'], 'publication-directory-changed')
    verify_archive_files(current, journal['replacement_files'])
    if os.path.lexists(staged):
        remove_recorded_archive(root, staged, journal['previous'], journal['files'])
    require(base.identity(journal_path, private=True, mode=0o600) == journal_identity,
            'publication-record-changed')
    journal_path.unlink()
    base.sync_directory(root)


def publish_archive(vm, root, archive):
    current = root / vm.name
    if not os.path.lexists(current):
        rename_archive(root, archive.name, current.name)
        return
    previous, manifest, _ = load_archive(vm, root)
    require(previous == current, 'legacy-generations; select a new dedicated backup_root')
    names = {'manifest.json', 'complete.json'} | {item['payload'] for item in manifest['files']}
    require({path.name for path in current.iterdir()} == names, 'publication-unknown-file')
    journal = dict(name=vm.name, staging=archive.name, previous=private_directory(current),
                   replacement=private_directory(archive),
                   files={name: stamp(current / name) for name in names},
                   replacement_files={item.name: stamp(item) for item in archive.iterdir()})
    atomic(publication_journal(vm, root), journal)
    finish_publication(vm, root)


def backup(api, vm, root, commands):
    with operation('Backing up registered VM disks, snapshots and provenance'):
        finish_publication(vm, root)
        cleanup_staging(vm, root)
        source, inventory, xml, snapshots, current, networks, files = archive_preflight(api, vm, commands)
        try:
            archive = root / ('.backup-' + vm.name + '-' + uuid.uuid4().hex)
            private_directory(archive, create=True)
            staging = dict(name=vm.name, staging=archive.name,
                           directory=private_directory(archive), files={})
            atomic(staging_journal(vm, root), staging)
            def created(path):
                staging['files'][path.name] = base.identity(path, private=True, mode=0o600)
                atomic(staging_journal(vm, root), staging)
            def write_record(name, value):
                path = archive / name
                with path.open('xb') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    created(path)
                    stream.write(base.encode(value))
                    stream.flush()
                    os.fsync(stream.fileno())
                base.sync_directory(archive)
            records = []
            stamps = {path: stamp(path) for _, _, path in files}
            for index, (area, relative, path) in enumerate(files):
                guard_domain(source.connection, api, vm, source.uuid)
                before = stamps[path]
                info = path.stat()
                payload = f'file-{index:05d}'
                copy_file(path, archive / payload, expected=before,
                          guard=lambda: guard_domain(source.connection, api, vm, source.uuid), created=created)
                records.append(dict(area=area, relative=relative, original=str(path), payload=payload,
                    sha256=checksum(archive / payload), size=info.st_size,
                    owner=pwd.getpwuid(info.st_uid).pw_name, group=grp.getgrgid(info.st_gid).gr_name,
                    mode=stat.S_IMODE(info.st_mode)))
                require(checksum(path) == records[-1]['sha256'], 'copy-checksum')
                require(stamp(path) == before, 'source-changed')
            guard_domain(source.connection, api, vm, source.uuid)
            require(source.domain.XMLDesc(api.VIR_DOMAIN_XML_INACTIVE) == xml and
                    snapshot_inventory(source.domain) == (snapshots, current), 'metadata-changed')
            check = base.Capture(source, commands, None)
            require(check.inventory() == (inventory, True), 'disk-chain-changed')
            require(all(stamp(path) == before for path, before in stamps.items()), 'source-changed')
            manifest = dict(schema_version=SCHEMA, name=vm.name, disk_anchor=str(vm.disk_anchor),
                uuid=source.uuid, domain_xml=xml, inventory=inventory, snapshots=snapshots,
                current_snapshot=current, networks=networks, files=records,
                registry=vm_config.read_document())
            if (vm.baseline_directory / 'phase.json').exists():
                manifest['baseline_sha256'] = base.baseline_sha256(
                    read_json(vm.baseline_directory / 'phase.json'), vm.baseline_directory)
            write_record('manifest.json', manifest)
            write_record('complete.json', dict(generation=vm.name,
                sha256=checksum(archive / 'manifest.json')))
            publish_archive(vm, root, archive)
            cleanup_staging(vm, root)
            print(f'backupvms: {vm.name}: backup complete: {root / vm.name}', flush=True)
        except BaseException:
            # Publication recovery owns the displaced old directory after the
            # exchange. Otherwise remove only this attempt's recorded scratch.
            if not os.path.lexists(publication_journal(vm, root)):
                cleanup_staging(vm, root)
            raise
        finally:
            source.close()


def relative_path(value):
    require(isinstance(value, str) and value and not value.startswith('/') and
            all(part not in ('', '.', '..') for part in value.split('/')) and
            not any(ord(char) < 32 for char in value), 'archive-path')
    return Path(value)


def target(vm, manifest, record):
    if record['area'] == 'disk':
        paths = {item['path'] for item in manifest['inventory']['chain']}
        path = vm_config.absolute_path(record['original'], 'archive-disk')
        require(str(path) in paths and path.parent == vm.disk_anchor.parent, 'archive-disk-location')
        return path
    relative = relative_path(record['relative'])
    require(relative.parts[0] not in ('.lock', JOURNAL) and
            not any(part.startswith('.restore-vms-') for part in relative.parts), 'archive-state-location')
    require(record['area'] in ('state', 'online'), 'archive-area')
    root = vm.baseline_directory if record['area'] == 'state' else online_directory(manifest['uuid'])
    return root / relative


def load_archive(vm, root):
    private_directory(root / vm.name)
    direct = os.path.lexists(root / vm.name / 'complete.json')
    latest = read_json(root / vm.name / ('complete.json' if direct else 'latest.json'))
    require(set(latest) == {'generation', 'sha256'} and isinstance(latest['generation'], str) and
            len(relative_path(latest['generation']).parts) == 1, 'latest-record')
    require(not direct or latest['generation'] == vm.name, 'latest-record')
    archive = root / vm.name if direct else root / vm.name / latest['generation']
    private_directory(archive)
    require(checksum(archive / 'manifest.json') == latest['sha256'], 'manifest-checksum')
    manifest = read_json(archive / 'manifest.json')
    require(manifest.get('schema_version') == SCHEMA and manifest.get('name') == vm.name and
            manifest.get('disk_anchor') == str(vm.disk_anchor), 'registry-backup-mismatch')
    require(str(uuid.UUID(manifest['uuid'])) == manifest['uuid'], 'archive-uuid')
    if 'baseline_sha256' in manifest:
        require(isinstance(manifest['baseline_sha256'], str) and
                len(manifest['baseline_sha256']) == 64 and
                all(char in '0123456789abcdef' for char in manifest['baseline_sha256']),
                'archive-baseline-identity')
    layout = base.domain_layout(manifest['domain_xml'], manifest['uuid'])
    require(layout == manifest['inventory']['layout'], 'archive-layout')
    chain = manifest['inventory']['chain']
    require(chain and chain[0]['path'] == layout['disk'] and
            chain[-1]['path'] == str(vm.disk_anchor) and len(chain) <= 32, 'archive-chain')
    destinations, payloads = set(), set()
    for record in manifest['files']:
        destination = target(vm, manifest, record)
        payload = relative_path(record['payload'])
        require(len(payload.parts) == 1 and destination not in destinations and
                payload not in payloads, 'duplicate-archive-file')
        destinations.add(destination)
        payloads.add(payload)
        source = archive / payload
        base.identity(source, private=True, mode=0o600)
        require(type(record['size']) is int and record['size'] >= 0 and
                source.stat().st_size == record['size'] and checksum(source) == record['sha256'],
                'payload-checksum')
        require(type(record['mode']) is int and 0 <= record['mode'] <= 0o777 and
                (record['area'] == 'disk' or record['mode'] == 0o600), 'payload-mode')
        # Map ownership by account names, not machine-specific numeric IDs.
        pwd.getpwnam(record['owner'])
        grp.getgrnam(record['group'])
    require({item['path'] for item in chain} ==
            {record['original'] for record in manifest['files'] if record['area'] == 'disk'}, 'missing-chain-file')
    validate_snapshots(manifest['snapshots'], vm, manifest['uuid'], {item['path'] for item in chain})
    require(manifest['current_snapshot'] is None or manifest['current_snapshot'] in
            {item['name'] for item in manifest['snapshots']}, 'current-snapshot')
    return archive, manifest, latest


def shared_disks(connection, api, identity, paths, commands):
    for domain in connection.listAllDomains(0):
        if domain.UUIDString() == identity:
            continue
        xmls = [domain.XMLDesc(0), domain.XMLDesc(api.VIR_DOMAIN_XML_INACTIVE)]
        xmls.extend(item['xml'] for item in snapshot_inventory(domain)[0])
        for xml in xmls:
            # Include backing chains: a foreign guest may use a different top
            # image backed by one of the selected VM's images.
            tree = ET.fromstring(xml)
            for source in tree.findall('.//disk//source'):
                file = source.get('file')
                if file:
                    require(file not in paths, 'disk-used-by-another-domain')
                    seen = set()
                    while True:
                        path = Path(file)
                        # Missing images of other inactive domains are expected
                        # after a multi-VM disk loss. Check every XML source and
                        # every readable backing link, without requiring those
                        # other VMs to be restored first. Never skip links or an
                        # active guest's unlinked/open storage.
                        require(path.is_absolute() and path == path.resolve(strict=False),
                                'foreign-disk-path')
                        require(str(path) not in paths, 'disk-used-by-another-domain')
                        require(path not in seen and len(seen) < 32, 'foreign-disk-chain')
                        seen.add(path)
                        if not os.path.lexists(path):
                            for parent in path.parents:
                                if os.path.lexists(parent):
                                    base.canonical(parent)
                            require(domain.ID() == -1, 'active-foreign-disk-missing')
                            break
                        base.canonical(path)
                        info = base.parse_json(commands.run(
                            ['qemu-img', 'info', '-U', '--output=json', str(path)]))
                        backing = info.get('backing-filename')
                        if not backing:
                            break
                        candidate = Path(backing)
                        file = candidate if candidate.is_absolute() else path.parent / candidate


def same_xml(left, right):
    return ET.canonicalize(left, strip_text=True) == ET.canonicalize(right, strip_text=True)


def same_network(left, right):
    # Domains refer to networks by name. Fresh host installations may create
    # an otherwise identical default network with a new UUID; keep that UUID.
    trees = [ET.fromstring(xml) for xml in (left, right)]
    for tree in trees:
        for item in tree.findall('uuid'):
            tree.remove(item)
    return same_xml(*(ET.tostring(tree, encoding='unicode') for tree in trees))


def network_preflight(connection, api, networks, plan=None):
    names = {item['name'] for item in networks}
    require(len(names) == len(networks), 'duplicate-network')
    require(plan is None or isinstance(plan, dict) and set(plan) == names, 'network-journal')
    result = {}
    for item in networks:
        require('<!' not in item['xml'], 'network-xml')
        tree = ET.fromstring(item['xml'])
        require(tree.tag == 'network' and tree.findtext('name') == item['name'], 'network-identity')
        identity = tree.findtext('uuid')
        require(str(uuid.UUID(identity)) == identity, 'network-uuid')
        missing = False
        try:
            network = connection.networkLookupByName(item['name'])
        except api.libvirtError as error:
            require(error.get_error_code() == api.VIR_ERR_NO_NETWORK, 'network-lookup')
            try:
                connection.networkLookupByUUIDString(tree.findtext('uuid'))
            except api.libvirtError as other:
                require(other.get_error_code() == api.VIR_ERR_NO_NETWORK, 'network-lookup')
            else:
                require(False, 'network-uuid-collision')
            missing = True
        else:
            xml = network.XMLDesc(api.VIR_NETWORK_XML_INACTIVE)
            require(network.isPersistent() and same_network(
                xml, item['xml']), 'network-definition-collision')
            identity = ET.fromstring(xml).findtext('uuid')
        expected = dict(uuid=identity, created=missing)
        if plan is not None:
            expected = plan[item['name']]
            require(isinstance(expected, dict) and set(expected) == {'uuid', 'created'} and
                    type(expected['created']) is bool and expected['uuid'] == identity and
                    (not missing or expected['created']), 'network-journal-identity')
        result[item['name']] = expected
    return result


def restore_networks(connection, api, networks, journal):
    # The durable intent precedes defineXML, whose successful return can be lost
    # on interruption. Restore-owned networks (including exact archived UUIDs
    # reconciled from older metadata journals) get their saved runtime settings.
    plan = journal['networks']
    network_preflight(connection, api, networks, plan)
    for item in networks:
        network_preflight(connection, api, [item], {item['name']: plan[item['name']]})
        try:
            network = connection.networkLookupByName(item['name'])
        except api.libvirtError as error:
            require(error.get_error_code() == api.VIR_ERR_NO_NETWORK, 'network-lookup')
            network = connection.networkDefineXML(item['xml'])
        network_preflight(connection, api, [item], {item['name']: plan[item['name']]})
        if plan[item['name']]['created']:
            if bool(network.autostart()) != item['autostart']:
                network.setAutostart(item['autostart'])
            if item['active'] and not network.isActive():
                network.create()
            require(bool(network.autostart()) == item['autostart'] and
                    bool(network.isActive()) == item['active'], 'network-runtime-state')


def restore_preflight(connection, api, vm, manifest, latest, commands):
    domain = guard_domain(connection, api, vm, manifest['uuid'], missing=True)
    journal_path = vm.baseline_directory / JOURNAL
    journal = None
    if os.path.lexists(journal_path):
        base.identity(journal_path, private=True, mode=0o600)
        try:
            journal = read_json(journal_path)
        except (json.JSONDecodeError, UnicodeError):
            pass  # Retain damaged bookkeeping before starting a new restore.
        except base.CaptureError as error:
            if str(error) != 'guard:duplicate-json-key':
                raise
    pending = (isinstance(journal, dict) and journal.get('phase') in ('files', 'metadata') and
               journal.get('schema_version') == SCHEMA and journal.get('backup') == latest and
               journal.get('uuid') == manifest['uuid'] and
               journal.get('directory') == private_directory(vm.baseline_directory))
    if pending:
        files = journal.get('files')
        run = journal.get('run')
        pending = (isinstance(run, str) and len(run) == 32 and
                   all(char in '0123456789abcdef' for char in run) and isinstance(files, dict) and
                   set(files) == {record['payload'] for record in manifest['files']} and
                   all(isinstance(item, dict) and item.get('phase') in ('pending', 'done') and
                       'original' in item and (item['phase'] != 'done' or 'installed' in item)
                       for item in files.values()))
    if domain is not None:
        layout = base.domain_layout(domain.XMLDesc(api.VIR_DOMAIN_XML_INACTIVE), manifest['uuid'])
        require(layout == manifest['inventory']['layout'], 'local-domain-layout-changed')
    paths = {item['path'] for item in manifest['inventory']['chain']}
    shared_disks(connection, api, manifest['uuid'], paths, commands)
    network_preflight(connection, api, manifest['networks'],
                      journal.get('networks') if pending else None)
    for record in manifest['files']:
        destination = target(vm, manifest, record)
        if os.path.lexists(destination):
            base.identity(destination, private=record['area'] != 'disk',
                          mode=0o600 if record['area'] != 'disk' else None)
            # Explicit recovery replaces registered destinations, preserving
            # their bytes. Local provenance may itself be the damaged state.
            # Domain UUID, foreign-disk, path and exclusive-lease guards own
            # authorization; stale controller records do not own this restore.
        # Validate every existing parent before making the durable write plan.
        for parent in (destination.parent, *destination.parent.parents):
            if os.path.lexists(parent):
                base.canonical(parent)
                require(parent.is_dir(), 'destination-parent')
    return journal if pending else None


def retain_record(vm, journal, path):
    """Durably retire bookkeeping without deleting or fabricating a test pass."""
    roots = (vm.baseline_directory, online_directory(journal['uuid']))
    require(any(path.is_relative_to(root) and path != root and
                all(part not in ('.lock', JOURNAL, '.', '..') and
                    not part.startswith('.restore-vms-') for part in path.relative_to(root).parts)
                for root in roots), 'retired-record-location')
    key = str(path)
    retired = journal.setdefault('retired_records', {})
    if key not in retired:
        if not os.path.lexists(path):
            return
        original = base.identity(path, private=True, mode=0o600)
        saved = path.with_name('.restore-vms-' + journal['run'] + '-' + uuid.uuid4().hex + '.record')
        retired[key] = dict(original=original, retained=str(saved))
        atomic(vm.baseline_directory / JOURNAL, journal)
    record = retired[key]
    saved = Path(record['retained'])
    require(saved.parent == path.parent and saved.name.startswith('.restore-vms-' + journal['run'] + '-'),
            'retained-record-location')
    if os.path.lexists(saved):
        require(base.identity(saved, private=True, mode=0o600) == dict(record['original'], path=str(saved))
                and not os.path.lexists(path), 'retained-record-changed')
    else:
        require(base.identity(path, private=True, mode=0o600) == record['original'], 'retired-record-changed')
        os.rename(path, saved)
        base.sync_directory(path.parent)


def retire_stale_records(vm, manifest, journal):
    destinations = {target(vm, manifest, record) for record in manifest['files']
                    if record['area'] != 'disk'}
    for root in (vm.baseline_directory, online_directory(manifest['uuid'])):
        for path in tree_files(root):
            if path not in destinations:
                retain_record(vm, journal, path)
    # Finish any rename whose acknowledgement was interrupted.
    for path in tuple(journal.get('retired_records', {})):
        retain_record(vm, journal, Path(path))


def publish_file(vm, manifest, record, archive, journal, guard=lambda: None,
                 publication_guard=lambda: None):
    guard()
    destination = target(vm, manifest, record)
    key = record['payload']
    previous = journal['files'][key]
    for parent in reversed(destination.parents):
        if parent == destination.parent or parent.is_relative_to(vm.baseline_directory) or (
                record['area'] == 'online' and parent.is_relative_to(online_directory(manifest['uuid']))):
            if record['area'] != 'disk':
                private_directory(parent, create=True)
    base.canonical(destination.parent)
    saved = destination.with_name('.restore-vms-' + journal['run'] + '-' + key + '.previous')
    staged = destination.with_name('.restore-vms-' + journal['run'] + '-' + key + '.new')
    if previous['phase'] == 'done':
        require(base.identity(destination) == previous['installed'] and
                checksum(destination) == record['sha256'], 'restored-file-changed')
        return
    if os.path.lexists(destination):
        current = base.identity(destination)
        if current != previous['original']:
            # Publication may have finished immediately before interruption.
            require(previous.get('staged') is not None and
                    dict(previous['staged'], path=str(destination)) == current and
                    checksum(destination) == record['sha256'],
                    'destination-replaced')
            previous.update(phase='done', installed=current)
            atomic(vm.baseline_directory / JOURNAL, journal)
            return
    if previous.get('staged') is None:
        # A killed copy can leave an incomplete file. Never overwrite or adopt
        # it: choose and record a fresh transaction-owned staging name instead.
        staged = staged.with_name(staged.name + '-' + uuid.uuid4().hex)
        copy_file(archive / key, staged, guard=guard)
        require(checksum(staged) == record['sha256'], 'staged-checksum')
        os.chown(staged, pwd.getpwnam(record['owner']).pw_uid, grp.getgrnam(record['group']).gr_gid)
        os.chmod(staged, record['mode'])
        with staged.open('rb') as stream:
            os.fsync(stream.fileno())
        previous['staged'] = base.identity(staged)
        atomic(vm.baseline_directory / JOURNAL, journal)
    else:
        staged = Path(previous['staged']['path'])
        require(staged.parent == destination.parent and staged.name.startswith(
            '.restore-vms-' + journal['run'] + '-' + key + '.new-'), 'staging-location')
        require(base.identity(staged) == previous['staged'] and
                checksum(staged) == record['sha256'], 'staging-changed')
    guard()
    # Copying a large disk can take long enough for a foreign domain's storage
    # definition to change. Recheck references at the publication boundary,
    # before moving either the original or the staged image.
    publication_guard()
    if previous['original'] is not None:
        if os.path.lexists(saved):
            require(base.identity(saved) == dict(previous['original'], path=str(saved)), 'previous-file-changed')
            require(not os.path.lexists(destination), 'destination-reappeared')
        else:
            require(base.identity(destination) == previous['original'], 'destination-replaced')
            os.rename(destination, saved)
            base.sync_directory(destination.parent)
    else:
        require(not os.path.lexists(destination), 'destination-reappeared')
    os.rename(staged, destination)
    base.sync_directory(destination.parent)
    previous.update(phase='done', installed=base.identity(destination))
    atomic(vm.baseline_directory / JOURNAL, journal)


def restore(connection, api, vm, root, commands):
    with operation('Restoring registered VM and reconciling provenance'):
        archive, manifest, latest = load_archive(vm, root)
        journal = restore_preflight(connection, api, vm, manifest, latest, commands)
        if journal is None:
            previous_journal = vm.baseline_directory / JOURNAL
            if os.path.lexists(previous_journal):
                copy_file(previous_journal, vm.baseline_directory /
                          ('.restore-vms-history-' + uuid.uuid4().hex + '.json'))
            journal = dict(schema_version=SCHEMA, phase='files', run=uuid.uuid4().hex,
                backup=latest, uuid=manifest['uuid'], directory=private_directory(vm.baseline_directory), files={})
            for record in manifest['files']:
                destination = target(vm, manifest, record)
                journal['files'][record['payload']] = dict(phase='pending', original=(
                    base.identity(destination) if os.path.lexists(destination) else None))
            domain = guard_domain(connection, api, vm, manifest['uuid'], missing=True)
            journal['previous_domain_xml'] = domain.XMLDesc(api.VIR_DOMAIN_XML_INACTIVE) if domain else None
            journal['previous_snapshots'] = snapshot_inventory(domain)[0] if domain else []
            journal['networks'] = network_preflight(connection, api, manifest['networks'])
            atomic(vm.baseline_directory / JOURNAL, journal)
        if 'networks' not in journal:
            # Explicit disaster reconciliation can repair an older metadata
            # journal too. Configure only exact archived UUIDs/definitions;
            # equivalent networks with another UUID remain pre-existing.
            journal['networks'] = network_preflight(connection, api, manifest['networks'])
            if journal['phase'] == 'metadata':
                for item in manifest['networks']:
                    entry = journal['networks'][item['name']]
                    if entry['uuid'] == ET.fromstring(item['xml']).findtext('uuid'):
                        entry['created'] = True
            atomic(vm.baseline_directory / JOURNAL, journal)
        if journal['phase'] == 'files':
            retire_stale_records(vm, manifest, journal)
            for record in manifest['files']:
                guard_domain(connection, api, vm, manifest['uuid'], missing=True)
                shared_disks(connection, api, manifest['uuid'],
                             {item['path'] for item in manifest['inventory']['chain']}, commands)
                publish_file(vm, manifest, record, archive, journal,
                             guard=lambda: guard_domain(connection, api, vm, manifest['uuid'], missing=True),
                             publication_guard=lambda: shared_disks(connection, api, manifest['uuid'],
                                 {item['path'] for item in manifest['inventory']['chain']}, commands))
            journal['phase'] = 'metadata'
            atomic(vm.baseline_directory / JOURNAL, journal)
        guard_domain(connection, api, vm, manifest['uuid'], missing=True)
        for record in manifest['files']:
            destination = target(vm, manifest, record)
            expected = journal['files'][record['payload']]['installed']
            retired = journal.get('retired_records', {}).get(str(destination))
            if retired is not None:
                destination = Path(retired['retained'])
                expected = dict(expected, path=str(destination))
            # phase.json is atomically rebound during metadata reconciliation;
            # all other bytes/identities must still match the published payload.
            if record['area'] == 'state' and record['relative'] == 'phase.json':
                continue
            require(base.identity(destination) == expected and checksum(destination) == record['sha256'],
                    'restored-file-changed')
        restore_networks(connection, api, manifest['networks'], journal)
        shared_disks(connection, api, manifest['uuid'],
                     {item['path'] for item in manifest['inventory']['chain']}, commands)
        domain = connection.defineXML(manifest['domain_xml'])
        require(domain is not None and domain.UUIDString() == manifest['uuid'], 'domain-define')
        domain.setAutostart(False)
        # Metadata redefine preserves saved disk/RAM bytes; no snapshot is
        # taken, deleted, or reverted during restoration.
        expected_names = {item['name'] for item in manifest['snapshots']}
        # Remove metadata only. Disk/RAM snapshots are already restored from
        # copied images; displaced definitions are retained in the journal.
        # Repeating after interruption recreates the same complete hierarchy.
        for item in reversed(snapshot_order(snapshot_inventory(domain)[0])):
            domain.snapshotLookupByName(item['name'], 0).delete(api.VIR_DOMAIN_SNAPSHOT_DELETE_METADATA_ONLY)
        for item in snapshot_order(manifest['snapshots']):
            flags = api.VIR_DOMAIN_SNAPSHOT_CREATE_REDEFINE
            if item['name'] == manifest['current_snapshot']:
                flags |= api.VIR_DOMAIN_SNAPSHOT_CREATE_CURRENT
            domain.snapshotCreateXML(item['xml'], flags)
        source = base.LibvirtSource(api)
        try:
            capture = base.Capture(source, commands, None)
            inventory, off = capture.inventory()
            require(off and inventory['layout'] == manifest['inventory']['layout'] and
                    [{k: v for k, v in item.items() if k not in ('device', 'inode')} for item in inventory['chain']] ==
                    [{k: v for k, v in item.items() if k not in ('device', 'inode')}
                     for item in manifest['inventory']['chain']], 'restored-chain')
            phase = vm.baseline_directory / 'phase.json'
            if os.path.lexists(phase):
                capture.directory_identity = capture.private_directory()
                phase_record = next((record for record in manifest['files'] if
                                     record['area'] == 'state' and record['relative'] == 'phase.json'), None)
                require(phase_record is not None, 'unexpected-local-baseline')
                original_state = read_json(archive / phase_record['payload'])
                state = dict(original_state)
                require(state['phase'] == 'finalized' and state['source']['layout'] == inventory['layout'],
                        'restored-baseline-layout')
                # Rebind only filesystem identities, retaining the original
                # guest, operation, recipe digest and internal snapshot proof.
                state['directory'] = capture.directory_identity
                state['source'] = inventory
                state['source_digests'] = None
                require(read_json(phase) in (original_state, state), 'restored-baseline-changed')
                capture.state = state
                capture.verify_snapshot()
                journal['baseline_identity'] = dict(original=manifest.get('baseline_sha256') or
                    hashlib.sha256(base.encode(original_state)).hexdigest(),
                    restored=hashlib.sha256(base.encode(state)).hexdigest())
                atomic(vm.baseline_directory / JOURNAL, journal)
                if read_json(phase) != state:
                    atomic(phase, state)
                capture.state = capture.read_state()
                capture.revalidate(off=True)
                capture.verify_snapshot()
            actual, current = snapshot_inventory(source.domain)
            require({item['name'] for item in actual} == expected_names and
                    current == manifest['current_snapshot'], 'restored-snapshot-inventory')
            for item in actual:
                expected = next(saved['xml'] for saved in manifest['snapshots'] if saved['name'] == item['name'])
                require(same_xml(item['xml'], expected), 'restored-snapshot-metadata')
            guard_domain(connection, api, vm, manifest['uuid'])
            # Prior attempts are historical evidence, not owners of the newly
            # restored guest. Retire both archived and leftover local records;
            # fresh controllers will record the restored identities themselves.
            for name in ('system-run.json', 'vm-control.json'):
                retain_record(vm, journal, vm.baseline_directory / name)
            retire_stale_records(vm, manifest, journal)
            journal['phase'] = 'complete'
            atomic(vm.baseline_directory / JOURNAL, journal)
            print(f'restorevms: {vm.name}: restored {latest["generation"]}; VM remains off. '
                  'App snapshot caches may require tools/prepare-appsnapshot.', flush=True)
        finally:
            source.close()


def main(argv=None):
    from vm_backup_launcher import FailureParser, failure
    parser = FailureParser(prog='VM disaster recovery', description=__doc__, allow_abbrev=False)
    parser.add_argument('action', choices=('backup', 'restore'))
    parser.add_argument('--vm', default='all')
    args = parser.parse_args(argv)
    try:
        require(os.geteuid() == os.getegid() == 0 and int(os.environ.get('PKEXEC_UID', '0')) > 0,
                'use-tools-backupvms-or-restorevms')
        _, vms = vm_config.execution(args.vm)
        root = vm_config.backup_root()
        require(all(root != vm.disk_anchor.parent and not vm.disk_anchor.parent.is_relative_to(root)
                    for vm in vms) and root != vm_config.STATE_ROOT and
                    not root.is_relative_to(vm_config.STATE_ROOT) and
                    not vm_config.STATE_ROOT.is_relative_to(root) and
                    not ROOT.is_relative_to(root) and not root.is_relative_to(ROOT), 'backup-root-overlap')
        # Import live APIs only after arguments and registry are validated.
        try:
            import libvirt as api
        except ImportError as error:
            raise ValueError('VM host prerequisites missing; run ./setup.sh') from error
        require(shutil.which('qemu-img') is not None, 'qemu-img-missing; run ./setup.sh')
        api.virEventRegisterDefaultImpl()
        def events():
            while True:
                try:
                    api.virEventRunDefaultImpl()
                except Exception:
                    return
        threading.Thread(target=events, daemon=True, name='vm-recovery-events').start()
        with operation('Validating registered VM disaster recovery selection'):
            private_directory(root, create=args.action == 'backup')
            lock = root / '.lock'
            fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            try:
                base.identity(lock, private=True, mode=0o600)
                from test_storage import disk_backed
                disk_backed(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for vm in vms:
                    vm_config.select(vm.name)
                    if args.action == 'restore':
                        ensure_parents(vm.disk_anchor.parent)
                        ensure_parents(vm_config.STATE_ROOT.parent)
                    commands = base.Commands()
                    with lease(vm, commands):
                        if args.action == 'backup':
                            backup(api, vm, root, commands)
                        else:
                            connection = api.open(vm_config.URI)
                            require(connection is not None, 'connection')
                            try:
                                restore(connection, api, vm, root, commands)
                            finally:
                                connection.close()
            finally:
                os.close(fd)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        category = str(error) if isinstance(error, (base.CaptureError, ValueError)) else type(error).__name__
        failure(f'{args.action}vms', f'{category}; preserve backups, displaced files and restore journals. '
                'Resolve the condition and rerun the same selection.')
        return 1


if __name__ == '__main__':
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    sys.exit(main())
