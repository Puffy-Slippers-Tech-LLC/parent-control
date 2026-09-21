"""Qualification rotation and explicit legacy cleanup fail closed."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

import qualification_storage as storage
import check_tmp_storage_cleanup as legacy
from tools import test_retention as retention


def test_standalone_qualifications_rotate_both_work_and_collector(tmp_path, monkeypatch):
    store = retention.Store(tmp_path / 'registry')
    monkeypatch.setattr(storage.test_retention, 'Store', lambda path: store)
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.delenv(retention.VARIABLE, raising=False)
    monkeypatch.setattr(storage, 'os', SimpleNamespace(geteuid=lambda: 0, environ=os.environ))
    # Exercise the real ownership/audit operations as the test user.
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    guards = []
    monkeypatch.setattr(storage.runpy, 'run_path', lambda path: {
        'retention_guard': lambda root: guards.append(root)})
    runs = []
    @storage.session()
    def qualify(fail=False):
        from private_artifacts import PrivateCollector
        work = Path(storage.allocate(tempfile.mkdtemp, dir=tmp_path))
        with PrivateCollector(run_id='qualification-test', secrets=[], parent=tmp_path) as collector:
            paths = [work, collector.path]
        for path in paths:
            (path / 'evidence').write_text('diagnostics')
        runs.append(paths)
        if fail:
            raise RuntimeError('qualification failed')
        return 7
    for index in range(5):
        if index == 1:
            with pytest.raises(RuntimeError):
                qualify(True)
        else:
            assert qualify() == 7
        assert all(path.exists() for pair in runs[-3:] for path in pair)
        assert all(not path.exists() for pair in runs[:-3] for path in pair)
    assert len(guards) == 10


def test_nested_qualification_joins_existing_run(tmp_path, monkeypatch):
    with retention.Store(tmp_path / 'registry').session() as token:
        @storage.session()
        def qualify():
            assert retention.token() == token
            return storage.allocate(tempfile.mkdtemp, dir=tmp_path)
        path = qualify()
    state = json.loads((tmp_path / 'registry/current.json').read_text())
    assert [record['path'] for record in state['paths']] == [path]


@pytest.mark.parametrize('fault', ['path', 'identity', 'duplicate', 'mode', 'active', 'mount'])
def test_legacy_cleanup_audits_everything_before_removing(tmp_path, monkeypatch, fault):
    record = dict(path='/tmp/onpc-graphical-smoke-abcdefgh', device=1, inode=2, mode=0o700)
    records = [record, dict(record, path='/tmp/onpc-e2e-evidence-abcdefgh')]
    calls = []
    def remove(value, *, validate_only=False):
        calls.append(validate_only)
        if validate_only and value is records[-1] and fault in ('identity', 'mount'):
            raise ValueError(fault)
    monkeypatch.setattr(legacy.retention, 'remove', remove)
    if fault == 'path':
        records[-1]['path'] = '/tmp/unrelated'
    if fault == 'duplicate':
        records[-1] = record
    if fault == 'mode':
        records[-1]['mode'] = 0o755
    def guard(paths):
        if fault == 'active':
            raise ValueError('active')
    with pytest.raises(ValueError):
        legacy.cleanup(records, guard)
    assert not any(value is False for value in calls)


def test_legacy_cleanup_removes_only_explicit_identity_records(monkeypatch):
    records = [dict(path='/tmp/onpc-graphical-smoke-abcdefgh', device=1, inode=2, mode=0o700)]
    calls = []
    monkeypatch.setattr(legacy.retention, 'remove', lambda record, **kw: calls.append((record, kw)))
    legacy.cleanup(records, lambda paths: None)
    assert calls == [(records[0], {'validate_only': True}), (records[0], {})]
