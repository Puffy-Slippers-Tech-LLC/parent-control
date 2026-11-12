"""Disposable source inputs for one VM test controller, never a checkout cache.

Imports keep their original filenames so VM configuration, journals and storage
remain anchored to the invoking checkout. Uncaptured inputs deliberately remain
live; this is a convenience boundary, not a claim of hermetic execution.
"""

from contextlib import contextmanager
import hashlib
import importlib.abc
from importlib.machinery import PathFinder
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
from types import ModuleType


# Folder rules include new helpers automatically. Runtime fixture payloads,
# bytecode, generated output and private checkout metadata are not source inputs.
FOLDERS = ('tests/integration', 'tests/e2e', 'tests/system', 'tests/support', 'tests/fixtures',
           'tools', 'common', 'config', 'data')
PATTERNS = ('*.py', '*.json', '*.txt', '*.toml', '*.pm', '*.png')
_active = None


def selected_paths(root):
    paths = {path for folder in FOLDERS for pattern in PATTERNS
             for path in (root / folder).rglob(pattern)
             if '__pycache__' not in path.parts}
    paths.update(path for pattern in ('*.json', '*.txt')
                 for path in (root / 'tests').glob(pattern))
    return sorted(paths)


def transfer_paths(root):
    """Select a finite VM source closure using the existing source inventories.

    Package inputs come from Make's manifest. VM/tool directories reuse this
    module's directory rules. Include ambiguous file types within those
    directories instead of assuming only today's filename extensions matter.
    Git filters generated/ignored/private output before directory selection;
    new nonignored source is included so uncommitted implementation works too.
    """
    from tools import package_inputs, regression_inputs
    root = Path(root)
    visible = set(regression_inputs.paths(root))
    # Start from Git rather than walking ignored/generated fixture trees.
    # Include the fixed helper safety suite and tests' top-level import/data
    # files: a detached source copy cannot fall back to a live parent checkout.
    selected = {path for path in visible if path.parent == Path('tests')
                or any(path.is_relative_to(folder)
                       for folder in (*FOLDERS, 'tests/unit', 'vscode/onpc-watch'))}
    selected.update(path for path in visible if path.parent == Path('.')
                    and any(path.match(pattern) for pattern in PATTERNS))
    selected.update(package_inputs.paths(root))
    # Public helpers validate these repository markers. Their implementation
    # and setup support are in the already selected tools/config directories.
    selected.update(Path(name) for name in ('setup.sh', 'Makefile', '.gitignore', 'child/preview',
                    '.codex/config.toml', '.codex/rules/tests.rules')
                    if Path(name) in visible)
    return sorted(root / path for path in selected)


@contextmanager
def input_file(path):
    """Pin one regular input and check its identity across a streamed read."""
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)
    if path.resolve() != path:
        raise ValueError('vm source snapshot: linked input')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError('vm source snapshot: nonregular input')
        yield source, before
        after = os.fstat(source.fileno())
    if (identity(before) != identity(after)
            or identity(path.stat(follow_symlinks=False)) != identity(after)):
        raise ValueError('vm source snapshot: input changed during capture')


def input_bytes(path):
    """Read a small source/metadata input under the same identity guard."""
    with input_file(path) as (source, info):
        content = source.read()
        if len(content) != info.st_size:
            raise ValueError('vm source snapshot: input changed during capture')
        return content, stat.S_IMODE(info.st_mode)


def transfer_archive(root, destination, *, inventory=transfer_paths):
    """Write working-tree bytes to a caller-owned archive and return its manifest.

    The caller owns source admission and scratch lifetime. Recheck selection
    and contents before allowing the archive to leave the controller. The
    manifest pins deletions/permissions as well as changed source bytes.
    """
    root = Path(root).resolve(strict=True)
    paths = inventory(root)
    manifest = {}
    with tarfile.open(fileobj=destination, mode='w|gz') as archive:
        for path in paths:
            with input_file(path) as (source, info):
                relative = path.relative_to(root).as_posix()
                entry = tarfile.TarInfo(relative)
                entry.size, entry.mode = info.st_size, stat.S_IMODE(info.st_mode)
                entry.uid = entry.gid = entry.mtime = 0
                digest = hashlib.sha256()
                class Payload:
                    def read(self, size):
                        block = source.read(size)
                        digest.update(block)
                        return block
                archive.addfile(entry, Payload())
                manifest[relative] = dict(size=entry.size, mode=entry.mode, sha256=digest.hexdigest())
    if inventory(root) != paths:
        raise ValueError('vm source snapshot: transfer inventory changed during capture')
    for path in paths:
        with input_file(path) as (source, info):
            entry = manifest[path.relative_to(root).as_posix()]
            if (info.st_size != entry['size'] or stat.S_IMODE(info.st_mode) != entry['mode']
                    or hashlib.file_digest(source, 'sha256').hexdigest() != entry['sha256']):
                raise ValueError('vm source snapshot: transfer inputs changed during capture')
    return manifest


