"""Terminal and secret handling regressions without a live auth service."""

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests/integration'))
import system_caller as caller
sys.path.pop(0)


def agent():
    instance = caller.TextAgent.__new__(caller.TextAgent)
    instance.master = 10
    instance.pending = b''
    return instance


def test_terminal_fragments_preserve_next_response(monkeypatch):
    instance = agent()
    monkeypatch.setattr(caller.select, 'select', Mock(return_value=([10], [], [])))
    monkeypatch.setattr(caller.os, 'read', Mock(side_effect=[b'Pass', b'word: next']))
    assert instance._until(b'Password:') == b'Password:'
    assert instance.pending == b' next'


@pytest.mark.parametrize('terminal', [
    b'Authenticating as: wrong\nPassword:',
    b'Authenticating as: selected or wrong\nPassword:',
    b'selected\nPassword:',
])
def test_prompt_rejects_unselected_or_ambiguous_identity(monkeypatch, terminal):
    instance = agent()
    instance._until = Mock(return_value=terminal)
    monkeypatch.setattr(caller.pwd, 'getpwuid', lambda uid: SimpleNamespace(
        pw_name='selected' if uid == 1001 else 'wrong'))
    with pytest.raises(caller.guest.GuestError, match='agent:selected-identity'):
        instance.prompt(1001, 1002)


def test_password_never_written_when_terminal_echoes(monkeypatch):
    instance = agent()
    monkeypatch.setattr(caller.termios, 'tcgetattr', Mock(return_value=[0, 0, 0, caller.termios.ECHO]))
    monkeypatch.setattr(caller.os, 'write', Mock())
    with pytest.raises(caller.guest.GuestError, match='agent:echo-enabled'):
        instance.authenticate(caller.FixturePassword())
    caller.os.write.assert_not_called()


@pytest.mark.parametrize('succeeds,marker,category', [
    (True, b'AUTHENTICATION COMPLETE', None),
    (False, b'AUTHENTICATION FAILED', None),
    (True, b'AUTHENTICATION FAILED', 'denied'),
    (False, b'AUTHENTICATION COMPLETE', 'accepted'),
    (True, b'AUTHENTICATION CANCELED', 'cancelled'),
])
def test_authentication_reports_actual_terminal_outcome(monkeypatch, capsys,
                                                       succeeds, marker, category):
    instance = agent()
    password = caller.FixturePassword()
    monkeypatch.setattr(caller.termios, 'tcgetattr', Mock(return_value=[0, 0, 0, 0]))
    monkeypatch.setattr(caller.os, 'write', Mock(side_effect=lambda fd, data: len(data)))
    monkeypatch.setattr(caller.select, 'select', Mock(return_value=([10], [], [])))
    # Include private diagnostic material and fragmented outcome markers. None
    # may reach errors or console output, including on an unexpected result.
    monkeypatch.setattr(caller.os, 'read', Mock(side_effect=[
        b'private-user ' + password._value + b' ' + marker[:8], marker[8:] + b' next']))
    if category:
        with pytest.raises(caller.guest.GuestError) as error:
            instance.authenticate(password, succeeds=succeeds)
        assert str(error.value) == 'agent:unexpected-' + category
    else:
        instance.authenticate(password, succeeds=succeeds)
    assert instance.pending == b' next'
    output = capsys.readouterr()
    assert 'private-user' not in output.out
    assert password._value.decode() not in output.out
    assert output.err == ''


def test_terminal_outcomes_are_consumed_in_stream_order():
    instance = agent()
    instance.pending = b'AUTHENTICATION FAILED AUTHENTICATION COMPLETE'
    assert instance._until(b'AUTHENTICATION COMPLETE', alternatives=(b'AUTHENTICATION FAILED',)) == \
        b'AUTHENTICATION FAILED'
    assert instance.pending == b' AUTHENTICATION COMPLETE'


