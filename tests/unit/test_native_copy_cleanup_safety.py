"""Exact copy writes and cleanup cannot follow or adopt foreign files.

Real descriptors in pytest-private storage; only account/root bindings are
substituted. No VM, service, bus, shared cache or process owner.
"""
import hashlib
import os
from pathlib import Path
import pwd
from types import SimpleNamespace

import pytest
import synthetic_files_guest as files


@pytest.fixture
def copy_boundary(tmp_path, monkeypatch):
    root = tmp_path / 'fixtures'
    root.mkdir(mode=0o755)
    (root / files.NATIVE_SPACE_SOURCE).write_bytes(b'fixed executable')
    (root / files.NATIVE_SPACE_SOURCE).chmod(0o755)
    for name in ('onpc-test-gui.py', 'gtk_automation.py'):
        (root / name).write_bytes(b'preserved runtime')
    monkeypatch.setattr(files, 'NATIVE_SPACE_PARENT', Path('/fixtures'))
    real_open = os.open

    def open_root(path, flags, *args, **kwargs):
        return real_open(tmp_path if path == '/' else path, flags, *args, **kwargs)

    monkeypatch.setattr(os, 'open', open_root)
    monkeypatch.setattr(pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir='/home/onpc-child-jordan'))
    expected = {'source': hashlib.sha256(b'fixed executable').hexdigest(),
                'nonmatching': hashlib.sha256(b'distinct executable').hexdigest()}

    def call(operation, previous=None):
        return files.native_space_operate(Path('/home/onpc-child-jordan'), operation,
                                          {'expected': expected, 'previous': previous})

    return root, call


def test_exact_copy_cleanup_preserves_source_and_unrelated_runtime(copy_boundary):
    root, call = copy_boundary
    staged = call('stage')
    copied = call('copy', staged)
    assert call('read', copied) == copied
    assert (root / files.NATIVE_SPACE_COPY).read_bytes() == b'fixed executable'
    assert call('cleanup', copied) == call('absent', {'absent': True}) == {'absent': True}
    assert (root / files.NATIVE_SPACE_SOURCE).read_bytes() == b'fixed executable'
    assert (root / 'onpc-test-gui.py').read_bytes() == b'preserved runtime'


@pytest.mark.parametrize('collision', ['file', 'symlink', 'hardlink'])
def test_copy_cannot_overwrite_or_follow_existing_destination(copy_boundary, collision):
    root, call = copy_boundary
    staged = call('stage')
    destination = root / files.NATIVE_SPACE_COPY
    if collision == 'file':
        destination.write_bytes(b'foreign file')
    elif collision == 'symlink':
        destination.symlink_to(root / 'onpc-test-gui.py')
    else:
        os.link(root / files.NATIVE_SPACE_SOURCE, destination)
    before = destination.lstat()
    with pytest.raises(ValueError, match='files:refused'):
        call('copy', staged)
    assert destination.lstat() == before
    assert (root / 'onpc-test-gui.py').read_bytes() == b'preserved runtime'


def test_cleanup_refuses_replaced_copy_even_with_identical_bytes(copy_boundary):
    root, call = copy_boundary
    copied = call('copy', call('stage'))
    destination = root / files.NATIVE_SPACE_COPY
    destination.rename(root.parent / 'old-copy')
    destination.write_bytes(b'fixed executable')
    destination.chmod(0o755)
    with pytest.raises(ValueError, match='files:refused'):
        call('cleanup', copied)
    assert destination.read_bytes() == b'fixed executable'


def test_copy_refuses_wrong_child_and_linked_directory_before_writing(copy_boundary, monkeypatch):
    root, call = copy_boundary
    staged = call('stage')
    with monkeypatch.context() as patch:
        patch.setattr(pwd, 'getpwnam', lambda name: SimpleNamespace(
            pw_uid=os.getuid() + 1, pw_gid=os.getgid(), pw_dir='/home/onpc-child-jordan'))
        with pytest.raises(ValueError, match='files:refused'):
            call('copy', staged)
    root.rename(root.parent / 'original')
    root.symlink_to(root.parent / 'original', target_is_directory=True)
    with pytest.raises(OSError):
        call('copy', staged)
    assert not (root / files.NATIVE_SPACE_COPY).exists()
