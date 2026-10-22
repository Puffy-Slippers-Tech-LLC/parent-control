"""Read-only execution inputs retain caller identity and journal ownership.

All files and locks are pytest-private. No processes, builds, VMs or shared
storage are acquired; these bounded descriptor tests permit unit overlap.
"""
import copy
import fcntl
import json
import os
from types import SimpleNamespace

import pytest

from tools import test_retention as retention, test_storage as storage


@pytest.fixture
def selected(tmp_path, monkeypatch):
    # Exercise descriptor checks with the test process's actual file owner.
    # Authentication itself is tested separately without requiring pkexec.
    monkeypatch.setattr(storage, '_input_caller', lambda caller_uid: os.getuid())
    journal = storage.directory('state', root=tmp_path) / 'retention-host'
    allocation = storage.directory('allocations', root=tmp_path) / 'onpc-fixture-input'
    journal.mkdir(mode=0o700)
    allocation.mkdir(mode=0o700)
    owner = os.open(journal / 'owner.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    writer = os.open(journal / 'writer.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    info, journal_info = allocation.stat(), journal.stat()
    record = dict(path=str(allocation), device=info.st_dev, inode=info.st_ino, mode=0o700)
    state = dict(run='a' * 32, finished=False, paths=[record], history=[])
    path = journal / 'current.json'
    path.write_text(json.dumps(state))
    path.chmod(0o600)
    selection = dict(schema='onpc-execution-fixture-v1', target='ubuntu', key='b' * 64,
                     allocation=str(allocation), device=info.st_dev, inode=info.st_ino,
                     journal=str(journal), journal_device=journal_info.st_dev,
                     journal_inode=journal_info.st_ino, run=state['run'], build_identity='c' * 64)
    try:
        yield SimpleNamespace(root=tmp_path, journal=journal, allocation=allocation,
                              owner=owner, writer=writer, record=selection, state=state)
    finally:
        os.close(writer)
        os.close(owner)


@pytest.mark.parametrize('euid,claimed,environment,expected', [
    (1000, None, None, 1000), (1000, 1000, None, 1000),
    (0, 1000, '1000', 1000), (0, None, '1000', 1000),
    (1000, 1001, None, None), (0, 1001, '1000', None),
    (0, 1000, None, None), (0, 1000, '0', None),
    (0, 1000, '+1000', None), (0, 1000, '١٠٠٠', None),
    (1000, True, None, None),
])
def test_actual_process_authentication_cannot_be_overridden(monkeypatch, euid, claimed,
                                                           environment, expected):
    monkeypatch.setattr(storage.os, 'geteuid', lambda: euid)
    if environment is None:
        monkeypatch.delenv('PKEXEC_UID', raising=False)
    else:
        monkeypatch.setenv('PKEXEC_UID', environment)
    if expected is None:
        with pytest.raises(ValueError, match='caller'):
            storage._input_caller(claimed)
    else:
        assert storage._input_caller(claimed) == expected


def test_reader_pins_read_only_input_and_excludes_journal_writers(selected):
    payload = selected.allocation / 'payload'
    payload.write_bytes(b'immutable input')
    before = (selected.journal / 'current.json').read_bytes()
    with storage.authenticated_input(selected.record, root=selected.root) as fd:
        assert fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        member = os.open('payload', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            assert os.read(member, 100) == b'immutable input'
        finally:
            os.close(member)
        with pytest.raises(BlockingIOError):
            fcntl.flock(selected.writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert (selected.journal / 'current.json').read_bytes() == before
    assert payload.read_bytes() == b'immutable input'


def test_finished_run_remains_readable_only_while_descendant_holds_owner(selected):
    selected.state['finished'] = True
    (selected.journal / 'current.json').write_text(json.dumps(selected.state))
    with storage.authenticated_input(selected.record, root=selected.root):
        # Unrelated directory changes must not invalidate pinned input identity.
        (selected.root / 'unrelated').mkdir()
    fcntl.flock(selected.owner, fcntl.LOCK_UN)
    with pytest.raises(ValueError, match='owner is not active'):
        with storage.authenticated_input(selected.record, root=selected.root):
            pytest.fail('ownerless finished input accepted')


@pytest.mark.parametrize('field,value', [('target', []), ('journal', None),
                                        ('allocation', {}), ('device', True), ('run', 1)])
def test_malformed_selection_refuses_before_path_operations(selected, field, value):
    selected.record[field] = value
    with pytest.raises(ValueError, match='invalid selection'):
        with storage.authenticated_input(selected.record, root=selected.root):
            pytest.fail('malformed input accepted')


@pytest.mark.parametrize('fault', ['run', 'unknown', 'retired', 'identity', 'journal',
                                  'foreign-journal', 'owner-missing', 'writer-missing',
                                  'idle', 'allocation-replaced', 'symlink', 'permissions'])
def test_foreign_stale_or_unowned_input_is_refused_without_repair(selected, fault):
    record = copy.deepcopy(selected.record)
    if fault == 'run':
        record['run'] = 'd' * 32
    elif fault == 'unknown':
        selected.state['paths'] = []
    elif fault == 'retired':
        selected.state['paths'][0]['retired'] = dict(transaction='d' * 32,
            destination=str(selected.journal), run='e' * 32)
    elif fault == 'identity':
        record['inode'] += 1
    elif fault == 'journal':
        record['journal_inode'] += 1
    elif fault == 'foreign-journal':
        record['journal'] = str(selected.root / 'retention-foreign')
    elif fault in ('owner-missing', 'writer-missing'):
        (selected.journal / ('owner.lock' if fault == 'owner-missing' else 'writer.lock')).unlink()
    elif fault == 'idle':
        fcntl.flock(selected.owner, fcntl.LOCK_UN)
    elif fault in ('allocation-replaced', 'symlink'):
        original = selected.allocation.with_name('preserved')
        selected.allocation.rename(original)
        if fault == 'symlink':
            selected.allocation.symlink_to(original)
        else:
            selected.allocation.mkdir(mode=0o700)
    elif fault == 'permissions':
        selected.allocation.chmod(0o755)
    (selected.journal / 'current.json').write_text(json.dumps(selected.state))
    before = (selected.journal / 'current.json').read_bytes()
    with pytest.raises((ValueError, OSError)):
        with storage.authenticated_input(record, root=selected.root):
            pytest.fail('unsafe input accepted')
    assert (selected.journal / 'current.json').read_bytes() == before
    if fault in ('owner-missing', 'writer-missing'):
        assert not (selected.journal / ('owner.lock' if fault == 'owner-missing' else 'writer.lock')).exists()


@pytest.mark.parametrize('fault', ['allocation', 'owner', 'writer', 'journal', 'owner-loss', 'journal-write'])
def test_replacement_or_owner_loss_during_read_preserves_input_and_refuses(selected, fault):
    with pytest.raises(ValueError, match='input:'):
        with storage.authenticated_input(selected.record, root=selected.root):
            if fault == 'owner-loss':
                fcntl.flock(selected.owner, fcntl.LOCK_UN)
            elif fault == 'journal-write':
                with (selected.journal / 'current.json').open('ab') as stream:
                    stream.write(b' ')
            else:
                target = (selected.allocation if fault == 'allocation' else
                          selected.journal / {'owner': 'owner.lock', 'writer': 'writer.lock',
                                              'journal': 'current.json'}[fault])
                target.rename(target.with_name(target.name + '.preserved'))
                if fault == 'allocation':
                    target.mkdir(mode=0o700)
                else:
                    target.write_bytes(b'replacement')
                    target.chmod(0o600)
    assert selected.allocation.exists()


@pytest.mark.parametrize('fault', ['foreign-owner', 'mount'])
def test_foreign_owner_and_mount_refuse_before_yield(selected, monkeypatch, fault):
    info = selected.allocation.stat()
    if fault == 'foreign-owner':
        original = storage.os.fstat
        def foreign(fd):
            value = original(fd)
            if value.st_ino == info.st_ino and value.st_dev == info.st_dev:
                return SimpleNamespace(**{name: (value.st_uid + 1 if name == 'st_uid' else getattr(value, name))
                    for name in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink')})
            return value
        monkeypatch.setattr(storage.os, 'fstat', foreign)
    else:
        original = retention.mount_id
        monkeypatch.setattr(retention, 'mount_id', lambda fd:
            'foreign-mount' if os.fstat(fd).st_ino == info.st_ino else original(fd))
    with pytest.raises(ValueError, match='input:'):
        with storage.authenticated_input(selected.record, root=selected.root):
            pytest.fail('foreign input accepted')


def test_verification_failure_is_propagated_without_adopting_partial_input(selected):
    partial = selected.allocation / 'incomplete'
    partial.write_bytes(b'preserve interrupted publication')
    with pytest.raises(ValueError, match='fixture:completion'):
        with storage.authenticated_input(selected.record, root=selected.root):
            # Content validation belongs to the fixture reader using this fd.
            raise ValueError('fixture:completion')
    assert partial.read_bytes() == b'preserve interrupted publication'


def test_history_claim_cannot_be_adopted_by_current_run(selected):
    selected.state['history'] = [dict(run='d' * 32, paths=selected.state['paths'])]
    selected.state['paths'] = []
    (selected.journal / 'current.json').write_text(json.dumps(selected.state))
    with pytest.raises(ValueError, match='not registered'):
        with storage.authenticated_input(selected.record, root=selected.root):
            pytest.fail('historical claim adopted')
