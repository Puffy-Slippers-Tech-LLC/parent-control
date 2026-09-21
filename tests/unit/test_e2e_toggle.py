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
    lease.state = {'run': 'a' * 32}
    context = SimpleNamespace(directory=tmp_path, host_key='fixture-key', lease=lease,
                              commands=Mock(), verified=Mock())

    qualification = ParentToggleQualification.__new__(ParentToggleQualification)
    qualification.prepare_context(context)

    lease.start.assert_called_once_with()
    setup.provision.assert_called_once_with(lease.guard)
    assert transport.call.call_args.args[0][-1] == 'prepare-toggle-session'
    lease.source.shutdown.assert_called_once_with(lease.guard, requested=False)
    lease.guard.assert_called_with(off=True)


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
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', @_]; }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable']; }
package main;
require onpc_parent_toggle;
my $exchange = sub {
    push @events, ['stage', $_[0]];
    return {observed => $_[0]};
};
my $ok = eval { onpc_parent_toggle::run($exchange); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
''';


def test_toggle_worker_consumes_every_result_before_shutdown_without_extra_input():
    result = json.loads(run_perl(PERL_WORKER).stdout)
    assert result['ok'], result['error']
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages == [
        'parent-window', 'parent-selected', 'wrong-control-refused', 'limit-enabled',
        'limit-disabled', 'limit-current', 'hidden-control-refused', 'disabled-settings',
    ]
    assert not any(event[0] in ('key', 'text', 'secret') for event in result['events'])
