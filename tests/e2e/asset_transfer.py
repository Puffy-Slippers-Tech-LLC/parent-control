"""Provision verified attempt assets before customer entry.

Offline consumers copy on the held powered-off disk; installed consumers copy
from the fresh setup payload after snapshot restoration. No installation,
lifecycle operation, or observation write API.
Partial/failed transfers are terminal; the outer lease owns restoration.
"""

import json
import inspect
import os
from pathlib import Path
import stat
import sys

from private_artifacts import EvidenceError, require
from provenance import digest, identity, package_filename, parent_directory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
from system_runner import mounted_guest
sys.path.pop(0)

DESTINATION = '/var/lib/onpc-e2e-assets'
TRANSFER_REFUSALS = frozenset('transfer:' + condition for condition in (
    'outside-provisioning', 'inventory-mismatch', 'package-mismatch',
    'unsafe-parent', 'destination-exists', 'unsafe-preservation-parent',
    'unsafe-preservation-file', 'unsafe-source', 'source-replaced',
    'copied-digest-mismatch', 'source-changed', 'copied-tree-mismatch',
    'preservation-changed',
))

from guest_observations import ASSETS as OBSERVE


def provision_installed_assets(files):
    """Fixed guest-side copy from fresh setup inputs; never adopt existing assets."""
    import hashlib
    import os
    from pathlib import Path
    import stat

    assert os.geteuid() == 0
    source = Path('/var/tmp/onpc-system-input')
    destination = Path('/var/lib/onpc-e2e-assets')
    for parent in (source.parent, destination.parent):
        info = parent.lstat()
        assert parent.resolve() == parent and stat.S_ISDIR(info.st_mode)
        assert info.st_uid == info.st_gid == 0
        assert (parent == source.parent and stat.S_IMODE(info.st_mode) == 0o1777
                or not stat.S_IMODE(info.st_mode) & 0o022)
    assert type(files) is dict and files
    directories = {'.'}
    seen_files, seen_directories = set(), {'.'}
    for name in files:
        path = Path(name)
        assert not path.is_absolute() and path.as_posix() == name
        assert all(part not in ('', '.', '..') for part in path.parts)
        directories.update(parent.as_posix() for parent in path.parents)

    def identity(info):
        return tuple(getattr(info, field) for field in (
            'st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
            'st_size', 'st_mtime_ns', 'st_ctime_ns'))

    def safe(info, directory=False):
        assert info.st_uid == info.st_gid == 0 and not stat.S_IMODE(info.st_mode) & 0o022
        assert stat.S_ISDIR(info.st_mode) if directory else (
            stat.S_ISREG(info.st_mode) and info.st_nlink == 1)

    def copy_tree(origin, target, prefix=''):
        before = os.fstat(origin)
        safe(before, directory=True)
        names = sorted(os.listdir(origin))
        for name in names:
            relative = prefix + name
            info = os.stat(name, dir_fd=origin, follow_symlinks=False)
            is_directory = stat.S_ISDIR(info.st_mode)
            safe(info, directory=is_directory)
            assert relative in (directories if is_directory else files)
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if is_directory:
                flags |= os.O_DIRECTORY
            original = os.open(name, flags, dir_fd=origin)
            try:
                assert identity(os.fstat(original)) == identity(info)
                if is_directory:
                    seen_directories.add(relative)
                    os.mkdir(name, 0o755, dir_fd=target)
                    copied = os.open(name, flags, dir_fd=target)
                    try:
                        os.fchmod(copied, 0o755)
                        copy_tree(original, copied, relative + '/')
                    finally:
                        os.close(copied)
                else:
                    seen_files.add(relative)
                    copied = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o644, dir_fd=target)
                    try:
                        os.fchmod(copied, 0o644)
                        digest = hashlib.sha256()
                        while block := os.read(original, 1048576):
                            digest.update(block)
                            view = memoryview(block)
                            while view:
                                count = os.write(copied, view)
                                assert count > 0
                                view = view[count:]
                        assert digest.hexdigest() == files[relative]
                        os.fsync(copied)
                        os.lseek(copied, 0, os.SEEK_SET)
                        digest = hashlib.sha256()
                        while block := os.read(copied, 1048576):
                            digest.update(block)
                        assert digest.hexdigest() == files[relative]
                        safe(os.fstat(copied))
                    finally:
                        os.close(copied)
                assert identity(os.fstat(original)) == identity(info)
                assert identity(os.stat(name, dir_fd=origin, follow_symlinks=False)) == identity(info)
            finally:
                os.close(original)
        assert sorted(os.listdir(origin)) == names and identity(os.fstat(origin)) == identity(before)

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    original = os.open(source, flags)
    try:
        safe(os.fstat(original), directory=True)
        assert source.resolve() == source
        # mkdir refuses directories, files and dangling symlinks alike.
        os.mkdir(destination, 0o755)
        copied = os.open(destination, flags)
        try:
            os.fchmod(copied, 0o755)
            copy_tree(original, copied)
            assert seen_files == set(files) and seen_directories == directories
            assert identity(source.lstat()) == identity(os.fstat(original))
            assert destination.resolve() == destination
        finally:
            os.close(copied)
    finally:
        os.close(original)


