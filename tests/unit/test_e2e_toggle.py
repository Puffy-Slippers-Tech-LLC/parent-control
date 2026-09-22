"""UI17 qualification routing, preparation and worker-order contracts."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import parent_setup_qualification
from parent_setup_qualification import ParentToggleQualification
from tests.support.perl import run_perl


def test_toggle_qualification_uses_the_fixed_installed_snapshot_and_selector(tmp_path):
    import check_e2e_toggle as check

    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentToggleQualification.journey(context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert journey.plan.worker_mode == 'parent_toggle'


def test_toggle_session_preparation_is_guarded_and_returns_the_vm_off(tmp_path, monkeypatch):
    transport = Mock()
    setup = Mock()
    monkeypatch.setattr(parent_setup_qualification.smoke.runner, 'address',
                        Mock(return_value='fixture-host'))
    monkeypatch.setattr(parent_setup_qualification.smoke, 'Transport',
                        Mock(return_value=transport))
    monkeypatch.setattr(parent_setup_qualification.smoke.installed_setup,
                        'InstalledSetup', Mock(return_value=setup))
    lease = Mock()
    lease.source.uuid = 'fixture-uuid'
    lease.view.domain_id = 7
    lease.state = {'run': 'a' * 32, 'phase': 'running', 'domain_id': 7}
    lease.save.side_effect = lambda phase: lease.state.update(phase=phase)
    context = SimpleNamespace(directory=tmp_path, host_key='fixture-key', lease=lease,
                              commands=Mock(), verified=Mock())

    qualification = ParentToggleQualification.__new__(ParentToggleQualification)
    qualification.prepare_context(context)

    lease.start.assert_called_once_with()
    setup.provision.assert_called_once_with(lease.guard)
    assert transport.call.call_args.args[0][-1] == 'prepare-toggle-session'
    lease.source.shutdown.assert_not_called()
    lease.stop.assert_called_once_with()
    lease.guard.assert_called_with(off=True)
    lease.save.assert_called_once_with('isolated')
    lifecycle = [call[0] for call in lease.mock_calls
                 if call[0] in ('start', 'stop', 'guard', 'save')]
    assert lifecycle == ['start', 'stop', 'guard', 'save']
    assert lease.view.domain_id is None
    assert lease.state['domain_id'] is None
    # Exercise the real post-preparation credential gate, without any secrets.
    # A powered-off VM with a stale running instance must not reach the worker.
    from fixture_credentials import FixtureCredentials
    credentials = FixtureCredentials.__new__(FixtureCredentials)
    credentials._ready, credentials._lease = True, lease
    credentials.variables = object()
    assert credentials.worker_secrets(lease) is credentials.variables


PERL_WORKER = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { push @main::events, ['reset']; }
sub select_console { push @main::events, ['console', @_]; }
sub record_info { push @main::events, ['record', $_[0]]; }
sub send_key { push @main::events, ['key', @_]; }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', @_]; }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable']; }
package main;
require onpc_parent_toggle;
my $exchange = sub {
    push @events, ['stage', $_[0]];
    die 'fixture:missing-focus' if $ENV{ONPC_TEST_MISSING_FOCUS}
        && $_[0] eq 'child-choice-highlighted';
    return {observed => $_[0], ui_focused => JSON::PP::true};
};
my $ok = eval { onpc_parent_toggle::run($exchange); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
''';


def test_toggle_worker_selects_the_child_before_toggling_and_consumes_every_result():
    result = json.loads(run_perl(PERL_WORKER).stdout)
    assert result['ok'], result['error']
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == [
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'wrong-control-refused', 'limit-enabled',
        'limit-disabled', 'limit-current', 'hidden-control-refused', 'disabled-settings',
    ]
    inputs = [event for event in result['events'] if event[0] in ('key', 'text', 'secret')]
    assert inputs == [['key', 'ret']]
    commit = result['events'].index(['key', 'ret'])
    assert result['events'][commit - 1] == ['stage', 'child-choice-highlighted']
    assert result['events'][commit + 1] == ['record', 'parent-toggle-parent-selected']


def test_toggle_worker_refuses_input_without_independent_choice_focus(monkeypatch):
    monkeypatch.setenv('ONPC_TEST_MISSING_FOCUS', '1')
    result = json.loads(run_perl(PERL_WORKER).stdout)
    assert not result['ok']
    assert 'fixture:missing-focus' in result['error']
    assert not any(event[0] in ('key', 'text', 'secret') for event in result['events'])
