#!/usr/bin/python3
"""Inventory, then migrate explicitly selected legacy test allocations.

No manifest means read-only inventory. A reviewed manifest at the fixed checkout
path authorizes only its exact directory identities. No process is signalled.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import test_retention as retention
import test_storage as storage
from check_tmp_storage_cleanup import unused
from check_test_recovery import reconcile_vm

MANIFEST = ROOT / 'output/test-runs/storage-migration.json'
LEGACY_RUNS = ('artifacts/fix-tests', 'artifacts/test-sessions',
               'artifacts/test-sessions-host', 'docs/TestAutomation/Evidence/test-all-runs')
DISPOSABLE = frozenset(('assets', 'input', 'previous', 'fixtures', 'package',
                        'distribution', 'qemuscreenshot', 'command-server-tmp'))


def identity(path):
    fd = retention.directory(path)
    try:
        info = os.fstat(fd)
        return dict(path=str(path), device=info.st_dev, inode=info.st_ino,
                    mode=stat.S_IMODE(info.st_mode), uid=info.st_uid)
    finally:
        os.close(fd)


def validate(record, caller):
    path = Path(record.get('path', ''))
    legacy_run = (path.parent in {ROOT / name for name in LEGACY_RUNS}
                  and re.fullmatch(r'(?:[0-9a-f]{32}|[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8})', path.name))
    if (set(record) != {'path', 'device', 'inode', 'mode', 'uid'}
            or not isinstance(record['path'], str)
            or (not legacy_run and re.fullmatch(r'/(?:var/)?tmp/onpc-[A-Za-z0-9_.-]+', record['path']) is None)
            or record['uid'] not in (0, caller)
            or record['mode'] not in (0o700, 0o711)
            or any(type(record[key]) is not int for key in ('device', 'inode', 'mode', 'uid'))
            or identity(record['path']) != record):
        raise ValueError('migration: invalid or replaced allocation')
    fd = retention.directory(record['path'])
    parent = retention.directory(Path(record['path']).parent)
    try:
        if retention.mount_id(fd) != retention.mount_id(parent):
            raise ValueError('migration: mounted allocation')
        retention.check_tree(fd, record['device'])
    finally:
        os.close(fd)
        os.close(parent)


def preserve(source, destination):
    """Keep diagnostics, not regenerable frozen inputs or stale sockets.

    All source trees have been validated under idle activity/storage ownership.
    Links and special files are never followed. Every copied regular file is
    content-verified before source removal; failed copies leave sources intact.
    """
    def copy_tree(source_fd, target):
        for name in os.listdir(source_fd):
            info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
            if name in DISPOSABLE or name.startswith('ssh-key'):
                continue
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=source_fd)
                try:
                    opened = os.fstat(child)
                    if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                            or retention.mount_id(child) != retention.mount_id(source_fd)):
                        raise ValueError('migration: mounted evidence')
                    (target / name).mkdir(mode=0o700)
                    copy_tree(child, target / name)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source_fd)
                with os.fdopen(descriptor, 'rb') as stream:
                    opened = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                            or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)):
                        raise ValueError('migration: replaced or hard-linked evidence')
                    digest = hashlib.sha256()
                    with (target / name).open('xb') as output:
                        os.fchmod(output.fileno(), 0o600)
                        for block in iter(lambda: stream.read(65536), b''):
                            digest.update(block)
                            output.write(block)
                        output.flush()
                        os.fsync(output.fileno())
                    with (target / name).open('rb') as copied:
                        if digest.hexdigest() != hashlib.file_digest(copied, 'sha256').hexdigest():
                            raise ValueError('migration: copied evidence changed')
                    after = os.fstat(stream.fileno())
                    if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError('migration: source changed during copy')
    fd = retention.directory(source)
    try:
        copy_tree(fd, destination)
    finally:
        os.close(fd)


def migrate(records, caller, *, guard=unused):
    if not isinstance(records, list) or not records or len(records) > 4096:
        raise ValueError('migration: invalid reviewed inventory')
    paths = {record['path'] for record in records}
    if len(paths) != len(records):
        raise ValueError('migration: duplicate allocation')
    for record in records:
        validate(record, caller)
    guard(paths)
    for record in records:
        source = Path(record['path'])
        destination = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-migrated-'))
        preserve(source, destination)
        (destination / 'migration.json').write_text(json.dumps(record))
        # Revalidate before deletion, and use the existing descriptor-pinned
        # deletion implementation under the recorded owner's credentials.
        validate(record, caller)
        previous = os.geteuid()
        try:
            os.seteuid(record['uid'])
            retention.remove({key: value for key, value in record.items() if key != 'uid'})
        finally:
            os.seteuid(previous)
        print(json.dumps({'removed': str(source), 'evidence': str(destination)}), flush=True)


def main():
    caller = int(os.environ.get('PKEXEC_UID', '0'))
    if len(sys.argv) != 1 or os.geteuid() != 0 or caller <= 0 or Path.cwd() != ROOT:
        raise ValueError('migration: authenticated dispatcher required')
    if not MANIFEST.exists():
        candidates = list(Path('/tmp').iterdir())
        for relative in LEGACY_RUNS:
            parent = ROOT / relative
            if parent.exists():
                candidates.extend(path for path in parent.iterdir() if re.fullmatch(
                    r'(?:[0-9a-f]{32}|[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8})', path.name))
        for path in sorted(candidates):
            if path.is_dir() and not path.is_symlink() and (
                    path.parent != Path('/tmp') or re.fullmatch(r'onpc-[A-Za-z0-9_.-]+', path.name)):
                record = identity(path)
                if record['uid'] in (0, caller) and record['mode'] in (0o700, 0o711):
                    print(json.dumps(record), flush=True)
        return 0
    descriptor = os.open(MANIFEST, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != caller or info.st_nlink != 1
                or info.st_mode & 0o022 or info.st_size > 1024 * 1024):
            raise ValueError('migration: unsafe reviewed inventory')
        records = json.load(stream)
    checkout = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    # Checkout activity is held by the launcher. Acquire all old storage owners
    # too, including host-only activity, before inspecting any deletion target.
    with ExitStack() as stack:
        activity = os.open(ROOT / 'artifacts/test-activity/host.lock', os.O_RDWR | os.O_NOFOLLOW)
        stack.callback(os.close, activity)
        import fcntl
        info = os.fstat(activity)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != caller or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError('migration: unsafe legacy activity lock')
        fcntl.flock(activity, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old_loop = ROOT / 'artifacts/fix-tests/owner'
        if old_loop.exists():
            lock = os.open(old_loop, os.O_RDWR | os.O_NOFOLLOW)
            stack.callback(os.close, lock)
            info = os.fstat(lock)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != caller or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError('migration: unsafe legacy repair lock')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for path in (ROOT / 'artifacts/test-retention', ROOT / 'artifacts/test-retention-host',
                     Path('/var/tmp') / f'onpc-test-retention-root-{caller}-{checkout}'):
            if path.exists():
                fd = retention.directory(path)
                stack.callback(os.close, fd)
                lock = os.open('owner.lock', os.O_RDWR | os.O_NOFOLLOW, dir_fd=fd)
                stack.callback(os.close, lock)
                info = os.fstat(lock)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, caller)
                        or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
                    raise ValueError('migration: unsafe legacy owner lock')
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reconcile_vm(ROOT)
        with retention.Store(storage.privileged_state(caller)).session():
            migrate(records, caller)
    return 0


if __name__ == '__main__':
    sys.exit(main())
