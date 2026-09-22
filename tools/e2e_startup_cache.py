"""Content-qualified startup work; never cache live VM or ownership decisions.

Only small, private receipts persist. Artifact payloads stay in normal retention:
each hit copies into the new run's owned allocation and verifies the copy. A
missing/rotated payload is a miss. Explicit builds and regression suites stay fresh.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import site
import stat
import subprocess
import sys
import sysconfig

import test_retention

SCHEMA = 2


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def file_digest(path):
    """Read bytes on every invocation, detecting replacement or mid-read edits."""
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('startup cache: nonregular input')
    value = hashlib.sha256()
    parent = test_retention.directory(path.parent)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError('startup cache: nonregular input')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
        after = os.fstat(stream.fileno())
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mode,
                             info.st_mtime_ns, info.st_ctime_ns)
    if not identity(before) == identity(opened) == identity(after) == identity(path.stat()):
        raise ValueError('startup cache: input changed during capture')
    return [stat.S_IMODE(before.st_mode), value.hexdigest()]


def files_digest(root, paths):
    values = {}
    for relative in sorted(paths):
        path = root / relative
        if path.resolve() != root.resolve() / relative:
            raise ValueError('startup cache: linked input')
        values[str(relative)] = file_digest(path)
    return digest(values)


def tree_digest(root):
    def inventory():
        paths = sorted(root.rglob('*'))
        if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):
            raise ValueError('startup cache: unsafe payload')
        return paths
    before = inventory()
    result = digest({str(p.relative_to(root)): (['directory', stat.S_IMODE(p.stat().st_mode)]
                     if p.is_dir() else file_digest(p)) for p in before})
    if before != inventory():
        raise ValueError('startup cache: payload inventory changed')
    return result


def bytecode_paths(root, sources):
    """Include ignored bytecode Python can load beside the selected sources."""
    directories = {parent for p in sources if p.suffix == '.py' for parent in p.parents}
    return {p.relative_to(root) for relative in directories
            for pattern in ('*.pyc', '__pycache__/*.pyc')
            for p in (root / relative).glob(pattern)}


def source_identity(root):
    def paths():
        result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others',
                                 '--exclude-standard'], cwd=root, check=True,
                                stdout=subprocess.PIPE)
        listed = {Path(os.fsdecode(p)) for p in result.stdout.split(b'\0') if p}
        if any(p.is_absolute() or '..' in p.parts for p in listed):
            raise ValueError('startup cache: invalid source inventory')
        # -B suppresses writes, not reads. Git excludes __pycache__ and legacy
        # .pyc files, but Python/pytest may load those bytes instead of source.
        # Include sibling caches even for deleted indexed modules, and parent
        # package directories where a sourceless module can still be imported.
        return sorted({p for p in listed if os.path.lexists(root / p)} | bytecode_paths(root, listed))
    before = paths()
    result = files_digest(root, before)
    if not before or paths() != before:
        raise ValueError('startup cache: source inventory changed')
    return result


def runtime_identity(root):
    """Include managed dependencies and actual importable Python/native bytes.

    No timestamp-only dependency shortcuts. Include existing bytecode too:
    Python's -B disables writes, but does not disable loading those files.
    """
    roots = {Path(p) for p in sys.path if p and Path(p).is_absolute()
             and not Path(p).resolve().is_relative_to(root.resolve())}
    roots.update(Path(sysconfig.get_path(p)) for p in ('stdlib', 'platstdlib', 'purelib', 'platlib'))
    if site.ENABLE_USER_SITE:
        roots.add(Path(site.getusersitepackages()))
    values = {}
    for directory in sorted(roots):
        if directory.is_file():
            values[str(directory)] = file_digest(directory.resolve())
        elif directory.is_dir():
            for path in sorted(directory.rglob('*')):
                if path.is_file() and (
                        path.suffix in ('.py', '.pyc', '.so', '.pth', '.zip')
                        or path.name in ('METADATA', 'entry_points.txt')):
                    values[str(path)] = [str(path.resolve()), file_digest(path.resolve())]
    for path in (Path('/var/lib/dpkg/status'), Path('/proc/sys/kernel/random/boot_id'),
                 Path('/etc/os-release'), Path(sys.executable).resolve()):
        values[str(path)] = file_digest(path.resolve())
    # The database's pending fragments also invalidate reuse during an update.
    values['dpkg-updates'] = tree_digest(Path('/var/lib/dpkg/updates'))
    values['installed-helpers'] = {
        str(path): file_digest(path.resolve())
        for path in sorted(Path('/usr/local/libexec').glob('onpc-*')) if path.is_file()}
    for name in ('make', 'cc', 'dpkg-buildpackage', 'dpkg-deb', 'flatpak', 'git'):
        executable = shutil.which(name)
        values[name] = [executable, file_digest(Path(executable).resolve())] if executable else None
    from test_launcher import environment
    env = environment(root)
    env.pop('ONPC_TEST_ACTIVITY_FD', None)
    env.pop('ONPC_TEST_RETENTION', None)
    return digest([sys.version, sys.path, os.uname(), os.getuid(), os.getgroups(), env, values])


def cache_path(root):
    checkout = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    return Path('/tmp') / f'onpc-startup-cache-{os.getuid()}-{checkout}'


@contextmanager
def receipt(root, name):
    store = test_retention.Store(cache_path(root))
    test_retention.ensure_directory(store.path)
    with store.opened() as fd, store.locked(fd, 'cache.lock'):
        try:
            source = os.open(name + '.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=fd)
        except FileNotFoundError:
            record = None
        else:
            with os.fdopen(source) as stream:
                test_retention.private(os.fstat(stream.fileno()), regular=True)
                try:
                    contents = stream.read(32769)
                    record = json.loads(contents) if len(contents) <= 32768 else None
                except ValueError:
                    record = None
                if not isinstance(record, dict) or record.get('schema') != SCHEMA:
                    record = None
        def save(value):
            store.save(fd, {'schema': SCHEMA, **value}, name=name + '.json')
        yield record, save


def qualified_cleanup(root, run):
    """Publish only a complete successful pass with unchanged captured inputs."""
    def inputs():
        return {'source': source_identity(root), 'runtime': runtime_identity(root)}
    with receipt(root, 'cleanup') as (record, save):
        try:
            captured = inputs()
        except (OSError, ValueError, subprocess.SubprocessError):
            # An optimization must not reject an otherwise valid fresh gate
            # merely because the developer is editing its fingerprint inputs.
            save({'passed': False})
            print('run-tests: cleanup identity unavailable; running fresh qualification', flush=True)
            return run()
        before = digest([SCHEMA, captured])
        if record and record.get('identity') == before and record.get('passed') is True:
            print('run-tests: cleanup qualification reused; content identity=' + before, flush=True)
            import test_activity
            test_activity.record_cleanup(before)
            return 0
        save({'passed': False})
        status = run()
        if status == 0:
            try:
                after = inputs()
            except (OSError, ValueError, subprocess.SubprocessError):
                print('run-tests: cleanup passed but qualification not cached; '
                      'input capture unavailable', flush=True)
                return status
            if after == captured:
                save({'identity': before, 'passed': True})
                print('run-tests: cleanup qualification recorded; content identity=' + before, flush=True)
            else:
                changed = ','.join(key for key in captured if after[key] != captured[key])
                print('run-tests: cleanup passed but qualification not cached; changed=' + changed,
                      flush=True)
        return status


def artifact_identity(builder):
    root = builder.REPOSITORY
    paths = builder.package_inputs.paths(root)
    metadata = builder._metadata(paths, builder.package_inputs.digest(root, paths))
    fixtures = tree_digest(root / 'tests/fixtures')
    helper_paths = {Path('tools') / p for p in (
        'build_test_artifacts.py', 'package_inputs.py', 'e2e_startup_cache.py', 'test_retention.py')}
    helpers = files_digest(root, helper_paths | bytecode_paths(root, helper_paths))
    return digest([SCHEMA, metadata, fixtures, helpers, runtime_identity(root)]), metadata


def prepare_artifacts(builder, output):
    """Build on a miss; never publish partial output or reuse unchecked metadata."""
    if test_retention.token() is None:
        raise ValueError('startup cache: preparation requires a retained launcher run')
    output = builder._require_empty_output(output)
    # Register before writing, including failures and interruptions. The cache
    # owns no payload generations outside the established retention journal.
    test_retention.retain(output)
    with receipt(builder.REPOSITORY, 'artifacts') as (record, save):
        before, metadata = artifact_identity(builder)
        hit = False
        if record and record.get('identity') == before:
            try:
                source = Path(record['path'])
                if (source.parent != Path('/tmp') or not source.name.startswith('onpc-test-')
                        or source.resolve() != source or source == output):
                    raise ValueError('startup cache: invalid retained path')
                test_retention.private(source.stat())
                if tree_digest(source) != record['payload']:
                    raise ValueError('startup cache: payload changed')
                manifest = builder.verify(source)
                if any(manifest.get(k) != v for k, v in metadata.items()):
                    raise ValueError('startup cache: metadata changed')
                hit = True
            except (OSError, ValueError, KeyError, TypeError, builder.ArtifactError):
                pass
        save({'identity': None})
        if hit:
            shutil.copytree(source, output, dirs_exist_ok=True)
            if tree_digest(output) != record['payload']:
                raise ValueError('startup cache: payload changed during copy')
            print('run-tests: verified artifact bundle reused; content identity=' + before, flush=True)
        else:
            builder.build(output)
        manifest = builder.verify(output)
        after, _ = artifact_identity(builder)
        if after != before or any(manifest.get(k) != v for k, v in metadata.items()):
            raise ValueError('startup cache: build inputs changed; retry preparation')
        save({'identity': before, 'path': str(output), 'payload': tree_digest(output)})
    return output / builder.MANIFEST_NAME
