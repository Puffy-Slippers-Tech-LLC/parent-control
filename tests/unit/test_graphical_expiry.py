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
