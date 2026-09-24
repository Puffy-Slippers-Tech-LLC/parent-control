"""The one-time migration cannot delete unreviewed, active or replaced trees."""
import os
from pathlib import Path
import tempfile

import pytest

import check_storage_migration as migration


def test_preserve_keeps_diagnostics_and_omits_inputs_and_links(tmp_path):
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir()
    target.mkdir()
    (source / 'input').mkdir()
    (source / 'input/bulk').write_bytes(b'not evidence')
    (source / 'result.json').write_bytes(b'evidence')
    (source / 'link').symlink_to('/etc/passwd')
    migration.preserve(source, target)
    assert (target / 'result.json').read_bytes() == b'evidence'
    assert sorted(p.name for p in target.iterdir()) == ['result.json']
    assert (source / 'input/bulk').exists()


@pytest.mark.parametrize('fault', ['path', 'inode', 'owner', 'mode'])
def test_migration_refuses_foreign_or_replaced_identity(fault):
    with tempfile.TemporaryDirectory(prefix='onpc-migration-', dir='/tmp') as name:
        record = migration.identity(Path(name))
        if fault == 'path':
            record['path'] = '/tmp/unrelated'
        elif fault == 'inode':
            record['inode'] += 1
        elif fault == 'owner':
            record['uid'] = os.geteuid() + 1
        else:
            record['mode'] = 0o755
        with pytest.raises(ValueError, match='invalid or replaced'):
            migration.validate(record, os.geteuid())
        assert Path(name).exists()


def test_live_reference_refuses_before_any_allocation(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    record = migration.identity(source)
    monkeypatch.setattr(migration, 'validate', lambda *args: None)
    def active(paths):
        raise ValueError('live process reference')
    monkeypatch.setattr(migration.retention, 'allocate', lambda *a, **k: pytest.fail('allocated before live-reference gate'))
    with pytest.raises(ValueError, match='live process'):
        migration.migrate([record], os.geteuid(), guard=active)
    assert source.exists()


def test_copy_failure_preserves_entire_original(tmp_path, monkeypatch):
    with tempfile.TemporaryDirectory(prefix='onpc-migration-', dir='/tmp') as name:
        source = Path(name)
        (source / 'result.log').write_text('original evidence')
        record = migration.identity(source)
        destination = tmp_path / 'migrated'
        destination.mkdir()
        monkeypatch.setattr(migration.retention, 'allocate', lambda *a, **k: str(destination))
        def fail(*args):
            raise OSError('full disk')
        monkeypatch.setattr(migration, 'preserve', fail)
        with pytest.raises(OSError, match='full disk'):
            migration.migrate([record], os.geteuid(), guard=lambda _: None)
        assert (source / 'result.log').read_text() == 'original evidence'


def test_successful_migration_preserves_diagnostics_before_removal(tmp_path, monkeypatch):
    source = Path(tempfile.mkdtemp(prefix='onpc-migration-', dir='/tmp'))
    (source / 'result.log').write_text('original evidence')
    (source / 'input').mkdir()
    (source / 'input/bulk').write_text('rebuildable')
    record = migration.identity(source)
    destination = tmp_path / 'migrated'
    destination.mkdir()
    monkeypatch.setattr(migration.retention, 'allocate', lambda *a, **k: str(destination))
    try:
        migration.migrate([record], os.geteuid(), guard=lambda _: None)
        assert not source.exists()
        assert (destination / 'result.log').read_text() == 'original evidence'
        assert not (destination / 'input').exists()
        assert (destination / 'migration.json').exists()
    finally:
        migration.retention.remove({key: value for key, value in record.items() if key != 'uid'})