def tree_paths(root):
    """Inventory one explicitly selected verified artifact bundle."""
    return sorted(path for path in root.rglob('*') if path.is_symlink() or not path.is_dir())


def transfer_git(root, destination):
    """Pack finite source snapshots, without copying repository history/caches.

    Current HEAD supplies Git identity; the artifact builder declares the only
    historical snapshots its released/activation profiles can consume. Missing
    optional profiles stay missing, just as they would on the controller.
    """
    import subprocess
    from tools import build_test_artifacts as artifacts, package_inputs
    from tools.host_dispatch import git
    root = Path(root)
    head = git(root, 'rev-parse', '--verify', 'HEAD^{commit}')
    commits = {head}
    references = {}
    objects = set()
    for release in artifacts.PREVIOUS_RELEASES.values():
        result = subprocess.run(['git', 'rev-parse', '--verify', 'refs/tags/' + release['name']],
                                cwd=root, capture_output=True, text=True, check=False)
        if not result.returncode and result.stdout.strip() == release['tag']:
            references[release['name']] = release['tag']
            objects.add(release['tag'])
            commits.add(release['commit'])
    for revision in (*artifacts.NO_ACTION_REVISIONS.values(), artifacts.PROCESS_BASELINE,
                     artifacts.SESSION_BASELINE, artifacts.REBOOT_BASELINE):
        result = subprocess.run(['git', 'cat-file', '-e', revision + '^{commit}'],
                                cwd=root, capture_output=True, check=False)
        if result.returncode == 0:
            commits.add(revision)
    # --no-walk includes each selected commit's tree/blob closure, never its
    # ancestors. Shared objects are packed once; no host checkout is updated.
    objects.update(git(root, 'rev-list', '--objects', '--no-walk', '--no-object-names',
                       *sorted(commits)).splitlines())
    subprocess.run(['git', 'pack-objects', '--stdout'], cwd=root, check=True,
                   input=('\n'.join(sorted(objects)) + '\n').encode(), stdout=destination)
    selected = package_inputs.paths(root)
    from tools.vm_selection import vm_config
    origin = vm_config.remote_origin() if root == vm_config.ROOT else None
    metadata = ([origin['package_revision'], str(origin['package_epoch'])]
                if origin is not None and 'package_revision' in origin else
                git(root, 'log', '-1', '--format=%H %ct', 'HEAD', '--',
                    *(path.as_posix() for path in selected)).split())
    if len(metadata) != 2 or not metadata[1].isdecimal():
        raise ValueError('vm source snapshot: invalid package revision')
    return dict(head=head, commits=sorted(commits), tags=references,
                package_revision=metadata[0], package_epoch=int(metadata[1]))


def receive_transfer(source, destination, manifest):
    """Unpack only manifest-pinned regular files into a new private directory.

    This function is self-contained for the SSH bootstrap. No extraction may
    name the VM host's checkout or traverse a link. The owner allocates/removes
    the parent through the shared scratch lifecycle, including after a crash.
    """
    import hashlib
    import os
    from pathlib import Path
    import stat
    import tarfile

    destination = Path(destination)
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError('vm source transfer: missing manifest')
    for name, entry in manifest.items():
        if not isinstance(name, str):
            raise ValueError('vm source transfer: invalid manifest path')
        path = Path(name)
        if (not name or not path.parts or path.is_absolute()
                or path.as_posix() != name or '..' in path.parts
                or path.parts[0] in ('.git', 'output', 'artifacts', '.aws', '.venv')
                or any(ord(char) < 32 for char in name)
                or not isinstance(entry, dict) or set(entry) != {'size', 'mode', 'sha256'}
                or type(entry['size']) is not int or entry['size'] < 0
                or type(entry['mode']) is not int or entry['mode'] & ~0o777
                or not isinstance(entry['sha256'], str) or len(entry['sha256']) != 64
                or any(char not in '0123456789abcdef' for char in entry['sha256'])):
            raise ValueError('vm source transfer: invalid manifest')
    if destination.parent.resolve(strict=True) != destination.parent:
        raise ValueError('vm source transfer: linked destination parent')
    # Exclusively create the root; never extract into any existing directory.
    destination.mkdir(mode=0o700)
    seen = set()
    with tarfile.open(fileobj=source, mode='r|gz') as archive:
        for item in archive:
            entry = manifest.get(item.name)
            if (entry is None or item.name in seen or not item.isfile()
                    or item.size != entry['size'] or item.mode != entry['mode']):
                raise ValueError('vm source transfer: archive differs from manifest')
            target = destination / item.name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if target.parent.resolve(strict=True) != target.parent:
                raise ValueError('vm source transfer: linked archive parent')
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600)
            digest, size = hashlib.sha256(), 0
            with os.fdopen(descriptor, 'wb') as output, archive.extractfile(item) as payload:
                for block in iter(lambda: payload.read(1024 * 1024), b''):
                    size += len(block)
                    digest.update(block)
                    output.write(block)
                os.fchmod(output.fileno(), entry['mode'])
                if not stat.S_ISREG(os.fstat(output.fileno()).st_mode):
                    raise ValueError('vm source transfer: replaced destination file')
            if size != entry['size'] or digest.hexdigest() != entry['sha256']:
                raise ValueError('vm source transfer: content digest differs')
            seen.add(item.name)
    if seen != set(manifest):
        raise ValueError('vm source transfer: missing archive files')


