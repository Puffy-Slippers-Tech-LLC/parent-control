"""Freeze the local import closure of guest entry points without importing it.

Entry points and non-Python resources are declared by their consumers. Ordinary
and function-local imports discover new helpers automatically. External modules
come from the prepared OS or installed product, never from the host checkout.
"""

import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


SEARCH = ('tests/integration', 'tests/integration/guest', 'tests/system')
EXTERNAL = frozenset(sys.stdlib_module_names) | {'pytest', 'gi', 'oh_no_parent_control'}


class InputError(ValueError):
    pass


def read(root, relative):
    path = root / relative
    if path.resolve() != path or not path.is_file():
        raise InputError('guest-inputs:missing-or-unsafe-source:' + relative)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise InputError('guest-inputs:unsafe-source:' + relative)
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                info.st_uid, info.st_gid, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise InputError('guest-inputs:source-replaced:' + relative)
        data = stream.read()
        stable = identity(os.fstat(stream.fileno())) == identity(before)
    if not stable or path.resolve() != path or identity(path.stat()) != identity(before):
        raise InputError('guest-inputs:source-changed-during-read:' + relative)
    return data


class Bundle:
    """One immutable set of bytes; later checkout edits affect the next bundle."""

    def __init__(self, root, entries, *, frozen=None):
        self.root = Path(root).resolve()
        self.frozen = frozen
        self.files = {}
        self.sources = {}
        self.modules = {}
        self.dependencies = {}
        self.pending = []
        for source, target in entries:
            self.add(source, target)
        while self.pending:
            source, target = self.pending.pop()
            tree = ast.parse(self.files[target], filename=source)
            package = target.removesuffix('.py').split('/')[:-1]
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.module(alias.name, source)
                elif isinstance(node, ast.ImportFrom):
                    name = node.module or ''
                    if node.level:
                        if node.level > len(package):
                            raise InputError('guest-inputs:relative-import:' + source)
                        name = '.'.join([*package[:len(package) - node.level + 1],
                                         *([name] if name else [])])
                    self.module(name, source)
                    for alias in node.names:
                        if alias.name != '*':
                            self.module(name + '.' + alias.name, source, optional=True)

    def add(self, source, target):
        for name in (source, target):
            if not name or Path(name).is_absolute() or '..' in Path(name).parts:
                raise InputError('guest-inputs:unsafe-path')
        if target in self.sources:
            if self.sources[target] != source:
                raise InputError('selection:duplicate-input-target')
            return
        self.sources[target] = source
        self.dependencies[source] = set()
        self.files[target] = read(self.root, source) if self.frozen is None else self.frozen[source]
        if target.endswith('.py'):
            module = target.removesuffix('.py').replace('/', '.').removesuffix('.__init__')
            self.modules[module] = target
            # The legacy guest/redact entry point has its own sys.path root.
            if target.startswith('guest/'):
                self.modules[module.removeprefix('guest.')] = target
            self.pending.append((source, target))

    def module(self, name, caller, *, optional=False):
        if name.split('.')[0] in EXTERNAL:
            return
        # Commands intentionally tolerates the absence of the host spectator.
        if name == 'watch_activity' and caller == 'tests/integration/owned_commands.py':
            return
        if name in self.modules:
            self.dependencies[caller].add(self.modules[name])
            return
        relative = name.replace('.', '/')
        candidates = [(base + '/' + suffix, suffix)
                      for base in SEARCH
                      for suffix in (relative + '.py', relative + '/__init__.py')
                      if ((base + '/' + suffix in self.frozen) if self.frozen is not None
                          else (self.root / base / suffix).exists())]
        if not candidates:
            if optional:
                return  # `from module import function`, not a submodule.
            raise InputError('guest-inputs:missing-module:' + name)
        if len(candidates) != 1:
            raise InputError('guest-inputs:ambiguous-module:' + name)
        source, target = candidates[0]
        if source.startswith('tests/integration/guest/'):
            target = 'guest/' + target
        # Include package initializers for dotted imports too.
        for length in range(1, len(name.split('.'))):
            self.module('.'.join(name.split('.')[:length]), caller)
        self.add(source, target)
        self.dependencies[caller].add(target)

    @classmethod
    def from_staged(cls, root, directory):
        """Reuse a system invocation's already verified, frozen selection."""
        entries = json.loads((directory / 'selected-inputs.json').read_bytes())['files']
        frozen = {}
        for target, item in entries.items():
            for name in (target, item['source']):
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise InputError('guest-inputs:unsafe-path')
            data = read(directory, target)
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise InputError('guest-inputs:staged-digest')
            frozen[item['source']] = data
        return cls(root, [(item['source'], target) for target, item in entries.items()],
                   frozen=frozen)

    def digest(self, entry):
        """Identify only an entry point's frozen transitive dependency closure."""
        pending, selected = [entry], set()
        while pending:
            target = pending.pop()
            if target in selected:
                continue
            selected.add(target)
            pending.extend(self.dependencies[self.sources[target]])
        value = hashlib.sha256()
        for target in sorted(selected):
            value.update(target.encode() + b'\0')
            value.update(hashlib.sha256(self.files[target]).digest())
        return value.hexdigest()

    def stage(self, destination):
        destination = Path(destination)
        result = {}
        for target, data in sorted(self.files.items()):
            path = destination / target
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink() or path.resolve() != path:
                raise InputError('guest-inputs:unsafe-destination')
            path.write_bytes(data)
            result[target] = {'source': self.sources[target],
                              'sha256': hashlib.sha256(data).hexdigest()}
        return result
