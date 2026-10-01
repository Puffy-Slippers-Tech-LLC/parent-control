"""UI17 qualification routing, preparation and worker-order contracts."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

import parent_setup_qualification
from parent_setup_qualification import ParentToggleQualification
from tests.support.perl import ALLOWANCE_WORKER, run_perl


@pytest.fixture
def snapshot_version(tmp_path, monkeypatch):
    """Pin qualification metadata independently of release version bumps."""
    root = tmp_path / 'snapshot-source'
    (root / 'data').mkdir(parents=True)
    (root / 'data/app.json').write_text(json.dumps({'version': '1.1'}))
    monkeypatch.setattr(parent_setup_qualification.smoke, 'ROOT', root)


def test_toggle_qualification_uses_the_fixed_installed_snapshot_and_selector(tmp_path, snapshot_version):
    import check_e2e_toggle as check
    import check_e2e_parent_save as save_check

    assert check.ASSETS == Path(__file__).resolve().parents[2] / 'output/test-runs/host/allocations/onpc-parent-setup-input'
    assert save_check.ASSETS == check.ASSETS
    context = SimpleNamespace(directory=tmp_path)
    journey = ParentToggleQualification.journey(context, lambda *_: None)
    assert context.installed_snapshot == 'onpc-v1.1'
    assert journey.plan.worker_mode == 'parent_toggle'


def test_toggle_uses_normal_snapshot_setup_without_autologin_or_autostart():
    from parent_setup_qualification import ParentJourneyQualification
    qualification = ParentToggleQualification.__new__(ParentToggleQualification)
    context = Mock()
    qualification.prepare_context(context)
    assert not context.mock_calls
    assert ParentToggleQualification.prepare_context is ParentJourneyQualification.prepare_context


PERL_WORKER = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_password.pm'} = 1; }
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
package onpc_gdm;
sub reattach_functional { }
sub choose_account { $_[0]->seen('parent-focused'); }
package onpc_password;
sub enter_parent_gdm_password {
    $_[0]->seen('recipient-qualified'); $_[0]->seen('recipient-rechecked');
}
package main;
require onpc_parent_toggle;
my $exchange = sub {
    push @events, ['stage', $_[0]];
    die 'fixture:missing-focus' if $ENV{ONPC_TEST_MISSING_FOCUS}
        && $_[0] eq 'child-choice-highlighted';
    die 'fixture:entry-refused' if $ENV{ONPC_TEST_REFUSE_ENTRY}
        && $_[0] eq $ENV{ONPC_TEST_REFUSE_ENTRY};
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
        'installed-greeter', 'parent-focused', 'recipient-qualified',
        'recipient-rechecked', 'desktop', 'parent-command',
        'parent-window', 'child-picker-opened', 'child-choice-highlighted',
        'parent-selected', 'wrong-control-refused', 'wrong-child-refused',
        'limit-enabled', 'save-enabled', 'save-reopened', 'limit-disabled',
        'save-disabled', 'limit-current', 'hidden-control-refused', 'disabled-settings',
    ]
    inputs = [event for event in result['events'] if event[0] in ('key', 'text', 'secret')]
    assert inputs == [['key', 'ret'], ['key', 'ret']]
    commit = max(index for index, event in enumerate(result['events']) if event == ['key', 'ret'])
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
    assert [event for event in result['events'] if event[0] == 'key'] == [['key', 'ret']]


@pytest.mark.parametrize('stage', ['desktop', 'parent-command', 'parent-window'])
def test_toggle_worker_stops_on_entry_refusal_without_launch_replay(monkeypatch, stage):
    monkeypatch.setenv('ONPC_TEST_REFUSE_ENTRY', stage)
    result = json.loads(run_perl(PERL_WORKER).stdout)
    assert not result['ok'] and 'fixture:entry-refused' in result['error']
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    assert stages[-1] == stage
    assert stages.count('parent-command') == (stage != 'desktop')
    assert 'child-picker-opened' not in stages


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


@pytest.mark.parametrize('selector', ['check_e2e_read_an_expanded_time_explanation',
                                      'check_e2e_time_explanation'])
def test_time_explanation_selector_and_prerequisites(monkeypatch, tmp_path, selector):
    import importlib
    check = importlib.import_module(selector)
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import TimeExplanationQualification
    from time_explanation import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['time_explanation'] is True
    with pytest.raises(CommandError, match='time-explanation-prerequisites'):
        smoke.main(time_explanation=True)
    with pytest.raises(CommandError, match='time-explanation-prerequisites'):
        smoke.main(assets=tmp_path, provision_credentials=True,
                   time_explanation=True, allowance=True)
    assert TimeExplanationQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is PLAN


def test_time_explanation_checks_all_balances_and_monotonic_order():
    from time_explanation import TimeExplanationJourney
    from private_artifacts import EvidenceError
    journey = TimeExplanationJourney(SimpleNamespace(), Mock())
    value = {'daily': {'seconds': 900, 'precision_seconds': 1},
             'one_time': {'seconds': 0, 'precision_seconds': 1},
             'total': {'seconds': 900, 'precision_seconds': 1}, 'observed_monotonic_ns': 10}
    observation = {'ui': {'time_explanation': value}}
    journey.check_settings('time-explanation-read', observation)
    with pytest.raises(EvidenceError, match='observation-order'):
        journey.check_settings('time-explanation-reread', observation)
    value['observed_monotonic_ns'] = 11
    value['one_time']['seconds'] = 1
    with pytest.raises(EvidenceError, match='ordinary-balances'):
        journey.check_settings('time-explanation-reread', observation)
    value['one_time']['seconds'] = 0
    journey.check_settings('time-explanation-reread', observation)
    value['observed_monotonic_ns'] = 12
    with pytest.raises(EvidenceError, match='ordinary-balances'):
        journey.check_settings('time-explanation-zero-read', observation)
    value['daily']['seconds'] = value['total']['seconds'] = 0
    journey.check_settings('time-explanation-zero-read', observation)
    value['observed_monotonic_ns'] = 13
    journey.check_settings('time-explanation-zero-reread', observation)


def test_set_allowance_selector_and_guarded_preparation(monkeypatch, tmp_path, snapshot_version):
    import check_e2e_set_an_allowance_for_a_named_child as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import SetAllowanceQualification, KioskEntryQualification
    from set_allowance import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['set_allowance'] is True
    with pytest.raises(CommandError, match='set-allowance-prerequisites'):
        smoke.main(set_allowance=True)
    with pytest.raises(CommandError, match='set-allowance-prerequisites'):
        smoke.main(assets=tmp_path, provision_credentials=True,
                   set_allowance=True, time_explanation=True)
    context = SimpleNamespace(directory=tmp_path)
    assert SetAllowanceQualification.journey(context, Mock()).plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert SetAllowanceQualification.finalize is KioskEntryQualification.finalize
    assert SetAllowanceQualification.prepare_context is KioskEntryQualification.prepare_context


def test_fresh_thirty_selector_and_guarded_preparation(monkeypatch, tmp_path, snapshot_version):
    import check_e2e_set_fresh_thirty_minute_allowance as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import FreshThirtyAllowanceQualification, KioskEntryQualification
    from fresh_thirty_allowance import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['fresh_thirty_allowance'] is True
    with pytest.raises(CommandError, match='set-allowance-prerequisites'):
        smoke.main(fresh_thirty_allowance=True)
    for conflict in ('set_allowance', 'time_explanation', 'app_restart', 'kiosk_valid_duration'):
        with pytest.raises(CommandError, match='prerequisites'):
            smoke.main(assets=tmp_path, provision_credentials=True,
                       fresh_thirty_allowance=True, **{conflict: True})
    context = SimpleNamespace(directory=tmp_path)
    assert FreshThirtyAllowanceQualification.journey(context, Mock()).plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert FreshThirtyAllowanceQualification.finalize is KioskEntryQualification.finalize
    assert FreshThirtyAllowanceQualification.prepare_context is KioskEntryQualification.prepare_context


def test_jordan_thirty_selector_and_guarded_preparation(monkeypatch, tmp_path, snapshot_version):
    import check_e2e_set_jordan_thirty_minute_allowance as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import JordanThirtyAllowanceQualification, KioskEntryQualification
    from fresh_thirty_allowance import JORDAN_PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['fresh_thirty_allowance'] is True
    assert run.call_args.kwargs['fresh_thirty_child'] == 'existing'
    for inputs in ({'fresh_thirty_child': 'existing'},
                   {'fresh_thirty_allowance': True, 'fresh_thirty_child': 'other'},
                   {'fresh_thirty_allowance': True, 'fresh_thirty_child': 'existing',
                    'time_explanation': True}):
        with pytest.raises(CommandError, match='prerequisites'):
            smoke.main(assets=tmp_path, provision_credentials=True, **inputs)
    context = SimpleNamespace(directory=tmp_path)
    assert JordanThirtyAllowanceQualification.journey(context, Mock()).plan is JORDAN_PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert JordanThirtyAllowanceQualification.finalize is KioskEntryQualification.finalize
    assert JordanThirtyAllowanceQualification.prepare_context is KioskEntryQualification.prepare_context


@pytest.mark.parametrize('stage,fault', [
    ('balance-reread', None), ('balance-reread', 'daily'),
    ('balance-reread', 'order'), ('final-settings', None),
    ('final-settings', 'child'), ('final-settings', 'enabled'),
])
def test_jordan_thirty_real_step_compares_before_durable_reply(tmp_path, monkeypatch, stage, fault):
    import fresh_thirty_allowance as setup
    import installed_journey
    from private_artifacts import EvidenceError
    plan = setup.JORDAN_PLAN
    journey = setup.FreshThirtyAllowanceJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    journey.steps = [{'stage': name} for name in plan.stages[:plan.stages.index(stage)]]
    journey.earlier_time_observation = 10
    result = ({'time_explanation': {
        'daily': {'seconds': 1801 if fault == 'daily' else 1800, 'precision_seconds': 1},
        'one_time': {'seconds': 0, 'precision_seconds': 1},
        'total': {'seconds': 1800, 'precision_seconds': 1},
        'observed_monotonic_ns': 10 if fault == 'order' else 11}}
        if stage == 'balance-reread' else {'settings': {
            'child': 'fixture-child' if fault == 'child' else 'existing-fixture-child',
            'limit_enabled': fault != 'enabled', 'allowance': ['30 minutes']}})
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(return_value=result))
    monkeypatch.setattr(setup, 'check_balances', Mock(wraps=setup.check_balances))
    original = installed_journey.InstalledJourney.check_settings
    inherited = Mock(side_effect=lambda self, *args: original(self, *args))
    monkeypatch.setattr(installed_journey.InstalledJourney, 'check_settings',
                        lambda self, *args: inherited(self, *args))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError):
            journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        journey.progress.assert_not_called()
        with pytest.raises(EvidenceError, match='previous-failure'):
            journey.step(Mock())
    else:
        journey.step(Mock())
        assert json.loads((tmp_path / (stage + '.reply.json')).read_bytes()) == {'observed': stage}
        assert journey.progress.call_count == 1
    assert inherited.call_count == 1
    assert setup.check_balances.call_count == int(stage == 'balance-reread')
    journey.ui.observe.assert_called_once_with(plan.screen_tags[stage][3:], **(
        {'child': 'existing'} if stage == 'balance-reread' else {}))


@pytest.mark.parametrize('fault', ['daily', 'one_time', 'total', 'order', 'child', 'enabled', 'allowance'])
def test_fresh_thirty_requires_balances_fresh_read_and_saved_settings(fault):
    from fresh_thirty_allowance import FreshThirtyAllowanceJourney
    from private_artifacts import EvidenceError
    journey = FreshThirtyAllowanceJourney(SimpleNamespace(), Mock())
    value = {'daily': {'seconds': 1800, 'precision_seconds': 1},
             'one_time': {'seconds': 0, 'precision_seconds': 1},
             'total': {'seconds': 1800, 'precision_seconds': 1}, 'observed_monotonic_ns': 10}
    observation = {'ui': {'time_explanation': value}}
    journey.check_settings('allowance-configured', observation)
    value['observed_monotonic_ns'] = 11
    settings = {'child': 'fixture-child', 'limit_enabled': True, 'allowance': ['30 minutes']}
    if fault in ('daily', 'one_time', 'total'):
        value[fault]['seconds'] += 1
    elif fault == 'order':
        value['observed_monotonic_ns'] = 10
    else:
        journey.check_settings('balance-reread', observation)
        settings[{'child': 'child', 'enabled': 'limit_enabled', 'allowance': 'allowance'}[fault]] = {
            'child': 'existing-fixture-child', 'enabled': False, 'allowance': ['15 minutes']}[fault]
    with pytest.raises(EvidenceError):
        if fault in ('daily', 'one_time', 'total', 'order'):
            journey.check_settings('balance-reread', observation)
        else:
            journey.check_settings('final-settings', {'ui': {'settings': settings}})


def test_app_restart_selector_uses_owned_snapshot_and_cleanup(monkeypatch, tmp_path, snapshot_version):
    import check_e2e_app_restart as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import AppRestartQualification, KioskEntryQualification
    from app_restart import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['app_restart'] is True
    with pytest.raises(CommandError, match='app-restart-prerequisites'):
        smoke.main(app_restart=True)
    with pytest.raises(CommandError, match='app-restart-prerequisites'):
        smoke.main(assets=tmp_path, provision_credentials=True,
                   app_restart=True, set_allowance=True)
    context = SimpleNamespace(directory=tmp_path)
    assert AppRestartQualification.journey(context, Mock()).plan is PLAN
    assert context.installed_snapshot == 'onpc-v1.1'
    assert AppRestartQualification.finalize is KioskEntryQualification.finalize
    assert AppRestartQualification.prepare_context is KioskEntryQualification.prepare_context


@pytest.mark.parametrize('module_name', ['allowance_boundaries', 'allowance_case'])
def test_allowance_boundaries_worker_and_every_refusal(monkeypatch, module_name):
    from importlib import import_module
    PLAN = import_module(module_name).PLAN
    from allowance_values import ACCEPTED, INVALID, PRESETS
    assert ACCEPTED == (0, 1, 15, 1439)
    assert list(INVALID.values()) == ['', 'abc', '-1', '0.5', '1440', '1441']
    assert PRESETS == (0, 15, 30, 45, *range(60, 1411, 30)) and len(PRESETS) == 50
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_' + module_name)
    script = script.replace('sub record_info { }',
                            "sub record_info { }\nsub type_string { push @main::events, ['text', @_]; }")
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    stages = list(PLAN.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


def test_allowance_installed_sample_preserves_rejection_and_real_reopen_checks():
    from allowance_case import PLAN
    from allowance_boundaries import BOUNDARY_SCREENS
    from ui_observations import SettingsObservation
    stages = list(PLAN.screen_tags)
    assert 'system:parent-continuous-activity' not in PLAN.screen_tags.values()
    presets = [PLAN.screen_tags[stage] for stage in stages if stage.startswith('preset-')]
    assert presets == [f'ui:allowance-{value}-{action}' for value in (15,)
                       for action in ('select', 'read')]
    for value in (1,):
        assert stages.index(f'boundary-{value}-saved') < stages.index(f'boundary-{value}-reopen')
    for binding in ('over',):
        prefix = 'invalid-' + binding
        assert PLAN.screen_tags[prefix + '-baseline'] == 'ui:allowance-15-select'
        assert PLAN.screen_tags[prefix + '-unchanged'] == 'ui:allowance-15-read'
        assert PLAN.screen_tags[prefix + '-reopen'] == 'ui:custom-15-reopen'
        assert stages.index(prefix + '-rejected') < stages.index(prefix + '-unchanged')
    assert len(PLAN.screen_tags) < len(BOUNDARY_SCREENS)
    assert stages.index('initial-selection') < stages.index('persist-away-open')
    assert PLAN.settings_checks['persist-away-selected'] == SettingsObservation(
        'existing-fixture-child', False, ('0 minutes',))
    assert PLAN.settings_checks['persist-back-selected'] == SettingsObservation(
        'fixture-child', True, ('15 minutes',))


def test_allowance_boundaries_uses_guarded_installed_envelope(monkeypatch, tmp_path):
    import check_e2e_allowance_boundaries as check
    import check_graphical_smoke as smoke
    from owned_commands import CommandError
    from parent_setup_qualification import AllowanceBoundariesQualification, KioskEntryQualification
    from allowance_boundaries import PLAN
    run = Mock(return_value=0)
    monkeypatch.setattr(check, 'smoke', run)
    assert check.main() == 0
    assert run.call_args.kwargs['allowance_boundaries'] is True
    with pytest.raises(CommandError, match='allowance-boundaries-prerequisites'):
        smoke.main(allowance_boundaries=True)
    with pytest.raises(CommandError, match='allowance-boundaries-prerequisites'):
        smoke.main(assets=tmp_path, provision_credentials=True,
                   allowance_boundaries=True, allowance=True)
    assert AllowanceBoundariesQualification.journey(SimpleNamespace(directory=tmp_path), Mock()).plan is PLAN
    assert AllowanceBoundariesQualification.finalize is KioskEntryQualification.finalize
    assert AllowanceBoundariesQualification.prepare_context is KioskEntryQualification.prepare_context


def test_set_allowance_actual_worker_stops_before_later_input_at_every_boundary(monkeypatch):
    from set_allowance import PLAN
    stages = list(PLAN.screen_tags)
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(ALLOWANCE_WORKER).stdout)
    assert success['ok'], success['error']
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert [event for event in success['events'] if event[0] == 'key'] == [
        ['key', 'ret'], ['key', 'ret'], ['key', 'alt-f4'], ['key', 'ret']]
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(ALLOWANCE_WORKER).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


@pytest.mark.parametrize('child', ['child', 'existing'])
def test_fresh_thirty_actual_worker_stops_at_every_refused_boundary(monkeypatch, child):
    from fresh_thirty_allowance import PLAN, JORDAN_PLAN
    PLAN = PLAN if child == 'child' else JORDAN_PLAN
    from accessible_ui import OPERATIONS
    from ui_observations import OPERATION_LABELS
    from tests.support.paths import ROOT
    import re
    dispatch = (ROOT / 'tests/integration/graphical_smoke/tests/smoke.pm').read_text()
    branches = re.findall(r'if \(\$ready->\{' + PLAN.worker_mode + r'\}\) \{(.*?)\n    \}', dispatch, re.S)
    assert len(branches) == 1
    invocation = ('onpc_fresh_thirty_allowance::run(\\&exchange);' if child == 'child' else
                  "onpc_fresh_thirty_allowance::run(\\&exchange, 'existing');")
    assert invocation in branches[0]
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_fresh_thirty_allowance')
    if child == 'existing':
        script = script.replace('onpc_fresh_thirty_allowance::run($exchange)',
                                "onpc_fresh_thirty_allowance::run($exchange, 'existing')")
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    stages = list(PLAN.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert [event for event in success['events'] if event[0] == 'key'] == [['key', 'ret'], ['key', 'ret']]
    assert set(PLAN.phases) == set(PLAN.stages)
    assert all(tag.removeprefix('ui:') in OPERATIONS for tag in PLAN.screen_tags.values())
    assert all(tag.removeprefix('ui:') in OPERATION_LABELS for tag in PLAN.screen_tags.values())
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


def test_zero_total_actual_worker_stops_at_each_refused_observation(monkeypatch):
    from zero_total import PLAN
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_zero_total')
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    stages = list(PLAN.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert [event for event in success['events'] if event[0] == 'key'] == [
        ['key', 'ret'], ['key', 'ret']]
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


def test_app_restart_worker_refusal_never_closes_or_relaunches_after_failure(monkeypatch):
    from app_restart import PLAN
    script = ALLOWANCE_WORKER.replace('onpc_set_allowance', 'onpc_app_restart')
    monkeypatch.setenv('ONPC_TEST_REFUSE', '')
    success = json.loads(run_perl(script).stdout)
    assert success['ok'], success['error']
    stages = list(PLAN.screen_tags)
    assert [event[1] for event in success['events'] if event[0] == 'stage'] == stages
    assert [event for event in success['events'] if event[0] == 'key'] == [
        ['key', 'ret'], ['key', 'alt-f4']]
    for stage in stages:
        monkeypatch.setenv('ONPC_TEST_REFUSE', stage)
        result = json.loads(run_perl(script).stdout)
        assert not result['ok'] and 'fixture:refused' in result['error']
        boundary = success['events'].index(['stage', stage])
        assert result['events'] == success['events'][:boundary + 1]


def test_lifecycle_requires_named_entry_destination_and_fresh_proof():
    script = ALLOWANCE_WORKER[:ALLOWANCE_WORKER.index('my $ok = eval')]
    script += r'''
require onpc_lifecycle;
my @errors;
for my $args (['about', {}, 'management'], ['parent', {}, 'denied'],
              ['parent', {}, 'management']) {
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'app-restart', review => 0);
    eval { onpc_lifecycle::reopen($journey, @$args); };
    push @errors, "$@";
}
print encode_json({errors => \@errors, events => \@events});
'''
    result = json.loads(run_perl(script).stdout)
    assert not result['events']
    assert all('lifecycle:binding' in error for error in result['errors'][:2])
    assert 'journey:stale-observation' in result['errors'][2]


def test_set_allowance_refuses_wrong_declared_bindings_before_any_input():
    script = ALLOWANCE_WORKER[:ALLOWANCE_WORKER.index('my $ok = eval')]
    script += r'''
my @errors;
for my $args (
    ['gdm', 'other-parent', 'fresh', 'new', 'child', 0, 0, 1],
    ['gdm', 'parent', 'fresh', 'retained', 'child', 0, 0, 1],
    ['desktop', 'parent', 'fresh', 'new', 'child', 0, 0, 1],
    ['gdm', 'parent', 'fresh', 'new', 'existing', 0, 0, 1],
    ['gdm', 'parent', 'fresh', 'retained', 'child', 0, 30, 1],
    ['gdm', 'parent', 'fresh', 'new', 'child', 1, 30, 1],
    ['desktop', 'parent', 'same-user', 'new', 'child', 1, 30, 1],
    ['desktop', 'parent', 'same-user', 'new', 'existing', 1, 30, 1],
    ['gdm', 'parent', 'fresh', 'new', 'existing', 1, 30, 1],
    ['gdm', 'parent', 'fresh', 'new', 'existing', 0, 15, 1],
    ['gdm', 'parent', 'fresh', 'new', 'child', 0, 45, 1]) {
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'set-allowance', review => 0);
    eval { onpc_parent::set_allowance($journey, @$args); };
    push @errors, "$@";
}
print encode_json({errors => \@errors, events => \@events});
'''
    result = json.loads(run_perl(script).stdout)
    assert not result['events']
    assert len(result['errors']) == 11
    assert all('parent:allowance-binding' in error for error in result['errors'])


def test_time_explanation_worker_stops_at_each_refused_boundary(monkeypatch):
    from time_explanation import PLAN, STAGES
    script = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; $INC{'onpc_gdm.pm'} = 1; $INC{'onpc_parent.pm'} = 1; }
package testapi;
sub record_info { }
sub send_key { die 'unexpected input'; }
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
require onpc_time_explanation;
my $exchange = sub {
    push @events, $_[0];
    die 'fixture:refused' if $_[0] eq $ENV{ONPC_TEST_REFUSE};
    return {observed => $_[0]};
};
my $ok = eval { onpc_time_explanation::run($exchange); 1; };
print encode_json({ok => $ok ? 1 : 0, events => \@events, error => "$@"});
'''
    stages = list(PLAN.screen_tags)
    stages = stages[stages.index('parent-selected'):]
    for refused in ('', *STAGES):
        monkeypatch.setenv('ONPC_TEST_REFUSE', refused)
        result = json.loads(run_perl(script).stdout)
        assert result['events'] == (stages[:stages.index(refused) + 1] if refused else stages)
        assert bool(result['ok']) == (not refused), result['error']


@pytest.mark.parametrize('minutes', [0, 15])
@pytest.mark.parametrize('action', ['reopen', 'reopen-current'])
@pytest.mark.parametrize('wrong_selection', [False, True])
def test_custom_reopen_checks_the_declared_reload_or_retained_selection(
        minutes, action, wrong_selection):
    # In-memory public observations only; no additional shared resources.
    from accessible_ui import AccessibleUI, CHILD, UiError
    ui = Mock()
    choice = ui.id_target.return_value
    choice.get_description.return_value = (
        'Daily allowance: Custom amount' if wrong_selection else
        'Selected daily allowance: Custom amount')
    if wrong_selection:
        ui.allowance_preset.side_effect = UiError('ui:allowance-value')
        with pytest.raises(UiError):
            AccessibleUI.custom_allowance(ui, CHILD, minutes, action=action)
        assert 'parent-daily-limit-custom' not in [
            call.args[0] for call in ui.activate_id.call_args_list]
        ui.read_synthetic_text.assert_not_called()
    else:
        assert AccessibleUI.custom_allowance(ui, CHILD, minutes, action=action) == {
            'minutes': minutes, 'action': action}
        ui.read_synthetic_text.assert_called_once_with('daily-' + str(minutes), child=CHILD)
        if action == 'reopen':
            ui.allowance_preset.assert_called_once_with(CHILD, minutes, action='read')
        else:
            ui.allowance_preset.assert_not_called()
            choice.get_description.assert_called_once_with()


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