def source_path(path):
    """Select a captured input, falling back to the checkout outside its scope."""
    path = Path(path)
    if _active is not None:
        relative = path.relative_to(_active.root) if path.is_relative_to(_active.root) else None
        if relative is not None and (relative in _active.files
                                     or (_active.directory / relative).is_dir()):
            return _active.directory / relative
    return path


def read_bytes(path):
    """Read captured bytes when available; ordinary host tests read live files."""
    return source_path(path).read_bytes()


class _Loader(importlib.abc.Loader):
    def __init__(self, path):
        self.path = path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Bypass stale checkout .pyc files and retain the original diagnostic
        # filenames and __file__-derived operational paths.
        exec(compile(read_bytes(self.path), str(self.path), 'exec'), module.__dict__)


class Snapshot(importlib.abc.MetaPathFinder):
    def __init__(self, root, directory):
        self.root, self.directory = Path(root), Path(directory)
        self.files = set()
        identity = hashlib.sha256()
        for path in selected_paths(self.root):
            content, _ = input_bytes(path)
            relative = path.relative_to(self.root)
            target = self.directory / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(content)
            self.files.add(relative)
            identity.update(str(relative).encode() + b'\0' + content)
        self.sha256 = identity.hexdigest()

    def find_spec(self, fullname, path=None, target=None):
        leaf = fullname.rpartition('.')[2]
        for parent in sys.path if path is None else path:
            base = Path(parent or os.getcwd())
            if not base.is_absolute():
                base = Path.cwd() / base
            if not base.is_relative_to(self.root):
                continue
            for candidate, package in ((base / leaf / '__init__.py', True),
                                       (base / (leaf + '.py'), False)):
                if candidate.relative_to(self.root) in self.files:
                    return importlib.util.spec_from_file_location(
                        fullname, candidate, loader=_Loader(candidate),
                        submodule_search_locations=[str(candidate.parent)] if package else None)
        return None


@contextmanager
def capture(root):
    """One scratch-owned copy per invocation, removed after controller cleanup.

    SIGKILL/host failure leaves it under the existing identity-recorded scratch
    owner; normal scratch recovery reclaims it once descendants release leases.
    No snapshots are registered as retained reports or reused across invocations.
    """
    global _active
    from tools.test_storage import scratch_directory

    if _active is not None:
        raise ValueError('vm source snapshot: controller already has a capture')
    with tempfile.TemporaryDirectory(prefix='vm-sources-', dir=scratch_directory()) as directory:
        snapshot = Snapshot(root, directory)
        _active = snapshot
        sys.meta_path.insert(sys.meta_path.index(PathFinder), snapshot)
        try:
            print(f'vm-source-snapshot: captured {len(snapshot.files)} files; '
                  f'sha256={snapshot.sha256}', flush=True)
            yield snapshot
        finally:
            sys.meta_path.remove(snapshot)
            _active = None


def main():
    root = Path(__file__).resolve().parents[1]
    target = Path(sys.argv[1])
    if (not target.is_absolute() or target.resolve() != target or target.suffix != '.py'
            or target.parent not in (root / 'tests/integration', root / 'tests/e2e')):
        raise ValueError('vm source snapshot: invalid controller')
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(target.parent))
    sys.argv = sys.argv[1:]
    with capture(root):
        module = ModuleType('__main__')
        module.__dict__.update(__file__=str(target), __package__='',
                               __spec__=None, __cached__=None)
        previous = sys.modules['__main__']
        sys.modules['__main__'] = module
        try:
            exec(compile(read_bytes(target), str(target), 'exec'), module.__dict__)
        finally:
            sys.modules['__main__'] = previous


if __name__ == '__main__':
    # Readers imported by the controller must see this same capture instance.
    sys.modules['tools.vm_source_snapshot'] = sys.modules[__name__]
    main()
