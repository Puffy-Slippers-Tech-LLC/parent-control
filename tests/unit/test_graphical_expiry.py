"""One-shot grant and asynchronous-observation contracts, with no real OS calls."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import system_graphical_expiry as expiry


@pytest.fixture
def seed_rig(monkeypatch, tmp_path):
    monkeypatch.setattr(expiry, 'FIXTURE', tmp_path)
    (tmp_path / 'prepared.json').write_text(json.dumps({'run': 'run', 'boot': 'old'}))
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'run'})
    monkeypatch.setattr(expiry, 'identities', lambda: {'child': 1001})
    monkeypatch.setattr(expiry, 'Path', lambda value: SimpleNamespace(read_text=lambda: 'new'))
    monkeypatch.setattr(expiry.pwd, 'getpwuid', lambda uid: SimpleNamespace(pw_name='fixture-child'))
    monkeypatch.setenv('PAM_TYPE', 'account')
    monkeypatch.setenv('PAM_SERVICE', 'gdm-autologin')
    monkeypatch.setenv('PAM_USER', 'fixture-child')
    monkeypatch.setattr(expiry.guest, 'run', Mock(return_value='a' * 32))
    monkeypatch.setattr(expiry.time, 'time', lambda: 10.1)
    monkeypatch.setattr(expiry.time, 'sleep', Mock())
    grant = Mock(return_value=11)
    monkeypatch.setattr(expiry, 'grant', grant)
    return tmp_path, grant


def test_seed_publishes_only_complete_result_and_never_regrants(seed_rig):
    path, grant = seed_rig
    def issue(*args):
        assert (path / 'seed-attempt.json').exists()
        assert not (path / 'seeded.json').exists()
        return 11
    grant.side_effect = issue
    expiry.seed()
    result = json.loads((path / 'seeded.json').read_text())
    assert result['remaining_seconds'] == 0.9
    assert result['boot'] == 'new'
    with pytest.raises(expiry.guest.GuestError, match='seed-already-complete'):
        expiry.seed()
    grant.assert_called_once_with(1001, 1)


def test_failed_seed_is_not_published_or_retried(seed_rig):
    path, grant = seed_rig
    grant.side_effect = RuntimeError('fixed test failure')
    with pytest.raises(RuntimeError, match='fixed test failure'):
        expiry.seed()
    assert not (path / 'seeded.json').exists()
    with pytest.raises(FileExistsError):
        expiry.seed()
    grant.assert_called_once()


def test_wait_requires_observation_and_keeps_one_deadline(monkeypatch):
    times = iter([0, 1, 91])
    monkeypatch.setattr(expiry.time, 'monotonic', lambda: next(times))
    pause = Mock()
    monkeypatch.setattr(expiry.time, 'sleep', pause)
    observe = Mock(return_value=False)
    with pytest.raises(expiry.guest.GuestError, match='test:missing'):
        expiry.wait_for(observe, 'test:missing')
    assert observe.call_count == 2
    pause.assert_called_once()


@pytest.mark.parametrize('properties', [
    'User=2000\nClass=user\nTTY=tty7',
    'User=1005\nClass=user\nTTY=tty3',
])
def test_foreground_fixture_refuses_an_occupied_vt_or_existing_other_session(monkeypatch, properties):
    monkeypatch.setattr(expiry.guest, 'guard', lambda: {'run': 'fixed-run'})
    monkeypatch.setattr(expiry, 'identities', lambda: {'other': 1005})
    run = Mock(side_effect=['9 2000 user seat0 tty7', properties])
    monkeypatch.setattr(expiry.guest, 'run', run)
    issue = Mock()
    monkeypatch.setattr(expiry, 'grant', issue)
    with pytest.raises(expiry.guest.GuestError, match='foreground-fixture-collision'):
        expiry.verify_other_foreground(1004, '4', Mock())
    assert all(c.args[0][0] == 'loginctl' for c in run.call_args_list)
    issue.assert_not_called()


@pytest.mark.parametrize(('hint', 'active'), [('no', True), ('yes', False)])
def test_lock_observer_preserves_hint_but_uses_native_activity(monkeypatch, hint, active):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'child_session', lambda uid: ('4', {'LockedHint': hint}))
    monkeypatch.setattr(expiry, 'account_property', lambda *args: 0)
    manager = Mock()
    manager._run_command.side_effect = [SimpleNamespace(stdout=value) for value in
        ('(true,)' if active else '(false,)', 'true', 'false')]
    state = expiry.screen_lock_observation(1004, '4', manager, Mock())
    assert state['screensaver_active'] is active
    assert state['logind_locked'] is (hint == 'yes')
    assert all(call.kwargs == {'require_live': True} for call in manager._run_command.call_args_list)


@pytest.mark.parametrize(('password_mode', 'enabled', 'disabled', 'category'), [
    (2, 'true', 'false', 'lock-policy-not-enforcing'),
    (0, 'false', 'false', 'lock-policy-not-enforcing'),
    (0, 'true', 'true', 'lock-policy-not-enforcing'),
    (0, 'unknown', 'false', 'lock-observation-response'),
])
def test_active_screensaver_alone_cannot_satisfy_lock_observer(
        monkeypatch, password_mode, enabled, disabled, category):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'child_session', lambda uid: ('4', {'LockedHint': 'yes'}))
    monkeypatch.setattr(expiry, 'account_property', lambda *args: password_mode)
    manager = Mock()
    manager._run_command.side_effect = [SimpleNamespace(stdout=value) for value in
                                       ('(true,)', enabled, disabled)]
    with pytest.raises(expiry.guest.GuestError, match=category):
        expiry.screen_lock_observation(1004, '4', manager, Mock())


def test_lock_observer_refuses_replacement_session_before_shell_query(monkeypatch):
    monkeypatch.setattr(expiry.guest, 'guard', Mock())
    monkeypatch.setattr(expiry, 'child_session', lambda uid: ('5', {'LockedHint': 'yes'}))
    manager = Mock()
    with pytest.raises(expiry.guest.GuestError, match='desktop-ended'):
        expiry.screen_lock_observation(1004, '4', manager, Mock())
    manager._run_command.assert_not_called()
