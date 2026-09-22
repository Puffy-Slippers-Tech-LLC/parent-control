"""Reusable preparation cannot certify stale, partial or substituted inputs."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import e2e_startup_cache as cache
import test_activity
import test_retention


@pytest.fixture
def private_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'cache_path', lambda _: tmp_path / 'receipts')
    return tmp_path


def test_content_changes_with_preserved_size_and_timestamp_invalidate(tmp_path):
    source = tmp_path / 'input'
    source.write_text('before')
    metadata = source.stat()
    before = cache.files_digest(tmp_path, [Path('input')])
    source.write_text('after!')
    os.utime(source, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    assert cache.files_digest(tmp_path, [Path('input')]) != before
    source.write_text('before')
    source.chmod(0o755)
    assert cache.files_digest(tmp_path, [Path('input')]) != before


def test_source_inventory_additions_and_deletions_invalidate(tmp_path, monkeypatch):
    (tmp_path / 'a').write_text('a')
    listing = Mock(return_value=SimpleNamespace(stdout=b'a\0'))
    monkeypatch.setattr(cache.subprocess, 'run', listing)
    first = cache.source_identity(tmp_path)
    (tmp_path / 'b').write_text('b')
    listing.return_value.stdout = b'a\0b\0'
    second = cache.source_identity(tmp_path)
    assert first != second
    (tmp_path / 'a').unlink()
    assert cache.source_identity(tmp_path) not in (first, second)


@pytest.mark.parametrize('relative', ['__pycache__/module.cpython-313.pyc', 'module.pyc'])
def test_ignored_checkout_bytecode_invalidates_cleanup(tmp_path, monkeypatch, relative):
    (tmp_path / 'module.py').write_text('source')
    monkeypatch.setattr(cache.subprocess, 'run', Mock(
        return_value=SimpleNamespace(stdout=b'module.py\0')))
    before = cache.source_identity(tmp_path)
    bytecode = tmp_path / relative
    bytecode.parent.mkdir(exist_ok=True)
    bytecode.write_bytes(b'compiled before')
    added = cache.source_identity(tmp_path)
    assert added != before
    metadata = bytecode.stat()
    bytecode.write_bytes(b'compiled after!')
    os.utime(bytecode, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    assert cache.source_identity(tmp_path) not in (before, added)


def test_runtime_tracks_import_bytes_inventory_and_search_order(tmp_path, monkeypatch):
    # Load the launcher before replacing import roots with the private fixture.
    import test_launcher
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    dependency = first / 'dependency.py'
    dependency.write_text('before')
    monkeypatch.setattr(cache.sys, 'path', [str(first), str(second)])
    monkeypatch.setattr(cache.sysconfig, 'get_path', lambda _: str(first))
    monkeypatch.setattr(cache.site, 'ENABLE_USER_SITE', False)
    initial = cache.runtime_identity(tmp_path / 'checkout')
    metadata = dependency.stat()
    dependency.write_text('after!')
    os.utime(dependency, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    changed = cache.runtime_identity(tmp_path / 'checkout')
    assert changed != initial
    (second / 'new.py').write_text('new dependency')
    added = cache.runtime_identity(tmp_path / 'checkout')
    assert added not in (initial, changed)
    (first / '__pycache__').mkdir()
    (first / '__pycache__/dependency.pyc').write_bytes(b'compiled dependency')
    compiled = cache.runtime_identity(tmp_path / 'checkout')
    assert compiled != added
    monkeypatch.setattr(cache.sys, 'path', [str(second), str(first)])
    assert cache.runtime_identity(tmp_path / 'checkout') != compiled


@pytest.mark.parametrize('change', ['product', 'fixture', 'builder', 'builder-bytecode',
                                  'revision', 'runtime'])
def test_artifact_key_covers_inputs_and_metadata(tmp_path, monkeypatch, change):
    (tmp_path / 'tests/fixtures').mkdir(parents=True)
    (tmp_path / 'tests/fixtures/input.c').write_text('fixture')
    (tmp_path / 'tools').mkdir()
    for name in ('build_test_artifacts.py', 'package_inputs.py', 'e2e_startup_cache.py', 'test_retention.py'):
        (tmp_path / 'tools' / name).write_text('builder')
    product = tmp_path / 'product'
    product.write_text('product')
    revision, runtime = ['one'], ['one']
    monkeypatch.setattr(cache, 'runtime_identity', lambda _: runtime[0])
    builder = SimpleNamespace(REPOSITORY=tmp_path, package_inputs=SimpleNamespace(
        paths=lambda _: [Path('product')], digest=cache.files_digest),
        _metadata=lambda paths, content: {'source': {'revision': revision[0], 'digest': content}})
    before, _ = cache.artifact_identity(builder)
    if change == 'product':
        product.write_text('changed')
    elif change == 'fixture':
        (tmp_path / 'tests/fixtures/input.c').write_text('changed')
    elif change == 'builder':
        (tmp_path / 'tools/build_test_artifacts.py').write_text('changed')
    elif change == 'builder-bytecode':
        (tmp_path / 'tools/__pycache__').mkdir()
        (tmp_path / 'tools/__pycache__/package_inputs.cpython-313.pyc').write_bytes(b'compiled')
    elif change == 'revision':
        revision[0] = 'two'
    elif change == 'runtime':
        runtime[0] = 'two'
    after, _ = cache.artifact_identity(builder)
    assert before != after


@pytest.mark.parametrize('change', ['source', 'runtime'])
def test_cleanup_hit_and_invalidation(private_cache, monkeypatch, change):
    inputs = {'source': 'one', 'runtime': 'one'}
    monkeypatch.setattr(cache, 'source_identity', lambda _: inputs['source'])
    monkeypatch.setattr(cache, 'runtime_identity', lambda _: inputs['runtime'])
    run = Mock(return_value=0)
    with test_activity.activity(private_cache, host_only=True):
        assert cache.qualified_cleanup(private_cache, run) == 0
    with test_activity.activity(private_cache, host_only=True):
        assert not test_activity.cleanup_verified(private_cache)
        assert cache.qualified_cleanup(private_cache, run) == 0
        assert test_activity.cleanup_verified(private_cache)
    assert run.call_count == 1
    inputs[change] = 'two'
    assert cache.qualified_cleanup(private_cache, run) == 0
    assert run.call_count == 2


@pytest.mark.parametrize('outcome', ['failure', 'interrupted', 'changed', 'exception'])
def test_cleanup_never_caches_failed_or_changing_pass(private_cache, monkeypatch, outcome):
    identity = ['one']
    monkeypatch.setattr(cache, 'source_identity', lambda _: identity[0])
    monkeypatch.setattr(cache, 'runtime_identity', lambda _: 'runtime')
    def first():
        if outcome == 'exception':
            raise RuntimeError('interrupted')
        if outcome == 'changed':
            identity[0] = 'two'
        return {'failure': 1, 'interrupted': 130}.get(outcome, 0)
    if outcome == 'exception':
        with pytest.raises(RuntimeError):
            cache.qualified_cleanup(private_cache, first)
    else:
        cache.qualified_cleanup(private_cache, first)
    identity[0] = 'one'
    retry = Mock(return_value=0)
    assert cache.qualified_cleanup(private_cache, retry) == 0
    retry.assert_called_once()


@pytest.mark.parametrize('capture', ['before', 'after'])
def test_unstable_cleanup_inputs_run_fresh_without_invalidating_pass(
        private_cache, monkeypatch, capture):
    source = Mock(side_effect=([ValueError('input changed during capture')] if capture == 'before'
                              else ['one', FileNotFoundError('concurrent deletion')]))
    monkeypatch.setattr(cache, 'source_identity', source)
    monkeypatch.setattr(cache, 'runtime_identity', lambda _: 'runtime')
    run = Mock(return_value=0)
    assert cache.qualified_cleanup(private_cache, run) == 0
    run.assert_called_once()
    with cache.receipt(private_cache, 'cleanup') as (record, _):
        assert record.get('passed') is False


def test_receipt_corruption_is_miss_but_unsafe_ownership_is_refused(private_cache):
    with cache.receipt(private_cache, 'cleanup') as (_, save):
        save({'passed': True})
    record = private_cache / 'receipts/cleanup.json'
    record.write_text('{incomplete')
    with cache.receipt(private_cache, 'cleanup') as (value, _):
        assert value is None
    record.chmod(0o666)
    with pytest.raises(ValueError, match='ownership'):
        with cache.receipt(private_cache, 'cleanup'):
            pytest.fail('unsafe receipt accepted')


def test_receipt_symlink_cannot_redirect_writes(private_cache):
    outside = private_cache / 'unrelated'
    outside.write_text('preserve')
    folder = private_cache / 'receipts'
    folder.mkdir(mode=0o700)
    (folder / 'cleanup.json').symlink_to(outside)
    with pytest.raises(OSError):
        with cache.receipt(private_cache, 'cleanup'):
            pytest.fail('symlink accepted')
    assert outside.read_text() == 'preserve'


def test_receipt_fifo_is_refused_without_waiting_for_a_writer(private_cache, monkeypatch):
    folder = private_cache / 'receipts'
    folder.mkdir(mode=0o700)
    os.mkfifo(folder / 'cleanup.json', 0o600)
    original = os.open
    def nonblocking(path, flags, *args, **kwargs):
        if path == 'cleanup.json':
            # Assert before the real open so a regression fails rather than
            # hanging this safety gate on a FIFO with no writer.
            assert flags & os.O_NONBLOCK
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(cache.os, 'open', nonblocking)
    with pytest.raises(ValueError, match='ownership'):
        with cache.receipt(private_cache, 'cleanup'):
            pytest.fail('FIFO accepted')


@pytest.fixture
def artifact_builder(private_cache, monkeypatch):
    metadata = {'source': {'revision': 'one'}, 'build_inputs': {}, 'tools': {}}
    identity = ['one']
    def build(output):
        (output / 'package').write_bytes(b'package')
        (output / 'volatile.flatpak').write_bytes(b'container')
        (output / 'manifest.json').write_text(json.dumps(metadata))
    builder = SimpleNamespace(REPOSITORY=private_cache, MANIFEST_NAME='manifest.json',
                              ArtifactError=RuntimeError, build=Mock(side_effect=build),
                              _require_empty_output=lambda p: p,
                              verify=lambda p: json.loads((p / 'manifest.json').read_text()))
    monkeypatch.setattr(cache, 'artifact_identity', lambda _: (identity[0], dict(metadata)))
    with ExitStack() as stack:
        stack.enter_context(test_retention.Store(private_cache / 'retention').session())
        def output():
            return Path(stack.enter_context(tempfile.TemporaryDirectory(
                prefix='onpc-test-cache-', dir='/tmp')))
        yield builder, output, identity, metadata


def test_artifact_hit_copies_all_bytes_into_new_owned_output(artifact_builder):
    builder, output, _, _ = artifact_builder
    first, second = output(), output()
    cache.prepare_artifacts(builder, first)
    cache.prepare_artifacts(builder, second)
    builder.build.assert_called_once_with(first)
    assert cache.tree_digest(first) == cache.tree_digest(second)
    assert (first / 'package').stat().st_ino != (second / 'package').stat().st_ino
    with cache.receipt(builder.REPOSITORY, 'artifacts') as (record, _):
        assert record['path'] == str(second)


@pytest.mark.parametrize('change', ['identity', 'metadata', 'payload', 'volatile', 'mode',
                                  'added', 'deleted', 'symlink'])
def test_changed_artifacts_and_metadata_are_rebuilt(artifact_builder, change):
    builder, output, identity, metadata = artifact_builder
    first, second = output(), output()
    cache.prepare_artifacts(builder, first)
    if change == 'identity':
        identity[0] = 'two'
    elif change == 'metadata':
        metadata['source'] = {'revision': 'two'}
    elif change == 'payload':
        (first / 'package').write_bytes(b'changed')
    elif change == 'volatile':
        (first / 'volatile.flatpak').write_bytes(b'changed')
    elif change == 'mode':
        (first / 'package').chmod(0o755)
    elif change == 'added':
        (first / 'unexpected').write_text('new')
    elif change == 'deleted':
        (first / 'package').unlink()
    elif change == 'symlink':
        (first / 'package').unlink()
        (first / 'package').symlink_to('/etc/passwd')
    cache.prepare_artifacts(builder, second)
    assert builder.build.call_count == 2
    assert (second / 'package').read_bytes() == b'package'


def test_input_edit_during_build_refuses_and_does_not_publish(artifact_builder):
    builder, output, identity, _ = artifact_builder
    build = builder.build.side_effect
    def changed(path):
        build(path)
        identity[0] = 'two'
    builder.build.side_effect = changed
    with pytest.raises(ValueError, match='build inputs changed'):
        cache.prepare_artifacts(builder, output())
    with cache.receipt(builder.REPOSITORY, 'artifacts') as (record, _):
        assert record['identity'] is None


def test_artifact_copy_race_refuses_instead_of_using_partial_copy(artifact_builder, monkeypatch):
    builder, output, _, _ = artifact_builder
    first = output()
    cache.prepare_artifacts(builder, first)
    copy = cache.shutil.copytree
    def changed(source, target, **kwargs):
        copy(source, target, **kwargs)
        (target / 'package').write_bytes(b'changed')
    monkeypatch.setattr(cache.shutil, 'copytree', changed)
    with pytest.raises(ValueError, match='during copy'):
        cache.prepare_artifacts(builder, output())
    with cache.receipt(builder.REPOSITORY, 'artifacts') as (record, _):
        assert record['identity'] is None


def test_reuse_without_retention_refuses_before_writing(artifact_builder, monkeypatch):
    builder, output, _, _ = artifact_builder
    target = output()
    with monkeypatch.context() as isolated:
        isolated.delenv(test_retention.VARIABLE)
        with pytest.raises(ValueError, match='retained launcher'):
            cache.prepare_artifacts(builder, target)
    assert not list(target.iterdir())
    builder.build.assert_not_called()


@pytest.mark.parametrize('refresh', [False, True])
def test_many_cache_generations_have_bounded_storage(artifact_builder, refresh):
    builder, output, identity, _ = artifact_builder
    store = test_retention.Store(builder.REPOSITORY / 'rotating-retention')
    allocations = []
    for index in range(20):
        with store.session():
            if refresh:
                identity[0] = str(index)
            target = output()
            allocations.append(target)
            cache.prepare_artifacts(builder, target)
        assert [p for p in allocations if p.exists()] == allocations[-test_retention.RUNS_TO_KEEP:]
        with cache.receipt(builder.REPOSITORY, 'artifacts') as (record, _):
            assert record['path'] == str(target)
        # No per-key receipt directories, saved payloads or abandoned .tmp files.
        assert sorted(p.name for p in cache.cache_path(builder.REPOSITORY).iterdir()) == [
            'artifacts.json', 'cache.lock']
    assert builder.build.call_count == (20 if refresh else 1)
