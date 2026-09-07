"""Controller-owned input capture; no worker output can supply these identities.

Capture after the existing Lease.prepare and asset staging, while the lease is
held. Recheck before worker startup and after outer cleanup, before releasing
the lease. This module does not acquire, mutate, boot or restore a VM.
"""

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from evidence import EvidenceContract
from private_artifacts import EvidenceError, require

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import build_test_artifacts
sys.path.pop(0)
sys.path.insert(0, str(ROOT / 'tests/fixtures'))
import build_test_applications
sys.path.pop(0)


def encoded(value):
    # Same serialization used by the installed runner's baseline identity.
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def identity(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink,
            metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def directory(path):
    require(path.is_absolute() and path.resolve() == path and path.is_dir(),
            'provenance:unsafe-directory')
    return (path.stat().st_dev, path.stat().st_ino)


@contextmanager
def parent_directory(path):
    """Open each parent without following links, including transient replacements."""
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                            | os.O_CLOEXEC, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def source_paths(root):
    try:
        result = subprocess.run(
            # The installed controller runs as root in the pinned, trusted
            # developer-owned checkout. Scope trust to this invocation/path;
            # never change global Git configuration or allow every directory.
            ['git', '-c', 'safe.directory=' + str(root),
             'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
            cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        paths = sorted(set(result.stdout.decode('utf-8').rstrip('\0').split('\0')))
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise EvidenceError('provenance:source-list-failed') from None
    require(paths and all(p and not Path(p).is_absolute() and '..' not in Path(p).parts
                          for p in paths), 'provenance:source-path')
    return paths


def snapshot(root, *, source=False):
    """Hash current bytes and modes, rejecting unsafe files and changes mid-read.

    The source aggregate deliberately matches build_test_artifacts' source
    digest format; the per-file map is also usable by stage_distribution.
    Metadata is private comparison state, never exported as provenance.
    """
    root = Path(root)
    root_identity = directory(root)
    paths = source_paths(root) if source else sorted(
        p.relative_to(root).as_posix() for p in root.rglob('*'))
    combined = hashlib.sha256()
    files, metadata = {}, {}
    for relative in paths:
        path = root / relative
        require(path.resolve() == path, 'provenance:unsafe-file')
        before = path.lstat()
        if not source and stat.S_ISDIR(before.st_mode):
            metadata[relative] = (before.st_dev, before.st_ino, before.st_mode)
            continue
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                'provenance:unsafe-file')
        combined.update(relative.encode('utf-8') + b'\0')
        combined.update(f'{before.st_mode & 0o7777:o}'.encode('ascii') + b'\0')
        content = hashlib.sha256()
        with parent_directory(path) as parent:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                         | os.O_CLOEXEC, dir_fd=parent)
            with os.fdopen(fd, 'rb') as stream:
                require(identity(os.fstat(fd)) == identity(before), 'provenance:file-replaced')
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    combined.update(block)
                    content.update(block)
                require(identity(os.fstat(fd)) == identity(before), 'provenance:file-changed')
        require(path.resolve() == path and identity(path.lstat()) == identity(before),
                'provenance:file-replaced')
        files[relative] = content.hexdigest()
        metadata[relative] = identity(before)
    after_paths = source_paths(root) if source else sorted(
        p.relative_to(root).as_posix() for p in root.rglob('*'))
    require(paths == after_paths and directory(root) == root_identity,
            'provenance:tree-changed')
    return {'sha256': combined.hexdigest(), 'files': files, 'metadata': metadata,
            'directory': root_identity}


def baseline_inputs(lease):
    """Reconcile durable baseline state and proof through the existing held lease."""
    require(lease.fd is not None, 'provenance:lease-required')
    lease.guard()
    state = lease.capture.read_state()
    require(state == lease.capture.state and state['phase'] == 'finalized',
            'provenance:baseline-state-changed')
    require(lease.capture.verify_snapshot() == state['proof'], 'provenance:baseline-proof-changed')
    baseline_sha256 = digest(state)
    require(baseline_sha256 == lease.state['baseline_sha256'],
            'provenance:baseline-identity-changed')
    require(state['guest']['ubuntu_version'] == '26.04', 'provenance:environment')
    # A safe content identity of the verified guest preparation, including its
    # account contract. Never export raw baseline/account records.
    return {'baseline_sha256': baseline_sha256,
            'environment_id': 'ubuntu26-04-' + digest(state['guest'])}


class VerifiedInputs:
    """Freeze expected inputs independently, and latch any preservation failure.

    The assets directory must be the private staged output of stage_assets, not
    a worker manifest. Product-free smoke may omit it; EvidenceContract enforces
    that exception against the selected category.
    """

    def __init__(self, *, lease, assets=None, root=ROOT):
        self.root, self.lease = Path(root), lease
        self.assets = Path(assets) if assets is not None else None
        self._failure = None
        self._contracts = []
        try:
            self._source = snapshot(self.root, source=True)
            self._baseline = baseline_inputs(lease)
            self._assets = snapshot(self.assets) if self.assets is not None else None
            package_sha256 = None
            if self.assets is not None:
                info = self.assets.stat()
                require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
                        'provenance:assets-not-private')
                manifest = build_test_artifacts.verify(self.assets)
                require(manifest['source']['digest_sha256'] == self._source['sha256'],
                        'provenance:package-source-mismatch')
                fixtures = self.assets / manifest['artifacts']['fixtures']['path']
                build_test_applications.verify(fixtures)
                require((fixtures / 'onpc-test-application.flatpak').is_file(),
                        'provenance:fixture-bundle-missing')
                package_sha256 = manifest['artifacts']['package']['sha256']
            self._inputs = {
                'source_sha256': self._source['sha256'],
                'inventory_sha256': self._source['files']['tests/e2e/scenarios.json'],
                'package_sha256': package_sha256,
                'assets_sha256': self._assets['sha256'] if self._assets else digest({}),
                **self._baseline,
            }
            # Detect edits while artifact and baseline verification was running.
            self.recheck()
        except EvidenceError:
            raise
        except Exception:
            raise EvidenceError('provenance:capture-failed') from None
        print('e2e:provenance-captured', file=sys.stderr, flush=True)

    @property
    def inputs(self):
        return copy.deepcopy(self._inputs)

    @property
    def source_files(self):
        return copy.deepcopy(self._source['files'])

    def recheck(self):
        require(self._failure is None, self._failure or 'provenance:previous-failure')
        try:
            require(snapshot(self.root, source=True) == self._source, 'provenance:source-changed')
            if self.assets is not None:
                require(snapshot(self.assets) == self._assets, 'provenance:assets-changed')
            require(baseline_inputs(self.lease) == self._baseline, 'provenance:baseline-changed')
        except Exception as error:
            self._failure = str(error) if isinstance(error, EvidenceError) else 'provenance:recheck-failed'
            print('e2e:provenance-rejected', file=sys.stderr, flush=True)
            raise EvidenceError(self._failure) from None

    def contract(self, *, run_id, selector=None):
        self.recheck()
        contract = EvidenceContract(inventory_path=self.root / 'tests/e2e/scenarios.json',
                                    root=self.root, selector=selector, run_id=run_id, inputs=self.inputs)
        self._contracts.append(contract)
        return contract

    def recheck_contract(self, contract):
        """Refuse a foreign plan before worker startup as well as at acceptance."""
        require(any(contract is item for item in self._contracts),
                'provenance:foreign-contract')
        self.recheck()

    def validate(self, contract, records, collector):
        """Require preserved inputs as well as real scenario evidence to pass."""
        self.recheck_contract(contract)
        result = contract.validate(records, collector)
        self.recheck()
        return result
