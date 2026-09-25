"""UI17 qualification routing, preparation and worker-order contracts."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

import parent_setup_qualification
from parent_setup_qualification import ParentToggleQualification
from tests.support.perl import run_perl


def test_toggle_qualification_uses_the_fixed_installed_snapshot_and_selector(tmp_path):
    import check_e2e_toggle as check
    import check_e2e_parent_save as save_check

    assert check.ASSETS == Path(__file__).resolve().parents[2] / 'output/test-runs/host/allocations/onpc-parent-setup-input'
    assert save_check.ASSETS == check.ASSETS
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
        'parent-selected', 'wrong-control-refused', 'wrong-child-refused',
        'limit-enabled', 'save-enabled', 'save-reopened', 'limit-disabled',
        'save-disabled', 'limit-current', 'hidden-control-refused', 'disabled-settings',
    ]
    inputs = [event for event in result['events'] if event[0] in ('key', 'text', 'secret')]
    assert inputs == [['key', 'ret']]
    commit = result['events'].index(['key', 'ret'])
    assert result['events'][commit - 1] == ['stage', 'child-choice-highlighted']
    assert result['events'][commit + 1] == ['record', 'parent-toggle-parent-selected']


def test_parent_save_is_the_fixed_argument_free_integration_selector():
    from tests.support.paths import ROOT

    source = (ROOT / 'tests/integration/check_e2e_parent_save.py').read_text()
    assert "ASSETS = named_input()" in source
    assert 'parent_toggle=True' in source
    assert 'sys.argv' not in source


def test_toggle_worker_refuses_input_without_independent_choice_focus(monkeypatch):
    monkeypatch.setenv('ONPC_TEST_MISSING_FOCUS', '1')
    result = json.loads(run_perl(PERL_WORKER).stdout)
    assert not result['ok']
    assert 'fixture:missing-focus' in result['error']
    assert not any(event[0] in ('key', 'text', 'secret') for event in result['events'])


def test_allowance_selector_and_prerequisites(monkeypatch, tmp_path):
    import check_e2e_allowance_presets as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import AllowancePresetsQualification
    from allowance_presets import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['allowance_presets'] is True
    with pytest.raises(CommandError, match='allowance-presets-prerequisites'):
        smoke.main(allowance_presets=True)
    with pytest.raises(CommandError, match='allowance-presets-prerequisites'):
        smoke.main(assets=tmp_path, provision_credentials=True,
                   allowance_presets=True, parent_toggle=True)
    journey = AllowancePresetsQualification.journey(SimpleNamespace(directory=tmp_path), Mock())
    assert journey.plan is PLAN


def test_allowance_worker_matches_plan_and_stops_on_refusal(monkeypatch):
    from allowance_presets import PLAN, PRESET_STAGES
    script = r'''
use strict;
use warnings;
use JSON::PP;
our @stages;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_parent.pm'} = 1; }
package testapi;
sub record_info { }
sub console { bless {}, 'Console' }
sub power { }
sub check_shutdown { 1 }
package Console;
sub disable { }
package onpc_gdm;
sub reattach_functional { }
package onpc_parent;
sub open_for_child { return $_[0]->seen('parent-selected'); }
package main;
require onpc_allowance_presets;
my $exchange = sub {
    push @stages, $_[0];
    die 'fixture:refused' if $_[0] eq $ENV{ONPC_TEST_REFUSE};
    return {observed => $_[0]};
};
my $ok = eval { onpc_allowance_presets::run($exchange); 1; };
print encode_json({ok => $ok ? 1 : 0, stages => \@stages, error => "$@"});
'''
    for refused in ('', 'allowance-0-select'):
        monkeypatch.setenv('ONPC_TEST_REFUSE', refused)
        result = json.loads(run_perl(script).stdout)
        expected = ['parent-selected', *PRESET_STAGES]
        if refused:
            expected = expected[:expected.index(refused) + 1]
        assert result['stages'] == expected
        assert bool(result['ok']) == (not refused), result['error']
        assert all(stage in PLAN.screen_tags for stage in expected)


def test_custom_allowance_selector_and_prerequisites(monkeypatch, tmp_path):
    import check_e2e_allowance as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import AllowanceQualification
    from allowance import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['allowance'] is True
    with pytest.raises(CommandError, match='allowance-prerequisites'):
        smoke.main(allowance=True)
    with pytest.raises(CommandError, match='allowance-prerequisites'):
        smoke.main(assets=tmp_path, provision_credentials=True,
                   allowance=True, allowance_presets=True)
    assert AllowanceQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is PLAN


def test_custom_worker_composes_all_routes_and_stops_before_refused_input(monkeypatch):
    from allowance import PLAN
    script = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_parent.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { push @main::events, ['key', @_]; }
sub type_string { push @main::events, ['text', @_]; }
sub console { bless {}, 'Console' }
sub power { }
sub check_shutdown { 1 }
package Console;
sub disable { }
package onpc_gdm;
sub reattach_functional { }
package onpc_parent;
sub open_for_child { return $_[0]->seen('parent-selected'); }
package main;
require onpc_allowance;
my $exchange = sub {
    push @events, ['stage', $_[0]];
    die 'fixture:refused' if $_[0] eq $ENV{ONPC_TEST_REFUSE};
    return {observed => $_[0]};
};
my $ok = eval { onpc_allowance::run($exchange); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    for refused in ('', 'text-daily-2-selected', 'text-daily-3-selected'):
        monkeypatch.setenv('ONPC_TEST_REFUSE', refused)
        result = json.loads(run_perl(script).stdout)
        expected = stages[:stages.index(refused) + 1] if refused else stages
        assert [event[1] for event in result['events'] if event[0] == 'stage'] == expected
        assert bool(result['ok']) == (not refused), result['error']
        if refused:
            assert result['events'][-1] == ['stage', refused]
        else:
            for value, suffix in ((1, ''), (2, '\n'), (3, '\t')):
                index = result['events'].index(['stage', f'text-daily-{value}-selected'])
                assert result['events'][index + 1] == [
                    'text', str(value) + suffix, 'max_interval', 20]
                assert result['events'][index + 2] == ['stage', f'text-daily-{value}-read']