def preservation_witness(g):
    """Finite account/locale/unrelated-file witness around offline provisioning."""
    paths = ['/etc/passwd', '/etc/group', '/etc/shadow', '/etc/hostname',
             '/etc/default/locale', '/etc/locale.conf', '/etc/machine-id', '/etc/motd']
    account_root = '/var/lib/AccountsService/users'
    if g.exists(account_root):
        require(not g.is_symlink(account_root) and g.realpath(account_root) == account_root,
                'transfer:unsafe-preservation-parent')
        paths += [account_root + '/' + name for name in g.find(account_root + '/')]
    witness = {}
    for path in paths:
        linked = g.is_symlink(path)
        if g.exists(path) or linked:
            info = g.lstatns(path)
            if linked:
                # Ubuntu 26.04's compatibility alias is not an asset input.
                # Preserve the link itself without hashing through it; the
                # canonical regular file has its own independent witness.
                require(path == '/etc/default/locale'
                        and g.exists(path)
                        and g.readlink(path) == '../locale.conf'
                        and g.realpath(path) == '/etc/locale.conf',
                        'transfer:unsafe-preservation-file')
                content = {'link': '../locale.conf'}
            else:
                require(stat.S_ISREG(info['st_mode']), 'transfer:unsafe-preservation-file')
                content = g.checksum('sha256', path)
            witness[path] = (content, {
                key: info[key] for key in ('st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink', 'st_size')})
        else:
            witness[path] = None
    return witness


