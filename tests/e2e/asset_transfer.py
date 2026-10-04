"""Provision verified assets on the held, powered-off guest before a journey.

No installation, guest command, lifecycle operation, or observation write API.
Partial/failed transfers are terminal; the outer lease owns restoration.
"""

import json
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
