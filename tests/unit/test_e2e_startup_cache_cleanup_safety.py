"""Reusable preparation cannot certify stale, partial or substituted inputs."""

from contextlib import ExitStack
from importlib.util import cache_from_source
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import e2e_startup_cache as cache
import artifact_inputs
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


@pytest.mark.parametrize('relative, invalidates', [
    ('README.md', False), ('AGENTS.md', False),
    ('tests/README.md', False), ('tests/e2e/README.md', False),
    ('docs/TestAutomation/E2E-Task-Queue.md', False), ('docs/Mandates/VM-Mandate.MD', False),
    ('docs/example.py', True), ('tools/cleanup', True), ('pyproject.toml', True),
    ('tests/e2e/scenarios.json', True), ('tests/fixtures/sample.md', True),
    ('tests/unit/test_new_cleanup_safety.py', True),
])
def test_prose_edits_do_not_requalify_but_all_executable_inputs_do(
        tmp_path, monkeypatch, relative, invalidates):
    (tmp_path / 'module.py').write_text('source')
    changed = tmp_path / relative
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text('before')
    monkeypatch.setattr(cache.subprocess, 'run', Mock(return_value=SimpleNamespace(
        stdout=b'module.py\0' + relative.encode() + b'\0')))
    before = cache.source_identity(tmp_path)
    changed.write_text('after!')
    assert (cache.source_identity(tmp_path) != before) is invalidates
    changed.unlink()
    assert (cache.source_identity(tmp_path) != before) is invalidates


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


def test_overlapping_runtime_roots_hash_dependency_once(tmp_path, monkeypatch):
    directory = tmp_path / 'lib'
    directory.mkdir()
    module = directory / 'dependency.py'
    module.write_text('dependency')
    monkeypatch.setattr(cache.sys, 'path', [str(tmp_path), str(directory)])
    monkeypatch.setattr(cache.sysconfig, 'get_path', lambda _: str(directory))
    monkeypatch.setattr(cache.site, 'ENABLE_USER_SITE', False)
    read = Mock(wraps=cache.file_digest)
    monkeypatch.setattr(cache, 'file_digest', read)
    cache.runtime_identity(tmp_path / 'checkout')
    assert sum(call.args == (module,) for call in read.call_args_list) == 1


