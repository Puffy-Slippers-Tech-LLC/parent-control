"""Destructive removal-fixture writes preserve unowned files and join workers."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_removal as removal


@pytest.mark.parametrize('substituted', [False, True])
def test_removal_state_stays_private_and_refuses_symlink(tmp_path, monkeypatch, substituted):
    monkeypatch.setattr(removal.guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'private').mkdir(mode=0o700)
    protected = tmp_path / 'protected'
    protected.write_text('keep')
    if substituted:
        removal.state_path().symlink_to(protected)
        with pytest.raises(removal.guest.GuestError, match='state-substituted'):
            removal.save_state({'accounts': [1004]})
        assert protected.read_text() == 'keep'
    else:
        removal.save_state({'accounts': [1004]})
        assert removal.state_path() == tmp_path / 'private/removal-state.json'
        assert removal.state_path().stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('fault', ['watcher', 'command'])
def test_aborted_watcher_always_joins_native_command_on_failure(tmp_path, monkeypatch, fault):
    events = []
    expected = {'uid': 1004}
    transaction = SimpleNamespace(directory=None, last_returncode=7)
    def run(argv, **kwargs):
        events.append('native')
        assert kwargs == {'check': False, 'timeout': 1800, 'merge_stderr': True}
        if fault == 'command':
            raise removal.guest.CommandError('native-failed')
        return b'native callback failure'
    transaction.run = run
    monkeypatch.setattr(removal.guest, 'Commands', lambda: transaction)
    monkeypatch.setattr(removal.guest, 'commands', SimpleNamespace(directory=tmp_path))
    monkeypatch.setattr(removal, 'removal_command', lambda: ['native-remove'])
    class Worker:
        def __init__(self, *, target, name):
            self.target = target
        def start(self):
            self.target()
        def is_alive(self):
            return True
        def join(self):
            events.append('joined')
    monkeypatch.setattr(removal.threading, 'Thread', Worker)
    ticks = iter([0, 1, 1801])
    monkeypatch.setattr(removal.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(removal.time, 'sleep', lambda value: None)
    def transition(uid):
        if fault == 'watcher':
            raise RuntimeError('watcher-failed')
        return {'snapshot': {'version': 1, 'accounts': [expected]},
                'native': [0, 0, [0, 0], [False, []]], 'extensions': [[], []],
                'policy_absent': list(removal.GENERATED_POLICY)}
    monkeypatch.setattr(removal, 'cleanup_transition', transition)
    with pytest.raises((RuntimeError, removal.guest.CommandError)):
        removal.observe_aborted_transaction(1004, expected, None, Mock())
    assert events == ['native', 'joined']


@pytest.mark.parametrize('replacement', ['content', 'inode', 'symlink'])
def test_refusal_hook_restoration_never_overwrites_replacement(tmp_path, monkeypatch, replacement):
    hook = tmp_path / 'hook'
    hook.write_bytes(b'original')
    identity = hook.stat()
    # The guest guard requires root; model only file ownership in this host test.
    native_fstat = os.fstat
    monkeypatch.setattr(removal.os, 'fstat', lambda fd: SimpleNamespace(
        st_mode=native_fstat(fd).st_mode, st_uid=0, st_nlink=native_fstat(fd).st_nlink,
        st_dev=native_fstat(fd).st_dev, st_ino=native_fstat(fd).st_ino))
    removal.write_hook(hook, identity, b'original', b'modified')
    if replacement == 'content':
        hook.write_bytes(b'foreign')
    else:
        hook.rename(tmp_path / 'old-hook')
        foreign = tmp_path / 'foreign'
        foreign.write_bytes(b'foreign')
        if replacement == 'symlink':
            hook.symlink_to(foreign)
        else:
            foreign.rename(hook)
    with pytest.raises(removal.guest.GuestError, match='hook-identity-changed'):
        removal.write_hook(hook, identity, b'modified', b'original')
    assert hook.read_bytes() == b'foreign'
