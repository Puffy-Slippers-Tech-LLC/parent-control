"""Real keyring qualification stays bound to one guarded, owned attempt."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_e2e_desktop_keyring as check
import check_graphical_smoke as smoke
import keyring_prompt_fixture as fixture
from fresh_desktop import KeyringDesktopJourney, prepare_keyring
from owned_commands import CommandError
from parent_setup_qualification import KeyringStandardDesktopQualification
from private_artifacts import EvidenceError
from tests.support.perl import run_perl


PROVIDER_METADATA = {'packages': {'gcr': '3.41.2-1', 'gnome-shell': '50.1-1'},
                     'provider_locale': 'en_US.UTF-8', 'keyboard_sources': [['xkb', 'us']]}
READY = (json.dumps(PROVIDER_METADATA, sort_keys=True) + '\n').encode()


def test_keyring_plan_keeps_gdm_safety_and_distinct_prompt_observation():
    context = SimpleNamespace()
    journey = KeyringStandardDesktopQualification.journey(
        KeyringStandardDesktopQualification.__new__(KeyringStandardDesktopQualification),
        context, Mock())
    assert isinstance(journey, KeyringDesktopJourney)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert journey.plan.screen_tags['wrong-recipient-refused'] == (
        'ui:gdm-standard-wrong-recipient-refused')
    assert list(journey.plan.screen_tags)[-4:] == [
        'standard-recipient-qualified', 'standard-recipient-rechecked',
        'desktop', 'keyring-cancelled-desktop']
    assert journey.plan.stage_actions == {'desktop': 'prepare-keyring'}
    assert journey.plan.screen_tags['keyring-cancelled-desktop'] == 'ui:keyring-cancel-standard'


def test_fixed_selector_uses_separate_attempts_and_stops_after_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 0)
    assert check.main() == 0
    assert calls == [
        {'assets': check.ASSETS, 'provision_credentials': True,
         'fresh_desktop': role}
        for role in ('parent', 'standard-keyring')]
    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    calls.clear()
    monkeypatch.setattr(check, 'smoke', lambda **kwargs: calls.append(kwargs) or 1)
    assert check.main() == 1
    assert len(calls) == 1
    with pytest.raises(CommandError, match='smoke:fresh-desktop-prerequisites'):
        smoke.main(fresh_desktop='standard-keyring')


def test_keyring_preparation_uses_guarded_fixed_guest_command():
    transport = SimpleNamespace(call=Mock(return_value=READY))
    journey = SimpleNamespace(transport=transport)
    guard = Mock()
    assert prepare_keyring(journey, guard) == {'profile': 'locked-login-keyring', **PROVIDER_METADATA}
    assert guard.call_count == 2
    argv = transport.call.call_args.args[0]
    assert argv == ['/usr/bin/python3', '-I', '-', 'standard']
    assert transport.call.call_args.kwargs['timeout'] == 60
    assert b'org.gnome.keyring.PrivatePrompter' in transport.call.call_args.kwargs['input']
    transport.call.return_value = b'wrong-profile\n'
    with pytest.raises(EvidenceError, match='keyring-fixture:preparation'):
        prepare_keyring(journey, guard)


def test_guest_fixture_uses_owned_bus_and_secret_service_without_extra_tool(monkeypatch, capsys):
    account = SimpleNamespace(pw_name='onpc-child-jordan', pw_uid=1002, pw_gid=1002,
                              pw_dir='/home/onpc-child-jordan')
    monkeypatch.setattr(fixture.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(fixture.sys, 'argv', ['keyring_prompt_fixture.py', 'standard'])
    monkeypatch.setattr(fixture.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(fixture.os, 'stat', lambda path, follow_symlinks: SimpleNamespace(
        st_uid=1002, st_mode=0o040700 if path == '/run/user/1002' else 0o140700))
    launch = Mock()
    read_fd, write_fd = fixture.os.pipe()
    fixture.os.write(write_fd, READY)
    fixture.os.close(write_fd)
    launch.return_value.stdout = fixture.os.fdopen(read_fd, 'rb')
    monkeypatch.setattr(fixture.subprocess, 'Popen', launch)
    fixture.main()
    command = launch.call_args.args[0]
    assert launch.call_args.kwargs['user'] == 1002
    assert launch.call_args.kwargs['group'] == 1002
    assert launch.call_args.kwargs['extra_groups'] == []
    assert launch.call_args.kwargs['env']['HOME'] == account.pw_dir
    assert command[-4:-1] == ['/usr/bin/python3', '-I', '-c']
    assert command[-1] == fixture.CHALLENGE
    assert 'secret-tool' not in command[-1]
    for method in ('ReadAlias', 'Lock', 'Unlock', 'Prompt'):
        assert "'" + method + "'" in command[-1]
    assert launch.call_args.kwargs['start_new_session'] is True
    assert capsys.readouterr().out == READY.decode()


@pytest.mark.parametrize('replaced', [True, False])
def test_challenge_binds_real_gcr_before_requesting_one_prompt(monkeypatch, capsys, replaced):
    from gi.repository import Gio, GLib
    import signal
    import time
    collection = '/org/freedesktop/secrets/collection/login'
    prompt = '/org/freedesktop/secrets/prompt/test'
    replies = [GLib.Variant('(u)', (1,)),
               GLib.Variant('(s)', (':1.42',)),
               GLib.Variant('(s)', (':1.42' if replaced else ':1.7',)),
               GLib.Variant('(u)', (4242,)),
               GLib.Variant('(o)', (collection,)),
               GLib.Variant('(v)', (GLib.Variant('s', 'Login'),)),
               GLib.Variant('(aoo)', ([collection], '/')),
               GLib.Variant('(aoo)', ([], prompt)), GLib.Variant('()', ())]
    bus = Mock()
    bus.call_sync.side_effect = replies
    monkeypatch.setattr(Gio, 'bus_get_sync', Mock(return_value=bus))
    monkeypatch.setattr(GLib, 'MainLoop', Mock())
    monkeypatch.setattr(GLib, 'timeout_add_seconds', Mock())
    monkeypatch.setattr(signal, 'alarm', Mock())
    monkeypatch.setattr(time, 'monotonic', Mock(side_effect=[0, 6]))
    read_environment = Mock(return_value=b'LANG=C.UTF-8\0LC_MESSAGES=en_US.UTF-8\0PRIVATE=hidden\0')
    monkeypatch.setattr(Path, 'read_bytes', read_environment)
    monkeypatch.setattr(fixture.subprocess, 'check_output', Mock(
        side_effect=['3.41.2-1', '50.1-1']))
    settings = Mock()
    settings.get_value.return_value = GLib.Variant('a(ss)', [('xkb', 'us')])
    monkeypatch.setattr(Gio.Settings, 'new', Mock(return_value=settings))
    exec(fixture.CHALLENGE, {})
    if not replaced:
        assert capsys.readouterr().out == 'keyring-fixture:failed:gcr-provider\n'
        assert bus.call_sync.call_count == 3
        return
    assert capsys.readouterr().out == READY.decode()
    assert [call.args[3] for call in bus.call_sync.call_args_list] == [
        'StartServiceByName', 'GetNameOwner', 'GetNameOwner', 'GetConnectionUnixProcessID',
        'ReadAlias', 'Get', 'Lock', 'Unlock', 'Prompt']
    assert [call.args[4].unpack() for call in bus.call_sync.call_args_list[:3]] == [
        ('org.gnome.keyring.PrivatePrompter', 0),
        ('org.gnome.keyring.PrivatePrompter',), ('org.gnome.keyring.SystemPrompter',)]
    assert fixture.provider_metadata(READY) == PROVIDER_METADATA
    read_environment.assert_called_once_with()


@pytest.mark.parametrize('value', [None, [], {}, {'unexpected': 'private'},
    {**PROVIDER_METADATA, 'packages': ['gcr', 'gnome-shell']},
    {**PROVIDER_METADATA, 'provider_locale': 'private value\n'},
    {**PROVIDER_METADATA, 'keyboard_sources': []},
    {**PROVIDER_METADATA, 'keyboard_sources': ['xk']},
    {**PROVIDER_METADATA, 'keyboard_sources': [['unexpected', 'us']]},
    {**PROVIDER_METADATA, 'provider_locale': 'x' * 4097},
])
def test_provider_metadata_refuses_unbounded_or_unexpected_fields(value):
    with pytest.raises(ValueError, match='^keyring-fixture:provider-metadata$'):
        fixture.provider_metadata(json.dumps(value).encode())


def test_guest_fixture_rejects_unbound_role_before_process_launch(monkeypatch):
    run = Mock()
    monkeypatch.setattr(fixture.subprocess, 'Popen', run)
    monkeypatch.setattr(fixture.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(fixture.sys, 'argv', ['keyring_prompt_fixture.py', 'other'])
    with pytest.raises(SystemExit, match='keyring-fixture:arguments'):
        fixture.main()
    run.assert_not_called()


def test_keyring_worker_waits_for_prompt_cancel_after_one_login():
    source = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_parent.pm'} = 1; }
package testapi;
sub record_info { push @main::events, ['stage', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package onpc_parent;
sub login_functional { die 'wrong role' }
sub login_standard_functional { push @main::events, ['login', 'standard'] }
package main;
require onpc_fresh_desktop;
{ no warnings 'redefine'; *onpc_journey::seen = sub {
    push @main::events, ['checkpoint', $_[1]]; return {};
}; }
my $ok = eval { onpc_fresh_desktop::run(sub { die 'unexpected exchange' }, 'standard', 1); 1 };
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
    import json
    result = json.loads(run_perl(source).stdout)
    assert result['ok'], result['error']
    assert result['events'] == [
        ['login', 'standard'], ['checkpoint', 'keyring-cancelled-desktop'],
        ['disable'], ['power', 'off'], ['stage', 'shutdown']]