@pytest.mark.parametrize('change,parts', [
    ('product', {'package'}), ('fixture', {'fixtures'}), ('builder', {'package', 'fixtures'}),
    ('builder-bytecode', {'package'}), ('revision', {'package'}),
    ('runtime', {'package', 'fixtures'}), ('unrelated-bytecode', set()),
    ('fixture-readme', set()), ('cleanup-code', set()), ('scenario', set()),
    ('retention-code', set()), ('fixture-bytecode', {'fixtures'}),
    ('copied-bytecode', set()), ('other-interpreter', set()),
])
def test_artifact_key_covers_inputs_and_metadata(tmp_path, monkeypatch, change, parts):
    for name in (*artifact_inputs.FIXTURE_SOURCES, 'tools/build_test_artifacts.py',
                 'tools/package_inputs.py', 'tools/artifact_inputs.py'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('input')
    product = tmp_path / 'product'
    product.write_text('product')
    revision, runtime = ['one'], ['one']
    monkeypatch.setattr(artifact_inputs, 'runtime_inputs', lambda _: {
        part: {'runtime': runtime[0]} for part in ('package', 'fixtures')})
    builder = SimpleNamespace(REPOSITORY=tmp_path, package_inputs=SimpleNamespace(
        paths=lambda _: [Path('product')], digest=cache.files_digest),
        _metadata=lambda paths, content: {'source': {'revision': revision[0], 'digest': content},
                                         'build_inputs': {}})
    before, _ = cache.artifact_identity(builder)
    if change == 'product':
        product.write_text('changed')
    elif change == 'fixture':
        (tmp_path / 'tests/fixtures/onpc_test_application.c').write_text('changed')
    elif change == 'builder':
        (tmp_path / 'tools/build_test_artifacts.py').write_text('changed')
    elif change == 'builder-bytecode':
        (tmp_path / 'tools/__pycache__').mkdir()
        Path(cache_from_source(str(tmp_path / 'tools/package_inputs.py'))).write_bytes(b'compiled')
    elif change == 'revision':
        revision[0] = 'two'
    elif change == 'runtime':
        runtime[0] = 'two'
    else:
        relative = {
            'unrelated-bytecode': 'tools/__pycache__/test_launcher.cpython-313.pyc',
            'fixture-readme': 'tests/fixtures/README.md',
            'cleanup-code': 'tools/e2e_startup_cache.py',
            'retention-code': 'tools/test_retention.py',
            'scenario': 'tests/e2e/scenarios.json',
            'fixture-bytecode': cache_from_source('tests/fixtures/gui_runtime.py'),
            'copied-bytecode': cache_from_source('tests/fixtures/gui_application.py'),
            'other-interpreter': 'tools/__pycache__/package_inputs.cpython-999.pyc',
        }[change]
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('changed')
    after, _ = cache.artifact_identity(builder)
    assert {part for part in before if before[part] != after[part]} == parts


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
    identity = [{'package': {'source': 'one'}, 'fixtures': {'source': 'one'}}]
    def build(output, *, reuse):
        for part in ('package', 'fixtures'):
            if part in reuse:
                cache.shutil.copytree(reuse[part], output / part)
            else:
                (output / part).mkdir()
                (output / part / 'payload').write_bytes(part.encode())
        if 'fixtures' not in reuse:
            (output / 'fixtures/volatile.flatpak').write_bytes(b'container')
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
    builder.build.assert_called_once_with(first, reuse={})
    assert cache.tree_digest(first) == cache.tree_digest(second)
    assert (first / 'package/payload').stat().st_ino != (second / 'package/payload').stat().st_ino
    with cache.receipt(builder.REPOSITORY, 'artifacts') as (record, _):
        assert record['path'] == str(second)


@pytest.mark.parametrize('part', ['package', 'fixtures'])
def test_only_changed_component_builds_and_records_the_current_bundle(artifact_builder, part, capsys):
    builder, output, identity, _ = artifact_builder
    first, second, third = output(), output(), output()
    cache.prepare_artifacts(builder, first)
    identity[0] = {**identity[0], part: {'source': 'changed'}}
    cache.prepare_artifacts(builder, second)
    other = 'fixtures' if part == 'package' else 'package'
    builder.build.assert_called_with(second, reuse={other: first / other})
    assert cache.tree_digest(first / other) == cache.tree_digest(second / other)
    cache.prepare_artifacts(builder, third)
    assert builder.build.call_count == 2
    assert f'artifact {part} build required; changed=source' in capsys.readouterr().out
    with cache.receipt(builder.REPOSITORY, 'artifacts') as (record, _):
        assert record['path'] == str(third)


def test_dependency_closure_excludes_unrelated_packages_and_tracks_providers():
    def record(name, **fields):
        values = dict(Package=name, Architecture='amd64', Status='install ok installed', Version='1')
        return '\n'.join(f'{key}: {value}' for key, value in (values | fields).items())
    records = [record('builder', Depends='virtual-tool (>= 1), library:any | fallback [amd64]'),
               record('provider', Provides='virtual-tool (= 1)', Depends='library'),
               record('library'), record('editor')]
    capture = lambda values: artifact_inputs.package_records('\n\n'.join(values), {'builder'})
    first = capture(records)
    assert set(first) == {'builder:amd64', 'provider:amd64', 'library:amd64'}
    assert capture([*records[:-1], record('editor', Version='2')]) == first
    assert capture([*records[:2], record('library', Version='2'), records[-1]]) != first
    assert capture([*records, record('fallback')]) != first


def test_tool_provider_follows_the_selected_compiler_alternative(tmp_path, monkeypatch):
    compiler = tmp_path / 'clang'
    compiler.write_bytes(b'compiler')
    alternative = tmp_path / 'cc'
    alternative.symlink_to(compiler)
    run = Mock(return_value=SimpleNamespace(stdout=f'clang-21:amd64: {compiler}\n'))
    monkeypatch.setattr(artifact_inputs.subprocess, 'run', run)
    assert artifact_inputs.tool_packages([str(alternative)]) == {'clang-21'}
    assert run.call_args.args[0] == ['dpkg-query', '--search', str(compiler)]


def test_runtime_tree_inventory_matches_copied_links_and_ignores_unused_bytecode(tmp_path):
    from tests.fixtures.gui_runtime import tree_sources
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'empty').mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'library.so').write_bytes(b'library')
    (source / 'linked').symlink_to(external, target_is_directory=True)
    (source / '__pycache__').mkdir()
    (source / '__pycache__/module.pyc').write_bytes(b'ignored')
    copied = tmp_path / 'copied'
    cache.shutil.copytree(source, copied, ignore=cache.shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert {p.relative_to(source) for p in tree_sources(source)} == {
        Path('.'), *(p.relative_to(copied) for p in copied.rglob('*'))}
    (external / 'cycle').symlink_to(source, target_is_directory=True)
    with pytest.raises(RuntimeError, match='cycle'):
        list(tree_sources(source))


@pytest.mark.parametrize('change', ['identity', 'metadata', 'payload', 'volatile', 'mode',
                                  'added', 'deleted', 'symlink'])
def test_changed_artifacts_and_metadata_are_rebuilt(artifact_builder, change):
    builder, output, identity, metadata = artifact_builder
    first, second = output(), output()
    cache.prepare_artifacts(builder, first)
    if change == 'identity':
        identity[0] = {part: {'source': 'two'} for part in identity[0]}
    elif change == 'metadata':
        metadata['source'] = {'revision': 'two'}
    elif change == 'payload':
        (first / 'package/payload').write_bytes(b'changed')
    elif change == 'volatile':
        (first / 'fixtures/volatile.flatpak').write_bytes(b'changed')
    elif change == 'mode':
        (first / 'package/payload').chmod(0o755)
    elif change == 'added':
        (first / 'unexpected').write_text('new')
    elif change == 'deleted':
        (first / 'package/payload').unlink()
    elif change == 'symlink':
        (first / 'package/payload').unlink()
        (first / 'package/payload').symlink_to('/etc/passwd')
    cache.prepare_artifacts(builder, second)
    assert builder.build.call_count == 2
    assert (second / 'package/payload').read_bytes() == b'package'


def test_input_edit_during_build_refuses_and_does_not_publish(artifact_builder):
    builder, output, identity, _ = artifact_builder
    build = builder.build.side_effect
    def changed(path, **kwargs):
        build(path, **kwargs)
        identity[0] = {part: {'source': 'two'} for part in identity[0]}
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
    def changed(source, target, *args, **kwargs):
        copy(source, target, *args, **kwargs)
        if (Path(target) / 'package/payload').exists():
            (Path(target) / 'package/payload').write_bytes(b'changed')
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
                identity[0] = {part: {'source': str(index)} for part in identity[0]}
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
