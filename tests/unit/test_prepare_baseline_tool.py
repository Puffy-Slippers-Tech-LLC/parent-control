"""Standalone baseline replacement cannot skip password, privilege or tools refresh."""
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT


@pytest.fixture
def launcher():
    loaded = runpy.run_path(str(ROOT / 'tools/prepare-baseline'))
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
    assert authorized['main'](['--mode', 'manual']) == 2
    assert 'unprivileged' in capsys.readouterr().err
    authorized['check'].assert_not_called()


def test_missing_password_fails_before_privilege_dispatch(launcher, tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(launcher, 'ROOT', tmp_path)
    monkeypatch.setattr(launcher['os'], 'geteuid', lambda: 1000)
    check = Mock(side_effect=AssertionError('authorization attempted'))
    monkeypatch.setitem(launcher, 'check', check)
    run = Mock(side_effect=AssertionError('pkexec attempted'))
    monkeypatch.setattr(launcher['subprocess'], 'run', run)
    assert launcher['main'](['--mode', 'manual']) == 2
    assert 'TEST_ACCOUNT_PASSWORD' in capsys.readouterr().err
    check.assert_not_called()
    run.assert_not_called()


def test_denied_authorization_never_starts_pkexec(authorized, monkeypatch, capsys):
    authorized['check'].side_effect = ValueError('noninteractive authorization unavailable')
    run = Mock(side_effect=AssertionError('pkexec attempted'))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'manual']) == 2
    assert 'noninteractive' in capsys.readouterr().err
    run.assert_not_called()
    authorized['check'].assert_called_once_with(authorized['HELPER'])


def test_failed_baseline_does_not_refresh_test_tools(authorized, monkeypatch, capsys):
    run = Mock(return_value=SimpleNamespace(returncode=1))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'manual']) == 1
    run.assert_called_once()
    assert run.call_args.args[0] == [
        '/usr/bin/pkexec', authorized['HELPER'], 'prepare-baseline', '--mode', 'manual']
    assert run.call_args.kwargs['env']['PATH'] == '/usr/sbin:/usr/bin:/sbin:/bin'
    output = capsys.readouterr()
    assert output.out == output.err == ''


@pytest.mark.parametrize('mode', ['auto', 'manual'])
def test_successful_baseline_refreshes_test_tools(authorized, monkeypatch, mode):
    run = Mock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)])
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', mode]) == 0
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == [
        '/usr/bin/pkexec', authorized['HELPER'], 'prepare-baseline', '--mode', mode]
    assert run.call_args_list[1].args[0] == [str(ROOT / 'setup.sh'), '--test-tools-only']
    assert run.call_args_list[1].kwargs['cwd'] == ROOT


def test_tools_refresh_failure_is_returned_after_baseline(authorized, monkeypatch):
    run = Mock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=23)])
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'manual']) == 23
    assert run.call_count == 2


@pytest.mark.parametrize('args', [[], ['--mode'], ['--mode', 'invalid'], ['--mode', '']])
def test_mode_is_required_with_friendly_help(authorized, capsys, args):
    with pytest.raises(SystemExit) as error:
        authorized['main'](args)
    assert error.value.code == 2
    output = capsys.readouterr().err
    assert '--mode auto' in output and '--mode manual' in output
    authorized['check'].assert_not_called()


def test_help_reuses_warning_bullets_without_red_color(launcher, capsys):
    from baseline_messages import mode_message
    with pytest.raises(SystemExit) as error:
        launcher['main'](['--help'])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert mode_message('auto') in output
    assert mode_message('manual') in output
    assert '\033[' not in output


def test_declined_preparation_does_not_refresh_helpers(authorized, monkeypatch):
    run = Mock(return_value=SimpleNamespace(returncode=3))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'auto']) == 0
    assert run.call_count == 1
