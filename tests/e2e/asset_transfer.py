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
from provenance import digest, identity, parent_directory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
from system_runner import mounted_guest
sys.path.pop(0)

DESTINATION = '/var/lib/onpc-e2e-assets'

from guest_observations import ASSETS as OBSERVE


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
            require(files['package.deb'] == self.verified.inputs['package_sha256'],
                    'transfer:package-mismatch')
            directories = sorted({parent.as_posix() for name in files
                                  for parent in Path(name).parents if parent != Path('.')},
                                 key=lambda name: (len(Path(name).parts), name))
            print('e2e:asset-transfer-started', file=sys.stderr, flush=True)
            with mounted_guest(guestfs, lease) as g:
                require(g.realpath('/var/lib') == '/var/lib', 'transfer:unsafe-parent')
                require(not g.exists(DESTINATION) and not g.is_symlink(DESTINATION),
                        'transfer:destination-exists')
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
            self.verified.recheck()
            self._receipt = {'files': len(files), 'sha256': digest(files)}
            print('e2e:asset-transfer-verified', file=sys.stderr, flush=True)
            return dict(self._receipt)
        except BaseException:
            self._failure = 'transfer:provisioning-failed'
            print('e2e:asset-transfer-rejected', file=sys.stderr, flush=True)
            raise

    def observe(self, observations):
        require(self._failure is None and self._receipt is not None,
                'transfer:verified-provisioning-required')
        try:
            observed = observations.read('assets')
            require(observed == self._receipt, 'transfer:booted-assets-mismatch')
            return dict(self._receipt)
        except BaseException:
            self._failure = 'transfer:observation-failed'
            raise
