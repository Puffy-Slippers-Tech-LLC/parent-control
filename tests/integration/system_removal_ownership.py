"""Finite guest ownership conflicts with identity-bound, serial restoration."""

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import grp
import json
import os
from pathlib import Path
import stat
import uuid

import system_guest as guest
from system_removal_faults import metadata, parents


OWNER_UID = 0
OWNERSHIP_VARIANTS = (
    'systemd-user-edit', 'gdm-password-link', 'systemd-user-link',
    'gdm-hook-link', 'confinement-record-owner', 'confinement-record-link',
    'confinement-record-uid',
)
COMMENT = b'\n# onpc removal ownership conflict\n'
STATE = Path('/var/lib/oh-no-parent-control')
FALLBACK_RULE = Path('/etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules')


def ownership_targets(distribution):
    """Historic variant labels retain IDs; these are their current authorities."""
    require(distribution in ('ubuntu', 'fedora'), 'unknown-distribution')
    selection = STATE / ('fedora-authselect.json' if distribution == 'fedora'
                         else 'malcontent-pam-before-install')
    return {
        'systemd-user-edit': selection,
        'gdm-password-link': selection,
        'systemd-user-link': STATE / 'installed-child-extension-trust',
        'gdm-hook-link': FALLBACK_RULE,
        **{variant: STATE / 'kiosk-configuration-account.json'
           for variant in OWNERSHIP_VARIANTS if variant.startswith('confinement-record-')},
    }


def ownership_reason(variant, distribution):
    require(variant in OWNERSHIP_VARIANTS and distribution in ('ubuntu', 'fedora'),
            'unknown-selection')
    if variant.startswith('confinement-record-'):
        return {'confinement-record-uid': b'changed-kiosk-expiry-record',
                'confinement-record-owner': b'unsafe-migration-file',
                'confinement-record-link': b'[Errno 40]'}[variant]
    if variant == 'systemd-user-link':
        return b'refusing substituted child trust integration'
    if variant == 'gdm-hook-link':
        return b'system integration was modified; preserving it and refusing removal'
    if distribution == 'fedora':
        return (b'invalid original authselect selection' if variant.endswith('-edit') else
                b'unsafe authselect ownership or substituted path')
    return (b'invalid original PAM selection' if variant.endswith('-edit') else
            b'unsafe original PAM selection')


def require(condition, reason):
    guest.require(condition, 'removal-ownership:' + reason)


