"""Standalone baseline replacement cannot skip password, privilege or tools refresh."""
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.support.paths import ROOT

VM_ARGS = ['--vm', 'onpc-Ubuntu26.04']


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


def test_failed_baseline_does_not_refresh_test_tools(authorized, monkeypatch, capsys):
    run = Mock(return_value=SimpleNamespace(returncode=1))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'manual', *VM_ARGS]) == 1
    run.assert_called_once()
    assert run.call_args.args[0] == [
        '/usr/bin/pkexec', '--keep-cwd', authorized['HELPER'], 'prepare-baseline', '--mode', 'manual', *VM_ARGS]
    assert run.call_args.kwargs['cwd'] == ROOT
    assert run.call_args.kwargs['env']['PATH'] == '/usr/sbin:/usr/bin:/sbin:/bin'
    output = capsys.readouterr()
    assert output.out == output.err == ''


@pytest.mark.parametrize('mode', ['auto', 'manual'])
@pytest.mark.parametrize('assume_yes', [False, True])
def test_successful_baseline_refreshes_test_tools(authorized, monkeypatch, mode, assume_yes, capsys):
    confirmation_args = ['--y'] if assume_yes else []
    run = Mock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)])
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', mode, *VM_ARGS, *confirmation_args]) == 0
    assert run.call_count == 2
    assert run.call_args_list[0].args[0] == [
        '/usr/bin/pkexec', '--keep-cwd', authorized['HELPER'], 'prepare-baseline', '--mode', mode,
        *confirmation_args, *VM_ARGS]
    assert run.call_args_list[1].args[0] == [str(ROOT / 'setup.sh'), '--test-tools-only']
    assert run.call_args_list[1].kwargs['cwd'] == ROOT
    assert 'onpc_baseline prepared and accepted for onpc-Ubuntu26.04' in capsys.readouterr().out


def test_tools_refresh_failure_is_returned_after_baseline(authorized, monkeypatch):
    run = Mock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=23)])
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'manual', *VM_ARGS]) == 23
    assert run.call_count == 2


@pytest.mark.parametrize('args', [[], ['--mode'], ['--mode', 'invalid'], ['--mode', ''], ['--y']])
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
    assert '--y' in output and 'Manual work: omit --y' in output
    assert '\033[' not in output


def test_declined_preparation_does_not_refresh_helpers(authorized, monkeypatch, capsys):
    run = Mock(return_value=SimpleNamespace(returncode=3))
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'auto', *VM_ARGS]) == 0
    assert run.call_count == 1
    assert capsys.readouterr().out == 'prepare-baseline: cancelled; no baseline snapshot was prepared.\n'


def test_missing_vm_prompts_in_config_order_before_dispatch(authorized, monkeypatch, capsys):
    names = list(authorized['registry']())
    def answer(prompt):
        output = capsys.readouterr().out
        for number, name in enumerate(names, 1):
            assert f'{number}. {name}' in output
        assert output.index(names[0]) < output.index(names[1])
        authorized['check'].assert_not_called()
        return '2'
    monkeypatch.setitem(authorized, 'input', answer)
    def dispatch(command, **kwargs):
        assert command[-2:] == ['--vm', names[1]]
        print('baseline warnings')
        return SimpleNamespace(returncode=3)
    monkeypatch.setattr(authorized['subprocess'], 'run', dispatch)
    assert authorized['main'](['--mode', 'auto']) == 0
    assert capsys.readouterr().out == ('baseline warnings\n'
                                     'prepare-baseline: cancelled; no baseline snapshot was prepared.\n')


def test_vm_prompt_retries_invalid_numbers(launcher, monkeypatch, capsys):
    monkeypatch.setitem(launcher, 'registry', lambda: {'first-vm': None, 'second-vm': None})
    answers = iter(['', 'first-vm', '0', '3', '-1', '1.5', ' 2 '])
    monkeypatch.setitem(launcher, 'input', lambda prompt: next(answers))
    assert launcher['choose_vm']() == 'second-vm'
    assert capsys.readouterr().out.count('Please enter a number') == 6


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
def test_cancelled_vm_selection_never_dispatches(authorized, monkeypatch, capsys, exception):
    monkeypatch.setitem(authorized, 'input', Mock(side_effect=exception))
    run = Mock()
    monkeypatch.setattr(authorized['subprocess'], 'run', run)
    assert authorized['main'](['--mode', 'auto']) == 2
    assert 'VM selection cancelled' in capsys.readouterr().err
    authorized['check'].assert_not_called()
    run.assert_not_called()


def test_explicit_vm_never_prompts(authorized, monkeypatch):
    monkeypatch.setitem(authorized, 'input', Mock(side_effect=AssertionError('unexpected prompt')))
    monkeypatch.setattr(authorized['subprocess'], 'run', Mock(return_value=SimpleNamespace(returncode=3)))
    assert authorized['main'](['--mode', 'auto', *VM_ARGS]) == 0


@pytest.mark.parametrize('action', ['down', 'up', 'number', 'mouse', 'scroll-up', 'scroll-down'])
def test_terminal_choice_updates_bold_row_and_number_before_enter(monkeypatch, action):
    import curses
    import vm_selection
    for name in ('mousemask', 'mouseinterval', 'curs_set'):
        monkeypatch.setattr(curses, name, Mock())
    events = {
        'down': curses.KEY_DOWN, 'up': curses.KEY_UP, 'number': '2',
        'mouse': curses.KEY_MOUSE, 'scroll-up': curses.KEY_MOUSE, 'scroll-down': curses.KEY_MOUSE,
    }
    buttons = {'mouse': curses.REPORT_MOUSE_POSITION, 'scroll-up': curses.BUTTON4_PRESSED,
               'scroll-down': curses.BUTTON5_PRESSED}
    monkeypatch.setattr(curses, 'getmouse', lambda: (0, 5, 2, 0, buttons.get(action, 0)))
    keys = iter([events[action], '\n'])
    screen = Mock()
    screen.getmaxyx.return_value = (24, 100)
    screen.get_wch.side_effect = lambda: next(keys)
    frames = []
    screen.erase.side_effect = lambda: frames.append([])
    screen.addnstr.side_effect = lambda *args: frames[-1].append(args)
    selected = vm_selection.choice_screen(screen, ['Ubuntu', 'Fedora'])
    expected = 0 if action == 'scroll-up' else 1
    assert selected == expected
    assert frames[-1][selected + 1][-1] == curses.A_BOLD
    assert frames[-1][2 - selected][-1] == curses.A_NORMAL
    assert frames[-1][3][2] == f'Select VM [1-2]: {selected + 1}'


def test_terminal_choice_restores_mouse_reporting_on_cancel(monkeypatch, capsys):
    import curses
    import vm_selection
    monkeypatch.setattr(curses, 'wrapper', Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(ValueError, match='VM selection cancelled'):
        vm_selection.interactive_choice(['Ubuntu', 'Fedora'])
    assert capsys.readouterr().out.endswith('\033[?1003l')


def test_tty_chooser_uses_interactive_selection(launcher, monkeypatch):
    monkeypatch.setattr(launcher['sys'].stdin, 'isatty', lambda: True)
    monkeypatch.setattr(launcher['sys'].stdout, 'isatty', lambda: True)
    monkeypatch.setenv('TERM', 'xterm-256color')
    chooser = Mock(return_value=1)
    monkeypatch.setitem(launcher, 'interactive_choice', chooser)
    names = list(launcher['registry']())
    assert launcher['choose_vm']() == names[1]
    chooser.assert_called_once_with(names)
