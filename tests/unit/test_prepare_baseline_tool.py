"""Standalone baseline replacement cannot skip password, privilege or tools refresh."""
from tests.support.vm_registry import vm_name
from contextlib import nullcontext
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import vm_selection

from tests.support.paths import ROOT

VM_ARGS = ['--vm', vm_name()]


@pytest.fixture
def launcher():
    loaded = runpy.run_path(str(ROOT / 'tools/prepare-vm'))
    return loaded['main'].__globals__


@pytest.fixture
def authorized(launcher, monkeypatch):
    monkeypatch.setattr(launcher['os'], 'geteuid', lambda: 1000)
    monkeypatch.setitem(launcher, 'read_password', lambda root: 'fixture-password')
    monkeypatch.setitem(launcher, 'check', Mock())
    return launcher


def test_invalid_options_are_refused_before_any_work(authorized):
    authorized['check'].side_effect = AssertionError('authorization attempted')
    with pytest.raises(SystemExit) as error:
        authorized['main'](['--reset'])
    assert error.value.code == 2
    authorized['check'].assert_not_called()


def test_root_invocation_never_requests_authorization(authorized, monkeypatch, capsys):
    monkeypatch.setattr(authorized['os'], 'geteuid', lambda: 0)
    authorized['check'].side_effect = AssertionError('authorization attempted')
    assert authorized['main'](['--mode', 'manual', *VM_ARGS]) == 2
    assert 'unprivileged' in capsys.readouterr().err
    authorized['check'].assert_not_called()


def test_missing_password_fails_before_privilege_dispatch(launcher, tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(launcher, 'ROOT', tmp_path)
    monkeypatch.setattr(launcher['os'], 'geteuid', lambda: 1000)
    check = Mock(side_effect=AssertionError('authorization attempted'))
    monkeypatch.setitem(launcher, 'check', check)
    run = Mock(side_effect=AssertionError('pkexec attempted'))
    monkeypatch.setattr(launcher['subprocess'], 'run', run)
    assert launcher['main'](['--mode', 'manual', *VM_ARGS]) == 2
    assert 'TEST_ACCOUNT_PASSWORD' in capsys.readouterr().err
    check.assert_not_called()
    run.assert_not_called()


def test_denied_authorization_never_starts_pkexec(authorized, monkeypatch, capsys):
    authorized['check'].side_effect = ValueError('noninteractive authorization unavailable')
    run = Mock(side_effect=AssertionError('pkexec attempted'))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'manual', *VM_ARGS]) == 2
    assert 'noninteractive' in capsys.readouterr().err
    run.assert_not_called()
    authorized['check'].assert_called_once_with(authorized['HELPER'])


def test_declined_preparation_does_not_refresh_helpers(authorized, monkeypatch, capsys):
    import test_activity
    import vm_pool

    # The declined result belongs to preparation, not reservation authorization.
    # Keep real VM acquisition and launcher locks outside this dispatch check.
    monkeypatch.setattr(vm_pool, 'reservation', lambda name: nullcontext())
    monkeypatch.setattr(vm_pool, 'arguments', lambda: [])
    monkeypatch.setattr(test_activity, 'activity', lambda *args, **kwargs: nullcontext())
    run = Mock(return_value=SimpleNamespace(returncode=3))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'auto', *VM_ARGS]) == 0
    assert run.call_count == 1
    assert capsys.readouterr().out == 'prepare-vm: cancelled; no baseline snapshot was prepared.\n'


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
def test_cancelled_queue_confirmation_never_dispatches(authorized, monkeypatch, capsys, exception):
    monkeypatch.setattr(vm_selection, 'input', Mock(side_effect=exception), raising=False)
    run = Mock()
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'auto', '--vm', 'all']) == 0
    assert 'cancelled' in capsys.readouterr().out
    run.assert_not_called()
