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
    from tools import test_storage
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'registry')
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


def test_recovery_diagnostics_rotate_without_changing_unfinished_vm_journal(tmp_path, monkeypatch):
    import check_graphical_recovery as recovery
    from tools import test_storage
    monkeypatch.setattr(test_storage, 'ROOT', tmp_path)
    monkeypatch.setattr(test_storage, 'privileged_state', lambda uid: tmp_path / 'vm-state')
    monkeypatch.setenv('PKEXEC_UID', '1000')
    monkeypatch.setattr(storage, 'os', SimpleNamespace(geteuid=lambda: 0, environ=os.environ))
    monkeypatch.setattr(recovery, 'os', SimpleNamespace(umask=lambda _: None))
    def missing_runtime(_):
        raise RuntimeError('injected recovery failure')
    monkeypatch.setattr(recovery, 'importlib', SimpleNamespace(import_module=missing_runtime))
    vm_store = retention.Store(tmp_path / 'vm-state')
    with vm_store.session():
        retention.preserve_for_recovery()
    original = (vm_store.path / 'current.json').read_bytes()
    journal = tmp_path / 'recovery-diagnostics-1000/current.json'
    paths = []
    for index in range(5):
        with storage.recovery_session():
            assert recovery.recover('vnc') == 1
        state = json.loads(journal.read_text())
        paths.append(Path(state['paths'][0]['path']))
        assert all((path / 'result.json').is_file() for path in paths[-3:])
        assert all(not path.exists() for path in paths[:-3])
        assert (vm_store.path / 'current.json').read_bytes() == original
        assert (vm_store.path / 'recovery-required').exists()
        if index == 0:
            # Abrupt termination of the diagnostic writer is independently
            # recoverable; it never clears the VM's recovery obligation.
            state['finished'] = False
            journal.write_text(json.dumps(state))


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
