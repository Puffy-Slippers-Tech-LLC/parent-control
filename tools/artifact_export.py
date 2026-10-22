"""Private single-file publications using the shared retention transaction."""
import hashlib
import os
from pathlib import Path
import stat
import tempfile

import evidence_bundle as bundle
import test_retention as retention
import test_storage as storage


def checksum(fd, size, output=None):
    result = hashlib.sha256()
    offset = 0
    while offset < size:
        chunk = os.pread(fd, min(65536, size - offset), offset)
        if not chunk:
            raise ValueError('artifact export: source was truncated')
        result.update(chunk)
        if output is not None:
            output.write(chunk)
        offset += len(chunk)
    return result.hexdigest()


def control_name(name):
    return '.onpc-export-control' if name == '.onpc-export' else '.onpc-export'


def verify(record, uid, *, checkout, revalidate=None):
    """Verify an owner-locked copy, including the exact private publication tree."""
    directory = bundle.path_text(record['path'])
    if not directory.name.startswith('onpc-artifact-export-'):
        raise ValueError('artifact export: expected a recorded private export')
    selected = bundle.Selection(checkout, uid, os.getegid(), [], [], [])
    selected.records = {str(directory): record}
    with selected.open(directory) as (fd, info):
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('artifact export: private directory owner or mode changed')
        names = set(os.listdir(fd))
    controls = names & {'.onpc-export', '.onpc-export-control'}
    control = next((name for name in controls
                    if (directory / name).is_dir()), None)
    if control is None:
        raise ValueError('artifact export: receipt is missing; recapture the source')
    with selected.open(directory / control / 'receipt.json') as (fd, info):
        if info.st_size > 16384 or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('artifact export: unsafe receipt')
        receipt = bundle.decoded(os.read(fd, 16385))
        receipt_identity = bundle.fingerprint(info)
    if (not isinstance(receipt, dict) or set(receipt) != {'schema', 'kind', 'selection', 'copy'}
            or receipt['schema'] != 1 or type(receipt['schema']) is not int
            or receipt['kind'] != 'onpc-artifact-export'):
        raise ValueError('artifact export: invalid receipt')
    selection, copied = receipt['selection'], receipt['copy']
    if (not isinstance(selection, dict)
            or set(selection) != {'source', 'identity', 'sha256', 'repository', 'uid', 'gid'}
            or selection['repository'] != selected.repository()
            or type(selection['uid']) is not int or selection['uid'] != uid
            or type(selection['gid']) is not int or selection['gid'] != os.getegid()
            or not isinstance(selection['identity'], list) or len(selection['identity']) != 10
            or any(type(value) is not int for value in selection['identity'])
            or not isinstance(copied, list) or len(copied) != 10
            or any(type(value) is not int for value in copied)):
        raise ValueError('artifact export: invalid selection or authority')
    source = bundle.path_text(selection['source'])
    if control != control_name(source.name) or names != {source.name, control}:
        raise ValueError('artifact export: unexpected publication files')
    with selected.open(directory / control) as (fd, info):
        if (info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700
                or set(os.listdir(fd)) != {'receipt.json'}):
            raise ValueError('artifact export: unsafe control directory')
    with selected.open(directory / source.name) as (fd, info):
        if (bundle.fingerprint(info) != copied or info.st_uid != uid
                or info.st_gid != selection['gid'] or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size != selection['identity'][6]
                or checksum(fd, info.st_size) != selection['sha256']):
            raise ValueError('artifact export: private copy changed; recapture the source')
        # Keep the verified copy pinned across source revalidation. A caller
        # must never return its saved path after an unchecked source walk.
        if revalidate is not None:
            revalidate(receipt)
        if bundle.fingerprint(os.fstat(fd)) != copied:
            raise ValueError('artifact export: private copy changed during verification')
        with selected.open(directory / source.name) as (_, current):
            if bundle.fingerprint(current) != copied:
                raise ValueError('artifact export: private copy replaced during verification')
    with selected.open(directory / control / 'receipt.json') as (_, info):
        if bundle.fingerprint(info) != receipt_identity:
            raise ValueError('artifact export: receipt changed during verification')
    return receipt


def export(fd, info, source, uid, gid, *, checkout, opener):
    """Reuse only exact verified bytes; preserve the original basename."""
    reader_uid, reader_gid = os.geteuid(), os.getegid()
    before = bundle.fingerprint(info)
    digest = checksum(fd, info.st_size)

    def source_unchanged():
        with bundle.identity(reader_uid, reader_gid):
            with opener() as (_, current):
                if bundle.fingerprint(current) != before:
                    raise ValueError('artifact export: source path changed; retry the export')
        if bundle.fingerprint(os.fstat(fd)) != before:
            raise ValueError('artifact export: source changed; retry the export')

    source_unchanged()
    with bundle.identity(uid, gid):
        parent = storage.directory('exports')
        probe = bundle.Selection(checkout, uid, gid, [], [], [])
        selection = dict(source=source, identity=before, sha256=digest,
                         repository=probe.repository(), uid=uid, gid=gid)

        def reuse(state):
            if state is None:
                return None
            records = retention.latest_allocations([*state['history'], state])
            for _, record in reversed(records):
                if not Path(record['path']).name.startswith('onpc-artifact-export-'):
                    continue
                # Legacy copies have no authenticated receipt. Missing or stale
                # receipts refuse explicitly instead of trusting a saved path.
                receipt = verify(record, uid, checkout=checkout,
                    revalidate=lambda receipt: source_unchanged()
                    if receipt['selection'] == selection else None)
                if receipt['selection'] == selection:
                    return str(Path(record['path']) / Path(source).name)
            return None

        with retention.Store(parent / 'retention').publication(
                projected_bytes=info.st_size + 65536, wait=True, reuse=reuse,
                verify=lambda record: bundle.inspect_publication(record, uid, checkout=checkout)) as transaction:
            if transaction.reused is not None:
                return transaction.reused
            state = transaction.original
            if state is not None:
                entries = [*state['history'], state]
                expire = max(0, len(entries) - (retention.RUNS_TO_KEEP - 1))
                if any(index < expire and Path(source).is_relative_to(record['path'])
                       for index, record in retention.latest_allocations(entries)):
                    raise ValueError('artifact export: publication would retire the selected source; '
                                     'read the existing private copy directly')
            directory = transaction.allocate(tempfile.mkdtemp, prefix='onpc-artifact-export-', dir=parent)
            destination = directory / Path(source).name
            with destination.open('xb') as output:
                os.fchmod(output.fileno(), 0o600)
                copied_digest = checksum(fd, info.st_size, output)
                output.flush()
                os.fsync(output.fileno())
                copied = bundle.fingerprint(os.fstat(output.fileno()))
            source_unchanged()
            if copied_digest != digest:
                raise ValueError('artifact export: source bytes changed; retry the export')
            control = directory / control_name(destination.name)
            control.mkdir(mode=0o700)
            with (control / 'receipt.json').open('xb') as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(bundle.encoded(dict(schema=1, kind='onpc-artifact-export',
                                                selection=selection, copy=copied)))
                output.flush()
                os.fsync(output.fileno())
            with retention.directory_descriptor(control) as control_fd:
                os.fsync(control_fd)
            transaction.commit()
            source_unchanged()
            return str(destination)