class AssetTransfer:
    def __init__(self, verified):
        self.verified = verified
        self._attempted = False
        self._failure = None
        self._receipt = None

    def provision_installed(self, lease, transport):
        """One current-package transfer after running snapshot restoration/setup."""
        require(not self._attempted, 'transfer:already-attempted')
        self._attempted = True
        try:
            require(lease is self.verified.lease and lease.fd is not None
                    and lease.state['phase'] == 'running' and lease.state['domain_id'] is not None
                    and transport.config['domain_uuid'] == lease.state['domain_uuid']
                    and transport.config['domain_id'] == lease.state['domain_id']
                    and transport.config['run'] == lease.state['run']
                    and not self.verified.upgrade_inputs, 'transfer:outside-provisioning')
            lease.guard()
            self.verified.recheck()
            files = self.verified.asset_files
            require(files[package_filename(files)] == self.verified.inputs['package_sha256'],
                    'transfer:package-mismatch')
            program = inspect.getsource(provision_installed_assets) + (
                '\nimport json,sys\nprovision_installed_assets(json.load(sys.stdin))\n')
            transport.call(['/usr/bin/python3', '-c', program],
                           input=json.dumps(files, sort_keys=True).encode(), timeout=300)
            lease.guard()
            self.verified.recheck()
            self._receipt = {'files': len(files), 'sha256': digest(files)}
            print('e2e:asset-transfer-verified', file=sys.stderr, flush=True)
            return dict(self._receipt)
        except BaseException:
            self._failure = 'transfer:provisioning-failed'
            print('e2e:asset-transfer-rejected code=' + self._failure, file=sys.stderr, flush=True)
            raise

    def provision(self, lease, guestfs):
        require(not self._attempted, 'transfer:already-attempted')
        self._attempted = True
        try:
            require(lease is self.verified.lease and lease.fd is not None
                    and lease.state['phase'] == 'isolated'
                    and lease.state['domain_id'] is None, 'transfer:outside-provisioning')
            lease.guard(off=True)
            self.verified.recheck()
            files = self.verified.asset_files
            assets = self.verified.assets
            inventory = json.loads((assets / 'transfer-sha256.json').read_bytes())
            require(inventory == {p: h for p, h in files.items()
                                  if p != 'transfer-sha256.json'}, 'transfer:inventory-mismatch')
            require(files[package_filename(files)] == self.verified.inputs['package_sha256'],
                    'transfer:package-mismatch')
            directories = sorted({parent.as_posix() for name in files
                                  for parent in Path(name).parents if parent != Path('.')},
                                 key=lambda name: (len(Path(name).parts), name))
            print('e2e:asset-transfer-started', file=sys.stderr, flush=True)
            with mounted_guest(guestfs, lease) as g:
                require(g.realpath('/var/lib') == '/var/lib', 'transfer:unsafe-parent')
                require(not g.exists(DESTINATION) and not g.is_symlink(DESTINATION),
                        'transfer:destination-exists')
                preserved_before = preservation_witness(g) if self.verified.upgrade_inputs else None
                for name in ['', *directories]:
                    target = DESTINATION + ('/' + name if name else '')
                    g.mkdir(target)
                    g.chown(0, 0, target)
                    g.chmod(0o755, target)
                for name, expected in files.items():
                    path = assets / name
                    before = path.lstat()
                    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                            'transfer:unsafe-source')
                    with parent_directory(path) as parent:
                        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                     dir_fd=parent)
                        try:
                            require(identity(os.fstat(fd)) == identity(before),
                                    'transfer:source-replaced')
                            target = DESTINATION + '/' + name
                            g.upload('/dev/fd/' + str(fd), target)
                            g.chown(0, 0, target)
                            g.chmod(0o644, target)
                            require(g.checksum('sha256', target) == expected,
                                    'transfer:copied-digest-mismatch')
                            require(identity(os.fstat(fd)) == identity(before),
                                    'transfer:source-changed')
                        finally:
                            os.close(fd)
                # find removes the supplied directory prefix verbatim. Include
                # its separator so returned names are relative, not /name.
                observed = set(g.find(DESTINATION + '/'))
                expected = set(files) | set(directories)
                print(f'e2e:asset-tree-observed expected_entries={len(expected)} '
                      f'observed_entries={len(observed)} '
                      f'expected_sha256={digest(sorted(expected))} '
                      f'observed_sha256={digest(sorted(observed))}',
                      file=sys.stderr, flush=True)
                require(observed == expected,
                        'transfer:copied-tree-mismatch')
                if preserved_before is not None:
                    require(preservation_witness(g) == preserved_before, 'transfer:preservation-changed')
            self.verified.recheck()
            self._receipt = {'files': len(files), 'sha256': digest(files)}
            if self.verified.upgrade_inputs:
                self._receipt['packages'] = self.verified.upgrade_inputs['packages']
            print('e2e:asset-transfer-verified', file=sys.stderr, flush=True)
            return dict(self._receipt)
        except BaseException as error:
            self._failure = 'transfer:provisioning-failed'
            # Outer cleanup may classify an unknown exception generically.
            # Retain only our finite diagnoses, never arbitrary error text.
            code = str(error) if isinstance(error, EvidenceError) and str(error) in TRANSFER_REFUSALS else (
                self._failure)
            print('e2e:asset-transfer-rejected code=' + code, file=sys.stderr, flush=True)
            raise

    def observe(self, observations):
        require(self._failure is None and self._receipt is not None,
                'transfer:verified-provisioning-required')
        try:
            observed = observations.read('assets-upgrade' if self.verified.upgrade_inputs else 'assets')
            require(observed == self._receipt, 'transfer:booted-assets-mismatch')
            return dict(self._receipt)
        except BaseException:
            self._failure = 'transfer:observation-failed'
            raise