def rename_exclusive(source, destination):
    """Linux's atomic no-replace rename never overwrites an occupied name."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


@dataclass(frozen=True)
class Witness:
    metadata: tuple
    mtime_ns: int
    xattrs: tuple
    contents: object


def witness(path):
    """Read only regular files or link text, never a substituted referent."""
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode), 'unsafe-type')
    if stat.S_ISLNK(info.st_mode):
        contents = os.readlink(path)
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(metadata(os.fstat(fd)) == metadata(info), 'read-identity-changed')
            contents = os.pread(fd, info.st_size + 1, 0)
            require(metadata(os.fstat(fd)) == metadata(info), 'read-identity-changed')
        finally:
            os.close(fd)
    attrs = tuple((name, os.getxattr(path, name, follow_symlinks=False))
                  for name in sorted(os.listxattr(path, follow_symlinks=False)))
    require(metadata(path.lstat()) == metadata(info), 'read-path-changed')
    return Witness(metadata(info), info.st_mtime_ns, attrs, contents)


def pinned(fd):
    info = os.fstat(fd)
    attrs = tuple((name, os.getxattr(fd, name)) for name in sorted(os.listxattr(fd)))
    return Witness(metadata(info), info.st_mtime_ns, attrs,
                   os.pread(fd, info.st_size + 1, 0))


class Conflict:
    def __init__(self, variant, path, fd, original, original_times, namespace,
                 mounts, ancestors):
        self.variant, self.path, self.fd = variant, path, fd
        self.original, self.original_times = original, original_times
        self.namespace, self.mounts, self.ancestors = namespace, mounts, ancestors
        self.backup = None
        self.expected = self.referent = None
        self.setup_bytes = original.contents
        self.setup_owner = original.metadata[2]
        self.setup_link = None

    def verify_setup(self):
        """Accept only the exact attributable prefix of our incomplete setup."""
        self.boundary()
        if self.backup is not None:
            require(witness(self.backup) == self.original and
                    pinned(self.fd) == self.original, 'partial-referent-changed')
            if self.setup_link is None:
                require(not os.path.lexists(self.path), 'partial-path-occupied')
            else:
                require(metadata(self.path.lstat()) == self.setup_link and
                        os.readlink(self.path) == self.backup.name,
                        'partial-link-changed')
            return
        value = pinned(self.fd)
        expected_metadata = list(self.original.metadata)
        expected_metadata[2] = self.setup_owner
        require(value.metadata == tuple(expected_metadata) and
                value.contents == self.setup_bytes and
                value.xattrs == self.original.xattrs and
                metadata(self.path.lstat()) == value.metadata,
                'partial-original-changed')

    def boundary(self):
        from system_removal import mount_inventory
        parents(self.path)
        current = tuple((p, metadata(p.lstat())) for p, _ in self.ancestors)
        try:
            require(current == self.ancestors, 'parent-identity-changed')
        except guest.GuestError as error:
            # Diagnose the exact failed observation, without a second stat that
            # could miss a transient change. Never disclose paths or account IDs.
            fields = ('device', 'inode', 'owner', 'group', 'mode', 'links')
            changes = []
            for index, ((_, before), (_, after)) in enumerate(zip(self.ancestors, current)):
                if before != after:
                    change = {
                        'ancestor_from_target': index,
                        'ancestor_from_root': len(self.ancestors) - index - 1,
                        'fields': [name for name, old, new in zip(fields, before, after)
                                   if old != new],
                    }
                    if before[5] != after[5]:
                        change['links_before'], change['links_after'] = before[5], after[5]
                    changes.append(change)
            error.add_note('ancestor-metadata-deltas=' + json.dumps(changes, sort_keys=True))
            raise
        namespace, mounts = mount_inventory()
        require(namespace == self.namespace and mounts == self.mounts,
                'mount-identity-changed')

    def verify(self):
        """Prove conflict and pinned referent metadata, inode and exact bytes."""
        self.boundary()
        require(witness(self.path) == self.expected, 'conflict-identity-changed')
        if self.backup is not None:
            require(witness(self.backup) == self.referent and
                    pinned(self.fd) == self.referent, 'referent-identity-changed')
        else:
            require(pinned(self.fd) == self.expected, 'pinned-identity-changed')

    def restore(self):
        if self.expected is None:
            self.verify_setup()
        else:
            self.verify()
        if self.backup is not None:
            if self.setup_link is not None:
                self.path.unlink()
            # Parents are guarded root directories; no wildcard or foreign
            # destination is adopted. Refuse rather than replace any new entry.
            require(not os.path.lexists(self.path), 'restore-path-occupied')
            rename_exclusive(self.backup, self.path)
        else:
            os.fchown(self.fd, self.original.metadata[2], self.original.metadata[3])
            os.fchmod(self.fd, stat.S_IMODE(self.original.metadata[4]))
            os.lseek(self.fd, 0, os.SEEK_SET)
            data = self.original.contents
            offset = 0
            while offset < len(data):
                written = os.write(self.fd, data[offset:])
                require(written > 0, 'restore-short-write')
                offset += written
            os.ftruncate(self.fd, len(data))
            for name, value in self.original.xattrs:
                os.setxattr(self.fd, name, value)
        os.utime(self.fd, ns=self.original_times)
        os.fsync(self.fd)
        self.boundary()
        require(witness(self.path) == self.original and pinned(self.fd) == self.original,
                'restoration-not-verified')


@contextmanager
def ownership_conflict(variant, target: Path, foreign_uid: int, record):
    """Mutate one guarded guest file and restore only its exact owned conflict."""
    guest.guard()
    require(variant in OWNERSHIP_VARIANTS, 'unknown-variant')
    require(isinstance(target, Path) and target.is_absolute() and
            '..' not in target.parts, 'unsafe-path')
    require(type(foreign_uid) is int and 0 < foreign_uid < 2 ** 32 - 1 and
            foreign_uid != OWNER_UID, 'unsafe-foreign-uid')
    parents(target)
    original = witness(target)
    info = target.lstat()
    # systemd applies the broker's Group to its StateDirectory tree. A private
    # root-owned record remains root-only with that group; preserve its exact
    # observed metadata through conflict injection and restoration below.
    group_matches = info.st_gid == OWNER_UID or (
        target.parent == STATE and stat.S_IMODE(info.st_mode) == 0o600 and
        info.st_gid == grp.getgrnam(
            'wheel' if guest.package_path().suffix == '.rpm' else 'sudo').gr_gid)
    # Native tmpfiles recursively assigns /etc/fapolicyd to its fixed service
    # group at boot, even for rules installed root:root. This public rule keeps
    # mode 0644; resolve the native group rather than adopting an observed gid.
    if not group_matches and target == FALLBACK_RULE and stat.S_IMODE(info.st_mode) == 0o644:
        try:
            group_matches = info.st_gid == grp.getgrnam('fapolicyd').gr_gid
        except KeyError:
            pass  # An absent native group cannot authorize the observed group.
    try:
        require(stat.S_ISREG(info.st_mode) and info.st_uid == OWNER_UID and group_matches and
                info.st_nlink == 1 and not info.st_mode & 0o022, 'unsafe-original')
    except guest.GuestError as error:
        # Retain the exact failed observation before any fixture mutation.
        # Distinguish a group-only mismatch from unsafe permissions or links
        # without disclosing account/group IDs, paths or file contents.
        try:
            admin_gid = grp.getgrnam(
                'wheel' if guest.package_path().suffix == '.rpm' else 'sudo').gr_gid
            group_is_administrator = info.st_gid == admin_gid
        except KeyError:
            group_is_administrator = None
        # Distinguish inherited directory groups from the writer's group.
        # Failure to observe the parent must not replace the original refusal.
        try:
            parent_info = target.parent.lstat()
            group_matches_parent = info.st_gid == parent_info.st_gid
            parent_inherits_group = bool(parent_info.st_mode & stat.S_ISGID)
        except OSError:
            group_matches_parent = parent_inherits_group = None
        error.add_note('original-safety=' + json.dumps({
            'regular': stat.S_ISREG(info.st_mode),
            'owner_matches': info.st_uid == OWNER_UID,
            'group_matches': group_matches,
            'group_is_administrator': group_is_administrator,
            'group_matches_fixture_process': info.st_gid == os.getegid(),
            'group_matches_parent': group_matches_parent,
            'parent_inherits_group': parent_inherits_group,
            'links': info.st_nlink,
            'mode': oct(stat.S_IMODE(info.st_mode)),
        }, sort_keys=True))
        raise
    if variant.startswith('confinement-record-'):
        require(stat.S_IMODE(info.st_mode) == 0o600, 'unsafe-record-mode')
        document = json.loads(original.contents)
        require(isinstance(document, dict) and
                set(document) == {'version', 'uid', 'expires', 'phase'} and
                type(document['version']) is int and document['version'] == 1 and
                type(document['uid']) is int and 0 < document['uid'] < 2 ** 32 - 1 and
                document['uid'] != foreign_uid and
                (document['expires'] is None or
                 (type(document['expires']) is int and document['expires'] >= 0)) and
                document['phase'] in ('quarantined', 'releasing'),
                'unsafe-record-uid')
    from system_removal import mount_inventory
    namespace, mounts = mount_inventory()
    require(not any(row[0][4] == str(target) for row in mounts.values()), 'mounted-target')
    ancestors = tuple((p, metadata(p.lstat())) for p in target.parents)
    fd = os.open(target, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    conflict = Conflict(variant, target, fd, original,
                        (info.st_atime_ns, info.st_mtime_ns), namespace, mounts, ancestors)
    try:
        require(pinned(fd) == original, 'original-identity-changed')
        conflict.boundary()
        try:
            if variant.endswith('-link'):
                # Atomic same-filesystem move retains the original SELinux
                # label and real PAM controls; occupied names are never replaced.
                backup = target.parent / ('.onpc-removal-owned-' + uuid.uuid4().hex)
                require(witness(target) == original, 'original-identity-changed')
                rename_exclusive(target, backup)
                conflict.backup = backup
                conflict.referent = witness(backup)
                require(conflict.referent == original, 'backup-identity-changed')
                target.symlink_to(backup.name)
                conflict.setup_link = metadata(target.lstat())
            elif variant == 'confinement-record-owner':
                os.fchown(fd, foreign_uid, original.metadata[3])
                conflict.setup_owner = foreign_uid
                os.fchmod(fd, 0o600)
            else:
                data = original.contents + COMMENT
                if variant == 'confinement-record-uid':
                    document['uid'] = foreign_uid
                    data = (json.dumps(document, sort_keys=True) + '\n').encode()
                elif variant == 'systemd-user-edit' and target.name == 'fedora-authselect.json':
                    # Keep a valid JSON document so the real owner diagnoses
                    # changed selection authority, rather than JSON syntax.
                    document = json.loads(original.contents)
                    require(isinstance(document, dict) and document.get('version') == 1 and
                            isinstance(document.get('original'), list) and document['original'],
                            'unsafe-pam-selection')
                    document['original'] = []
                    data = (json.dumps(document, sort_keys=True) + '\n').encode()
                os.lseek(fd, 0, os.SEEK_SET)
                offset = 0
                while offset < len(data):
                    written = os.write(fd, data[offset:])
                    require(written > 0, 'conflict-short-write')
                    offset += written
                    conflict.setup_bytes = data[:offset] + original.contents[offset:]
                os.ftruncate(fd, len(data))
                conflict.setup_bytes = data
            conflict.verify_setup()
            expected = witness(target)
            if conflict.backup is not None:
                require(expected.metadata == conflict.setup_link and
                        expected.contents == conflict.backup.name,
                        'published-link-changed')
            else:
                require(expected == pinned(fd) and expected.contents == conflict.setup_bytes,
                        'published-original-changed')
            conflict.expected = expected
            conflict.verify()
            record('onpc.ownership.conflict', json.dumps({
                'variant': variant, 'device': conflict.expected.metadata[0],
                'inode': conflict.expected.metadata[1],
                'referent_device': original.metadata[0],
                'referent_inode': original.metadata[1]}, sort_keys=True))
            yield conflict
        finally:
            conflict.restore()
    finally:
        os.close(fd)
