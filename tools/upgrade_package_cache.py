"""Share verified upgrade inputs without sharing a VM's execution allocation."""

import json
import os
from pathlib import Path
import shutil
import tempfile

from e2e_startup_cache import MAX_RECEIPT_BYTES, SCHEMA, cache_path, digest, file_digest, receipt, tree_digest
import test_retention
from test_launcher import SOURCE_CAPTURE
from test_storage import cache_staging_directory, snapshot_credential_root
from vm_selection import vm_config


def _scope(repository, target):
    root = snapshot_credential_root() or repository
    return root, digest([vm_config.current_branch(), target.name, target.architecture])


def _reuse_current(builder, output, source, cached):
    if not isinstance(cached, dict):
        return []
    allocations = cached.get('allocations', [cached.get('allocation')])
    if not isinstance(allocations, list):
        return []
    for index, allocation in enumerate(allocations):
        with tempfile.TemporaryDirectory(prefix='.current-', dir=output.parent) as temporary:
            staged = Path(temporary) / 'current'
            try:
                if Path(allocation).name != allocation or not allocation.startswith('onpc-'):
                    raise ValueError('invalid retained upgrade allocation')
                path = output.parent.with_name(allocation) / output.name
                if path == output or path.resolve(strict=True) != path:
                    raise ValueError('invalid retained upgrade input path')
                test_retention.private(path.parent.stat())
                shutil.copytree(path, staged, symlinks=True)
                if tree_digest(staged) != cached['payload'] or builder.verify(staged)['source'] != source:
                    raise ValueError('retained upgrade input changed')
            except (OSError, KeyError, TypeError, ValueError, builder.ArtifactError):
                continue  # Ordinary retention can rotate any one worker's copy.
            staged.rename(output)
            return [name for name in allocations[index:] if isinstance(name, str)]
    return []


def prepare_current(builder, output, target, metadata, build):
    """Build the current input once for compatible workers in a queue pass."""
    capture = os.environ.get(SOURCE_CAPTURE)
    if not test_retention.valid_token(capture) or test_retention.token() is None:
        build()
        return
    root, scope = _scope(builder.REPOSITORY, target)
    name = 'upgrade-current-' + scope
    key = digest([capture, metadata])
    with receipt(root, name, lock=name + '.lock') as (record, save):
        outputs = (record or {}).get('outputs')
        outputs = outputs if isinstance(outputs, dict) else {}
        cached = outputs.pop(key, None)
        allocations = _reuse_current(builder, output, metadata['source'], cached)
        if allocations:
            payload = cached['payload']
            print('test-artifacts: reused current upgrade input for this VM queue', flush=True)
        else:
            build()
            payload = tree_digest(output)
        allocations = list(dict.fromkeys([output.parent.name, *allocations]))
        outputs[key] = {'allocations': allocations, 'payload': payload}
        # Fit the shared receipt format, keeping the newest capture and copies.
        while len(json.dumps({'schema': SCHEMA, 'outputs': outputs})) > MAX_RECEIPT_BYTES:
            if len(outputs) > 1:
                del outputs[next(iter(outputs))]
            else:
                allocations.pop()
        save({'outputs': outputs})


def _read_release(entry, expected, target):
    with test_retention.Store(entry).opened() as fd:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open('receipt.json', flags, dir_fd=fd)) as stream:
            test_retention.private(os.fstat(stream.fileno()), regular=True)
            record = json.loads(stream.read(32769))
        metadata = record['metadata']
        inputs = metadata['build_inputs']
        package_name = record['package']
        if (record.get('schema') != 1 or metadata['source'] != expected
                or not isinstance(metadata['tools'], dict)
                or inputs['build_target'] != target.name or inputs['target_architecture'] != target.architecture
                or type(inputs['source_date_epoch']) is not int or inputs['source_date_epoch'] < 0
                or not isinstance(inputs['deb_build_options'], str)
                or not isinstance(package_name, str) or Path(package_name).name != package_name
                or not package_name.endswith('.' + target.package_format)
                or set(os.listdir(fd)) != {'receipt.json', package_name}):
            raise ValueError('invalid release package receipt')
        test_retention.private(os.stat(package_name, dir_fd=fd, follow_symlinks=False), regular=True)
    package = entry / package_name
    if file_digest(package)[1] != record['sha256']:
        raise ValueError('release package digest changed')
    return package, metadata, record['sha256']


def _publish_release(scratch, entry, parent, output, manifest, source):
    asset = manifest['artifacts']['package']
    package = output / asset['path']
    metadata = {key: manifest[key] for key in ('build_inputs', 'tools')}
    metadata['source'] = source
    stage = scratch / 'release'
    stage.mkdir(mode=0o700)
    with (stage / package.name).open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        with package.open('rb') as original:
            shutil.copyfileobj(original, stream)
        stream.flush()
        os.fsync(stream.fileno())
    if file_digest(stage / package.name)[1] != asset['sha256']:
        raise ValueError('upgrade cache: release input changed during publication')
    store = test_retention.Store(stage)
    with store.opened() as fd:
        store.save(fd, {'schema': 1, 'metadata': metadata, 'package': package.name,
                        'sha256': asset['sha256']}, name='receipt.json')
    os.rename(stage, entry.name, dst_dir_fd=parent)
    os.fsync(parent)


def prepare_release(builder, output, target, source, build):
    """Preserve the binary and original build metadata for an immutable Git release."""
    root, scope = _scope(builder.REPOSITORY, target)
    expected = {key: value for key, value in source.items() if key != 'release_name'}
    name = 'upgrade-release-' + digest([scope, expected])
    store = test_retention.Store(cache_path(root))
    entry = store.path / name
    with store.opened() as parent, store.locked(parent, name + '.lock'):
        if not os.path.lexists(entry):
            with cache_staging_directory(root) as scratch:
                _publish_release(scratch, entry, parent, output, build(), expected)
            return
        try:
            package, metadata, checksum = _read_release(entry, expected, target)
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f'upgrade cache: invalid stored release package at {entry}: {error}') from error
        try:
            manifest = build(package=package, metadata={**metadata, 'source': source})
            if manifest['artifacts']['package']['sha256'] != checksum:
                raise ValueError('release input changed during copy')
        except (OSError, ValueError, builder.ArtifactError) as error:
            raise ValueError(f'upgrade cache: preparation failed using archived release at {entry}: {error}') from error
        print(f"test-artifacts: reused cached release {source['revision'][:12]} for {target.name}", flush=True)
