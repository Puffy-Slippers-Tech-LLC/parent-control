"""Private source/evidence doubles and bounded waited Perl; no VM or settings."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import check_graphical_smoke as smoke
import overlay_reminders as reminders
from owned_commands import CommandError
from tests.support.e2e_kiosk import WORKER
from tests.support.modules import load_module
from tests.support.paths import ROOT
from tests.support.perl import run_perl


def test_selector_prepares_current_inputs_and_reuses_installed_snapshot(monkeypatch, tmp_path):
    import package_inputs
    import test_storage
    import tools.package_inputs as packaged_inputs
    import tools.test_storage as storage
    import tools.test_commands as commands
    from parent_setup_qualification import OverlayReminderEditingQualification, KioskEntryQualification
    from tools.test_storage import named_input

    (tmp_path / 'package-input').write_text('stable qualification source')
    for module in (storage, test_storage):
        monkeypatch.setattr(module, 'ROOT', tmp_path)
    for module in (packaged_inputs, package_inputs):
        monkeypatch.setattr(module, 'paths', lambda _: [Path('package-input')])
    entry = load_module('overlay_reminder_registration_fixture',
        ROOT / 'tests/integration/check_e2e_overlay_reminder_editing.py')
    launch = Mock(return_value=0)
    monkeypatch.setattr(entry, 'smoke', launch)
    assert entry.main() == 0
    launch.assert_called_once_with(assets=entry.ASSETS, provision_credentials=True,
                                  overlay_reminder_editing=True)
    assert entry.ASSETS == named_input(package_source=True)
    assert OverlayReminderEditingQualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    context = SimpleNamespace(directory=tmp_path)
    assert OverlayReminderEditingQualification.journey(context, Mock()).plan is reminders.PLAN
    assert context.installed_snapshot.startswith('onpc-')
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: False)
    allocate = Mock(return_value=str(entry.ASSETS))
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    command = commands.qualification_artifact_command(ROOT, 'integration',
        ['check_e2e_overlay_reminder_editing'])
    assert command[command.index('--output') + 1] == str(entry.ASSETS)
    assert '--upgrade-inputs' not in command
    allocate.assert_called_once_with(str(entry.ASSETS))


@pytest.mark.parametrize('name', ['check_e2e_overlay_reminder_editing',
                                 'check_e2e_overlay_reminder_editing.py'])
def test_registered_cached_inputs_are_verified_without_reallocation(monkeypatch, name):
    import tools.test_commands as commands
    from tools.test_storage import named_input
    from vm_selection import arguments

    expected = str(named_input(package_source=True))
    validate, allocate = Mock(), Mock()
    monkeypatch.setattr(commands.os.path, 'lexists', lambda _: True)
    monkeypatch.setattr(commands, 'artifact_path', validate)
    monkeypatch.setattr(commands, 'allocate_artifact_output', allocate)
    assert commands.qualification_artifact_command(ROOT, 'integration', [name]) == commands.python_file(
        ROOT, 'tools/vm_artifacts.py', '--candidate', expected, '--output', expected, *arguments())
    validate.assert_called_once_with(expected)
    allocate.assert_not_called()


@pytest.mark.parametrize('extra', [
    {'assets': None}, {'provision_credentials': False}, {'fresh_desktop': 'parent'},
    {'lock_surface': 'command'}, {'parent_entry': 'retained'}, {'approval_flow': 'cancel'},
    *({name: True} for name in ('overlay_language', 'kiosk_language', 'parent_language',
        'challenges', 'parent_setup', 'parent_toggle', 'native_fixtures', 'request_duration',
        'package_upgrade', 'restart_notice', 'file_chooser', 'kiosk_notification_wellbeing')),
])
def test_exclusive_mode_refuses_invalid_combinations_before_setup(monkeypatch, extra):
    credentials = Mock(side_effect=AssertionError('setup must not start'))
    monkeypatch.setattr(smoke, 'FixtureCredentials', credentials)
    arguments = {'assets': 'inputs', 'provision_credentials': True,
                 'overlay_reminder_editing': True, **extra}
    with pytest.raises(CommandError, match='smoke:.*-prerequisites'):
        smoke.main(**arguments)
    credentials.assert_not_called()


@pytest.mark.parametrize('value', [None, 1, 'true'])
def test_mode_requires_a_canonical_boolean_before_setup(monkeypatch, value):
    credentials = Mock(side_effect=AssertionError('setup must not start'))
    monkeypatch.setattr(smoke, 'FixtureCredentials', credentials)
    with pytest.raises(CommandError, match='smoke:overlay-reminder-editing-prerequisites'):
        smoke.main(assets='inputs', provision_credentials=True, overlay_reminder_editing=value)
    credentials.assert_not_called()


@pytest.mark.parametrize('refuse', ['', 'setup-detached'])
def test_actual_smoke_dispatch_retains_detached_setup_before_worker(monkeypatch, refuse):
    source = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    if refuse:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refuse)
    program = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'basetest.pm'} = 1; }
package basetest;
sub new { bless {}, shift }
package testapi;
sub import { no strict 'refs'; *{caller() . '::console'} = \&console; }
sub console { push @main::events, ['console', $_[0]]; bless {}, 'Console' }
package Console;
sub disable { push @main::events, ['disabled']; }
package main;
my $source = decode_json(SOURCE_JSON);
while ($source =~ /use (onpc_\w+)/g) { $INC{"$1.pm"} = 1; }
eval 'package DispatchProbe;' . $source;
die $@ if $@;
{
    no warnings 'redefine';
    *DispatchProbe::exchange = sub {
        push @events, ['stage', $_[0]];
        die 'fixture:refused' if $_[0] eq ($ENV{ONPC_TEST_REFUSE_STAGE} // '');
        return {overlay_reminder_editing => JSON::PP::true, invocations => ['finite'],
                challenge_bindings => {login => ['child', 'one', 'two']}};
    };
    *onpc_request_flow::overlay_reminder_editing = sub {
        push @events, ['worker', $_[1], $_[2]];
        die 'fixture:callback' unless ref($_[0]) eq 'CODE';
    };
}
my $ok = eval { DispatchProbe::run(); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''
    literal = "'" + json.dumps(source).replace('\\', '\\\\').replace("'", "\\'") + "'"
    result = json.loads(run_perl(program.replace('SOURCE_JSON', literal)).stdout)
    expected = [['stage', 'ready'], ['console', 'sut'], ['disabled'], ['stage', 'setup-detached']]
    if not refuse:
        expected.append(['worker', ['finite'], {'login': ['child', 'one', 'two']}])
    assert result['events'] == expected
    assert bool(result['ok']) is (not refuse), result['error']


@pytest.mark.parametrize('refuse', ['', *reminders.SCREENS])
def test_complete_real_worker_order_titles_and_refusal_stop(monkeypatch, refuse):
    if refuse:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refuse)
    worker = WORKER.replace('onpc_kiosk_eligible_choices', 'onpc_request_flow')
    worker = worker.replace('onpc_request_flow::run', 'onpc_request_flow::overlay_reminder_editing')
    worker = worker.replace('sub record_info { }',
        "sub record_info { push @main::events, ['title', $_[0]] }")
    worker = worker.replace('return {observed => $stage};', r'''
        my %proofs = (
            'recipient-qualified' => ['parent-login', 'parent', 'qualified'],
            'recipient-rechecked' => ['parent-login', 'parent', 'rechecked'],
            'fresh-child-recipient-qualified' => ['child-login', 'child', 'qualified'],
            'fresh-child-recipient-rechecked' => ['child-login', 'child', 'rechecked'],
            'return-qualified' => ['return-parent', 'parent', 'qualified'],
            'return-rechecked' => ['return-parent', 'parent', 'rechecked']);
        if (exists $proofs{$stage}) {
            my ($id, $role, $check) = @{$proofs{$stage}};
            return {observed => $stage, challenge => {id => $id, role => $role,
                surface => 'gdm', check => $check}};
        }
        return {observed => $stage};''')
    challenges = '{' + ', '.join('"' + key + '" => ' + json.dumps(list(value))
        for key, value in reminders.PLAN.challenges.items()) + '}'
    worker = worker.replace('    });', '    }, ' + json.dumps(list(reminders.PLAN.invocations))
                            + ', ' + challenges + ');')
    result = json.loads(run_perl(worker).stdout)
    expected = list(reminders.SCREENS)
    if refuse:
        expected = expected[:expected.index(refuse) + 1]
    assert bool(result['ok']) == (not refuse), result['error']
    assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
    assert [event[1] for event in result['events'] if event[0] == 'title' and event[1] != 'shutdown'] == [
        'overlay-reminders-' + stage for stage in expected]
    assert (['power', 'off'] in result['events']) is (not refuse)
    if 'initial-form' in expected:
        boundary = result['events'].index(['stage', 'initial-form'])
        end = next((index for index, event in enumerate(result['events'][boundary + 1:], boundary + 1)
                    if event == ['stage', 'child-switch-user']), len(result['events']))
        assert not any(event[0] in ('key', 'secret') for event in result['events'][boundary + 1:end])
