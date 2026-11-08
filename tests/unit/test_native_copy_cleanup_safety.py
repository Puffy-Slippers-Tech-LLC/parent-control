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


@pytest.mark.parametrize('administrative', [False, True])
def test_version_copy_cleanup_refuses_replaced_source_in_parent_directory(tmp_path, monkeypatch, administrative):
    child_uid, child_gid = os.getuid(), os.getgid()
    root = tmp_path / 'Applications'
    root.mkdir(mode=0o755)
    versioned = root / 'Versioned'
    versioned.mkdir(mode=0o755)
    source = root / files.NATIVE_VERSION_SOURCE
    source.write_bytes(b'next version')
    source.chmod(0o755)
    for name in ('Lunar Client-3.7.17.AppImage', 'PrismLauncher.AppImage',
                 'onpc-test-gui.py', 'gtk_automation.py'):
        (versioned / name).write_bytes(b'preserved')
    monkeypatch.setattr(files, 'NATIVE_VERSION_PARENT', Path('/Applications/Versioned'))
    real_open = os.open
    monkeypatch.setattr(os, 'open', lambda path, flags, *args, **kwargs:
                        real_open(tmp_path if path == '/' else path, flags, *args, **kwargs))
    monkeypatch.setattr(pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=child_uid, pw_gid=child_gid, pw_dir='/home/onpc-child-jordan'))
    if administrative:
        monkeypatch.setattr(os, 'getuid', lambda: 0)
        monkeypatch.setattr(os, 'geteuid', lambda: 0)
    expected = {'source': hashlib.sha256(b'next version').hexdigest(),
                'nonmatching': hashlib.sha256(b'other version').hexdigest()}

    def call(operation, previous=None):
        return files.native_space_operate(Path('/home/onpc-child-jordan'), operation,
            {'expected': expected, 'previous': previous}, profile='native-version-next',
            administrative=administrative)

    staged = call('stage')
    if administrative:
        # Root input still cannot follow a destination link or adopt a collision.
        destination = versioned / files.NATIVE_VERSION_NEXT
        destination.symlink_to(source)
        with pytest.raises(ValueError, match='files:refused'):
            call('copy', staged)
        assert destination.is_symlink()
        destination.unlink()
    copied = call('copy', staged)
    assert call('read', copied) == copied
    destination = versioned / files.NATIVE_VERSION_NEXT
    assert (destination.stat().st_uid, destination.stat().st_gid) == (child_uid, child_gid)
    source.rename(root / 'original-source')
    source.write_bytes(b'next version')
    source.chmod(0o755)
    with pytest.raises(ValueError, match='files:refused'):
        call('cleanup', copied)
    assert (versioned / files.NATIVE_VERSION_NEXT).read_bytes() == b'next version'
    assert (versioned / 'PrismLauncher.AppImage').read_bytes() == b'preserved'


def test_administrative_copy_refuses_other_profiles_and_nonroot_before_files(monkeypatch):
    monkeypatch.setattr(os, 'getuid', lambda: 12345)
    monkeypatch.setattr(os, 'geteuid', lambda: 12345)
    monkeypatch.setattr(pwd, 'getpwnam', lambda name: SimpleNamespace(
        pw_uid=12345, pw_gid=12345, pw_dir='/home/onpc-child-jordan'))
    for profile in ('native-space', 'native-version-next'):
        with pytest.raises(ValueError, match='files:refused'):
            files.native_space_operate(Path('/home/onpc-child-jordan'), 'stage', None,
                                       profile, administrative=True)
