"""Passing image cleanup must never erase diagnostics or another attempt."""

import os
from types import SimpleNamespace

import pytest

from tests import conftest as hooks
from tests.support.ui_artifacts import RenderArtifacts


def report(item, phase, passed):
    hook = hooks.pytest_runtest_makereport(item, None)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(SimpleNamespace(get_result=lambda: SimpleNamespace(when=phase, passed=passed)))


@pytest.mark.parametrize('failure', [None, 'setup', 'call', 'teardown'])
def test_images_live_until_successful_teardown(tmp_path, failure):
    item = SimpleNamespace()
    allocate = hooks.render_artifacts.__wrapped__(SimpleNamespace(node=item))
    directory = allocate('onpc-render-', parent=tmp_path)
    image = directory / 'request-1280x800-normal.png'
    image.write_bytes(b'image')
    (directory / 'layout.json').write_text('{}')
    for phase in ('setup', 'call'):
        report(item, phase, phase != failure)
        assert image.exists()
    report(item, 'teardown', failure != 'teardown')
    assert directory.exists() == (failure is not None)


def test_logs_unknown_files_and_other_attempts_survive(tmp_path):
    first = RenderArtifacts('onpc-render-', parent=tmp_path)
    second = RenderArtifacts('onpc-render-', parent=tmp_path)
    keep = ['preview.log', 'input.jsonl', 'events.jsonl', 'result.json', 'unknown.txt']
    for name in keep:
        (first.path / name).write_text('diagnostic')
    (first.path / 'image.png').write_bytes(b'passing')
    (second.path / 'image.png').write_bytes(b'active')
    first.finish(True)
    assert sorted(p.name for p in first.path.iterdir()) == sorted(keep)
    assert (second.path / 'image.png').read_bytes() == b'active'


@pytest.mark.parametrize('replacement', ['symlink', 'directory'])
def test_replaced_root_is_refused(tmp_path, replacement):
    attempt = RenderArtifacts('onpc-render-', parent=tmp_path)
    original = tmp_path / 'original'
    attempt.path.rename(original)
    if replacement == 'symlink':
        attempt.path.symlink_to(original, target_is_directory=True)
    else:
        attempt.path.mkdir()
    (attempt.path / 'image.png').write_bytes(b'keep')
    with pytest.raises((OSError, ValueError)):
        attempt.finish(True)
    assert (attempt.path / 'image.png').read_bytes() == b'keep'


def test_linked_images_are_not_deleted(tmp_path):
    attempt = RenderArtifacts('onpc-render-', parent=tmp_path)
    target = tmp_path / 'target.png'
    target.write_bytes(b'keep')
    (attempt.path / 'symlink.png').symlink_to(target)
    os.link(target, attempt.path / 'hardlink.png')
    attempt.finish(True)
    assert len(list(attempt.path.iterdir())) == 2
    assert target.read_bytes() == b'keep'


@pytest.mark.parametrize('passed', [False, True])
def test_only_successful_shader_caches_are_discarded(tmp_path, passed):
    attempt = RenderArtifacts('onpc-shell-', parent=tmp_path, shader_cache=True)
    cache = attempt.path / 'cache'
    driver = cache / 'mesa_shader_cache' / 'ab'
    driver.mkdir(parents=True)
    (driver / 'compiled').write_bytes(b'shader')
    (cache / 'other-cache').write_bytes(b'keep')
    (attempt.path / 'shell.log').write_text('keep')
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'compiled').write_bytes(b'foreign')
    (cache / 'nvidia').symlink_to(outside, target_is_directory=True)
    attempt.finish(passed)
    assert driver.exists() != passed
    assert (outside / 'compiled').read_bytes() == b'foreign'
    assert (cache / 'other-cache').exists()
    assert (attempt.path / 'shell.log').exists()


def test_symlink_cache_parent_is_refused(tmp_path):
    attempt = RenderArtifacts('onpc-shell-', parent=tmp_path, shader_cache=True)
    outside = tmp_path / 'outside'
    (outside / 'mesa_shader_cache').mkdir(parents=True)
    (attempt.path / 'cache').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        attempt.finish(True)
    assert (outside / 'mesa_shader_cache').exists()
