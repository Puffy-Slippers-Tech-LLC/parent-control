"""Protect the new finite Snap installation boundary, without a baseline matrix."""
import json
import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.modules import load_module
from tests.support.paths import ROOT

snaps = load_module('baseline_snap_safety', ROOT / 'tests/integration/baseline_snaps.py')


def test_wrong_manifest_refuses_before_any_package_command(monkeypatch):
    monkeypatch.setattr(snaps, 'read', lambda path: json.dumps({'foreign.snap': 'a' * 64}).encode())
    runner = SimpleNamespace(run=Mock())
    with pytest.raises(ValueError, match='snap-fixtures:manifest'):
        snaps.reconcile('a' * 64, runner=runner)
    runner.run.assert_not_called()


def test_unowned_installed_name_is_preserved_without_package_installation(monkeypatch):
    import hashlib
    inputs = {name: name.encode() for name in snaps.assets.packages()}
    expected = {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}
    monkeypatch.setattr(snaps, 'read', lambda path, **kwargs:
        json.dumps(expected).encode() if path.name == 'SHA256SUMS.json' else inputs[path.name])
    monkeypatch.setattr(snaps.os.path, 'lexists', lambda path: False)
    name = snaps.assets.ASSETS[0][1]
    monkeypatch.setattr(snaps, 'installed', lambda: {name: ['foreign']})
    runner = SimpleNamespace(run=Mock())
    with pytest.raises(ValueError, match='snap-fixtures:foreign-package'):
        snaps.reconcile('a' * 64, runner=runner)
    assert all('/usr/bin/snap' not in call.args[0] or 'install' not in call.args[0]
               for call in runner.run.call_args_list)


def test_installed_blob_must_match_the_declared_digest(monkeypatch):
    monkeypatch.setattr(snaps, 'read', lambda path, **kwargs: b'substituted package')
    name = snaps.assets.ASSETS[0][1]
    with pytest.raises(ValueError, match='snap-fixtures:installed-digest'):
        snaps.package_readback(name, [name, '1', 'x1', '-', '-', 'dangerous'],
                               expected='a' * 64, title=snaps.assets.ASSETS[0][2])


def test_unknown_package_refuses_before_reading_any_file(monkeypatch):
    reader = Mock()
    monkeypatch.setattr(snaps, 'read', reader)
    with pytest.raises(ValueError, match='snap-fixtures:package-recipient'):
        snaps.package_readback('foreign', ['foreign', '1', '1', '-', 'publisher', 'base'])
    reader.assert_not_called()


@pytest.mark.parametrize('replaced', [False, True])
def test_base_cache_requires_the_same_root_owned_inode(monkeypatch, replaced):
    import os
    blob = SimpleNamespace(st_dev=5, st_ino=9)
    peer = SimpleNamespace(st_dev=5, st_ino=10 if replaced else 9,
        st_uid=0, st_gid=0, st_mode=stat.S_IFREG | 0o600, st_nlink=2)
    parent = SimpleNamespace(st_uid=0, st_gid=0, st_mode=stat.S_IFDIR | 0o700)
    interface = SimpleNamespace(O_RDONLY=os.O_RDONLY, O_DIRECTORY=os.O_DIRECTORY,
        O_NOFOLLOW=os.O_NOFOLLOW, open=Mock(return_value=41),
        fstat=Mock(return_value=parent), listdir=Mock(return_value=['a' * 96]),
        stat=Mock(return_value=peer), close=Mock())
    monkeypatch.setattr(snaps, 'os', interface)
    if replaced:
        with pytest.raises(ValueError, match='snap-fixtures:base-cache-peer'):
            snaps.base_cache_peer(blob)
    else:
        assert snaps.base_cache_peer(blob) == 'a' * 96
    interface.close.assert_called_once_with(41)


def test_foreign_file_read_refuses_without_changing_bytes(tmp_path):
    path = tmp_path / 'foreign.snap'
    path.write_bytes(b'keep foreign input')
    with pytest.raises(ValueError, match='snap-fixtures:ancestor-owner|snap-fixtures:file-owner'):
        snaps.read(path)
    assert path.read_bytes() == b'keep foreign input'


@pytest.mark.parametrize('substituted', [False, True])
def test_copied_snap_sources_require_their_exact_receipt_before_retirement(substituted):
    import baseline_guest as guest
    from prepare_baseline import CaptureError
    record = {'purpose': 'onpc-preparation-source-staging-v1', 'pending': None,
              'files': dict.fromkeys(guest.STAGED_MOVABLE_SOURCES, 'a' * 64)}
    target = guest.STAGE + '/checkout/tests/fixtures/snap_assets.py'

    def metadata(path):
        regular = path == guest.SOURCE_STAGING or path in {
            guest.STAGE + '/checkout/' + name for name in record['files']}
        return {'st_mode': (stat.S_IFREG | 0o600) if regular else (stat.S_IFDIR | 0o700),
                'st_uid': 0, 'st_gid': 0, 'st_nlink': 1}

    g = SimpleNamespace(exists=lambda path: True, is_symlink=lambda path: False,
        realpath=lambda path: path, lstatns=metadata,
        read_file=lambda path: json.dumps(record).encode(),
        checksum=lambda algorithm, path: 'b' * 64 if substituted and path == target else 'a' * 64,
        rm=Mock(), sync=Mock())
    if substituted:
        with pytest.raises(CaptureError, match='guest:source-staging-substituted'):
            guest.recover_source_staging(g)
        g.rm.assert_not_called()
    else:
        guest.recover_source_staging(g)
        removed = {call.args[0] for call in g.rm.call_args_list}
        assert removed == {guest.STAGE + '/checkout/' + name for name in record['files']}
        assert {target, guest.STAGE + '/checkout/tests/integration/baseline_snaps.py'} <= removed
