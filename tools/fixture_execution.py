"""Select immutable native fixtures owned by an existing execution journal.

This is neither a cache nor a retention owner. Call prepare before acquiring a
VM, forward the existing retention descriptors, and pass Selection.record() to
descendants rather than selecting again after checkout edits.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import fixture_bundle as bundle, fixture_manifest, test_retention as retention
from tools import test_storage as storage

SCHEMA = 'onpc-execution-fixture-v1'
_HEX = re.compile(r'[0-9a-f]{64}')


def input_key(source, environment, target):
    """Fixture inputs only: product packages have their own invalidation key."""
    return bundle.digest({'source': source, 'environment': environment,
                          'target': bundle.TARGETS[target],
                          'dependencies': fixture_manifest.DEPENDENCIES})


@dataclass(frozen=True)
class Selection:
    target: str
    key: str
    allocation: str
    device: int
    inode: int
    journal: str
    journal_device: int
    journal_inode: int
    run: str
    build_identity: str

    @property
    def path(self):
        return Path(self.allocation) / 'native-runtime'

    def record(self):
        return {'schema': SCHEMA, **self.__dict__}

    @classmethod
    def from_record(cls, value):
        fields = set(cls.__dataclass_fields__)
        if (type(value) is not dict or set(value) != fields | {'schema'}
                or value['schema'] != SCHEMA):
            raise ValueError('fixture execution: invalid selection fields')
        result = cls(**{name: value[name] for name in fields})
        if (type(result.target) is not str or result.target not in bundle.TARGETS
                or any(type(getattr(result, name)) is not str
                       or _HEX.fullmatch(getattr(result, name)) is None
                       for name in ('key', 'build_identity'))
                or not retention.valid_token(result.run)
                or any(type(getattr(result, name)) is not int or getattr(result, name) <= 0
                       for name in ('device', 'inode', 'journal_device', 'journal_inode'))
                or not retention.journal_path(result.journal)):
            raise ValueError('fixture execution: invalid selection identity')
        if type(result.allocation) is not str:
            raise ValueError('fixture execution: invalid allocation locator')
        path = Path(result.allocation)
        if (not path.is_absolute() or '..' in path.parts
                or not path.name.startswith(_prefix(result.target, result.key))):
            raise ValueError('fixture execution: invalid allocation locator')
        return result


def _prefix(target, key):
    return 'onpc-native-runtime-' + target + '-' + key + '-'


def _owner():
    # The inherited owner descriptor is a capability, not just an environment
    # token or evidence that an unrelated process happens to hold a lock.
    retention.owner_descriptor()
    value = json.loads(os.environ[retention.VARIABLE])
    journal, run = value
    return retention.Store(journal), run


@contextmanager
def _activity():
    store, run = _owner()
    with store.opened() as fd:
        with store.locked(fd, 'fixture-input.lock', blocking=False):
            yield store, fd, run


def _state(store, fd, run):
    current, current_run = _owner()
    if current.path != store.path or current_run != run:
        raise ValueError('fixture execution: retention owner changed')
    with current.opened() as current_fd:
        before, after = os.fstat(fd), os.fstat(current_fd)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError('fixture execution: retention journal replaced')
    with store.locked(fd, 'writer.lock'):
        state = store.read(fd)
        if state is None or state['run'] != run or state['finished']:
            raise ValueError('fixture execution: input has no active owner')
        return state


def _registered(record):
    path = Path(record['path'])
    descriptor = retention.directory(path)
    try:
        info = os.fstat(descriptor)
        retention.allocation_identity(info, 0o700)
        if (info.st_dev, info.st_ino) != (record['device'], record['inode']):
            raise ValueError('fixture execution: registered input replaced')
        if set(os.listdir(descriptor)) != {'native-runtime'}:
            raise ValueError('fixture execution: incomplete or unexpected input')
        retention.check_tree(descriptor, info.st_dev, regular_only=True)
        parent = retention.directory(path.parent)
        try:
            if retention.mount_id(parent) != retention.mount_id(descriptor):
                raise ValueError('fixture execution: mounted input refused')
        finally:
            os.close(parent)
    finally:
        os.close(descriptor)


def _publication_allocation(record):
    descriptor = retention.directory(record['path'])
    try:
        info = os.fstat(descriptor)
        retention.allocation_identity(info, 0o700)
        if (info.st_dev, info.st_ino) != (record['device'], record['inode']):
            raise ValueError('fixture execution: publication allocation replaced')
        parent = retention.directory(Path(record['path']).parent)
        try:
            if retention.mount_id(parent) != retention.mount_id(descriptor):
                raise ValueError('fixture execution: mounted publication allocation refused')
        finally:
            os.close(parent)
    finally:
        os.close(descriptor)


def _read_bundle(allocation, target):
    """Verify through pinned descriptors, then recheck the child's locator."""
    if set(os.listdir(allocation)) != {'native-runtime'}:
        raise ValueError('fixture execution: incomplete or unexpected input')
    descriptor = os.open('native-runtime', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=allocation)
    try:
        before = os.fstat(descriptor)
        if (stat.S_IMODE(before.st_mode) != 0o700
                or before.st_uid != os.fstat(allocation).st_uid
                or retention.mount_id(descriptor) != retention.mount_id(allocation)):
            raise ValueError('fixture execution: unsafe bundle directory')
        manifest = fixture_manifest._verify(descriptor, target, True)
        after = os.stat('native-runtime', dir_fd=allocation, follow_symlinks=False)
        if (not stat.S_ISDIR(after.st_mode) or
                (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
            raise ValueError('fixture execution: bundle replaced during verification')
        if set(os.listdir(allocation)) != {'native-runtime'}:
            raise ValueError('fixture execution: input changed during verification')
        return manifest
    finally:
        os.close(descriptor)


def _manifest(record, target, key):
    _registered(record)
    allocation = retention.directory(record['path'])
    try:
        info = os.fstat(allocation)
        if (info.st_dev, info.st_ino) != (record['device'], record['inode']):
            raise ValueError('fixture execution: input replaced during verification')
        manifest = _read_bundle(allocation, target)
    finally:
        os.close(allocation)
    inputs = manifest['inputs']
    if input_key(inputs['source'], inputs['toolchain']['environment'], target) != key:
        raise ValueError('fixture execution: frozen input key mismatch')
    _registered(record)
    return manifest


def _selection(store, fd, run, record, target, key, manifest):
    info = os.fstat(fd)
    return Selection(target, key, record['path'], record['device'], record['inode'],
                     str(store.path), info.st_dev, info.st_ino, run,
                     manifest['build_identity'])


def prepare(*, target, root=ROOT):
    """Register then build, or reuse verified bytes from this exact active run.

    A failed/interrupted allocation stays recorded. Matching incomplete,
    corrupt, missing or replaced input refuses; this function never replaces it.
    """
    if type(target) is not str or target not in bundle.TARGETS:
        raise ValueError('fixture execution: unsupported target')
    with _activity() as (store, fd, run):
        source, _ = bundle.source_snapshot(root)
        environment = bundle.environment_inputs(root, target)
        key = input_key(source, environment, target)
        prefix = _prefix(target, key)
        state = _state(store, fd, run)
        records = [record for record in state['paths']
                   if Path(record['path']).name.startswith(prefix) and 'retired' not in record]
        if len(records) > 1:
            raise ValueError('fixture execution: ambiguous registered inputs')
        if records:
            record = records[0]
            manifest = _manifest(record, target, key)
        else:
            path = Path(retention.allocate(tempfile.mkdtemp, prefix=prefix,
                                           dir=str(storage.allocation_parent())))
            state = _state(store, fd, run)
            records = [record for record in state['paths'] if record['path'] == str(path)]
            if len(records) != 1:
                raise ValueError('fixture execution: new input was not registered')
            record = records[0]

            def publish_guard():
                current = _state(store, fd, run)
                if record not in current['paths'] or 'retired' in record:
                    raise ValueError('fixture execution: publication registration changed')
                _publication_allocation(record)
                if (bundle.source_snapshot(root)[0] != source
                        or bundle.environment_inputs(root, target) != environment):
                    raise ValueError('fixture execution: selected sources changed before publication')

            bundle.build(path, target=target, root=root, publication='copy',
                         publish_guard=publish_guard)
            manifest = _manifest(record, target, key)
        _state(store, fd, run)
        return _selection(store, fd, run, record, target, key, manifest)


def verify(selection):
    """Read the selected immutable bytes; never consult the changing checkout."""
    selection = Selection.from_record(selection.record() if isinstance(selection, Selection)
                                      else selection)
    # The shared handoff pins the caller's allocation read-only and retains its
    # journal locks. A live descendant may finish reads after its coordinator
    # closes; its inherited owner descriptor still excludes cleanup/rotation.
    with storage.authenticated_input(selection.record(), root=storage.ROOT) as allocation:
        manifest = _read_bundle(allocation, selection.target)
        inputs = manifest['inputs']
        if input_key(inputs['source'], inputs['toolchain']['environment'],
                     selection.target) != selection.key:
            raise ValueError('fixture execution: selected input key changed')
        if manifest['build_identity'] != selection.build_identity:
            raise ValueError('fixture execution: selected build changed')
        return manifest


def validate_source_selection(record, selection):
    """Validate a proof locator; authenticated_input still owns authority.

    The source allocation is deliberately separate from the immutable runtime
    input. Its schema and owner fields are the same authenticated handoff, but
    it is not a Selection and must never be interpreted as a runtime bundle.
    """
    selection = Selection.from_record(selection.record() if isinstance(selection, Selection)
                                      else selection)
    expected = selection.record()
    locators = {'allocation', 'device', 'inode'}
    if (type(record) is not dict or set(record) != set(expected)
            or any(type(record[key]) is not type(expected[key]) or record[key] != expected[key]
                   for key in set(expected) - locators)
            or type(record['allocation']) is not str
            or any(type(record[key]) is not int or record[key] <= 0
                   for key in ('device', 'inode'))):
        raise ValueError('fixture execution: invalid source proof selection')
    path = Path(record['allocation'])
    if (not path.is_absolute() or '..' in path.parts
            or path.parent != Path(selection.allocation).parent
            or re.fullmatch(r'onpc-fixture-source-edit-[A-Za-z0-9_.-]+', path.name) is None):
        raise ValueError('fixture execution: invalid source proof allocation')
    return dict(record)


def prepare_source_edit(*, target, root=ROOT):
    """Select from a private actual source origin, then edit only that origin.

    This finite host qualification proof is registered before its first write.
    Runtime bytes keep their ordinary separate input allocation and schema.
    """
    if target != 'ubuntu' or os.geteuid() == 0:
        raise ValueError('fixture execution: source edit qualification requires Ubuntu and an unprivileged owner')
    allocation = None
    try:
        with _activity() as (store, fd, run):
            path = Path(retention.allocate(tempfile.mkdtemp, prefix='onpc-fixture-source-edit-',
                                           dir=str(storage.allocation_parent())))
            records = [item for item in _state(store, fd, run)['paths']
                       if item['path'] == str(path)]
            if len(records) != 1:
                raise ValueError('fixture execution: source proof was not registered')
            record = records[0]
            _publication_allocation(record)
            allocation = retention.directory(path)
            info = os.fstat(allocation)
            if (info.st_dev, info.st_ino) != (record['device'], record['inode']):
                raise ValueError('fixture execution: source proof allocation replaced')
            os.mkdir('source', mode=0o700, dir_fd=allocation)
            # All writes and prepare's source reads use the pinned allocation,
            # including if its public locator is replaced during a failed run.
            source = Path('/proc/self/fd/' + str(allocation)) / 'source'
            original, environment = bundle.freeze(Path(root), source, target)
            _publication_allocation(record)
        selected = prepare(target=target, root=source)
        if verify(selected)['inputs']['source'] != original:
            raise ValueError('fixture execution: source proof does not match selected build')
        _publication_allocation(record)
        changed = 'tests/fixtures/onpc_test_application.c'
        origin = source / changed
        origin.write_bytes(origin.read_bytes() + b'\n/* qualification edit after fixture selection */\n')
        edited, _ = bundle.source_snapshot(source)
        if (set(edited) != set(original) or edited[changed] == original[changed]
                or any(edited[name] != original[name] for name in original if name != changed)):
            raise ValueError('fixture execution: source proof changed unexpected inputs')
        proof = {'schema': 'onpc-fixture-source-edit-v1', 'selection': selected.record(),
                 'before': original, 'after': edited, 'environment': environment,
                 'edited': changed}
        output = os.open('source-edit.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=allocation)
        with os.fdopen(output, 'wb') as stream:
            stream.write(bundle.encoded(proof) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(allocation)
        _publication_allocation(record)
        handoff = selected.record() | {'allocation': str(path),
                                      'device': info.st_dev, 'inode': info.st_ino}
        return selected, validate_source_selection(handoff, selected)
    finally:
        if allocation is not None:
            os.close(allocation)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--target', choices=tuple(bundle.TARGETS), required=True)
    parser.add_argument('--qualify-source-edit', action='store_true')
    args = parser.parse_args()
    try:
        source = None
        if args.qualify_source_edit:
            selection, source = prepare_source_edit(target=args.target)
        else:
            selection = prepare(target=args.target)
        print('fixture-execution: selection=' + bundle.encoded(selection.record()).decode())
        if source is not None:
            print('fixture-execution: source-edit=' + bundle.encoded(source).decode())
        print('fixture-execution: output=' + str(selection.path))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print((error.stderr or '')[-16000:], file=sys.stderr)
        print('fixture-execution: failed=' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
