"""Finite identity/root conflicts; restore only the exact recorded mutation.

Directory witnesses deliberately cover the root and a foreign-owned sentinel,
not mutable product records: removal may legitimately update those records.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import pwd
import stat
import uuid

import system_guest as guest
from system_removal_faults import metadata, parents
from system_removal_ownership import pinned, rename_exclusive, witness


IDENTITY_FILESYSTEM_VARIANTS = (
    'kiosk-marker-uid', 'home-owner', 'home-link', 'home-mount',
    'state-owner', 'state-link', 'state-mount',
)
HOME = Path('/home/oh-no-parent-control')
STATE_ROOT = Path('/var/lib/oh-no-parent-control')
OWNER_UID = 0
SENTINEL_BYTES = b'onpc identity filesystem foreign preservation witness\n'


def require(condition, reason):
    guest.require(condition, 'removal-identity:' + reason)


def attributes(fd):
    return tuple((name, os.getxattr(fd, name)) for name in sorted(os.listxattr(fd)))


def directory_witness(fd):
    return metadata(os.fstat(fd)), attributes(fd)


def ancestor_metadata(path, variant):
    value = metadata(path.lstat())
    # Account finalization runs after postrm consumes owned rollback folders.
    # Those removals change only the state root's directory link count. Its
    # inode, device, owner/group and mode remain authoritative boundaries.
    return value[:-1] if variant == 'kiosk-marker-uid' and path == STATE_ROOT else value


def write_all(fd, data, progress):
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        require(written > 0, 'short-write')
        offset += written
        progress(offset)


class IdentityConflict:
    def __init__(self, variant, target, fd, namespace, mounts, ancestors, foreign_account):
        self.variant, self.target, self.fd = variant, target, fd
        self.namespace, self.mounts, self.ancestors = namespace, mounts, ancestors
        self.foreign_account = foreign_account
        self.expected_marker_uid = None
        self.preflight = variant in ('kiosk-marker-uid', 'home-owner', 'home-link',
                                     'state-owner', 'state-link')
        self.reason = (
            b'uninstall snapshot directory is unsafe' if variant in ('state-owner', 'state-link') else
            b'changed-kiosk-identity' if variant == 'kiosk-marker-uid' else
            b'changed-kiosk-home' if variant in ('home-owner', 'home-link') else
            b'refusing cleanup of a mounted directory')
        self.original = self.expected = None
        self.backup = self.link = None
        self.owned_mounts = {}
        self.sentinel = self.sentinel_fd = self.sentinel_expected = None
        self.sentinel_bytes = b''

    def boundary(self):
        from system_removal import mount_inventory
        try:
            actual = pwd.getpwuid(self.foreign_account.pw_uid)
        except KeyError:
            raise guest.GuestError('removal-identity:foreign-account-changed') from None
        require(actual == self.foreign_account, 'foreign-account-changed')
        parents(self.target)
        require(tuple((p, ancestor_metadata(p, self.variant)) for p, _ in self.ancestors) ==
                self.ancestors, 'parent-identity-changed')
        namespace, mounts = mount_inventory()
        require(namespace == self.namespace and mounts == self.mounts | self.owned_mounts,
                'mount-identity-changed')

    def root(self):
        return self.backup if self.backup is not None else self.target

    def verify(self):
        self.boundary()
        if self.variant == 'kiosk-marker-uid':
            require(witness(self.target) == self.expected and pinned(self.fd) == self.expected,
                    'marker-identity-changed')
            return
        require(directory_witness(self.fd) == self.expected and
                metadata(self.root().lstat()) == self.expected[0], 'root-identity-changed')
        if self.backup is not None:
            if self.link is None:
                require(not os.path.lexists(self.target), 'partial-path-occupied')
            else:
                require(metadata(self.target.lstat()) == self.link and
                        os.readlink(self.target) == self.backup.name, 'link-identity-changed')
        if self.sentinel_fd is not None:
            expected = self.sentinel_expected
            require(pinned(self.sentinel_fd) == expected and
                    witness(self.root() / self.sentinel.name) == expected,
                    'sentinel-identity-changed')

    def restore(self):
        self.verify()
        if self.variant == 'kiosk-marker-uid':
            os.lseek(self.fd, 0, os.SEEK_SET)
            write_all(self.fd, self.original.contents, lambda _: None)
            os.ftruncate(self.fd, len(self.original.contents))
            os.utime(self.fd, ns=self.original_times)
            os.fsync(self.fd)
            require(witness(self.target) == self.original and pinned(self.fd) == self.original,
                    'marker-restoration-not-verified')
            return
        if self.owned_mounts:
            guest.run(['umount', '--', str(self.target)], timeout=30)
            self.owned_mounts = {}
            self.verify()
        if self.backup is not None:
            if self.link is not None:
                self.target.unlink()
                self.link = None
            require(not os.path.lexists(self.target), 'restore-path-occupied')
            rename_exclusive(self.backup, self.target)
            self.backup = None
        if self.variant.endswith('-owner'):
            os.fchown(self.fd, self.original[0][2], self.original[0][3])
            self.expected = directory_witness(self.fd)
            require(self.expected == self.original, 'owner-restoration-not-verified')
        if self.sentinel_fd is not None:
            # verify() just established this exact public entry and pinned file.
            self.verify()
            os.unlink(self.sentinel.name, dir_fd=self.fd)
            self.sentinel_fd, sentinel_fd = None, self.sentinel_fd
            os.close(sentinel_fd)
        os.fsync(self.fd)
        self.boundary()
        require(directory_witness(self.fd) == self.original and
                metadata(self.target.lstat()) == self.original[0], 'root-restoration-not-verified')


@contextmanager
def identity_filesystem_conflict(variant, foreign_uid, record):
    """Apply one fixed conflict; unknown changes block restoration and survive."""
    guest.guard()
    require(variant in IDENTITY_FILESYSTEM_VARIANTS, 'unknown-variant')
    require(type(foreign_uid) is int and 0 < foreign_uid < 2 ** 32 - 1 and
            foreign_uid != OWNER_UID, 'unsafe-foreign-uid')
    try:
        foreign_account = pwd.getpwuid(foreign_uid)
    except KeyError:
        raise guest.GuestError('removal-identity:foreign-account-missing') from None
    require(foreign_account.pw_uid == foreign_uid and
            foreign_account.pw_name != 'oh-no-parent-control', 'unsafe-foreign-account')
    marker = variant == 'kiosk-marker-uid'
    if marker:
        # The marker also drives prerm's active-manager check. Use a dormant
        # existing identity, never stop a foreign user's manager to reach postrm.
        guest.commands.run(['systemctl', 'is-active', '--quiet', f'user@{foreign_uid}.service'],
                           check=False, timeout=30, merge_stderr=True)
        require(guest.commands.last_returncode in (3, 4), 'foreign-manager-not-inactive')
    target = (STATE_ROOT / 'package-created-kiosk-uid' if marker else
              HOME if variant.startswith('home-') else STATE_ROOT)
    parents(target)
    info = target.lstat()
    require((stat.S_ISREG(info.st_mode) if marker else stat.S_ISDIR(info.st_mode)) and
            not info.st_mode & 0o022 and (not marker or info.st_nlink == 1), 'unsafe-original')
    require(info.st_uid == (OWNER_UID if marker or variant.startswith('state-') else
                           pwd.getpwnam('oh-no-parent-control').pw_uid),
            'unsafe-original-owner')
    require(info.st_uid != foreign_uid, 'unchanged-owner')
    from system_removal import mount_inventory
    namespace, mounts = mount_inventory()
    # A nested mount is equally unsafe; do not hide or adopt an existing mount.
    require(not any(row[0][4] == str(target) or
                    row[0][4].startswith(str(target) + '/') for row in mounts.values()),
            'preexisting-mount')
    ancestors = tuple((p, ancestor_metadata(p, variant)) for p in target.parents)
    fd = os.open(target, (os.O_RDWR if marker else os.O_RDONLY | os.O_DIRECTORY) |
                 os.O_NOFOLLOW | os.O_CLOEXEC)
    conflict = IdentityConflict(variant, target, fd, namespace, mounts, ancestors, foreign_account)
    try:
        require(metadata(os.fstat(fd)) == metadata(info), 'original-identity-changed')
        conflict.original = pinned(fd) if marker else directory_witness(fd)
        conflict.expected = conflict.original
        conflict.original_times = (info.st_atime_ns, info.st_mtime_ns)
        conflict.boundary()
        if marker:
            contents = conflict.original.contents
            require(stat.S_IMODE(info.st_mode) == 0o600 and contents.strip().isdigit() and
                    int(contents) > 0 and int(contents) != foreign_uid, 'unsafe-marker')
        try:
            if marker:
                data = (str(foreign_uid) + '\n').encode()
                conflict.expected_marker_uid = foreign_uid
                os.lseek(fd, 0, os.SEEK_SET)

                def progress(offset):
                    # Include any original tail until ftruncate succeeds.
                    conflict.expected = pinned(fd)
                    require(conflict.expected.contents == data[:offset] + contents[offset:],
                            'partial-marker-write-changed')

                write_all(fd, data, progress)
                os.ftruncate(fd, len(data))
                conflict.expected = pinned(fd)
                require(conflict.expected.contents == data, 'marker-write-changed')
            else:
                name = '.onpc-removal-identity-' + uuid.uuid4().hex
                conflict.sentinel = target / name
                sentinel_fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL |
                                      os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
                conflict.sentinel_fd = sentinel_fd
                conflict.sentinel_expected = pinned(sentinel_fd)

                def sentinel_progress(offset):
                    conflict.sentinel_bytes = SENTINEL_BYTES[:offset]
                    conflict.sentinel_expected = pinned(sentinel_fd)
                    require(conflict.sentinel_expected.contents == conflict.sentinel_bytes,
                            'partial-sentinel-write-changed')

                write_all(sentinel_fd, SENTINEL_BYTES, sentinel_progress)
                os.fchown(sentinel_fd, foreign_uid, os.fstat(sentinel_fd).st_gid)
                conflict.sentinel_expected = pinned(sentinel_fd)
                os.fsync(sentinel_fd)
                if variant.endswith('-owner'):
                    os.fchown(fd, foreign_uid, info.st_gid)
                    expected = list(conflict.original[0])
                    expected[2] = foreign_uid
                    conflict.expected = (tuple(expected), conflict.original[1])
                elif variant.endswith('-link'):
                    backup = target.parent / ('.onpc-removal-identity-root-' + uuid.uuid4().hex)
                    rename_exclusive(target, backup)
                    conflict.backup = backup
                    target.symlink_to(backup.name)
                    conflict.link = metadata(target.lstat())
                else:
                    try:
                        guest.run(['mount', '--bind', str(target), str(target)], timeout=30)
                    finally:
                        # A command may fail after the kernel accepted its mount.
                        # Recover only our one exact self-bind, never extra rows.
                        current_namespace, current = mount_inventory()
                        owned = {key: row for key, row in current.items() if key not in mounts}
                        if current_namespace == namespace and not owned and current == mounts:
                            pass
                        else:
                            require(current_namespace == namespace and len(owned) == 1 and
                                    next(iter(owned.values()))[0][4] == str(target) and
                                    current == mounts | owned and
                                    metadata(target.lstat()) == conflict.original[0],
                                    'mount-not-attributable')
                            conflict.owned_mounts = owned
                    require(bool(conflict.owned_mounts), 'mount-not-created')
            conflict.verify()
            record('onpc.identity.conflict', json.dumps({
                'variant': variant, 'namespace': namespace, 'mounts': conflict.owned_mounts,
                'device': info.st_dev, 'inode': info.st_ino}, sort_keys=True))
            yield conflict
        finally:
            conflict.restore()
    finally:
        if conflict.sentinel_fd is not None:
            os.close(conflict.sentinel_fd)
        os.close(fd)