@pytest.mark.parametrize('diagnostic,category', [
    (b'polkit-agent-helper-1: pam_authenticate failed:', 'pam-authenticate'),
    (b'polkit-agent-helper-1: pam_acct_mgmt failed:', 'pam-account'),
    (b'polkit-agent-helper-1: error response to PolicyKit daemon:', 'authority-response'),
    (b'unknown helper error:', 'unclassified'),
])
def test_denied_helper_diagnostics_export_only_fixed_category(monkeypatch, capsys,
                                                             diagnostic, category):
    instance = agent()
    password = caller.FixturePassword()
    monkeypatch.setattr(caller.termios, 'tcgetattr', Mock(return_value=[0, 0, 0, 0]))
    monkeypatch.setattr(caller.os, 'write', Mock(side_effect=lambda fd, data: len(data)))
    instance.pending = (diagnostic + b' private-user ' + password._value +
                        b'\nAUTHENTICATION FAILED')
    with pytest.raises(caller.guest.GuestError) as error:
        instance.authenticate(password)
    assert str(error.value) == 'agent:unexpected-denied'
    assert capsys.readouterr() == (
        'onpc-system: stage=authentication outcome=denied\n'
        'onpc-system: stage=authentication-helper outcome=denied '
        f'category={category}\n', '')


def test_password_installation_uses_stdin_without_diagnostics(monkeypatch):
    import owned_commands
    controller = Mock(directory=None)
    factory = Mock(return_value=controller)
    monkeypatch.setattr(owned_commands, 'Commands', factory)
    monkeypatch.setattr(caller.guest, 'guard', Mock())
    monkeypatch.setattr(caller.pwd, 'getpwuid', Mock(return_value=SimpleNamespace(pw_name='fixture')))
    password = caller.FixturePassword()
    password.install(1001)
    args, kwargs = controller.run.call_args
    assert args == (['/usr/sbin/chpasswd'],)
    assert kwargs['input'].startswith(b'fixture:')
    assert controller.directory is None
    assert password._value not in repr(args).encode()


@pytest.mark.parametrize('terminal,expected', [
    (b'Error registering authentication agent: private-user :1.123', 'polkit-registration'),
    (b'agent-wrapper:executable-missing', 'executable-missing'),
    (b'Error registering authentication agent: Only unix-process and unix-session subjects',
     'unsupported-subject'),
    (b'private-user unexpected secret', 'startup-unknown'),
])
def test_startup_diagnostics_only_return_fixed_categories(monkeypatch, capsys, terminal, expected):
    instance = agent()
    monkeypatch.setattr(caller.select, 'select', Mock(side_effect=[([10], [], []), ([], [], [])]))
    monkeypatch.setattr(caller.os, 'read', Mock(return_value=terminal))
    assert instance._startup_category() == expected
    assert capsys.readouterr() == ('', '')


def test_agent_process_identity_reads_only_pinned_caller(monkeypatch):
    instance = caller.PersistentCaller.__new__(caller.PersistentCaller)
    instance.pidfd = 42
    instance.child = Mock(pid=12345)
    instance.child.poll.return_value = None
    paths = []

    def read_stat(path):
        paths.append(str(path))
        return '12345 (name with ) delimiter) S ' + '0 ' * 18 + '67890 0'

    monkeypatch.setattr(Path, 'read_text', read_stat)
    assert instance.agent_subject() == '12345,67890'
    assert paths == ['/proc/12345/stat']


@pytest.mark.parametrize('pin,statuses', [(None, [None]), (42, [1]), (42, [None, 1])])
def test_agent_process_identity_refuses_unpinned_or_exited_caller(monkeypatch, pin, statuses):
    instance = caller.PersistentCaller.__new__(caller.PersistentCaller)
    instance.pidfd = pin
    instance.child = Mock(pid=12345)
    instance.child.poll.side_effect = statuses
    monkeypatch.setattr(Path, 'read_text', Mock(return_value='12345 (caller) S ' + '0 ' * 18 + '67890'))
    with pytest.raises(caller.guest.GuestError, match='caller:agent-subject-'):
        instance.agent_subject()
