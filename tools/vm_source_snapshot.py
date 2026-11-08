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
import tempfile
from types import ModuleType


# Folder rules include new helpers automatically. Runtime fixture payloads,
# bytecode, generated output and private checkout metadata are not source inputs.
FOLDERS = ('tests/integration', 'tests/e2e', 'tests/support', 'tests/fixtures',
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
            if path.resolve() != path:
                raise ValueError('vm source snapshot: linked input')
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('vm source snapshot: nonregular input')
                content = source.read()
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
