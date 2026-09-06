"""Privileged screenshot export must not become arbitrary file copy access."""

import os
from pathlib import Path
import runpy
import tempfile

import pytest


HELPER = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/onpc-export-screenshot'))
EXPORT = HELPER['export']
PNG = HELPER['PNG_SIGNATURE'] + b'test image payload'


@pytest.fixture
def artifacts():
    with tempfile.TemporaryDirectory(prefix='onpc-graphical-smoke-', dir='/tmp') as folder:
        root = Path(folder)
        results = root / 'testresults'
        results.mkdir(mode=0o755)
        source = results / 'smoke-2.png'
        source.write_bytes(PNG)
        source.chmod(0o600)
        destination = Path('/tmp') / (root.name + '-export.png')
        yield source, destination
        if destination.is_symlink() or destination.exists():
            destination.unlink()


def copy(source, destination):
    EXPORT(str(source), str(destination), os.getuid(), os.getgid())


def test_exports_bytes_with_private_mode_and_caller_ownership(artifacts):
    source, destination = artifacts
    copy(source, destination)
    assert destination.read_bytes() == PNG
    assert destination.stat().st_mode & 0o777 == 0o600
    assert (destination.stat().st_uid, destination.stat().st_gid) == (os.getuid(), os.getgid())
    assert source.read_bytes() == PNG


@pytest.mark.parametrize('source', ['/etc/shadow', '/tmp/onpc-x.png',
    '/tmp/onpc-graphical-smoke-x/testresults/../../secret.png',
    '/tmp/onpc-graphical-smoke-x/testresults/*.png'])
def test_rejects_unapproved_source_paths(artifacts, source):
    with pytest.raises(ValueError):
        copy(source, artifacts[1])
    assert not artifacts[1].exists()


@pytest.mark.parametrize('destination', ['/etc/onpc-x.png', '/tmp/x.png',
    '/tmp/onpc-x/../victim.png', '/tmp/onpc-*.png', '/tmp/onpc-x.log'])
def test_rejects_unapproved_destinations(artifacts, destination):
    with pytest.raises(ValueError):
        copy(artifacts[0], destination)


@pytest.mark.parametrize('kind', ['file', 'symlink', 'dangling'])
def test_never_overwrites_existing_destination(artifacts, kind):
    source, destination = artifacts
    if kind == 'file':
        destination.write_bytes(b'preserve')
    else:
        destination.symlink_to(source if kind == 'symlink' else source.parent / 'missing')
    with pytest.raises(FileExistsError):
        copy(source, destination)
    assert source.read_bytes() == PNG
    if kind == 'file':
        assert destination.read_bytes() == b'preserve'


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'directory', 'non_png', 'writable'])
def test_rejects_unsafe_source(artifacts, kind):
    source, destination = artifacts
    original = source.with_name('original.png')
    source.rename(original)
    if kind == 'symlink':
        source.symlink_to(original)
    elif kind == 'hardlink':
        os.link(original, source)
    elif kind == 'fifo':
        os.mkfifo(source)
    elif kind == 'directory':
        source.mkdir()
    else:
        source.write_bytes(PNG if kind == 'writable' else b'not a PNG')
        source.chmod(0o600)
        if kind == 'writable':
            source.chmod(0o666)
    with pytest.raises((ValueError, OSError)):
        copy(source, destination)
    assert not destination.exists()
    assert original.read_bytes() == PNG


def test_rejects_symlinked_parent(artifacts):
    source, destination = artifacts
    moved = source.parent.with_name('real-results')
    source.parent.rename(moved)
    source.parent.symlink_to(moved, target_is_directory=True)
    with pytest.raises(OSError):
        copy(source, destination)
    assert not destination.exists()


def test_rejects_writable_directory(artifacts):
    source, destination = artifacts
    source.parent.chmod(0o777)
    with pytest.raises(ValueError):
        copy(source, destination)


def test_rejects_oversized_source(artifacts):
    source, destination = artifacts
    with source.open('r+b') as stream:
        stream.truncate(HELPER['MAX_BYTES'] + 1)
    with pytest.raises(ValueError):
        copy(source, destination)
    assert not destination.exists()


@pytest.mark.parametrize('value', ['', '0', '-1', 'invalid'])
def test_requires_unprivileged_pkexec_identity(monkeypatch, value):
    monkeypatch.setenv('PKEXEC_UID', value)
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    with pytest.raises(ValueError):
        HELPER['caller']()
